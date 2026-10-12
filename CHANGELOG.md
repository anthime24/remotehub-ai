# Changelog

All notable changes are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-12

First public release.

### Added
- Desktop dashboard (CustomTkinter): connection state, live CPU / RAM / GPU / VRAM telemetry, launcher cards.
- Wake-on-LAN on every local interface, SSH relay, and optional Freebox API for waking from outside the LAN.
- SSH over Tailscale with trust-on-first-use host keys (a changed key is refused).
- Port forwarding and **SOCKS5 proxy** on the SSH session, with a "Tunnels" window to open a tower link
  (`localhost:3000`) on the laptop or browse through the tower's network.
- File explorer over SFTP: browse, search, safe downloads (`.part` files renamed when complete), folder upload, cancel.
- Launchers: terminal (Warp / Windows Terminal), PyCharm Remote, RustDesk, Ollama, ComfyUI, JupyterLab,
  Docker, WSL2, VirtualBox Linux VM (start/stop, terminal, RDP desktop) with a self-healing start script.
- Tower scripts: `Setup-Tower.ps1` (OpenSSH, key login, firewall restriction, Wake-on-LAN card settings), services
  bound to loopback only, VM creation and start scripts.
- English and French user interface and documentation; `config.yaml` actions can carry `*_fr` labels.
- `--demo` mode (fake data, no network), privacy checker (`tools/check_privacy.py`), CI, unit tests.
