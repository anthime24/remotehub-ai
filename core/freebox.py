"""Optional Wake-on-LAN through the Freebox OS API (works from 4G: the box sends from inside the LAN).

Only useful if your router is a Freebox (France). One-time registration (physical button on the box):
    python tools/register_freebox.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import ssl
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .config import Config
from .i18n import t

APP_ID = "fr.remotehub.ai"
LOCAL_BASE = "http://mafreebox.freebox.fr"
LogFn = Callable[[str, str], None]
# "Freebox ECC Root CA", public (https://dev.freebox.fr/sdk/os/), missing from the Windows trust store.
CA_FILE = Path(__file__).resolve().parent / "data" / "freebox_ca.pem"


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if CA_FILE.exists():
        ctx.load_verify_locations(cafile=str(CA_FILE))
    return ctx


class FreeboxError(Exception):
    pass


def token_path(cfg: Config) -> Path:
    name = cfg.section("freebox").get("token_file", "freebox_token.json")
    return Path(name) if Path(name).is_absolute() else cfg.path.parent / name


def _call(url: str, method="GET", body: dict | None = None, session: str | None = None,
          timeout: float = 5) -> dict:
    headers = {"Content-Type": "application/json"}
    if session:
        headers["X-Fbx-App-Auth"] = session
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as exc:  # the API returns JSON even on 4xx
        try:
            payload = json.load(exc)
        except Exception:
            raise FreeboxError(f"HTTP {exc.code}") from exc
    if not payload.get("success"):
        raise FreeboxError(f"{payload.get('error_code', '?')}: {payload.get('msg', payload)}")
    return payload.get("result") or {}


def register(cfg: Config, log: LogFn, device_name: str = "laptop") -> None:
    """Requests access; the user must approve on the Freebox Server screen/buttons."""
    base = f"{LOCAL_BASE}/api/latest"
    info = json.load(urllib.request.urlopen(f"{LOCAL_BASE}/api_version", timeout=8))
    res = _call(f"{base}/login/authorize/", "POST", {
        "app_id": APP_ID, "app_name": "RemoteHub-AI", "app_version": "1.0", "device_name": device_name})
    track = res["track_id"]
    log("warn", t("Press the right arrow / the check button on the Freebox Server screen to authorize…"))
    for _ in range(60):
        st = _call(f"{base}/login/authorize/{track}")["status"]
        if st == "granted":
            path = token_path(cfg)
            path.write_text(json.dumps({
                "app_token": res["app_token"], "api_domain": info.get("api_domain"),
                "https_port": info.get("https_port")}, indent=2), encoding="utf-8")
            log("ok", t("Freebox authorized. Token saved in {path} (keep it secret, never commit it).", path=path))
            return
        if st in ("denied", "timeout"):
            raise FreeboxError(t("authorization {status}", status=st))
        time.sleep(2)
    raise FreeboxError(t("timed out: button not pressed"))


def _bases(tok: dict) -> list[str]:
    bases = [f"{LOCAL_BASE}/api/latest"]
    if tok.get("api_domain") and tok.get("https_port"):
        bases.append(f"https://{tok['api_domain']}:{tok['https_port']}/api/latest")
    return bases


def _session(base: str, app_token: str, timeout: float) -> str:
    challenge = _call(f"{base}/login/", timeout=timeout)["challenge"]
    pwd = hmac.new(app_token.encode(), challenge.encode(), hashlib.sha1).hexdigest()
    return _call(f"{base}/login/session/", "POST", {"app_id": APP_ID, "password": pwd}, timeout=timeout)["session_token"]


def wake(cfg: Config, log: LogFn) -> bool:
    """Sends the WoL through the Freebox (local network first, then remote HTTPS access)."""
    fb = cfg.section("freebox")
    if not fb.get("enabled"):
        return False
    path = token_path(cfg)
    if not path.exists():
        log("warn", t("Freebox: not registered (run tools/register_freebox.py)."))
        return False
    tok = json.loads(path.read_text(encoding="utf-8"))
    last = ""
    for base in _bases(tok):
        where = "local" if base.startswith(LOCAL_BASE) else "remote"
        try:
            sess = _session(base, tok["app_token"], timeout=4)
            _call(f"{base}/lan/wol/{fb.get('interface', 'pub')}/", "POST",
                  {"mac": cfg.vars["mac"], "password": ""}, session=sess, timeout=6)
            log("ok", t("Freebox: magic packet sent ({where})", where=where))
            return True
        except Exception as exc:
            last = f"{where}: {exc}"
            log("dbg", f"Freebox {last}")
    if "insufficient_rights" in last or "auth_required" in last:
        log("err", t("Freebox: insufficient rights. Freebox OS > Settings > Access management > "
                     "Applications > RemoteHub-AI: tick \"Modify Freebox settings\"."))
    else:
        log("err", t("Freebox unreachable ({last}). Is remote HTTPS access enabled in Freebox OS?", last=last))
    return False
