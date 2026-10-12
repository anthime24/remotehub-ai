# 6 · Security

> 🇫🇷 [Version française](../fr/06-securite.md) · [← Back to the README](../../README.md) · [Security policy](../../SECURITY.md)

Remote control of a PC is only worth it if it is safe. This page explains **how** RemoteHub-AI is built to be safe, what
risks remain, and what you should do about them.

## The design in one picture

```
Internet ──✗── (no port forwarded, no DMZ, nothing listening for the public)

laptop ═══ Tailscale (WireGuard, encrypted, authenticated by device) ═══ tower :22 (sshd, key login)
   │                                                                       │
   └── ONE SSH session carries everything else:                            ├─ 127.0.0.1:11434  Ollama
         tunnels, SOCKS5, SFTP, commands                                   ├─ 127.0.0.1:8888   JupyterLab (+ token)
                                                                           ├─ 127.0.0.1:8188   ComfyUI
                                                                           ├─ 127.0.0.1:21118  RustDesk (direct IP)
                                                                           └─ 127.0.0.1:2223/33890  VM (VirtualBox NAT)
```

1. **No public exposure.** You do not forward ports on your router. Tailscale connects the devices outbound.
2. **One door.** Only SSH (port 22) is reachable, and only from Tailscale (and optionally your LAN) once you run
   `Setup-Tower.ps1 -RestrictFirewall`.
3. **Everything else is loopback.** Ollama, Jupyter, ComfyUI, RustDesk and the VM listen on `127.0.0.1` and are reached by
   SSH port forwarding. The service scripts in this repo bind to `127.0.0.1` on purpose.
4. **Keys, not passwords.** SSH key login; password login can be switched off (`-DisablePasswordAuth`).
5. **Host key pinning.** First connection → key remembered in `~/.ssh/known_hosts`. If it changes, RemoteHub **refuses**
   with an explicit message instead of silently reconnecting. (This is what stops someone on the same network from posing as
   your tower.)
6. **Secrets stay local.** `config.yaml`, `freebox_token.json`, `.privacy-denylist` are git-ignored. The SSH password is only
   read from an environment variable. Jupyter requires a token that the service script **refuses to start without**
   (no `change-me`, 16+ characters).
7. **Safe file transfers.** Downloads go to `name.part` and are renamed at the end (no truncated file under the real name);
   uploads are size-checked and a failed upload is removed from the tower; overwrites ask for confirmation.

## Residual risks — be honest with yourself

| Risk | Why it matters | What to do |
|---|---|---|
| **Your private key is the keys to the tower** | The SSH account is usually an administrator | Use a passphrase, `ssh-agent`, disk encryption (BitLocker) on the laptop. Never copy the private key anywhere |
| **A stolen/compromised laptop** | It holds the key and a Tailscale session | Remove the key from the tower (`C:\ProgramData\ssh\administrators_authorized_keys`) and remove the device in the Tailscale admin console |
| **Tailscale account takeover** | Whoever controls the account can add devices to your network | Turn on 2-factor authentication for the identity provider, enable *device approval*, review devices regularly |
| **Other devices on your tailnet** | They can reach port 22 | Use Tailscale **ACLs** (below) so only your laptop reaches the tower on port 22 |
| **A process on the tower reading `127.0.0.1`** | Loopback services are visible to local users/processes | Token on Jupyter (done); do not run untrusted software on the tower; keep Windows updated |
| **Running an admin SSH session is powerful by design** | RemoteHub can run any command you configure | Only add actions you understand; treat a shared `config.yaml` like code |
| **Browser via the tower (SOCKS)** | The dedicated browser can reach your home LAN (router, NAS…) | That is the feature — only use it on sites you trust, close the proxy when done |

### Tailscale ACL example (admin console → Access controls)

Only the laptop may reach the tower's SSH port; the tower cannot initiate connections to the laptop:

```json
{
  "tagOwners": { "tag:tower": ["autogroup:admin"] },
  "acls": [
    { "action": "accept", "src": ["autogroup:member"], "dst": ["tag:tower:22"] }
  ]
}
```
Tag the tower (`tag:tower`) in the machines list. Adapt `src` to a specific user or device if you share the tailnet.

## Hardening checklist

- [ ] Key with passphrase; key loaded in `ssh-agent` (`Get-Service ssh-agent | Set-Service -StartupType Manual; Start-Service ssh-agent; ssh-add`)
- [ ] `Setup-Tower.ps1 -RestrictFirewall` and `-DisablePasswordAuth` applied
- [ ] Tailscale: 2FA, ACLs, key expiry on the laptop, device approval
- [ ] `vars.jupyter_token` long and random; RustDesk permanent password long and random
- [ ] No router port-forward to the tower, no DMZ, no UPnP-opened ports (check your router's page)
- [ ] BitLocker/device encryption on the laptop; screen lock
- [ ] Windows Update, Tailscale, OpenSSH and VirtualBox kept current

## Publishing your own fork safely

Your configuration contains private values (Tailscale IP, MAC, user name, tokens). This repository is built so that those
never get committed, but **you** must keep it that way:

```powershell
git config core.hooksPath .githooks        # pre-commit hook
python tools\check_privacy.py              # scan now
```

The checker looks for private keys, tokens, Tailscale (100.64.0.0/10) addresses, MAC addresses, e-mail addresses, Windows
profile paths, and for every line of **`.privacy-denylist`** — a git-ignored file where you list your own private strings
(IP, MAC, user and computer names, domains, e-mail), one per line. CI runs the generic patterns on every push.
Screenshots: use `python main.py --demo` (fake data) — never a screenshot of your real window.

If a secret was committed by mistake, **revoke it first** (new key, new token), then rewrite history — deleting the file
in a later commit is not enough because it stays in the history.

## Networks that block Tailscale (schools, companies)

Some networks block VPN/Tailscale traffic. RemoteHub-AI deliberately offers **no workaround** for filters that an
organisation chose to enforce: bypassing them can break the network's rules and get you into trouble. Ask the IT team
(they may whitelist Tailscale — a short, polite request explaining your use works best), or use your phone's hotspot
(see the [troubleshooting guide](07-troubleshooting.md#networks-that-block-tailscale)).

---

**Previous:** [← 5 · Configuration](05-configuration.md) · **Next:** [7 · Troubleshooting →](07-troubleshooting.md)
