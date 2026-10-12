## What does this change? / Que change cette PR ?

## Checklist
- [ ] `ruff check .` and `pytest` pass
- [ ] New user-facing text uses `t("English text")` and has a French entry in `core/locales/fr.py`
- [ ] Docs updated in **both** `docs/en/` and `docs/fr/` if behaviour changed
- [ ] `python tools/check_privacy.py` passes: no IP, MAC, user name, token or key in the diff
- [ ] Nothing here opens a port to the Internet or weakens the default security settings
