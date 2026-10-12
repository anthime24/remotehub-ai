"""Registers RemoteHub-AI with a Freebox (once, at home). Optional: only for Freebox users."""
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import Config  # noqa: E402
from core.freebox import FreeboxError, register  # noqa: E402
from core.i18n import set_language  # noqa: E402

cfg = Config.load(ROOT / "config.yaml")
set_language(cfg.data.get("language", "auto"))
try:
    register(cfg, lambda lvl, msg: print(f"[{lvl}] {msg}"), device_name=socket.gethostname())
except (FreeboxError, OSError) as exc:
    print(f"[err] {exc}")
    sys.exit(1)
