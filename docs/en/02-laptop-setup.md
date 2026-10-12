# 2 · Set up the laptop (the PC you work from)

> 🇫🇷 [Version française](../fr/02-installation-laptop.md) · [← Back to the README](../../README.md)

## 1. Prerequisites

- Windows 10/11 and [Python 3.10+](https://www.python.org/downloads/) (tick "Add Python to PATH" in the installer)
- The OpenSSH client (already in Windows 10/11 — check with `ssh -V`)
- [Tailscale](https://tailscale.com/download), signed in with the **same account as the tower**
- Optional: [Warp](https://www.warp.dev), [PyCharm](https://www.jetbrains.com/pycharm/), [RustDesk](https://rustdesk.com)

Check the tower is reachable: `tailscale ping 100.x.y.z` (your tower's Tailscale IP).

## 2. Get RemoteHub-AI

```powershell
git clone https://github.com/OWNER/remotehub-ai.git
cd remotehub-ai
```

(or download the ZIP from GitHub and unzip it).

Want to look around first? `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`, then
`.venv\Scripts\python main.py --demo` opens the interface with **fake data** and no network.

## 3. Configure

Double-click **`run.bat`**. On the first launch it copies `config.example.yaml` to **`config.yaml`** and opens it
in Notepad. Edit at least:

```yaml
connection:
  name: "MY-TOWER"
  tailscale_ip: "100.101.102.103"     # tailscale ip -4   (on the tower)
  user: "your-windows-user"            # the account you gave to Setup-Tower.ps1
  mac: "AA:BB:CC:DD:EE:FF"             # printed by Setup-Tower.ps1 (or: ipconfig /all on the tower)
vars:
  jupyter_token: "<long random string>"   # python -c "import secrets;print(secrets.token_urlsafe(32))"
wake_on_lan:
  broadcasts: ["192.168.1.255"]       # your LAN's broadcast address (x.y.z.255)
```

`config.yaml` is **git-ignored**: your addresses and secrets never leave your laptop.
The app warns in its log if it still finds example values. Every key is documented in the file and in
[05 · Configuration](05-configuration.md).

Run `run.bat` again. The first time, creating the virtual environment takes a minute.

### What you should see

- Top right: **Online · 12 ms** (green) when the tower is on and reachable through Tailscale.
- The first connection logs a yellow line *"First connection to 100.x.y.z: host key SHA256:… remembered"*. The key is saved
  to `~/.ssh/known_hosts`. If you want to be strict, compare the fingerprint with
  `ssh-keygen -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub` run on the tower. **If this key ever changes later,
  RemoteHub refuses to connect** and tells you why (see [Security](06-security.md)).
- Live CPU / RAM / GPU bars on the right.

## 4. Deploy the tower scripts

The service launchers (Ollama, ComfyUI, JupyterLab) and the VM script live on the tower. Copy them with:

```powershell
python tools\deploy_tower.py --dry-run      # list what will be copied
python tools\deploy_tower.py                # copies tower\services and tower\vm to vars.scripts_dir (default C:\RemoteHub)
```

The tool uses your SSH session — no extra password, nothing else to configure. Re-run it after updating the repo.

## 5. Daily use

| You want to… | Do this |
|---|---|
| Turn the tower on | **Wake the tower** (works on the same LAN; for outside see [Wake-on-LAN](03-wake-on-lan.md)) |
| Open a terminal on it | **Terminal (SSH)** card (Warp: paste with Ctrl+V; falls back to Windows Terminal) |
| Use Ollama from the laptop | **Ollama** card, then use `http://127.0.0.1:11435` as the Ollama URL in your tools |
| Open a web app running on the tower | **Tunnels** → type `3000` or `http://localhost:3000` |
| Browse through the tower's network | **Tunnels** → *Browser via the tower* |
| Copy files | **Files** (browse, search, drag in folders with *Upload*, download) |
| Work in a Linux desktop | **Linux desktop (RDP)** card ([VM guide](04-linux-vm.md)) |
| Shut it down | **Shut down** (confirmation dialog) |

Everything started from the cards runs **on the tower**, detached from your SSH session: closing the app does not stop
your notebook or your model server. Use each card's **Stop** button when you are done.

## 6. Updating

```powershell
git pull
.venv\Scripts\pip install -r requirements.txt
python tools\deploy_tower.py
```

Compare `config.example.yaml` with your `config.yaml` after an update to pick up new options.

---

**Previous:** [← 1 · Tower](01-tower-setup.md) · **Next:** [3 · Wake-on-LAN →](03-wake-on-lan.md)
