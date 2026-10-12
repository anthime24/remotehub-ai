"""Reusable dark-theme components."""
from __future__ import annotations

import time
from collections.abc import Callable

import customtkinter as ctk

from core.i18n import localized, t

from . import theme as T


def font(size=13, weight="normal", mono=False):
    return ctk.CTkFont(family=T.MONO if mono else T.FONT, size=size, weight=weight)


class Card(ctk.CTkFrame):
    def __init__(self, master, title: str = "", **kw):
        super().__init__(master, fg_color=T.SURFACE, border_color=T.BORDER, border_width=1,
                         corner_radius=12, **kw)
        if title:
            ctk.CTkLabel(self, text=title.upper(), font=font(11, "bold"), text_color=T.MUTED
                         ).pack(anchor="w", padx=16, pady=(14, 6))


def button(master, text, command, kind="default", width=0, **kw) -> ctk.CTkButton:
    colors = {
        "default": (T.BTN, T.BTN_HOVER, T.TEXT),
        "primary": (T.CYAN, "#67e3f5", "#04252b"),
        "danger": ("#3a1518", "#55191e", "#ff8d8d"),
    }[kind]
    return ctk.CTkButton(master, text=text, command=command, fg_color=colors[0], hover_color=colors[1],
                         text_color=colors[2], text_color_disabled=T.MUTED, corner_radius=8, height=34,
                         width=width, font=font(13, "bold" if kind == "primary" else "normal"), **kw)


class StatusBadge(ctk.CTkFrame):
    """Coloured dot + label."""

    def __init__(self, master):
        super().__init__(master, fg_color=T.SURFACE_2, corner_radius=20)
        self.dot = ctk.CTkLabel(self, text="●", font=font(16), text_color=T.RED, width=20)
        self.dot.pack(side="left", padx=(12, 2), pady=6)
        self.label = ctk.CTkLabel(self, text=t("Offline"), font=font(13, "bold"), text_color=T.TEXT)
        self.label.pack(side="left", padx=(0, 14))

    def set(self, color: str, text: str):
        self.dot.configure(text_color=color)
        self.label.configure(text=text)


class MetricBar(ctk.CTkFrame):
    def __init__(self, master, name: str):
        super().__init__(master, fg_color="transparent")
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=name, font=font(12, "bold"), text_color=T.MUTED, width=48, anchor="w"
                     ).grid(row=0, column=0, sticky="w")
        self.bar = ctk.CTkProgressBar(self, height=8, fg_color=T.SURFACE_2, progress_color=T.CYAN)
        self.bar.grid(row=0, column=1, sticky="ew", padx=10)
        self.bar.set(0)
        self.value = ctk.CTkLabel(self, text="—", font=font(12, mono=True), text_color=T.TEXT,
                                  width=130, anchor="e")
        self.value.grid(row=0, column=2, sticky="e")

    def update_value(self, pct: float | None, text: str = ""):
        if pct is None:
            self.bar.set(0)
            self.bar.configure(progress_color=T.BORDER)
            self.value.configure(text="—")
            return
        pct = max(0.0, min(100.0, pct))
        self.bar.set(pct / 100)
        self.bar.configure(progress_color=T.usage_color(pct))
        self.value.configure(text=text or f"{pct:.0f} %")


class ActionCard(ctk.CTkFrame):
    """Card of a dynamic launcher: tag, name, state, Start/Stop buttons."""

    def __init__(self, master, action: dict, on_start: Callable, on_stop: Callable | None):
        super().__init__(master, fg_color=T.SURFACE_2, corner_radius=10)
        self.action = action
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=action.get("tag", "•"), font=font(10, "bold"), text_color=T.CYAN,
                     fg_color="#0e2a31", corner_radius=6, width=52, height=24
                     ).grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=12)
        ctk.CTkLabel(self, text=localized(action, "name", "?"), font=font(13, "bold"), anchor="w"
                     ).grid(row=0, column=1, sticky="w", pady=(10, 0))
        self.desc = ctk.CTkLabel(self, text=localized(action, "description"), font=font(11),
                                 text_color=T.MUTED, anchor="w", justify="left", wraplength=260)
        self.desc.grid(row=1, column=1, sticky="w", pady=(0, 10))
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=0, column=2, rowspan=2, padx=10)
        self.dot = ctk.CTkLabel(box, text="●", font=font(12), text_color=T.BORDER, width=14)
        self.dot.pack(side="left", padx=(0, 6))
        self.start_btn = button(box, t("Start"), lambda: on_start(action), "primary", width=76)
        self.start_btn.pack(side="left")
        self.stop_btn = None
        if on_stop and action.get("stop_steps"):
            self.stop_btn = button(box, t("Stop"), lambda: on_stop(action), "danger", width=60)
            self.stop_btn.pack(side="left", padx=(6, 0))

    def set_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        self.start_btn.configure(state=state, text="…" if busy else t("Start"))
        if self.stop_btn:
            self.stop_btn.configure(state=state)

    def set_active(self, active: bool):
        self.dot.configure(text_color=T.GREEN if active else T.BORDER)


class ConfirmDialog(ctk.CTkToplevel):
    """Dark confirmation dialog (the native messagebox is white)."""

    def __init__(self, master, title: str, message: str, confirm_text: str, on_confirm: Callable):
        super().__init__(master, fg_color=T.SURFACE)
        self.title(title)
        self.geometry("420x190")
        self.resizable(False, False)
        self.transient(master)
        ctk.CTkLabel(self, text=title, font=font(16, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(self, text=message, font=font(13), text_color=T.MUTED, wraplength=370,
                     justify="left").pack(anchor="w", padx=22)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", fill="x", padx=22, pady=18)
        button(row, t("Cancel"), self.destroy, width=100).pack(side="right")
        button(row, confirm_text, lambda: (self.destroy(), on_confirm()), "danger", width=130
               ).pack(side="right", padx=8)
        self.after(120, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            pass


class LogConsole(ctk.CTkTextbox):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color="#07090c", border_width=0, corner_radius=8,
                         font=font(12, mono=True), text_color=T.TEXT, wrap="word", **kw)
        for lvl, col in T.LOG_COLORS.items():
            self._textbox.tag_config(lvl, foreground=col)
        self._textbox.tag_config("ts", foreground=T.MUTED)
        self.configure(state="disabled")

    def write(self, level: str, msg: str):
        self.configure(state="normal")
        self._textbox.insert("end", time.strftime("%H:%M:%S  "), "ts")
        self._textbox.insert("end", msg + "\n", level if level in T.LOG_COLORS else "info")
        lines = int(self._textbox.index("end-1c").split(".")[0])
        if lines > 500:
            self._textbox.delete("1.0", f"{lines - 500}.0")
        self.configure(state="disabled")
        self._textbox.see("end")
