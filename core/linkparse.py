"""Parses a "tower link" typed by the user (3000, localhost:3000/x, http://192.168.1.1...)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .i18n import t


@dataclass
class Target:
    scheme: str
    host: str   # as seen from the tower
    port: int
    path: str

    def url(self, local_port: int) -> str:
        return f"{self.scheme}://127.0.0.1:{local_port}{self.path}"


def parse_target(text: str) -> Target:
    raw = text.strip()
    if not raw:
        raise ValueError(t("Enter a port or a link (e.g. 3000 or http://localhost:8080/app)"))
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://(.*)$", raw)
    scheme, rest = (m.group(1).lower(), m.group(2)) if m else ("http", raw)
    if scheme not in ("http", "https"):
        raise ValueError(t("Only http:// and https:// links are supported (use a plain port otherwise)"))
    hostport, slash, tail = rest.partition("/")
    path = slash + tail
    if re.fullmatch(r"\d{1,5}", hostport):
        hostport = "127.0.0.1:" + hostport
    host, sep, port_s = hostport.rpartition(":")
    if not sep or not port_s.isdigit():
        host, port_s = hostport, "443" if scheme == "https" else "80"
    host = (host or "127.0.0.1").strip("[]")
    if host.lower() == "localhost":
        host = "127.0.0.1"  # "localhost" means the tower, not the laptop
    port = int(port_s)
    if not 1 <= port <= 65535:
        raise ValueError(t("Invalid port: {port}", port=port))
    return Target(scheme, host, port, path)
