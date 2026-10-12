""""Tunnels" window: open a tower link/port on the laptop, or browse through the tower's network."""
from __future__ import annotations

import os
import queue
import shutil
import socket
import subprocess
import tempfile
import webbrowser
from pathlib import Path

import customtkinter as ctk

from core.i18n import t
from core.linkparse import parse_target
from core.tunnels import TunnelManager

from . import theme as T
from .widgets import Card, button, font

SOCKS_PORT = 1080


def _free_port(preferred: int | None = None) -> int:
    for p in ([preferred] if preferred and preferred >= 1024 else []) + [0]:
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Aucun port local libre")


def _find_browser() -> str | None:
    for name in ("msedge", "chrome"):
        w = shutil.which(name)
        if w:
            return w
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LocalAppData")):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            if base and (Path(base) / rel).exists():
                return str(Path(base) / rel)
    return None


class TunnelWindow(ctk.CTkToplevel):
    def __init__(self, app, tunnels: TunnelManager, pool, log):
        super().__init__(app, fg_color=T.BG)
        self.tunnels, self.pool, self.log = tunnels, pool, log
        self.title(t("Tunnels & browsing through the tower"))
        self.geometry("760x640")
        self.minsize(640, 520)
        self.q: queue.Queue = queue.Queue()
        self.urls: dict[int, str] = {}
        self._build()
        self.after(150, self._poll)
        self._refresh()

    def _build(self):
        c1 = Card(self, t("Open a tower link on this laptop"))
        c1.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(c1, text=t("A port (3000) or a link as seen from the tower: http://localhost:3000/app, "
                              "http://192.168.1.1, https://localhost:8443…"), font=font(11), text_color=T.MUTED,
                     anchor="w", wraplength=680, justify="left").pack(fill="x", padx=16)
        row = ctk.CTkFrame(c1, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(8, 14))
        row.columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(row, placeholder_text=t("3000  or  http://localhost:3000"), height=36,
                                  fg_color=T.SURFACE_2, border_color=T.BORDER, font=font(13, mono=True))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self._open_link())
        button(row, t("Open"), self._open_link, "primary", width=100).grid(row=0, column=1)

        c2 = Card(self, t("Browse with the tower's network (SOCKS5 proxy)"))
        c2.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(c2, text=t("A dedicated browser goes out through the tower's connection: its router, its local "
                              "services (192.168.1.x), its machine names. Your usual browser is left untouched."),
                     font=font(11), text_color=T.MUTED, anchor="w", wraplength=680, justify="left"
                     ).pack(fill="x", padx=16)
        row2 = ctk.CTkFrame(c2, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(8, 4))
        self.socks_btn = button(row2, "", self._toggle_socks, width=210)
        self.socks_btn.pack(side="left")
        self.browser_btn = button(row2, "🌐  " + t("Browser via the tower"), self._open_proxy_browser, "primary", width=210)
        self.browser_btn.pack(side="left", padx=8)
        self.socks_hint = ctk.CTkLabel(c2, text="", font=font(11, mono=True), text_color=T.MUTED, anchor="w")
        self.socks_hint.pack(fill="x", padx=16, pady=(2, 14))

        c3 = Card(self, t("Active tunnels"))
        c3.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.list = ctk.CTkScrollableFrame(c3, fg_color="transparent", height=150)
        self.list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    # ------------------------------------------------------------ actions
    def _open_link(self):
        try:
            target = parse_target(self.entry.get())
        except ValueError as exc:
            self.log("err", str(exc))
            return
        self.log("info", t("Tunnel to {host}:{port} (tower side)…", host=target.host, port=target.port))

        def job():
            try:
                existing = next((p for p, lab in self.tunnels.labels.items()
                                 if lab == f"→ {target.host}:{target.port}"), None)
                lp = existing or _free_port(target.port)
                if not existing:
                    self.tunnels.start(lp, target.port, target.host)
                url = target.url(lp)
                self.urls[lp] = url
                self.q.put(("opened", url))
            except Exception as exc:
                self.q.put(("err", t("Tunnel: {exc}", exc=exc)))
        self.pool.submit(job)

    def _toggle_socks(self):
        try:
            if self.tunnels.is_active(SOCKS_PORT):
                self.tunnels.stop(SOCKS_PORT)
                self.log("info", t("SOCKS proxy stopped"))
            else:
                self.tunnels.start_socks(SOCKS_PORT)
                self.log("ok", t("SOCKS5 proxy active on 127.0.0.1:{port}", port=SOCKS_PORT))
        except Exception as exc:
            self.log("err", str(exc))
        self._refresh()

    def _open_proxy_browser(self):
        exe = _find_browser()
        if not exe:
            self.log("err", t("Edge/Chrome not found: set the SOCKS5 proxy 127.0.0.1:{port} by hand", port=SOCKS_PORT))
            return
        if not self.tunnels.is_active(SOCKS_PORT):
            self._toggle_socks()
        profile = Path(tempfile.gettempdir()) / "remotehub-proxy-profile"
        subprocess.Popen([exe, f"--proxy-server=socks5://127.0.0.1:{SOCKS_PORT}",
                          "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1",
                          f"--user-data-dir={profile}", "--no-first-run", "--new-window", "about:blank"])
        self.log("ok", t("Browser started: it goes out through the tower's network (separate window)"))

    def _close_tunnel(self, port: int):
        self.tunnels.stop(port)
        self.urls.pop(port, None)
        self.log("info", t("Tunnel :{port} closed", port=port))
        self._refresh()

    # ------------------------------------------------------------ rendering
    def _refresh(self):
        on = self.tunnels.is_active(SOCKS_PORT)
        self.socks_btn.configure(text="■  " + t("Stop the proxy") if on else "▶  " + t("Start the proxy"))
        self.socks_hint.configure(text=t("SOCKS5 127.0.0.1:{port} · active", port=SOCKS_PORT) if on else t("proxy stopped"))
        for w in self.list.winfo_children():
            w.destroy()
        ports = self.tunnels.active_ports
        if not ports:
            ctk.CTkLabel(self.list, text=t("No open tunnel"), font=font(12), text_color=T.MUTED).pack(pady=12)
        for p in ports:
            r = ctk.CTkFrame(self.list, fg_color=T.SURFACE_2, corner_radius=8)
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=f"127.0.0.1:{p}  {self.tunnels.labels.get(p, '')}", font=font(12, mono=True),
                         anchor="w").pack(side="left", padx=12, pady=8)
            button(r, t("Close"), lambda p=p: self._close_tunnel(p), "danger", width=80).pack(side="right", padx=8)
            if p in self.urls:
                button(r, t("Open"), lambda u=self.urls[p]: webbrowser.open(u), width=80).pack(side="right")

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "opened":
                    self.log("ok", t("Link opened: {url}", url=val))
                    webbrowser.open(val)
                else:
                    self.log("err", val)
                self._refresh()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(150, self._poll)
