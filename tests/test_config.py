from pathlib import Path

import yaml

from core.config import Config

ROOT = Path(__file__).resolve().parent.parent


def make(data):
    return Config(data, ROOT / "config.yaml")


def test_render_and_vars():
    cfg = make({"connection": {"tailscale_ip": "100.64.0.9", "user": "bob", "mac": "02:00:00:00:00:01"},
                "vars": {"scripts_dir": "C:\\RH"}})
    assert cfg.render("ssh {{user}}@{{tailscale_ip}} {{scripts_dir}} {{nope}}") == "ssh bob@100.64.0.9 C:\\RH {{nope}}"
    assert cfg.render(5) == 5


def test_hosts_order_and_blank_lan():
    assert make({"connection": {"tailscale_ip": "100.64.0.9", "lan_ip": ""}}).hosts == ["100.64.0.9"]
    assert make({"connection": {"tailscale_ip": "100.64.0.9", "lan_ip": "192.168.1.5"}}).hosts == \
        ["100.64.0.9", "192.168.1.5"]


def test_problems_flags_example_values():
    example = Config.load(ROOT / "config.example.yaml")
    text = " ".join(example.problems())
    assert "tailscale_ip" in text          # "100.x.y.z" is not an IP
    assert "mac" in text                   # example MAC
    assert "jupyter_token" in text         # "change-me"


def test_problems_clean_config():
    cfg = make({"connection": {"tailscale_ip": "100.64.0.9", "user": "bob", "mac": "02:00:00:00:00:01"},
                "vars": {"jupyter_token": "x" * 32}})
    assert cfg.problems() == []


def test_example_config_is_valid_yaml_with_known_step_types():
    data = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))
    known = {"local", "warp_ssh", "ssh", "tunnel", "tunnel_stop", "url", "rdp", "check_file", "wait_port", "wait"}
    ids = set()
    for action in data["actions"]:
        assert action["id"] not in ids
        ids.add(action["id"])
        steps = action.get("steps", []) + action.get("stop_steps", []) + ([action] if "steps" not in action else [])
        for step in steps:
            assert step["type"] in known, (action["id"], step)
        assert action["category"] in {"dev", "ai", "system"}
