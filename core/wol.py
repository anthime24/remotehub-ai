"""Multi-target Wake-on-LAN: broadcast on every interface, unicast, SSH relay, Freebox."""
from __future__ import annotations

import re
import socket
from collections.abc import Callable

import paramiko

from . import freebox
from .config import Config, expand_path
from .i18n import t


def magic_packet(mac: str) -> bytes:
    raw = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(raw) != 12:
        raise ValueError(t("Invalid MAC address: {mac}", mac=repr(mac)))
    return b"\xff" * 6 + bytes.fromhex(raw) * 16


def _local_ipv4s() -> list[str]:
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def send_wol(cfg: Config, log: Callable[[str, str], None]) -> int:
    """Sends the packet everywhere it can go. Returns the number of successful sends."""
    w = cfg.section("wake_on_lan")
    pkt = magic_packet(cfg.vars["mac"])
    ports = [int(p) for p in w.get("ports", [9])]
    sent = 0

    # (local source address or None, destination)
    jobs: list[tuple[str | None, str]] = []
    for b in w.get("broadcasts", ["255.255.255.255"]):
        jobs += [(ip, b) for ip in _local_ipv4s()] + [(None, b)]
    jobs += [(None, u) for u in w.get("unicast", [])]

    for src, dst in jobs:
        for port in ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.settimeout(2)
                    if src:
                        s.bind((src, 0))
                    s.sendto(pkt, (dst, port))
                    sent += 1
            except OSError as exc:
                log("dbg", f"WoL {src or '*'} -> {dst}:{port}: {exc}")

    if freebox.wake(cfg, log):
        sent += 1

    relay = w.get("relay") or {}
    if relay.get("enabled"):
        sent += _via_relay(cfg, relay, log)
    return sent


def _via_relay(cfg: Config, relay: dict, log) -> int:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())  # the relay must already be in known_hosts
    try:
        key = expand_path(relay.get("key_file"))
        client.connect(relay["host"], port=int(relay.get("port", 22)), username=relay["user"],
                       key_filename=key or None, timeout=8, banner_timeout=10, auth_timeout=10)
        _, out, err = client.exec_command(cfg.render(relay.get("command", "wakeonlan {{mac}}")), timeout=15)
        code = out.channel.recv_exit_status()
        log("ok" if code == 0 else "err",
            t("WoL relay {host}: exit code {code} {err}", host=relay["host"], code=code,
              err=err.read().decode(errors="replace").strip()))
        return 1 if code == 0 else 0
    except Exception as exc:
        log("err", t("WoL relay unreachable ({host}): {exc}", host=relay.get("host"), exc=exc))
        return 0
    finally:
        client.close()
