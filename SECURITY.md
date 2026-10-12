# Security policy / Politique de sécurité

## Reporting a vulnerability / Signaler une faille

**EN** — Please do **not** open a public issue for a security problem. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) ("Security" tab → "Report a vulnerability").
Include what you found, how to reproduce it and, if you can, a suggested fix. You will get an answer within a few days.

**FR** — N'ouvrez **pas** d'issue publique pour un problème de sécurité. Utilisez le
[signalement privé de GitHub](../../security/advisories/new) (onglet « Security » → « Report a vulnerability »).
Décrivez la faille, comment la reproduire et, si possible, une piste de correction.

## Security model in one minute / Le modèle de sécurité en une minute

| | |
|---|---|
| **What is exposed** | Nothing to the Internet. The tower only accepts SSH from your Tailscale network (and optionally your LAN). |
| **Authentication** | SSH keys (password login can be switched off). Tailscale adds device-level authentication and encryption. |
| **Everything else** (Ollama, Jupyter, ComfyUI, RustDesk, the VM's SSH/RDP) | Bound to `127.0.0.1` on the tower and reached **through the SSH session** (port forwarding). They are never listening on the network. |
| **Host keys** | Trusted on first use, then pinned in `~/.ssh/known_hosts`. A changed key is refused with a clear message. |
| **Secrets** | `config.yaml` (git-ignored) may hold a Jupyter token; the SSH password is never stored (environment variable only); the Freebox token lives in a git-ignored file. |
| **The SSH account is powerful** | If it is a Windows administrator (usual case), anyone holding your private key controls the tower. Protect the key with a passphrase and your laptop with disk encryption. |

## Hardening checklist / Liste de durcissement

1. Use a key **with a passphrase** (`ssh-keygen -t ed25519`) and load it in `ssh-agent`.
2. Run `tower\Setup-Tower.ps1 -RestrictFirewall` so port 22 is reachable from Tailscale only.
3. After testing key login, run `tower\Setup-Tower.ps1 -DisablePasswordAuth`.
4. In the Tailscale admin console enable **key expiry** and, if you can, **ACLs** limiting who may reach the tower on port 22.
5. Set a long random `vars.jupyter_token` and never share `config.yaml`.
6. Keep Windows, OpenSSH, Tailscale and VirtualBox updated.
7. Before publishing a fork: `python tools/check_privacy.py`.

## Out of scope / Hors périmètre

RemoteHub-AI is a convenience layer over standard tools (OpenSSH, Tailscale, VirtualBox). Vulnerabilities in those
products must be reported to their own maintainers.
