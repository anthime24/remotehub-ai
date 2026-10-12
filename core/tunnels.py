"""Local port forwarding (-L) and SOCKS5 proxy (-D) on the Paramiko transport, with no external ssh process."""
from __future__ import annotations

import socket
import socketserver
import struct
import threading
from collections.abc import Callable

from .i18n import t
from .ssh_client import SSHManager


def _pump(src, dst, close_both: Callable[[], None]) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        close_both()


def _bridge(chan, sock) -> None:
    def close_both() -> None:
        for s in (chan, sock):
            try:
                s.close()
            except Exception:
                pass

    threading.Thread(target=_pump, args=(chan, sock, close_both), daemon=True).start()
    _pump(sock, chan, close_both)


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        srv: _Server = self.server  # type: ignore[assignment]
        try:
            chan = srv.ssh.open_channel(srv.remote_host, srv.remote_port, self.request.getpeername())
        except Exception:
            return  # tower unreachable: cleanly refuse the local connection
        _bridge(chan, self.request)


def _recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def _socks_reply(code: int) -> bytes:
    return bytes([5, code, 0, 1, 0, 0, 0, 0, 0, 0])


class _SocksHandler(socketserver.BaseRequestHandler):
    """SOCKS5 (CONNECT only, no authentication): names are resolved by the tower."""

    def handle(self) -> None:
        srv: _Server = self.server  # type: ignore[assignment]
        sock = self.request
        sock.settimeout(30)
        try:
            ver, nmeth = _recv_exact(sock, 2)
            _recv_exact(sock, nmeth)
            if ver != 5:
                return
            sock.sendall(bytes([5, 0]))
            _, cmd, _, atyp = _recv_exact(sock, 4)
            if atyp == 1:
                host = socket.inet_ntoa(_recv_exact(sock, 4))
            elif atyp == 3:
                host = _recv_exact(sock, _recv_exact(sock, 1)[0]).decode("idna")
            elif atyp == 4:
                host = socket.inet_ntop(socket.AF_INET6, _recv_exact(sock, 16))
            else:
                sock.sendall(_socks_reply(8))
                return
            (port,) = struct.unpack("!H", _recv_exact(sock, 2))
            if cmd != 1:
                sock.sendall(_socks_reply(7))
                return
            try:
                chan = srv.ssh.open_channel(host, port, sock.getpeername())
            except Exception:
                sock.sendall(_socks_reply(5))
                return
            sock.sendall(_socks_reply(0))
            sock.settimeout(None)
        except Exception:
            return
        _bridge(chan, sock)


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, ssh: SSHManager, remote_host: str, remote_port: int, handler=_Handler):
        super().__init__(addr, handler)
        self.ssh, self.remote_host, self.remote_port = ssh, remote_host, remote_port


class TunnelManager:
    def __init__(self, ssh: SSHManager):
        self.ssh = ssh
        self._servers: dict[int, _Server] = {}
        self.labels: dict[int, str] = {}
        self._lock = threading.Lock()

    def _listen(self, local_port: int, remote_host: str, remote_port: int, handler, bind: str, label: str) -> None:
        with self._lock:
            if local_port in self._servers:
                return
            try:
                srv = _Server((bind, local_port), self.ssh, remote_host, remote_port, handler)
            except OSError as exc:
                raise RuntimeError(t("Local port {port} unavailable: {exc}", port=local_port, exc=exc)) from exc
            threading.Thread(target=srv.serve_forever, daemon=True, name=f"tunnel-{local_port}").start()
            self._servers[local_port] = srv
            self.labels[local_port] = label

    def start(self, local_port: int, remote_port: int, remote_host: str = "localhost",
              bind: str = "127.0.0.1", label: str = "") -> None:
        self._listen(local_port, remote_host, remote_port, _Handler, bind,
                     label or f"→ {remote_host}:{remote_port}")

    def start_socks(self, local_port: int = 1080) -> None:
        """Local SOCKS5 proxy: everything sent through it leaves via the tower's network."""
        self._listen(local_port, "", 0, _SocksHandler, "127.0.0.1", t("SOCKS5 proxy (tower network)"))

    def stop(self, local_port: int) -> None:
        with self._lock:
            srv = self._servers.pop(local_port, None)
            self.labels.pop(local_port, None)
        if srv:
            srv.shutdown()
            srv.server_close()

    def stop_all(self) -> None:
        for p in list(self._servers):
            self.stop(p)

    def is_active(self, local_port: int) -> bool:
        return local_port in self._servers

    @property
    def active_ports(self) -> list[int]:
        return sorted(self._servers)
