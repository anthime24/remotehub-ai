# 1 · Set up the tower (the PC you want to control)

> 🇫🇷 [Version française](../fr/01-installation-tour.md) · [← Back to the README](../../README.md)

The **tower** is the always-reachable Windows PC (desktop or laptop) that does the heavy work.
This guide takes about 20 minutes. Nothing here opens a port to the Internet.

**You need:** Windows 10/11 (Home is fine), an administrator account, an Ethernet cable if you want
Wake-on-LAN, and a free [Tailscale](https://tailscale.com) account.

---

## Step 1 — Install Tailscale on the tower

Tailscale creates a private encrypted network between *your* devices, even behind a router or on mobile data.

1. Download it from <https://tailscale.com/download> and sign in.
2. Open a terminal and note the tower's address:
   ```powershell
   tailscale ip -4        # prints something like 100.101.102.103
   ```
3. Do the same on your laptop **with the same account** (see [step 2 of the laptop guide](02-laptop-setup.md)).

> Tip: in the Tailscale admin console, give the tower a clear name and disable "key expiry" for it if you want it
> reachable for months without re-login (you can leave expiry on for the laptop).

## Step 2 — Get the scripts on the tower

On the tower, download this repository (**Code → Download ZIP**, then unzip) or `git clone` it.
You only need the `tower\` folder.

## Step 3 — Create your SSH key on the laptop

On the **laptop**, in PowerShell:

```powershell
ssh-keygen -t ed25519 -C "remotehub laptop"
# Press Enter for the default location, then CHOOSE A PASSPHRASE.
type $HOME\.ssh\id_ed25519.pub
```

The last command prints one line starting with `ssh-ed25519 AAAA…` — that is your **public** key and it is safe to
share. Copy it to the tower (USB stick, a message to yourself…). **Never** copy the file without `.pub`: that is your
private key and it stays on the laptop.

## Step 4 — Run the setup script (elevated PowerShell on the tower)

Right-click the Start button → **Terminal (Admin)**, then:

```powershell
cd path\to\remotehub-ai\tower

# 1) Preview: shows what would change, changes nothing
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -DryRun

# 2) Apply, installing your public key (paste the key text, or give the path of the .pub file)
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -PublicKey "ssh-ed25519 AAAA… remotehub laptop"
```

What it does (every step is idempotent, re-run it any time):

| Step | Effect |
|---|---|
| OpenSSH server | Installs the Windows feature, starts `sshd` automatically at boot |
| Public key | Adds your key to `administrators_authorized_keys` (admin accounts) or `~\.ssh\authorized_keys`, with locked-down permissions |
| `sshd_config` | Adds a clearly marked block (`# BEGIN RemoteHub … # END RemoteHub`): 3 login attempts, key login on, TCP forwarding on. **A backup is made first** and the file is validated with `sshd -t`; on error the backup is restored |
| Firewall | Reports rules that allow SSH from any address; with `-RestrictFirewall` limits SSH to Tailscale |
| Wake-on-LAN | Enables magic-packet wake on the Ethernet card, turns off the power-saving options that break it, disables Fast Startup |

It ends by printing the values to put in your laptop's `config.yaml` (name, Tailscale IP, MAC address, LAN IP).

Options: `-User <name>` (account for SSH, default = current user), `-WolAdapter "Ethernet"` (pick the NIC),
`-LanSubnet 192.168.1.0/24` (also allow your LAN when restricting the firewall).

## Step 5 — Test the key login, **then** lock the door

From the laptop:

```powershell
ssh your-windows-user@100.x.y.z hostname
```

You should get the tower's name after typing your key passphrase (no Windows password prompt). Once this works:

```powershell
# on the tower, elevated:
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -RestrictFirewall -DisablePasswordAuth
```

- `-RestrictFirewall` → SSH reachable **only** from Tailscale (`100.64.0.0/10`) [+ your LAN with `-LanSubnet`].
  The other inbound rules allowing port 22 are disabled and listed in `C:\ProgramData\RemoteHub\` so you can undo it.
- `-DisablePasswordAuth` → key-only login. The script refuses if no key is installed, so you cannot lock yourself out
  by accident.

## Step 6 — BIOS settings for Wake-on-LAN

Read [Wake-on-LAN](03-wake-on-lan.md): one BIOS option ("Power On By PCI-E" / "Wake on LAN") must be enabled.

## Step 7 — Optional software

Install only what you will use. RemoteHub starts and stops them for you:

| Feature | Install on the tower |
|---|---|
| AI models | [Ollama](https://ollama.com/download) |
| Image generation | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (set `COMFYUI_DIR` or use `C:\Users\you\ComfyUI`) |
| Notebooks | `pip install jupyterlab` |
| Remote desktop | [RustDesk](https://rustdesk.com) → Settings → Security → **Enable direct IP access** and set a permanent password |
| Linux VM | [VirtualBox](https://www.virtualbox.org/) → [guide](04-linux-vm.md) |
| Linux shell | `wsl --install -d Ubuntu` |
| Containers | Docker Desktop |

Then deploy the helper scripts from the laptop (see [laptop guide](02-laptop-setup.md#4-deploy-the-tower-scripts)).

---

**Next:** [2 · Set up the laptop →](02-laptop-setup.md)
