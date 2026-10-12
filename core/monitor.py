"""Live telemetry of the tower over SSH: CPU, RAM, NVIDIA GPU, VRAM."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable

from .config import Config
from .ssh_client import SSHManager, ps_command

# Self-contained script: uses no file on the tower.
_SCRIPT = r"""
$ErrorActionPreference='SilentlyContinue'
$cpu=(Get-CimInstance Win32_Processor|Measure-Object LoadPercentage -Average).Average
$os=Get-CimInstance Win32_OperatingSystem
$o=[ordered]@{cpu=[double]$cpu
 ram_total_gb=[math]::Round($os.TotalVisibleMemorySize/1MB,2)
 ram_used_gb=[math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/1MB,2)
 disk_c_free_gb=[math]::Round((Get-PSDrive C).Free/1GB,1)}
$g=(& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits) 2>$null
if($g){$p=@("$g".Split(',')|ForEach-Object{[double]$_.Trim()})
 $o.gpu=$p[0];$o.vram_used_mb=$p[1];$o.vram_total_mb=$p[2];$o.gpu_temp=$p[3]}
$o|ConvertTo-Json -Compress
"""


def parse_stats(text: str) -> dict | None:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                return None
    return None


class StatsPoller(threading.Thread):
    """Polls the tower while it is online; publishes None when a measurement fails."""

    def __init__(self, cfg: Config, ssh: SSHManager, is_online: Callable[[], bool],
                 on_stats: Callable[[dict | None], None]):
        super().__init__(daemon=True, name="stats")
        m = cfg.section("monitoring")
        self.enabled = bool(m.get("enabled", True))
        self.interval = float(m.get("interval_s", 3))
        custom = str(m.get("custom_command") or "").strip()
        self.command = cfg.render(custom) if custom else ps_command(_SCRIPT)
        self.ssh, self.is_online, self.on_stats = ssh, is_online, on_stats
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        while not self._halt.wait(self.interval):
            if not self.enabled:
                continue
            try:
                if not self.is_online():
                    if self.ssh.connected:
                        self.ssh.close()  # the tower went down: release the dead session
                    self.on_stats(None)
                    continue
                res = self.ssh.run(self.command, timeout=15)
                self.on_stats(parse_stats(res.out) if res.ok else None)
            except Exception:
                self.on_stats(None)
