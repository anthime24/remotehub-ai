# 5 · Configuration reference

> 🇫🇷 [Version française](../fr/05-configuration.md) · [← Back to the README](../../README.md)

Everything is in **`config.yaml`** (copied from [`config.example.yaml`](../../config.example.yaml)). Restart the app after
editing. No code change is ever needed to add a launcher.

## Sections

| Section | Purpose |
|---|---|
| `language` | `auto` (system language), `en`, `fr` |
| `connection` | Tower name, Tailscale IP (`tailscale_ip`), optional `lan_ip` (tried second), SSH `user`, `key_file`, `mac`, `connect_timeout` |
| `vars` | Your own variables, usable as `{{name}}` in commands (see below) |
| `health` | `interval_s` (how often the connection state is checked), `boot_grace_s` (how long to stay "Booting" after a WoL) |
| `monitoring` | Telemetry on/off, `interval_s`; raise it (e.g. 30) on a metered connection, or set `enabled: false` |
| `wake_on_lan` | Broadcast addresses, ports, optional unicast, SSH `relay` |
| `freebox` | Optional Freebox WoL |
| `files` | `start_path`, `download_dir`, `roots` (shortcuts in the file explorer) |
| `power` | Commands run by *Restart* / *Shut down* |
| `local_tools` | Paths of programs on the **laptop** (Warp, PyCharm, RustDesk) — also usable as `{{warp_exe}}` etc. |
| `actions` | The launcher cards |

### Variables

Available everywhere in strings: `{{tailscale_ip}}`, `{{lan_ip}}`, `{{user}}`, `{{ssh_port}}`, `{{mac}}`,
`{{project_dir}}`, every key of `local_tools` and `vars`. Unknown names are left as is.

### Passwords

SSH password login is discouraged. If you must, **never write it in the file**: set the environment variable named in
`connection.password_env` (`REMOTEHUB_SSH_PASSWORD`).

## Actions

```yaml
actions:
  - id: my-app                  # unique
    name: "My app"              # card title            (name_fr: ... for French)
    tag: "WEB"                  # little label on the card
    category: ai                # dev | ai | system → which section
    description: "Starts it and opens the browser"      # (description_fr: ...)
    steps: [ ... ]              # what the Start button does, in order
    stop_steps: [ ... ]         # optional: adds a Stop button
```

An action can also be a single step written inline (`type: warp_ssh`, `type: local`…).
Steps run in order and stop at the first error, which is shown in the log.

### Step types

| `type` | Parameters | What it does |
|---|---|---|
| `ssh` | `command` (cmd line) **or** `powershell` (script) · `detach: true` · `ignore_errors: true` · `timeout: 30` | Runs on the **tower**. `detach` starts it in the background so it survives the SSH session |
| `tunnel` | `local_port`, `remote_port`, `remote_host: localhost` | Forwards a tower port to `127.0.0.1:<local_port>` on the laptop |
| `tunnel_stop` | `local_port` | Closes a tunnel |
| `wait_port` | `remote_port`, `remote_host`, `timeout`, and one of `http_path: /api` (wait for a real HTTP answer) · `expect_banner: "SSH-"` · `probe_hex` + `expect_hex` | Waits until a service **really** answers (not merely a port opening) |
| `check_file` | `path` | Fails early, with a clear message, if a file is missing on the tower |
| `url` | `url` | Opens a web page or custom scheme on the laptop |
| `local` | `command`, `console: true` | Runs a command on the **laptop** |
| `warp_ssh` | `remote_command` (e.g. `wsl -d Ubuntu`) or `command` (a full ssh command) | Terminal on the tower: Warp (command copied, paste it) → Windows Terminal → cmd |
| `rdp` | `local_port`, `user`, `width`, `height` | Opens Remote Desktop on a tunnelled port with a generated `.rdp` file |
| `wait` | `seconds` | Sleeps |

> **Why `127.0.0.1` and not `localhost` in `remote_host`?** Windows may resolve `localhost` to IPv6 first and add a
> 2-second delay or hit a service listening on IPv4 only. Prefer `127.0.0.1`.

### Recipes

**A web app on the tower (e.g. Streamlit on port 8501), opened on the laptop:**
```yaml
- id: streamlit
  name: "My Streamlit app"
  tag: "WEB"
  category: ai
  description: "streamlit run app.py on the tower"
  steps:
    - {type: ssh, detach: true, powershell: 'Set-Location C:\work\app; streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true'}
    - {type: wait_port, remote_host: "127.0.0.1", remote_port: 8501, http_path: /, timeout: 60}
    - {type: tunnel, local_port: 8501, remote_host: "127.0.0.1", remote_port: 8501}
    - {type: url, url: "http://127.0.0.1:8501"}
  stop_steps:
    - {type: tunnel_stop, local_port: 8501}
    - {type: ssh, ignore_errors: true, powershell: 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "streamlit" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'}
```
*Always bind to `127.0.0.1`* — the tunnel is what makes it reachable, so nothing listens on the network.

**A Docker container:**
```yaml
- id: db
  name: "Postgres"
  tag: "DOCKER"
  category: system
  steps:      [{type: ssh, command: "docker start my-postgres"}]
  stop_steps: [{type: ssh, command: "docker stop my-postgres"}]
```

**Open the tower's files in VS Code Remote-SSH, PyCharm Gateway, etc.:** these tools speak SSH themselves — point them at
`your-user@<tailscale_ip>`. A card can just launch the program: `{type: local, command: '"C:\...\Code.exe"'}`.

**A one-off tunnel without a card:** use the **Tunnels** window (a port, or a `http://localhost:3000/path` link).

## Telemetry on a custom machine

The built-in script reports CPU, RAM, free `C:` space and NVIDIA GPU (via `nvidia-smi`). To report something else, set
`monitoring.custom_command` to a command that prints **one JSON line** with some of: `cpu`, `ram_used_gb`, `ram_total_gb`,
`gpu`, `vram_used_mb`, `vram_total_mb`, `gpu_temp`, `disk_c_free_gb`.

## Languages

`language: fr` (or `en`) forces the UI language. In `actions`, add `name_fr` / `description_fr` (or `name_<code>` for any
language the app supports) for translated card text. Adding a language: see [CONTRIBUTING](../../CONTRIBUTING.md).

---

**Previous:** [← 4 · Linux VM](04-linux-vm.md) · **Next:** [6 · Security →](06-security.md)
