"""File browsing and transfer on the tower over SFTP (on the existing SSH session).

Paths: the app works with Windows paths (D:\\data\\x); on the SFTP side, OpenSSH for Windows
expects /D:/data/x and exposes the root "/" as the list of drives.
"""
from __future__ import annotations

import json
import os
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import paramiko

from .config import Config, expand_path
from .i18n import t
from .ssh_client import SSHManager, ps_command

Progress = Callable[[int, int, str], None]  # (bytes done, bytes total, current file)
MAX_DEPTH = 25
CANCELLED = "Transfer cancelled."   # translated at display time (see _cancelled())
CHUNK = 1 << 20          # read/write size
PIPELINE = 64            # max read requests in flight (64 x 32 KB = 2 MB): bounds the cancel latency


class FileError(Exception):
    """Error that can be shown as is to the user."""


@dataclass
class FileEntry:
    name: str
    path: str  # full Windows path
    is_dir: bool
    size: int = 0
    mtime: float = 0.0


def to_remote(path: str) -> str:
    p = path.replace("\\", "/").strip()
    if p in ("", "/"):
        return "/"
    return p if p.startswith("/") else "/" + p


def join(parent: str, name: str) -> str:
    if not parent:
        return name + "\\"
    return parent.rstrip("\\") + "\\" + name


def parent_of(path: str) -> str:
    p = path.rstrip("\\")
    return p.rsplit("\\", 1)[0] + "\\" if "\\" in p and len(p) > 3 else ""


class FileManager:
    def __init__(self, cfg: Config, ssh: SSHManager, log: Callable[[str, str], None]):
        self.cfg, self.ssh, self.log = cfg, ssh, log
        f = cfg.section("files")
        self.roots: list[str] = list(f.get("roots") or [])
        self.start_path: str = f.get("start_path") or ""
        self.download_dir = Path(expand_path(f.get("download_dir") or "~/Downloads/RemoteHub"))
        self._sftp: paramiko.SFTPClient | None = None
        self._sftp_transport = None
        self._lock = threading.RLock()
        self._op_lock = threading.RLock()  # a Paramiko SFTPClient does not support concurrent requests

    # -- session ----------------------------------------------------------
    def _client(self) -> paramiko.SFTPClient:
        with self._lock:
            if not self.ssh.connect():
                raise FileError(t("Tower unreachable: cannot open SFTP (off, network down or auth refused)."))
            transport = self.ssh._transport()
            if self._sftp is None or self._sftp_transport is not transport:
                try:
                    self._sftp = paramiko.SFTPClient.from_transport(transport, window_size=2**22, max_packet_size=2**15)
                except Exception as exc:
                    raise FileError(t("Cannot open SFTP: {exc}", exc=exc)) from exc
                self._sftp_transport = transport
            return self._sftp

    def _reset(self) -> None:
        with self._lock:
            self._sftp = None
            self._sftp_transport = None

    def _new_client(self) -> paramiko.SFTPClient:
        """SFTP channel dedicated to one transfer (sharing it with browsing would cause stalls)."""
        if not self.ssh.connect():
            raise FileError(t("Tower unreachable: cannot open SFTP (off, network down or auth refused)."))
        try:
            return paramiko.SFTPClient.from_transport(self.ssh._transport(), window_size=2**22, max_packet_size=2**15)
        except Exception as exc:
            raise FileError(t("Cannot open SFTP: {exc}", exc=exc)) from exc

    @staticmethod
    def _wrap(fn, client, args):
        try:
            return fn(client, *args)
        except PermissionError as exc:
            raise FileError(t("Access denied.")) from exc
        except FileNotFoundError as exc:
            raise FileError(t("Path not found.")) from exc

    def _op(self, fn, *args, client: paramiko.SFTPClient | None = None):
        """Runs an SFTP operation and converts errors to FileError.

        Without `client`: the shared browsing channel, serialised by a lock, with one retry if the session
        died. With `client`: a dedicated channel used by a single thread.
        """
        if client is not None:
            try:
                return self._wrap(fn, client, args)
            except (EOFError, OSError, paramiko.SSHException) as exc:
                raise FileError(t("SFTP error: {exc}", exc=exc)) from exc
        with self._op_lock:
            for attempt in (1, 2):
                try:
                    return self._wrap(fn, self._client(), args)
                except (EOFError, OSError, paramiko.SSHException) as exc:
                    alive = self.ssh.connected
                    self._reset()
                    if alive or attempt == 2:  # healthy session: the error comes from the operation itself
                        raise FileError(t("SFTP error: {exc}", exc=exc)) from exc
                    # dead session (mobile network lost...): retry once on a new connection

    # -- navigation -------------------------------------------------------
    def list(self, path: str) -> list[FileEntry]:
        attrs = self._op(lambda c, p: c.listdir_attr(p), to_remote(path))
        out = []
        for a in attrs:
            is_dir = stat.S_ISDIR(a.st_mode or 0)
            name = a.filename
            if path == "":
                name = name.rstrip(":") + ":"  # drives
            out.append(FileEntry(name, join(path, name) if path else name + "\\", is_dir,
                                 0 if is_dir else (a.st_size or 0), a.st_mtime or 0))
        out.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return out

    def exists(self, path: str, client: paramiko.SFTPClient | None = None) -> bool:
        try:
            self._op(lambda c, p: c.stat(p), to_remote(path), client=client)
            return True
        except FileError:
            return False

    def mkdir(self, parent: str, name: str) -> str:
        if not name or any(ch in name for ch in '\\/:*?"<>|'):
            raise FileError(t("Invalid folder name."))
        path = join(parent, name)
        self._op(lambda c, p: c.mkdir(p), to_remote(path))
        return path

    # -- recherche --------------------------------------------------------
    def search(self, root: str, query: str, limit: int = 300) -> list[FileEntry]:
        """Recursive search on the tower (PowerShell). `query` accepts the * and ? wildcards."""
        q = query.strip()
        if not q:
            raise FileError(t("Enter a name to search for."))
        if "*" not in q and "?" not in q:
            q = f"*{q}*"
        q = q.replace("'", "''")
        start = (root or "C:\\").replace("'", "''")
        script = (
            f"Get-ChildItem -LiteralPath '{start}' -Recurse -Force -Filter '{q}' -ErrorAction SilentlyContinue | "
            f"Select-Object -First {int(limit)} | ForEach-Object {{ "
            "[pscustomobject]@{p=$_.FullName;d=[bool]$_.PSIsContainer;s=[long]$(if($_.PSIsContainer){0}else{$_.Length});"
            "m=[double]([DateTimeOffset]$_.LastWriteTimeUtc).ToUnixTimeSeconds()} | ConvertTo-Json -Compress }"
        )
        res = self.ssh.run(ps_command(script), timeout=120)
        if not res.ok and not res.out:
            raise FileError(res.err.strip() or t("Search failed."))
        found = []
        for line in res.out.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    j = json.loads(line)
                except json.JSONDecodeError:
                    continue
                found.append(FileEntry(os.path.basename(j["p"]) or j["p"], j["p"], j["d"], j["s"], j["m"]))
        return found

    # -- download ---------------------------------------------------
    def download(self, entries: list[FileEntry], progress: Progress, cancel: threading.Event) -> list[Path]:
        xfer = self._new_client()
        try:
            return self._download(xfer, entries, progress, cancel)
        finally:
            xfer.close()

    def _download(self, xfer, entries, progress: Progress, cancel: threading.Event) -> list[Path]:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        plan: list[tuple[str, Path, int]] = []  # (remote, local, size)
        tops: list[Path] = []
        for e in entries:
            target = self._free_name(self.download_dir / e.name)
            tops.append(target)
            if e.is_dir:
                target.mkdir(parents=True, exist_ok=True)
                self._walk_remote(xfer, e.path, target, plan, 0)
            else:
                plan.append((to_remote(e.path), target, e.size))
        total = sum(p[2] for p in plan)
        done = 0
        for remote, local, size in plan:
            if cancel.is_set():
                raise FileError(t(CANCELLED))
            base = done
            local.parent.mkdir(parents=True, exist_ok=True)
            self._get_file(xfer, remote, local, size, lambda sent, base=base, n=local.name: progress(base + sent, total, n), cancel)
            done += size
        progress(total, total, "")
        return tops

    def _get_file(self, xfer, remote: str, local: Path, size: int, report, cancel: threading.Event) -> None:
        """Downloads to a .part renamed at the end: never a truncated file under the real name."""
        part = local.with_name(local.name + ".part")

        def work(c):
            with c.open(remote, "rb") as src, open(part, "wb") as dst:
                if size:
                    src.prefetch(size, max_concurrent_requests=PIPELINE)
                sent = 0
                while True:
                    if cancel.is_set():
                        raise FileError(t(CANCELLED))
                    chunk = src.read(CHUNK)
                    if not chunk:
                        break
                    dst.write(chunk)
                    sent += len(chunk)
                    report(sent)
            if size and sent != size:
                raise FileError(t("Incomplete file ({sent} / {size} bytes): {name}", sent=sent, size=size, name=local.name))

        try:
            self._op(lambda c: work(c), client=xfer)
            part.replace(local)
        except BaseException:
            part.unlink(missing_ok=True)
            raise

    def _put_file(self, xfer, local: Path, remote: str, report, cancel: threading.Event) -> None:
        expected = local.stat().st_size

        def work(c):
            with local.open("rb") as src, c.open(remote, "wb") as dst:
                dst.set_pipelined(True)
                sent = 0
                while True:
                    chunk = src.read(CHUNK)
                    if not chunk:
                        break
                    if cancel.is_set():
                        raise FileError(t(CANCELLED))
                    dst.write(chunk)
                    sent += len(chunk)
                    report(sent)
            if c.stat(remote).st_size != expected:  # check what the tower really received
                raise FileError(t("Incomplete upload: {name}", name=local.name))

        try:
            self._op(lambda c: work(c), client=xfer)
        except BaseException:
            try:
                xfer.remove(remote)  # leave no partial file on the tower
            except Exception:
                pass
            raise

    def _walk_remote(self, xfer, rdir: str, ldir: Path, plan: list, depth: int) -> None:
        if depth > MAX_DEPTH:
            self.log("warn", t("Maximum depth reached, skipped: {path}", path=rdir))
            return
        try:
            items = self._op(lambda c, p: c.listdir_attr(p), to_remote(rdir), client=xfer)
        except FileError as exc:
            self.log("warn", t("Folder skipped ({exc}): {path}", exc=exc, path=rdir))
            return
        for a in items:
            rpath = join(rdir, a.filename)
            lpath = ldir / a.filename
            if stat.S_ISDIR(a.st_mode or 0):
                lpath.mkdir(exist_ok=True)
                self._walk_remote(xfer, rpath, lpath, plan, depth + 1)
            else:
                plan.append((to_remote(rpath), lpath, a.st_size or 0))

    @staticmethod
    def _free_name(p: Path) -> Path:
        if not p.exists():
            return p
        i = 1
        while True:
            q = p.with_name(f"{p.stem} ({i}){p.suffix}")
            if not q.exists():
                return q
            i += 1

    # -- upload ------------------------------------------------------------
    def plan_upload(self, locals_: list[Path], remote_dir: str) -> list[tuple[Path, str]]:
        """List of (local file, remote path) for files and folders (recursive)."""
        plan: list[tuple[Path, str]] = []
        for p in locals_:
            if p.is_dir():
                for root, dirs, files in os.walk(p):
                    rel = Path(root).relative_to(p.parent)
                    if not dirs and not files:  # empty folder: recreate it (a "folder" entry in the plan)
                        plan.append((Path(root), join(remote_dir, str(rel).replace("/", "\\"))))
                    for f in files:
                        plan.append((Path(root) / f, join(remote_dir, str(rel / f).replace("/", "\\"))))
            else:
                plan.append((p, join(remote_dir, p.name)))
        return plan

    def upload(self, plan: list[tuple[Path, str]], progress: Progress, cancel: threading.Event) -> int:
        xfer = self._new_client()
        try:
            return self._upload(xfer, plan, progress, cancel)
        finally:
            xfer.close()

    def _upload(self, xfer, plan, progress: Progress, cancel: threading.Event) -> int:
        total = sum(lp.stat().st_size for lp, _ in plan if lp.is_file())
        done = 0
        made: set[str] = set()
        for lp, rpath in plan:
            if cancel.is_set():
                raise FileError(t(CANCELLED))
            if lp.is_dir():
                self._ensure_dirs(xfer, rpath + "\\", made)
                continue
            self._ensure_dirs(xfer, parent_of(rpath), made)
            base = done
            self._put_file(xfer, lp, to_remote(rpath), lambda sent, base=base, n=lp.name: progress(base + sent, total, n), cancel)
            done += lp.stat().st_size
        progress(total, total, "")
        return len(plan)

    def _ensure_dirs(self, xfer, path: str, made: set[str]) -> None:
        """Recursively creates missing remote folders (e.g. when uploading a folder)."""
        parts = path.rstrip("\\").split("\\")
        for i in range(2, len(parts) + 1):  # parts[0] = drive "D:"
            cur = "\\".join(parts[:i])
            if cur in made:
                continue
            if not self.exists(cur + "\\", client=xfer):
                self._op(lambda c, p: c.mkdir(p), to_remote(cur), client=xfer)
            made.add(cur)
