"""Builds the real main window (and the two tool windows) against an unreachable fake tower."""
from pathlib import Path

import pytest
import yaml

from core.config import Config
from core.i18n import set_language

ROOT = Path(__file__).resolve().parent.parent

tk = pytest.importorskip("tkinter")
ctk = pytest.importorskip("customtkinter")


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_main_window_builds(lang):
    data = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))
    data["connection"].update({"tailscale_ip": "100.64.0.1", "user": "tester", "connect_timeout": 1})
    data["monitoring"]["enabled"] = False
    data["language"] = lang
    set_language(lang)
    cfg = Config(data, ROOT / "config.yaml")

    try:
        from gui.app import App
        app = App(cfg)
    except tk.TclError as exc:  # headless machine
        pytest.skip(f"no display available: {exc}")
    try:
        for _ in range(5):
            app.update()
        assert len(app.cards) == len(cfg.actions)
        app._open_files()
        app._open_tunnels()
        for _ in range(5):
            app.update()
        assert app.tunnel_win.winfo_exists() and app.browser.winfo_exists()
    finally:
        app._close()
