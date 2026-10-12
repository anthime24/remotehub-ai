"""Action engine: runs the `steps` / `stop_steps` declared in config.yaml."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .config import Config
from .i18n import t
from .runner import LocalRunner
from .ssh_client import SSHManager, ps_command, ps_detached
from .tunnels import TunnelManager

LogFn = Callable[[str, str], None]


class StepError(Exception):
    pass


class ActionEngine:
    def __init__(self, cfg: Config, ssh: SSHManager, tunnels: TunnelManager,
                 runner: LocalRunner, log: LogFn):
        self.cfg, self.ssh, self.tunnels, self.runner, self.log = cfg, ssh, tunnels, runner, log

    # -- API --------------------------------------------------------------
    @staticmethod
    def steps_of(action: dict[str, Any], stop: bool = False) -> list[dict[str, Any]]:
        if stop:
            return list(action.get("stop_steps") or [])
        return list(action.get("steps") or [action])

    @staticmethod
    def has_stop(action: dict[str, Any]) -> bool:
        return bool(action.get("stop_steps"))

    def is_active(self, action: dict[str, Any]) -> bool:
        """Active = every tunnel of the action is open (False if the action has no tunnel)."""
        ports = [int(s["local_port"]) for s in self.steps_of(action) if s.get("type") == "tunnel"]
        return bool(ports) and all(self.tunnels.is_active(p) for p in ports)

    def execute(self, action: dict[str, Any], stop: bool = False) -> tuple[bool, str]:
        """Runs an action. Never raises: returns (ok, message)."""
        name = action.get("name", action.get("id", "?"))
        try:
            for step in self.steps_of(action, stop):
                self._step(step)
            return True, t("{name}: stopped", name=name) if stop else t("{name}: OK", name=name)
        except StepError as exc:
            return False, f"{name}: {exc}"
        except Exception as exc:  # safety net: the UI must never crash
            return False, t("{name}: unexpected error ({kind}: {exc})", name=name, kind=type(exc).__name__, exc=exc)

    # -- steps ------------------------------------------------------------
    def _step(self, step: dict[str, Any]) -> None:
        r = self.cfg.render
        kind = step.get("type")

        if kind == "local":
            self.runner.run(r(step["command"]), console=bool(step.get("console")))

        elif kind == "warp_ssh":
            self.log("info", self.runner.warp_ssh(step.get("remote_command", ""), r(step.get("command", ""))))

        elif kind == "url":
            self.runner.open_url(r(step["url"]))

        elif kind == "rdp":
            self.runner.open_rdp(int(step["local_port"]), r(step.get("user", "{{user}}")),
                                 int(step.get("width", 1600)), int(step.get("height", 900)))

        elif kind == "ssh":
            self._ssh_step(step)

        elif kind == "tunnel":
            if not self.ssh.connect():
                raise StepError(t("tower unreachable: cannot open the tunnel"))
            try:
                self.tunnels.start(int(step["local_port"]), int(step["remote_port"]),
                                   r(step.get("remote_host", "localhost")))
            except RuntimeError as exc:
                raise StepError(str(exc)) from exc
            self.log("ok", t("Tunnel localhost:{local} → tower:{remote}", local=step["local_port"],
                             remote=step["remote_port"]))

        elif kind == "tunnel_stop":
            self.tunnels.stop(int(step["local_port"]))
            self.log("info", t("Tunnel localhost:{local} closed", local=step["local_port"]))

        elif kind == "check_file":
            path = r(step["path"])
            res = self.ssh.run(ps_command("Test-Path -LiteralPath '" + path.replace("'", "''") + "'"), timeout=20)
            if not res.ok:
                raise StepError(res.err.strip() or t("tower unreachable"))
            if res.out.strip() != "True":
                raise StepError(t("file not found on the tower: {path} (did you deploy the tower scripts? "
                                  "see tools/deploy_tower.py and `vars.scripts_dir` in config.yaml)", path=path))

        elif kind == "wait_port":
            self._wait_port(r(step.get("remote_host", "localhost")), int(step["remote_port"]),
                            float(step.get("timeout", 60)), step.get("http_path"), step)

        elif kind == "wait":
            time.sleep(float(step.get("seconds", 1)))

        else:
            raise StepError(t("unknown step type: {kind}", kind=repr(kind)))

    def _ssh_step(self, step: dict[str, Any]) -> None:
        r = self.cfg.render
        if "powershell" in step:
            script = r(step["powershell"])
            cmd = ps_detached(script) if step.get("detach") else ps_command(script)
        elif "command" in step:
            cmd = r(step["command"])
            if step.get("detach"):
                cmd = ps_detached(f"cmd /c {cmd}")
        else:
            raise StepError(t("ssh step without `command` or `powershell`"))
        res = self.ssh.run(cmd, timeout=float(step.get("timeout", 30)))
        if res.text:
            self.log("dbg", res.text[-400:])
        if not res.ok and not step.get("ignore_errors"):
            raise StepError(res.err.strip() or t("remote command failed (code {code})", code=res.code))

    def _wait_port(self, host: str, port: int, timeout: float, http_path: str | None = None,
                   step: dict | None = None) -> None:
        step = step or {}
        expect = step.get("expect_banner")                       # e.g. "SSH-": text sent unprompted
        expect_hex, probe_hex = step.get("expect_hex"), step.get("probe_hex")  # e.g. RDP: probe then reply
        if http_path:
            what = t("HTTP answer from {host}:{port}{path}", host=host, port=port, path=http_path)
        elif expect or expect_hex:
            what = t("service ready on {host}:{port}", host=host, port=port)
        else:
            what = t("port {host}:{port}", host=host, port=port)
        self.log("info", t("Waiting for {what} on the tower…", what=what))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if http_path:
                ready = self.ssh.http_ready(host, port, http_path)
            elif expect or expect_hex:
                ready = self.ssh.tcp_expect(host, port, expect.encode() if expect else bytes.fromhex(expect_hex),
                                            bytes.fromhex(probe_hex) if probe_hex else b"")
            else:
                ready = self.ssh.port_open_remote(host, port)
            if ready:
                return
            time.sleep(2)
        raise StepError(t("the service on port {port} did not answer within {seconds}s "
                          "(not started? check the logs on the tower)", port=port, seconds=f"{timeout:.0f}"))
