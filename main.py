"""RemoteHub-AI: entry point."""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    from core.config import Config
    from core.i18n import set_language, t

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    demo = "--demo" in sys.argv  # fake data, no network: screenshots / trying the UI without a tower
    cfg_path = Path(args[0]) if args else ROOT / ("config.example.yaml" if demo else "config.yaml")
    set_language(None)  # system language until the config is read
    if not cfg_path.exists():
        _fatal(t("No configuration found.\n\nCopy config.example.yaml to config.yaml and edit it "
                 "(see docs/en/02-laptop-setup.md).\n\nExpected: {path}", path=cfg_path))
        return 1
    try:
        cfg = Config.load(cfg_path)
    except Exception as exc:  # unreadable config: show it instead of crashing silently
        _fatal(t("Cannot read {path}:\n{exc}", path=cfg_path, exc=exc))
        return 1
    set_language(cfg.data.get("language", "auto"))

    from gui.app import App
    App(cfg, demo=demo).mainloop()
    return 0


def _fatal(msg: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("RemoteHub-AI", msg)
    except Exception:
        print(msg, file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        _fatal(traceback.format_exc())
        sys.exit(1)
