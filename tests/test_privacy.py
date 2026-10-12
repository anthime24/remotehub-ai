import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_privacy", Path(__file__).resolve().parent.parent / "tools" / "check_privacy.py")
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def scan(text, deny=()):
    return cp.scan_text("f.txt", text, list(deny))


def test_flags_private_values():
    assert any("CGNAT" in f for f in scan("host: 100.100." + "1.2"))
    assert any("MAC" in f for f in scan("mac: 3A:5F:21:" + "C4:D8:90"))
    assert any("e-mail" in f for f in scan("contact bob@" + "gmail.com"))
    assert any("Windows profile" in f for f in scan("C:\\Users\\" + "bob" + "\\Desktop"))
    assert any("private key" in f for f in scan("-----BEGIN OPENSSH " + "PRIVATE KEY-----"))
    assert any("JSON web token" in f for f in scan("eyJhbGciOiJIUzI1NiJ9." + "a" * 20 + "." + "b" * 20))
    assert any("denylisted" in f for f in scan("my tower is Foo-PC", ["foo-pc"]))


def test_allows_placeholders():
    ok = "tailscale_ip: 100.x.y.z\nmac: AA:BB:CC:DD:EE:FF\nlan 192.168.1.255\nnoreply@github.com\nC:\\Users\\Public\\x\n"
    assert scan(ok) == []
