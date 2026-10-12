# Contributing / Contribuer

Thanks for helping! Contributions in English **or** French are welcome.
Merci de votre aide ! Les contributions en anglais **ou** en français sont bienvenues.

## Quick start

```powershell
git clone https://github.com/OWNER/remotehub-ai.git
cd remotehub-ai
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
git config core.hooksPath .githooks      # blocks commits that contain personal data
.venv\Scripts\python main.py --demo      # the UI with fake data: no tower needed
.venv\Scripts\pytest
.venv\Scripts\ruff check .
```

`--demo` starts the window with sample data and no network access, handy to work on the interface.

## Project layout

| Path | What it is |
|---|---|
| `core/` | No-UI logic: SSH (`ssh_client.py`), tunnels and SOCKS5 (`tunnels.py`), actions engine (`actions.py`), Wake-on-LAN, SFTP, health, telemetry |
| `gui/` | CustomTkinter windows. Background threads never touch widgets: they post to a queue |
| `core/locales/` | Translations (`fr.py`). Source strings in the code are English: `t("English text")` |
| `tower/` | PowerShell scripts that run **on the tower** (setup, services, VM) |
| `tools/` | Helper scripts for the laptop (deploy, Freebox registration, privacy check) |
| `docs/en`, `docs/fr` | The guides, kept in sync |
| `config.example.yaml` | The documented configuration with placeholders only |

## Rules that keep the project safe

1. **Never commit personal data**: IP addresses, MAC addresses, user names, hostnames, tokens, keys, screenshots of your
   real setup. Run `python tools/check_privacy.py` (the pre-commit hook does it). Put your own private values in
   `.privacy-denylist` (git-ignored, one per line) so the checker also catches them.
2. **Secure by default.** Nothing may listen on a non-loopback address, open a firewall port to the Internet, or store a
   secret in clear text in the repo. New services must bind to `127.0.0.1` and be reached through a tunnel.
3. **Never raise into the UI.** Network code returns results/messages; the interface must never crash because the tower is off.
4. **Translate.** User-facing text goes through `t("English text")`; add the French string in `core/locales/fr.py`
   (a test fails if one is missing). Documentation changes go in both `docs/en` and `docs/fr`.
5. **Test what you can without a tower.** See `tests/` for examples (SOCKS5 and port forwarding are tested against a local echo server).

## Adding a launcher

Most needs require **no code**: add an entry under `actions:` in `config.yaml`
(see [docs/en/05-configuration.md](docs/en/05-configuration.md)). If it is generally useful, add it to
`config.example.yaml` (with `description_fr`) and, if it needs a script on the tower, to `tower/services/`.

## Adding a language

1. Copy `core/locales/fr.py` to `core/locales/<code>.py` and translate the values.
2. Add the code to `SUPPORTED` in `core/i18n.py`.
3. Translate `docs/en` into `docs/<code>` if you can.

## Pull requests

Small focused PRs are easier to review. Describe what you tested and on which Windows versions.
Do not include screenshots that show your real IPs or machine names (use `python main.py --demo`).
