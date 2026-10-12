"""Resilient Paramiko SSH connection: never raises to the caller."""
from __future__ import annotations

import base64
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import paramiko

from .config import Config, expand_path
from .i18n import t

LogFn = Callable[[str, str], None]  # (level, message)
KNOWN_HOSTS = Path(expand_path("~/.ssh/known_hosts"))


@dataclass
class ExecResult:
    ok: bool
    code: int
    out: str = ""
    err: str = ""

    @property
    def text(self) -> str:
        return (self.out or self.err).strip()


def ps_command(script: str) -> str:
    """Wraps a PowerShell script in -EncodedCommand (no cmd.exe quoting trouble)."""
    script = "$ProgressPreference='SilentlyContinue'\n" + script  # avoids CLIXML noise on stderr
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc}"


def ps_detached(script: str) -> str:
    """Runs `script` outside the SSH session.

    With OpenSSH on Windows, child processes die with the session (job object); Win32_Process.Create
    starts them through WMI, so they survive the disconnection.
    """
    inner = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    cmdline = f"powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -EncodedCommand {inner}"
    outer = (
        f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmdline}'}}\n"
        "if ($r.ReturnValue -ne 0) { throw \"Win32_Process.Create returned $($r.ReturnValue)\" }"
    )
    return ps_command(outer)


class TrustOnFirstUse(paramiko.MissingHostKeyPolicy):
    """Remembers a host key the first time it is seen (like OpenSSH `accept-new`).

    A key that later CHANGES is rejected by Paramiko itself (BadHostKeyException): this is the protection
    against someone impersonating the tower.
    """

    def __init__(self, log: LogFn, path: Path = KNOWN_HOSTS):
        self.log, self.path = log, path

    def missing_host_key(self, client, hostname, key):
        client.get_host_keys().add(hostname, key.get_name(), key)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(f"{hostname} {key.get_name()} {key.get_base64()}\n")
        except OSError:
            pass
        self.log("warn", t("First connection to {host}: host key {fp} remembered. Check it matches your tower "
                           "(ssh-keygen -lf on the tower's host key).", host=hostname, fp=_fingerprint(key)))


def _fingerprint(key: paramiko.PKey) -> str:
    import hashlib
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


class SSHManager:
    def __init__(self, cfg: Config, log: LogFn):
        self.cfg = cfg
        self.log = log
        self._client: paramiko.SSHClient | None = None
        self._lock = threading.RLock()
        self.host: str | None = None
        self._last_auth_error = ""
        self._last_hostkey_error = ""

    # -- state ------------------------------------------------------------
    @property
    def connected(self) -> bool:
        tr = self._transport()
        return bool(tr and tr.is_active())

    def _transport(self) -> paramiko.Transport | None:
        c = self._client
        return c.get_transport() if c else None

    # -- connection -------------------------------------------------------
    def connect(self, hosts: list[str] | None = None) -> bool:
        """Tries each candidate host (Tailscale, then LAN). Returns False (never raises) on failure."""
        with self._lock:
            if self.connected:
                return True
            return self._connect_direct(hosts)

    def _creds(self):
        c = self.cfg.section("connection")
        key = expand_path(c.get("key_file"))
        password = os.environ.get(c.get("password_env") or "", "") or None
        return c, (key if key and Path(key).exists() else None), password

    def _connect_direct(self, hosts: list[str] | None) -> bool:
        c, key, password = self._creds()
        for host in hosts or self.cfg.hosts:
            client = paramiko.SSHClient()
            if KNOWN_HOSTS.exists():
                try:
                    client.load_host_keys(str(KNOWN_HOSTS))
                except (OSError, paramiko.SSHException):
                    pass
            client.set_missing_host_key_policy(TrustOnFirstUse(self.log))
            try:
                client.connect(
                    host,
                    port=int(c.get("ssh_port", 22)),
                    username=c.get("user"),
                    key_filename=key,
                    password=password,
                    timeout=float(c.get("connect_timeout", 8)),
                    banner_timeout=15,
                    auth_timeout=15,
                    allow_agent=True,
                    look_for_keys=False,
                )
                client.get_transport().set_keepalive(15)
                self._client, self.host = client, host
                self._last_auth_error = self._last_hostkey_error = ""
                self.log("ok", t("SSH connected to {user}@{host}", user=c.get("user"), host=host))
                return True
            except paramiko.BadHostKeyException:
                client.close()
                self._report_hostkey(host)
                return False  # never fall through to another host after a key mismatch
            except paramiko.AuthenticationException:
                self._report_auth(host)
                client.close()
            except Exception as exc:  # network down, tower off, timeout...
                client.close()
                self.log("dbg", f"SSH {host}: {type(exc).__name__}: {exc}")
        return False

    def _report_hostkey(self, host: str) -> None:
        msg = t("HOST KEY CHANGED for {host}: connection refused. Either the tower was reinstalled, or someone is "
                "impersonating it. If you are sure it is the tower, delete its line from ~/.ssh/known_hosts.",
                host=host)
        if msg != self._last_hostkey_error:
            self._last_hostkey_error = msg
            self.log("err", msg)

    def _report_auth(self, host: str) -> None:
        msg = t("SSH authentication refused on {host}: install your public key on the tower "
                "(see docs) or set the REMOTEHUB_SSH_PASSWORD environment variable.", host=host)
        if msg != self._last_auth_error:  # do not spam the log every few seconds
            self._last_auth_error = msg
            self.log("err", msg)

    def close(self) -> None:
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None

    # -- execution --------------------------------------------------------
    def run(self, command: str, timeout: float = 30) -> ExecResult:
        if not self.connect():
            return ExecResult(False, -1, err=t("Tower unreachable over SSH (off, network down or auth refused)."))
        try:
            _, stdout, stderr = self._client.exec_command(command, timeout=timeout)  # type: ignore[union-attr]
            stdout.channel.settimeout(timeout)
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            code = stdout.channel.recv_exit_status()
            return ExecResult(code == 0, code, out, err)
        except Exception as exc:
            # the connection is probably dead (mobile network lost, shutdown...): start clean next time
            self.close()
            return ExecResult(False, -1, err=f"{type(exc).__name__}: {exc}")

    def open_channel(self, remote_host: str, remote_port: int, origin=("127.0.0.1", 0)):
        """direct-tcpip channel used for port forwarding. Raises on failure (handled by the caller)."""
        if not self.connect():
            raise ConnectionError("SSH not connected")
        tr = self._transport()
        return tr.open_channel("direct-tcpip", (remote_host, remote_port), origin, timeout=8)  # type: ignore[union-attr]

    def http_ready(self, remote_host: str, remote_port: int, path: str = "/", timeout: float = 4.0) -> bool:
        """Does the web service really answer? (the port can open before the application is ready)"""
        ch = None
        try:
            ch = self.open_channel(remote_host, remote_port)
            ch.settimeout(timeout)
            ch.sendall(f"GET {path} HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
            buf = b""
            while b"\r\n" not in buf and len(buf) < 256:
                chunk = ch.recv(256)
                if not chunk:
                    break
                buf += chunk
            parts = buf.split(b" ", 2)
            return buf.startswith(b"HTTP/") and len(parts) > 1 and parts[1].isdigit() and int(parts[1]) < 500
        except Exception:
            return False
        finally:
            _close_quietly(ch)

    def tcp_expect(self, remote_host: str, remote_port: int, expect: bytes, send: bytes = b"",
                   timeout: float = 4.0) -> bool:
        """True if the service answers with `expect` (banner sent unprompted, or reply to `send`).

        Stricter than port_open_remote: VirtualBox NAT accepts the connection before the VM has booted,
        but sends nothing until the guest service (sshd, xrdp) is really ready.
        """
        ch = None
        try:
            ch = self.open_channel(remote_host, remote_port)
            ch.settimeout(timeout)
            if send:
                ch.sendall(send)
            buf = b""
            while len(buf) < len(expect):
                chunk = ch.recv(64)
                if not chunk:
                    return False
                buf += chunk
            return buf.startswith(expect)
        except Exception:
            return False
        finally:
            _close_quietly(ch)

    def port_open_remote(self, remote_host: str, remote_port: int) -> bool:
        """Is a service really listening on the tower?

        OpenSSH for Windows accepts the channel BEFORE connecting to the target, so opening it succeeds even
        on a closed port. The channel has to be observed: closed at once (EOF) = nothing listens;
        data received or silence = a service answers.
        """
        ch = None
        try:
            ch = self.open_channel(remote_host, remote_port)
            ch.settimeout(0.8)
            try:
                return ch.recv(1) != b""  # b"": the SSH server closed it, the connection failed
            except TimeoutError:
                return True               # silent: open, waiting for the client to speak (HTTP, RDP...)
        except Exception:
            return False
        finally:
            _close_quietly(ch)


def _close_quietly(ch) -> None:
    if ch is not None:
        try:
            ch.close()
        except Exception:
            pass
