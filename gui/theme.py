"""Palette sombre inspirée Warp / Cursor / Vercel."""

BG = "#0A0C10"
SURFACE = "#12151C"
SURFACE_2 = "#181C26"
BORDER = "#242a38"
TEXT = "#E6EDF3"
MUTED = "#7D8590"

CYAN = "#22D3EE"
BLUE = "#3B82F6"
VIOLET = "#A78BFA"
GREEN = "#22C55E"
YELLOW = "#EAB308"
RED = "#EF4444"

BTN = "#1D2230"
BTN_HOVER = "#262d40"

FONT = "Segoe UI"
MONO = "Cascadia Mono"

LOG_COLORS = {"ok": GREEN, "err": RED, "info": CYAN, "dbg": MUTED, "warn": YELLOW}


def usage_color(pct: float) -> str:
    return GREEN if pct < 60 else YELLOW if pct < 85 else RED
