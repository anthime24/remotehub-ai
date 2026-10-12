"""Non-blocking health check: TCP:22 + latency, ICMP ping fallback, Wake-on-LAN state."""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .config import Config
from .i18n import t

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class State(Enum):
    OFFLINE = "offline"
    BOOTING = "booting"
    ONLINE = "online"


@dataclass
class HealthStatus:
    state: State = State.OFFLINE
    latency_ms: float | None = None
    host: str | None = None
    ssh_port_open: bool = False
    ping_ok: bool = False
    detail: str = ""


def tcp_probe(host: str, port: int, timeout: float) -> float | None:
    """TCP connection latency in ms, or None."""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - t0) * 1000
    except OSError:
        return None


def icmp_ping(host: str, timeout_ms: int = 1000) -> float | None:
    cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host] if sys.platform == "win32" else \
        ["ping", "-c", "1", "-W", "1", host]
    try:
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, creationflags=_NO_WINDOW, timeout=timeout_ms / 1000 + 2)
        return (time.perf_counter() - t0) * 1000 if r.returncode == 0 and b"TTL" in r.stdout.upper() else None
    except Exception:
        return None


class HealthMonitor(threading.Thread):
    def __init__(self, cfg: Config, on_status: Callable[[HealthStatus], None]):
        super().__init__(daemon=True, name="health")
        h = cfg.section("health")
        self.cfg = cfg
        self.on_status = on_status
        self.interval = float(h.get("interval_s", 4))
        self.tcp_timeout = float(h.get("tcp_timeout_s", 2))
        self.grace = float(h.get("boot_grace_s", 240))
        self.port = int(cfg.section("connection").get("ssh_port", 22))
        self._halt = threading.Event()
        self._wake = threading.Event()
        self._wol_until = 0.0

    def note_wol(self) -> None:
        self._wol_until = time.time() + self.grace
        self._wake.set()

    def force_check(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._halt.set()
        self._wake.set()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                status = self.check()
            except Exception as exc:  # the thread must never die
                status = HealthStatus(detail=t("Health check error: {exc}", exc=exc))
            self.on_status(status)
            self._wake.wait(self.interval)
            self._wake.clear()

    def check(self) -> HealthStatus:
        hosts = self.cfg.hosts
        for host in hosts:
            lat = tcp_probe(host, self.port, self.tcp_timeout)
            if lat is not None:
                self._wol_until = 0.0
                return HealthStatus(State.ONLINE, lat, host, True, True, t("Online · {ms} ms", ms=f"{lat:.0f}"))
        for host in hosts:
            if icmp_ping(host) is not None:
                return HealthStatus(State.BOOTING, None, host, False, True, t("Host reachable, SSH not available"))
        if time.time() < self._wol_until:
            return HealthStatus(State.BOOTING, detail=t("Starting up (Wake-on-LAN sent)"))
        return HealthStatus(State.OFFLINE, detail=t("Offline"))
