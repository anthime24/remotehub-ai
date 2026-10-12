import json

import paramiko
import pytest

from core.files import join, parent_of, to_remote
from core.monitor import parse_stats
from core.ssh_client import TrustOnFirstUse, ps_command, ps_detached
from core.wol import magic_packet


def test_magic_packet():
    pkt = magic_packet("aa:bb:cc:dd:ee:ff")
    assert len(pkt) == 102 and pkt[:6] == b"\xff" * 6 and pkt[6:12] == bytes.fromhex("aabbccddeeff")
    assert magic_packet("AA-BB-CC-DD-EE-FF") == pkt
    with pytest.raises(ValueError):
        magic_packet("not a mac")


def test_windows_sftp_paths():
    assert to_remote("D:\\data\\x") == "/D:/data/x"
    assert to_remote("") == "/"
    assert join("D:\\data", "a.txt") == "D:\\data\\a.txt"
    assert join("", "C:") == "C:\\"
    assert parent_of("D:\\data\\x") == "D:\\data\\"
    assert parent_of("D:\\") == ""


def test_parse_stats_takes_last_json_line():
    out = "noise\n" + json.dumps({"cpu": 1}) + "\n" + json.dumps({"cpu": 7, "gpu": 3}) + "\n"
    assert parse_stats(out) == {"cpu": 7, "gpu": 3}
    assert parse_stats("garbage") is None
    assert parse_stats("{broken") is None


def test_ps_wrappers_are_encoded():
    c = ps_command("Write-Output 'a b'")
    assert c.startswith("powershell ") and "-EncodedCommand" in c and "a b" not in c
    assert "Win32_Process" not in ps_detached("x")        # hidden inside the encoded payload
    assert len(ps_detached("Start-Sleep 1")) < 8000


def test_trust_on_first_use_remembers_key(tmp_path):
    logs = []
    kh = tmp_path / "known_hosts"
    key = paramiko.RSAKey.generate(1024)
    client = paramiko.SSHClient()
    TrustOnFirstUse(lambda lvl, msg: logs.append((lvl, msg)), kh).missing_host_key(client, "100.64.0.9", key)
    assert kh.read_text().startswith("100.64.0.9 ssh-rsa ")
    assert client.get_host_keys().check("100.64.0.9", key)
    assert logs and logs[0][0] == "warn" and "SHA256:" in logs[0][1]
    # a different key for an already known host must be rejected by Paramiko's check()
    other = paramiko.RSAKey.generate(1024)
    assert not client.get_host_keys().check("100.64.0.9", other)
