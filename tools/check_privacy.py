"""Scans the repository for personal data and secrets BEFORE you commit or publish.

    python tools/check_privacy.py                       # generic patterns + .privacy-denylist (if present)
    python tools/check_privacy.py --denylist my.txt     # extra literal strings to forbid

`.privacy-denylist` (git-ignored) is YOUR list of private values, one per line, matched case-insensitively:
your Tailscale IP, MAC address, Windows user name, computer name, domain names, e-mail...
It stays on your machine; the CI only runs the generic patterns.

Exit code 0 = clean, 1 = findings (printed with file:line).
"""
from __future__ import annotations

import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
SKIP_FILES = {"check_privacy.py", ".privacy-denylist"}   # the patterns themselves / your private list (git-ignored)
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe", ".dll", ".zip", ".pyc", ".woff", ".woff2"}
ALLOWED_EMAILS = re.compile(r"(@example\.(com|org)|noreply|@users\.noreply\.github\.com)", re.I)
ALLOWED_MACS = {"AA:BB:CC:DD:EE:FF", "00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF", "02:00:00:00:00:01"}
# documentation examples that are fine to publish (a real Tailscale address anywhere else is flagged)
ALLOWED_IPS = {"100.101.102.103", "100.64.0.0"} | {f"100.64.0.{n}" for n in range(1, 10)}
ALLOWED_WIN_USERS = {"public", "you", "vous", "user", "username", "your-windows-user", "default", "all users",
                     "%username%", "<user>", "name"}

PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN (?:[A-Z ]*)PRIVATE KEY-----")),
    ("JSON web token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("API token or secret-looking value", re.compile(r"(?i)\b(?:api[_-]?token|secret|passwd|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{20,}")),
    ("SSH public key blob", re.compile(r"\bssh-(?:ed25519|rsa)\s+AAAA[A-Za-z0-9+/=]{20,}")),
]
IPV4 = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")
MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WIN_USER = re.compile(r"[A-Za-z]:\\Users\\([^\\\s'\"<>|]+)", re.I)
CGNAT = ipaddress.ip_network("100.64.0.0/10")


def candidate_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.splitlines()
        return [ROOT / p for p in out if (ROOT / p).is_file()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS)]


def scan_text(name: str, text: str, denylist: list[str]) -> list[str]:
    findings: list[str] = []
    low = text.lower()
    for term in denylist:
        if term in low:
            line = low[: low.index(term)].count("\n") + 1
            findings.append(f"{name}:{line}: denylisted private value ({term[:3]}…)")
    for n, line in enumerate(text.splitlines(), 1):
        for label, rx in PATTERNS:
            if rx.search(line):
                findings.append(f"{name}:{n}: {label}")
        for m in IPV4.finditer(line):
            try:
                ip = ipaddress.ip_address(m.group(0))
            except ValueError:
                continue
            if ip in CGNAT and str(ip) not in ALLOWED_IPS:
                findings.append(f"{name}:{n}: Tailscale/CGNAT address {ip}")
        for m in MAC.finditer(line):
            if m.group(0).upper().replace("-", ":") not in ALLOWED_MACS:
                findings.append(f"{name}:{n}: MAC address {m.group(0)}")
        for m in EMAIL.finditer(line):
            if not ALLOWED_EMAILS.search(m.group(0)):
                findings.append(f"{name}:{n}: e-mail address {m.group(0)}")
        for m in WIN_USER.finditer(line):
            if m.group(1).lower() not in ALLOWED_WIN_USERS:
                findings.append(f"{name}:{n}: Windows profile path for user '{m.group(1)}'")
    return findings


def load_denylist(paths: list[Path]) -> list[str]:
    terms: list[str] = []
    for p in paths:
        if p.exists():
            terms += [ln.strip().lower() for ln in p.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.startswith("#")]
    return terms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--denylist", action="append", default=[], help="file with private strings to forbid")
    args = ap.parse_args()
    deny = load_denylist([ROOT / ".privacy-denylist", *map(Path, args.denylist)])

    findings: list[str] = []
    for f in candidate_files():
        if f.name in SKIP_FILES or f.suffix.lower() in BINARY_EXT:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings += scan_text(f.relative_to(ROOT).as_posix(), text, deny)

    if findings:
        print("PRIVACY CHECK FAILED - do not publish:\n")
        print("\n".join(findings))
        return 1
    print(f"Privacy check passed ({len(deny)} private term(s) checked + generic patterns).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
