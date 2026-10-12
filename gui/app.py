"""Main window. Background threads NEVER write to the UI: everything goes through a queue."""
from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk

from core.actions import ActionEngine
from core.config import Config
from core.files import FileManager
from core.health import HealthMonitor, HealthStatus, State
from core.i18n import t
from core.monitor import StatsPoller
from core.runner import LocalRunner
from core.ssh_client import SSHManager
from core.tunnels import TunnelManager
from core.wol import send_wol

from . import theme as T
from .files import FileBrowser
from .tunnels import TunnelWindow
from .widgets import ActionCard, Card, ConfirmDialog, LogConsole, MetricBar, StatusBadge, button, font

SECTIONS = [("dev", "Developer tools"), ("ai", "AI hub & remote services"),
            ("system", "Containers & virtual machines")]


class App(ctk.CTk):
    def __init__(self, cfg: Config, demo: bool = False):
        super().__init__(fg_color=T.BG)
        self.demo = demo  # fake data, no network: used for screenshots and UI development
        ctk.set_appearance_mode("dark")
        if demo:  # shrink everything so the whole dashboard fits one screenshot
            ctk.set_widget_scaling(0.62)
            ctk.set_window_scaling(0.62)
        self.cfg = cfg
        self.title(f"RemoteHub-AI · {cfg.section('connection').get('name', '')}")
        self.geometry("1160x1330" if demo else "1120x820")
        self.minsize(900, 640)

        self.events: queue.Queue = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="job")
        self.health_status = HealthStatus()
        self.cards: dict[str, ActionCard] = {}
        self.browser: FileBrowser | None = None
        self.tunnel_win: TunnelWindow | None = None

        # --- backend ---
        self.ssh = SSHManager(cfg, self.log)
        self.tunnels = TunnelManager(self.ssh)
        self.files = FileManager(cfg, self.ssh, self.log)
        self.engine = ActionEngine(cfg, self.ssh, self.tunnels, LocalRunner(cfg), self.log)
        self.health = HealthMonitor(cfg, lambda s: self.events.put(("health", s)))
        self.stats = StatsPoller(cfg, self.ssh,
                                 lambda: self.health_status.state is State.ONLINE,
                                 lambda s: self.events.put(("stats", s)))

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        if demo:
            self.after(300, self._demo_feed)
        else:
            self.health.start()
            self.stats.start()
        self.after(100, self._pump)
        c = cfg.section("connection")
        self.log("info", t("RemoteHub-AI ready · target {user}@{host}", user=c.get("user", "?"),
                           host=c.get("tailscale_ip", "?")))
        for problem in () if demo else cfg.problems():
            self.log("warn", problem)

    # ------------------------------------------------------------------ UI
    def _build(self):
        c = self.cfg.section("connection")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0, height=64)
        head.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(head, text="Remote", font=font(22, "bold")).pack(side="left", padx=(24, 0), pady=14)
        ctk.CTkLabel(head, text="Hub·AI", font=font(22, "bold"), text_color=T.CYAN).pack(side="left", pady=14)
        ctk.CTkLabel(head, text=f"{c.get('name', '')} · {c.get('tailscale_ip', '')}", font=font(12, mono=True),
                     text_color=T.MUTED).pack(side="left", padx=18)
        self.badge = StatusBadge(head)
        self.badge.pack(side="right", padx=(10, 24))
        button(head, "📁  " + t("Files"), self._open_files, width=110).pack(side="right")
        button(head, "🔌  " + t("Tunnels"), self._open_tunnels, width=110).pack(side="right", padx=(0, 8))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=T.BORDER)
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(10, 0))
        body.columnconfigure((0, 1), weight=1, uniform="col")

        self._energy_card(body).grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self._monitor_card(body).grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        row = 1
        for cat, title in SECTIONS:
            actions = [a for a in self.cfg.actions if a.get("category", "dev") == cat]
            if not actions:
                continue
            card = Card(body, t(title))
            card.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
            grid = ctk.CTkFrame(card, fg_color="transparent")
            grid.pack(fill="x", padx=12, pady=(0, 14))
            grid.columnconfigure((0, 1), weight=1, uniform="a")
            for i, act in enumerate(actions):
                w = ActionCard(grid, act, self._start_action, self._stop_action)
                w.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=4)
                self.cards[act.get("id", act.get("name"))] = w
            row += 1

        log_card = Card(self, t("Log"))
        log_card.grid(row=2, column=0, sticky="ew", padx=20, pady=12)
        self.console = LogConsole(log_card, height=130)
        self.console.pack(fill="x", padx=12, pady=(0, 12))

    def _energy_card(self, master) -> Card:
        card = Card(master, t("Power & connectivity"))
        self.status_line = ctk.CTkLabel(card, text=t("Offline"), font=font(13), text_color=T.MUTED, anchor="w")
        self.status_line.pack(fill="x", padx=16)
        button(card, "⏻  " + t("Wake the tower (Wake-on-LAN)"), self._wake, "primary"
               ).pack(fill="x", padx=16, pady=(12, 8))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        row.columnconfigure((0, 1), weight=1, uniform="b")
        button(row, t("Restart"), lambda: self._power("restart"), "danger"
               ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        button(row, t("Shut down"), lambda: self._power("shutdown"), "danger"
               ).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        return card

    def _monitor_card(self, master) -> Card:
        card = Card(master, t("Live telemetry"))
        self.m_cpu, self.m_ram, self.m_gpu, self.m_vram = (MetricBar(card, n) for n in ("CPU", "RAM", "GPU", "VRAM"))
        for m in (self.m_cpu, self.m_ram, self.m_gpu, self.m_vram):
            m.pack(fill="x", padx=16, pady=5)
        self.m_extra = ctk.CTkLabel(card, text="", font=font(11, mono=True), text_color=T.MUTED, anchor="w")
        self.m_extra.pack(fill="x", padx=16, pady=(4, 14))
        return card

    # ------------------------------------------------------------- events
    def log(self, level: str, msg: str):
        self.events.put(("log", level, msg))  # callable from any thread

    def _pump(self):
        try:
            for _ in range(80):
                ev = self.events.get_nowait()
                getattr(self, f"_on_{ev[0]}")(*ev[1:])
        except queue.Empty:
            pass
        for aid, card in self.cards.items():
            card.set_active(aid in ("ollama", "jupyter") if self.demo else self.engine.is_active(card.action))
        self._refresh_badge()
        self.after(150, self._pump)

    def _on_log(self, level, msg):
        self.console.write(level, msg)

    def _on_health(self, status: HealthStatus):
        self.health_status = status

    def _on_stats(self, s: dict | None):
        if not s:
            for m in (self.m_cpu, self.m_ram, self.m_gpu, self.m_vram):
                m.update_value(None)
            self.m_extra.configure(text="")
            return
        gb = t("GB")
        self.m_cpu.update_value(s.get("cpu"))
        if s.get("ram_total_gb"):
            used, tot = s.get("ram_used_gb", 0), s["ram_total_gb"]
            self.m_ram.update_value(used / tot * 100, f"{used:.1f}/{tot:.0f} {gb}")
        if s.get("gpu") is not None:
            temp = f" · {s['gpu_temp']:.0f}°C" if s.get("gpu_temp") is not None else ""
            self.m_gpu.update_value(s["gpu"], f"{s['gpu']:.0f} %{temp}")
            vu, vt = s.get("vram_used_mb", 0), s.get("vram_total_mb") or 1
            self.m_vram.update_value(vu / vt * 100, f"{vu / 1024:.1f}/{vt / 1024:.0f} {gb}")
        else:
            self.m_gpu.update_value(None)
            self.m_vram.update_value(None)
        if s.get("disk_c_free_gb") is not None:
            self.m_extra.configure(text=t("Disk C: free {n} {unit}", n=s["disk_c_free_gb"], unit=gb))

    def _on_done(self, aid, ok, msg):
        card = self.cards.get(aid)
        if card:
            card.set_busy(False)
        self.log("ok" if ok else "err", msg)

    def _refresh_badge(self):
        h = self.health_status
        if h.state is State.ONLINE and (self.ssh.connected or self.demo):
            self.badge.set(T.GREEN, t("Online · {ms} ms", ms=f"{h.latency_ms:.0f}"))
            self.status_line.configure(text=t("SSH active via {host}", host=self.ssh.host or "100.x.y.z"),
                                       text_color=T.GREEN)
        elif h.state is State.ONLINE:
            self.badge.set(T.YELLOW, t("SSH connecting…"))
            self.status_line.configure(text=t("Port 22 open ({ms} ms), SSH connecting…", ms=f"{h.latency_ms:.0f}"),
                                       text_color=T.YELLOW)
        elif h.state is State.BOOTING:
            self.badge.set(T.YELLOW, t("Booting…"))
            self.status_line.configure(text=h.detail, text_color=T.YELLOW)
        else:
            self.badge.set(T.RED, t("Offline"))
            self.status_line.configure(text=t("Offline: use Wake-on-LAN"), text_color=T.MUTED)

    def _demo_feed(self):
        self.events.put(("health", HealthStatus(State.ONLINE, 23.0, "100.x.y.z", True, True)))
        self.events.put(("stats", {"cpu": 18, "ram_used_gb": 9.4, "ram_total_gb": 32, "gpu": 62, "gpu_temp": 58,
                                   "vram_used_mb": 5200, "vram_total_mb": 12288, "disk_c_free_gb": 142.3}))
        for lvl, msg in (("ok", t("SSH connected to {user}@{host}", user="you", host="100.x.y.z")),
                         ("info", t("Starting {name}…", name="Ollama (LLM)")),
                         ("ok", t("Tunnel localhost:{local} → tower:{remote}", local=11435, remote=11434)),
                         ("ok", t("{name}: OK", name="Ollama (LLM)")),
                         ("ok", t("Tunnel localhost:{local} → tower:{remote}", local=8888, remote=8888)),
                         ("ok", t("{name}: OK", name="JupyterLab"))):
            self.events.put(("log", lvl, msg))

    # ------------------------------------------------------------ actions
    def _open_files(self):
        if self.browser is not None and self.browser.winfo_exists():
            self.browser.deiconify()
            self.browser.focus_force()
            return
        self.browser = FileBrowser(self, self.files, self.pool, self.log)

    def _open_tunnels(self):
        if self.tunnel_win is not None and self.tunnel_win.winfo_exists():
            self.tunnel_win.deiconify()
            self.tunnel_win.focus_force()
            return
        self.tunnel_win = TunnelWindow(self, self.tunnels, self.pool, self.log)

    def _wake(self):
        def job():
            try:
                n = send_wol(self.cfg, self.log)
                self.health.note_wol()
                self.log("ok" if n else "err", t("Magic packet: {n} send(s) succeeded", n=n) if n
                         else t("No packet sent (network down?)"))
            except Exception as exc:
                self.log("err", t("Wake-on-LAN: {exc}", exc=exc))
        self.pool.submit(job)

    def _power(self, kind: str):
        label = t("Restart") if kind == "restart" else t("Shut down")
        ConfirmDialog(self, t("{action} the tower?", action=label),
                      t("Running services (Ollama, ComfyUI…) will be interrupted.") + " "
                      + (t("The tower will restart.") if kind == "restart"
                         else t("You can wake it again with Wake-on-LAN.")),
                      label, lambda: self.pool.submit(self._power_job, kind))

    def _power_job(self, kind: str):
        cmd = self.cfg.section("power").get(f"{kind}_command")
        self.log("info", t("Sending: {cmd}", cmd=cmd))
        res = self.ssh.run(cmd, timeout=10)
        # a session cut during shutdown is normal
        if res.ok or res.code == -1 and self.health_status.state is State.ONLINE:
            self.log("ok", t("Command sent"))
            self.tunnels.stop_all()
            self.ssh.close()
            self.health.force_check()
        else:
            self.log("err", t("Failed: {err}", err=res.err.strip() or res.out.strip()))

    def _start_action(self, action):
        self._run_action(action, stop=False)

    def _stop_action(self, action):
        self._run_action(action, stop=True)

    def _run_action(self, action, stop: bool):
        aid = action.get("id", action.get("name"))
        self.cards[aid].set_busy(True)
        name = action.get("name")
        self.log("info", t("Stopping {name}…", name=name) if stop else t("Starting {name}…", name=name))

        def job():
            ok, msg = self.engine.execute(action, stop)
            self.events.put(("done", aid, ok, msg))
        self.pool.submit(job)

    # -------------------------------------------------------------- close
    def _close(self):
        self.health.stop()
        self.stats.stop()
        self.tunnels.stop_all()
        self.ssh.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.destroy()
