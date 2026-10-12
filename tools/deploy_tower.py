"""Copies the tower scripts (tower/services, tower/vm) to the tower over SFTP, into `vars.scripts_dir`.

    python tools/deploy_tower.py            # uses config.yaml
    python tools/deploy_tower.py --dry-run  # list what would be copied
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import Config  # noqa: E402
from core.i18n import set_language  # noqa: E402
from core.ssh_client import SSHManager, ps_command  # noqa: E402


def collect(subdirs=("services", "vm")) -> list[tuple[Path, str]]:
    """(local file, path relative to scripts_dir with Windows separators)."""
    out = []
    for sub in subdirs:
        for p in sorted((ROOT / "tower" / sub).glob("*.ps1")):
            out.append((p, f"{sub}\\{p.name}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    set_language(cfg.data.get("language", "auto"))
    dest = cfg.vars.get("scripts_dir", "").rstrip("\\")
    if not dest:
        print("vars.scripts_dir is not set in the config", file=sys.stderr)
        return 1
    files = collect()
    for local, rel in files:
        print(f"  {local.relative_to(ROOT)}  ->  {dest}\\{rel}")
    if args.dry_run:
        return 0

    log = lambda level, msg: print(f"[{level}] {msg}")  # noqa: E731
    ssh = SSHManager(cfg, log)
    if not ssh.connect():
        print("Tower unreachable over SSH. Is it on, and is Tailscale connected?", file=sys.stderr)
        return 1
    try:
        for sub in sorted({rel.split("\\")[0] for _, rel in files}):
            res = ssh.run(ps_command(f"New-Item -ItemType Directory -Force -Path '{dest}\\{sub}' | Out-Null"))
            if not res.ok:
                print(f"Cannot create {dest}\\{sub}: {res.text}", file=sys.stderr)
                return 1
        sftp = paramiko.SFTPClient.from_transport(ssh._transport())
        try:
            for local, rel in files:
                remote = "/" + (dest + "\\" + rel).replace("\\", "/")
                sftp.put(str(local), remote)
                print(f"copied {rel}")
        finally:
            sftp.close()
    finally:
        ssh.close()
    print("Done. Scripts are in", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
