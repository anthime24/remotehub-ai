import socket
import struct
import threading

import pytest

from core.tunnels import TunnelManager


class FakeSSH:
    """open_channel() just opens a TCP socket from this process (stands in for an SSH direct-tcpip channel)."""

    def __init__(self, target_port):
        self.target_port = target_port
        self.requests = []

    def open_channel(self, host, port, origin=None):
        self.requests.append((host, port))
        if port == 1:
            raise ConnectionError("refused")
        return socket.create_connection(("127.0.0.1", self.target_port), 3)


@pytest.fixture
def echo():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)

    def serve(c):
        try:
            while True:
                d = c.recv(4096)
                if not d:
                    break
                c.sendall(d.upper())
        finally:
            c.close()

    def loop():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=serve, args=(c,), daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    yield srv
    srv.close()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def socks_connect(port, host, dest_port):
    s = socket.create_connection(("127.0.0.1", port), 3)
    s.sendall(bytes([5, 1, 0]))
    assert s.recv(2) == bytes([5, 0])
    if isinstance(host, str):
        h = host.encode()
        s.sendall(bytes([5, 1, 0, 3, len(h)]) + h + struct.pack("!H", dest_port))
    else:
        s.sendall(bytes([5, 1, 0, 1]) + bytes(host) + struct.pack("!H", dest_port))
    return s, s.recv(10)


def test_local_forward_roundtrip(echo):
    ssh = FakeSSH(echo.getsockname()[1])
    tm = TunnelManager(ssh)
    port = free_port()
    tm.start(port, 8888, "127.0.0.1")
    try:
        assert tm.is_active(port) and tm.active_ports == [port]
        assert tm.labels[port] == "→ 127.0.0.1:8888"
        with socket.create_connection(("127.0.0.1", port), 3) as c:
            c.sendall(b"hello")
            assert c.recv(10) == b"HELLO"
        assert ssh.requests[-1] == ("127.0.0.1", 8888)
    finally:
        tm.stop_all()
    assert not tm.is_active(port)


def test_socks5_domain_and_ipv4(echo):
    ssh = FakeSSH(echo.getsockname()[1])
    tm = TunnelManager(ssh)
    port = free_port()
    tm.start_socks(port)
    try:
        s, reply = socks_connect(port, "example.com", 80)
        assert reply[:2] == bytes([5, 0])
        s.sendall(b"abc")
        assert s.recv(10) == b"ABC"
        s.close()
        assert ssh.requests[-1] == ("example.com", 80)      # the NAME reaches the tower: it is resolved there
        s, reply = socks_connect(port, (192, 168, 1, 1), 8080)
        assert reply[:2] == bytes([5, 0])
        s.close()
        assert ssh.requests[-1] == ("192.168.1.1", 8080)
    finally:
        tm.stop_all()


def test_socks5_failures():
    tm = TunnelManager(FakeSSH(1))
    port = free_port()
    tm.start_socks(port)
    try:
        s, reply = socks_connect(port, "nowhere.test", 1)         # open_channel raises
        assert reply[:2] == bytes([5, 5])
        s.close()
        s = socket.create_connection(("127.0.0.1", port), 3)       # wrong protocol version
        s.sendall(bytes([4, 1, 0]))
        assert s.recv(10) == b""
        s.close()
        s = socket.create_connection(("127.0.0.1", port), 3)       # BIND command is not supported
        s.sendall(bytes([5, 1, 0]))
        s.recv(2)
        s.sendall(bytes([5, 2, 0, 1, 1, 1, 1, 1, 0, 80]))
        assert s.recv(10)[:2] == bytes([5, 7])
        s.close()
    finally:
        tm.stop_all()


def test_port_in_use_is_reported():
    tm = TunnelManager(FakeSSH(1))
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    try:
        with pytest.raises(RuntimeError, match="unavailable"):
            tm.start(blocker.getsockname()[1], 80)
    finally:
        blocker.close()
