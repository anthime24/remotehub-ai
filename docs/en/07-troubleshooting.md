# 7 · Troubleshooting

> 🇫🇷 [Version française](../fr/07-depannage.md) · [← Back to the README](../../README.md)

Start with the **Log** panel at the bottom of the window: messages are color-coded (green OK, yellow warning, red error).

## The badge says **Offline**

| Check | How |
|---|---|
| Is the tower on and awake? | Look at it / use **Wake the tower** and wait up to 4 minutes |
| Is Tailscale connected on **both** machines? | `tailscale status` — the tower should be listed as active, not "offline" |
| Can the laptop reach it? | `tailscale ping 100.x.y.z` then `Test-NetConnection 100.x.y.z -Port 22` |
| Right IP in `config.yaml`? | `tailscale ip -4` on the tower |
| Firewall? | If you ran `-RestrictFirewall`, the rule only allows Tailscale (and `-LanSubnet`). Check `Get-NetFirewallRule -DisplayName "RemoteHub SSH"` |
| sshd running? | On the tower: `Get-Service sshd` |

## The badge is yellow: "SSH connecting…" (port open, no login)

- **"SSH authentication refused"** in the log → your public key is not installed, or its permissions are wrong. On the
  tower: for an administrator account the key must be in `C:\ProgramData\ssh\administrators_authorized_keys` (not in
  `~\.ssh`), only readable by *Administrators* and *SYSTEM*. Re-run `Setup-Tower.ps1 -PublicKey …`.
  Test with `ssh -v your-user@100.x.y.z` and read the last lines.
- **Key has a passphrase and RemoteHub can't use it?** Load the key into `ssh-agent` (`ssh-add`) — RemoteHub uses the agent.
- **"HOST KEY CHANGED"** → the tower was reinstalled (new host keys) *or* someone is impersonating it. If you reinstalled
  Windows/OpenSSH, delete the tower's line from `C:\Users\you\.ssh\known_hosts` and reconnect.

## Buttons fail

- *"file not found on the tower: …\Start-Ollama.ps1"* → run `python tools\deploy_tower.py`; check `vars.scripts_dir`.
- *"the service on port 8188 did not answer within 180s"* → the program did not start. Logs are in
  `C:\ProgramData\RemoteHub\logs\` on the tower (`comfyui.err.log`, `ollama.err.log`, `jupyter.err.log`).
- *"Local port 11435 unavailable"* → another program uses it; change `local_port` in the action (and the URL you use).
- *Ollama says the model is not found* → models are per machine: `ollama pull <model>` **on the tower** (or via the Ollama card's tunnel, `OLLAMA_HOST=http://127.0.0.1:11435 ollama pull <model>`).
- *JupyterLab: "Refusing to start … weak token"* → set a 16+ character `vars.jupyter_token`.
- *Warp opens but nothing runs* → by design on Windows: the command is on your clipboard, press **Ctrl+V** then **Enter**.
- A step stuck on "Waiting for …" for a long time → the service is slow to start (first launch of ComfyUI, a big model). It stops after the step's `timeout`.

## Wake-on-LAN does nothing

Read [Wake-on-LAN §4](03-wake-on-lan.md#4-troubleshooting-wol). Quick tests: (1) wake it from another PC on the same LAN;
(2) check `connection.mac` and `wake_on_lan.broadcasts`; (3) from outside the LAN you need a relay or the Freebox option.

## The Linux VM

| Symptom | Fix |
|---|---|
| Stays "Waiting for service ready…" | The VM can freeze at boot in NEM mode. `ensure_vm.ps1` resets it up to 3 times; look at `C:\ProgramData\RemoteHub\logs\vm-ensure.log` |
| RDP: "login failed" | Wrong password for the *Linux* user (not your Windows one). Reset: in a VM terminal, `sudo passwd <user>` |
| RDP: black screen / immediate disconnect | In the VM: `echo xfce4-session > ~/.xsession`, then `sudo systemctl restart xrdp`; make sure you are not already logged in on another RDP session |
| `Create-LinuxVm.ps1`: "port already in use" | Pick other ports with `-SshPort` / `-RdpPort` (and update the action's ports) |
| No Hyper-V, "VT-x is not available" | Enable virtualization (SVM/VT-x) in the BIOS |

## Files

- Slow transfers over mobile data/relayed Tailscale → expected; the progress bar shows speed and ETA. **Cancel** is immediate.
- *"Access denied"* on a folder → the SSH account lacks rights there.

## Windows OpenSSH quirks (good to know)

- Opening a forwarded port **always succeeds** on Windows' OpenSSH, even if nothing listens on the target; RemoteHub
  therefore reads the connection to detect "really open". If a browser tab opens blank, the service behind the tunnel is down.
- Processes started in an SSH session die with it. Cards use WMI (`detach`) to start long-running services outside
  the session.

## Networks that block Tailscale

At some schools, universities and companies the firewall blocks VPN traffic, including Tailscale. Symptoms:
`tailscale status` shows the tower as offline/relayed with no data received, `tailscale netcheck` shows no UDP and no DERP
reachable, and RemoteHub stays **Offline**.

- RemoteHub-AI does **not** include tricks to defeat such filters. They are the network owner's decision and bypassing them
  may violate the rules you accepted.
- What works: **ask the IT team** to allow Tailscale (a short, polite message explaining what you use it for), or switch to a
  **phone hotspot** (your own network). On a hotspot, save data: lower telemetry (`monitoring.interval_s: 30`), avoid RDP
  and RustDesk, and prefer terminal, Files and API tunnels.
- Alternative workflow that needs no live connection: push your work with Git and let the tower run it later.

## Still stuck?

Open an [issue](https://github.com/anthime24/remotehub-ai/issues) with: what you did, what you expected, what happened, the
log lines (secrets removed), your Windows versions. **Never paste your key, token, Tailscale IP or MAC address.**

---

**Previous:** [← 6 · Security](06-security.md) · [Back to the README](../../README.md)
