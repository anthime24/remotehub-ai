# 4 · A real Linux machine on the tower (VirtualBox)

> 🇫🇷 [Version française](../fr/04-vm-linux.md) · [← Back to the README](../../README.md)

Get a full **Ubuntu** (terminal and graphical desktop) running on the tower's CPU/RAM, started and stopped from RemoteHub.

**Why VirtualBox and not Hyper-V?** Hyper-V is missing from Windows *Home*, and on some Pro installs its
component store is damaged. VirtualBox runs everywhere (it automatically uses the Windows Hypervisor Platform
if that is enabled — the "NEM" engine). If you only need a Linux shell, **WSL2** is lighter: use the
`Ubuntu terminal (WSL2)` card and skip this page.

```
laptop ──SSH session (Tailscale)──▶ tower ──127.0.0.1:2223──▶ VM sshd   (VirtualBox NAT)
                                          └─127.0.0.1:33890─▶ VM xrdp   (remote desktop)
```

The VM sits behind VirtualBox NAT and its ports are forwarded to **127.0.0.1 of the tower only**. Nobody on any network
can reach them; RemoteHub opens them *inside* the SSH tunnel.

## 1. Install VirtualBox and get an Ubuntu ISO (on the tower)

```powershell
winget install Oracle.VirtualBox
```

Download **Ubuntu Server 24.04 LTS** ("live server" ISO, ~2.6 GB) from <https://ubuntu.com/download/server> and verify
its SHA-256 against the `SHA256SUMS` file on the same site:

```powershell
(Get-FileHash .\ubuntu-24.04.*-live-server-amd64.iso -Algorithm SHA256).Hash
```

## 2. Create the VM

Elevated PowerShell on the tower, in the `tower\vm` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\Create-LinuxVm.ps1 `
    -IsoPath D:\VM\ubuntu-24.04.5-live-server-amd64.iso -WithDesktop
```

You are asked for the Linux user's password (8+ characters; it is never written to a log or to the command line).
Defaults: 4 GB RAM, 2 vCPU, 40 GB dynamic disk, user `remotehub`, ports 2223 (SSH) and 33890 (RDP).
Change them with `-MemoryMB 6144 -Cpus 4 -DiskGB 60 -User alice -VmName MyVM -SshPort … -RdpPort …`.
`-WithDesktop` also installs the XFCE desktop and `xrdp`.

The script refuses to run if the VM name or a port is already taken — it never overwrites anything.
The unattended installation takes **10–25 minutes**, headless. Follow it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\ensure_vm.ps1     # returns 0 once the VM's SSH answers
Get-Content $env:ProgramData\RemoteHub\logs\vm-create.log
```

Match `vars.vm_name` / `vars.vm_user` in your laptop's `config.yaml`, then run
`python tools\deploy_tower.py` (it copies `ensure_vm.ps1` to the tower's `scripts_dir`).

## 3. First login and your SSH key

1. In RemoteHub click **Start** on **Linux VM terminal**. The terminal opens an SSH session to the VM:
   log in once with the password you chose.
2. Install your laptop's public key *inside the VM* and turn the password off for SSH:
   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   echo "ssh-ed25519 AAAA… remotehub laptop" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
   # then, from the laptop, check that the key works (open a new terminal) BEFORE the next command:
   printf 'PasswordAuthentication no\nPermitRootLogin no\n' | sudo tee /etc/ssh/sshd_config.d/99-remotehub.conf
   sudo systemctl reload ssh
   ```
   (The VM is only reachable through your tunnel, so this is defence in depth, but it costs nothing.)

> **If SSH never answers** (the install seems finished but port 2223 stays silent): the post-install package step may
> have failed. Reach the tower's desktop (RustDesk), open the VM's window in the VirtualBox Manager, log in and run
> `sudo apt update && sudo apt install -y openssh-server` (and `xfce4 xrdp xorgxrdp` for the desktop). Then
> `echo xfce4-session > ~/.xsession` as your user.

## 4. The graphical desktop

Click **Start** on **Linux desktop (RDP)**: RemoteHub starts the VM if needed, waits until `xrdp` really answers, opens
a tunnel and launches Windows' Remote Desktop with a generated `.rdp` file. Log in with the VM user and password
(`xrdp` session type *Xorg*). If the desktop is a black screen, check that `~/.xsession` contains `xfce4-session`.

### Make it prettier / Ubuntu-like

```bash
sudo apt install -y yaru-theme-gtk yaru-theme-icon fonts-ubuntu ubuntu-wallpapers plank \
                    arc-theme papirus-icon-theme
```
Then *Settings → Appearance* → pick *Yaru-dark* (or *Arc-Dark* + *Papirus-Dark* icons) and set the wallpaper.
Add `plank` to *Session and Startup → Application Autostart* for an Ubuntu-style dock.
Want the full Ubuntu GNOME desktop? `sudo apt install ubuntu-desktop-minimal` works but is heavy over RDP.

## 5. Everyday use

| Card | What it does |
|---|---|
| **Linux VM (Ubuntu)** — Start | Starts the VM and waits for SSH. **Stop** = clean ACPI shutdown |
| **Linux VM terminal** | Starts if needed, tunnels, opens an SSH terminal |
| **Linux desktop (RDP)** | Starts if needed, tunnels, opens the graphical desktop |

`ensure_vm.ps1` makes starting robust: it only *resets* a VM that **it** started and that froze at boot (a known
VirtualBox-NEM quirk, up to 3 tries). A VM that was already running when you clicked is **never** restarted.

## 6. Backups, snapshots, resources

- Snapshot before risky changes: `& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" snapshot MyVM take before-upgrade`
- Resize RAM/CPUs with the VM powered off: `VBoxManage modifyvm MyVM --memory 6144 --cpus 4`
- The disk is dynamic (grows as used) — keep an eye on the tower's free space.
- Delete everything: `VBoxManage unregistervm MyVM --delete`

---

**Previous:** [← 3 · Wake-on-LAN](03-wake-on-lan.md) · **Next:** [5 · Configuration →](05-configuration.md)
