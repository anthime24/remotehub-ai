"""Launching local processes, URLs, the Warp terminal and Remote Desktop (RDP) sessions."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import webbrowser
from pathlib import Path

from .config import Config, expand_path
from .i18n import t

_DETACHED = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_NEW_CONSOLE = 0x00000010 | 0x00000200         # CREATE_NEW_CONSOLE | CREATE_NEW_PROCESS_GROUP

# Windows .rdp file. CredSSP is off because xrdp (Linux) does not speak it; the connection only ever goes
# through the SSH tunnel to 127.0.0.1, so nothing is exposed to the network.
RDP_TEMPLATE = """full address:s:127.0.0.1:{port}
username:s:{user}
prompt for credentials:i:0
enablecredsspsupport:i:0
authentication level:i:0
negotiate security layer:i:1
screen mode id:i:1
desktopwidth:i:{width}
desktopheight:i:{height}
smart sizing:i:1
session bpp:i:24
compression:i:1
connection type:i:6
audiomode:i:2
redirectclipboard:i:1
redirectprinters:i:0
redirectsmartcards:i:0
redirectcomports:i:0
autoreconnection enabled:i:1
use multimon:i:0
"""


class LocalRunner:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def run(self, command: str, console: bool = False) -> None:
        subprocess.Popen(command, shell=True, creationflags=_NEW_CONSOLE if console else _DETACHED,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def open_url(self, url: str) -> None:
        if url.lower().startswith(("http://", "https://")):
            webbrowser.open(url)
        else:
            os.startfile(url)  # custom schemes: jetbrains-gateway://, warp://...

    def open_rdp(self, local_port: int, user: str, width: int = 1600, height: int = 900) -> None:
        """Opens mstsc on 127.0.0.1:<local_port> (an SSH tunnel) with a generated .rdp file."""
        path = Path(tempfile.gettempdir()) / f"remotehub-rdp-{local_port}.rdp"
        path.write_text(RDP_TEMPLATE.format(port=local_port, user=user, width=width, height=height),
                        encoding="ascii", errors="replace")
        subprocess.Popen(["mstsc", str(path)], creationflags=_DETACHED)

    # -- Warp -------------------------------------------------------------
    def warp_ssh(self, remote_command: str = "", full_command: str = "") -> str:
        """Opens a Warp tab and puts the ssh command on the clipboard.

        Warp on Windows accepts no command at launch (launch configurations run nothing), so the user
        pastes with Ctrl+V and presses Enter. Fallback: Windows Terminal, which runs ssh directly.
        """
        c = self.cfg.section("connection")
        ssh_cmd = f"ssh {'-t ' if remote_command else ''}{c['user']}@{c['tailscale_ip']} -p {c.get('ssh_port', 22)}"
        if full_command:  # complete SSH command supplied by the config (e.g. towards the VM)
            ssh_cmd = full_command
        elif remote_command:  # e.g. "wsl -d Ubuntu": opens a shell straight into WSL
            ssh_cmd += f" {self.cfg.render(remote_command)}"
        warp = expand_path(self.cfg.section("local_tools").get("warp_exe"))
        if warp and Path(warp).exists():
            subprocess.run(["clip"], input=ssh_cmd.encode("ascii"), check=False, creationflags=0x08000000)
            os.startfile("warp://action/new_tab")
            return t("Warp opened: command copied, press Ctrl+V then Enter ({cmd})", cmd=ssh_cmd)
        if shutil.which("wt"):
            subprocess.Popen(["wt", "new-tab", "--title", "Tower"] + ssh_cmd.split())
            return t("Windows Terminal (Warp not found)")
        subprocess.Popen(f"cmd /k {ssh_cmd}", creationflags=_NEW_CONSOLE)
        return t("cmd (Warp not found)")
