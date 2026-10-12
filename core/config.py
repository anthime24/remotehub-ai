"""Loads config.yaml and substitutes {{variables}}."""
from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .i18n import t

_VAR = re.compile(r"\{\{(\w+)\}\}")
PLACEHOLDER_MAC = "AA:BB:CC:DD:EE:FF"
PLACEHOLDER_SECRET = "change-me"


def expand_path(p: str | None) -> str:
    return os.path.expandvars(os.path.expanduser(p)) if p else ""


class Config:
    def __init__(self, data: dict[str, Any], path: Path):
        self.data = data or {}
        self.path = Path(path).resolve()  # absolute: relative paths in the config depend on it
        conn = self.section("connection")
        loc = self.section("local_tools")
        self.vars: dict[str, str] = {
            "tailscale_ip": str(conn.get("tailscale_ip", "")),
            "lan_ip": str(conn.get("lan_ip", "")),
            "user": str(conn.get("user", "")),
            "ssh_port": str(conn.get("ssh_port", 22)),
            "mac": str(conn.get("mac", "")),
            **{k: expand_path(str(v)) for k, v in loc.items()},
            "project_dir": str(self.path.parent),
            **{k: str(v) for k, v in self.section("vars").items()},
        }

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {}, path)

    def section(self, name: str) -> dict[str, Any]:
        v = self.data.get(name)
        return v if isinstance(v, dict) else {}

    @property
    def actions(self) -> list[dict[str, Any]]:
        return [a for a in self.data.get("actions", []) if isinstance(a, dict)]

    @property
    def hosts(self) -> list[str]:
        """Candidate hosts, in order of preference (Tailscale first, LAN as a fallback)."""
        c = self.section("connection")
        return [str(h) for h in (c.get("tailscale_ip"), c.get("lan_ip")) if h]

    def render(self, text: Any) -> Any:
        if not isinstance(text, str):
            return text
        return _VAR.sub(lambda m: self.vars.get(m.group(1), m.group(0)), text)

    def problems(self) -> list[str]:
        """Human-readable list of settings that still hold example values (shown in the log at startup)."""
        c = self.section("connection")
        out: list[str] = []
        for key in ("tailscale_ip", "lan_ip"):
            value = str(c.get(key) or "")
            if key == "tailscale_ip" and not value:
                out.append(t("connection.tailscale_ip is empty: set your tower's Tailscale IP."))
                continue
            if value:
                try:
                    ipaddress.ip_address(value)
                except ValueError:
                    out.append(t("connection.{key} is not a valid IP address: {value}", key=key, value=value))
        if not c.get("user"):
            out.append(t("connection.user is empty: set the Windows account used for SSH."))
        mac = str(c.get("mac") or "")
        if not mac or mac.upper() == PLACEHOLDER_MAC:
            out.append(t("connection.mac still holds the example value: Wake-on-LAN will not work."))
        if self.vars.get("jupyter_token", PLACEHOLDER_SECRET) == PLACEHOLDER_SECRET and any(
                "jupyter_token" in str(a) for a in self.actions):
            out.append(t("vars.jupyter_token is still \"change-me\": choose a long random token."))
        return out
