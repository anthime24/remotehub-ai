import ast
import re
from pathlib import Path

from core.i18n import localized, set_language, t
from core.locales.fr import MESSAGES

ROOT = Path(__file__).resolve().parent.parent
# strings passed to t() through a variable or constant (not visible as literals in t(...) calls)
EXTRA_KEYS = {"Developer tools", "AI hub & remote services", "Containers & virtual machines", "Transfer cancelled."}


def source_keys() -> set[str]:
    keys = set()
    files = [*ROOT.glob("core/*.py"), *ROOT.glob("gui/*.py"), *ROOT.glob("tools/*.py"), ROOT / "main.py"]
    for f in files:
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "t" and n.args
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                keys.add(n.args[0].value)
    return keys


def test_every_message_has_a_french_translation():
    missing = sorted((source_keys() | EXTRA_KEYS) - set(MESSAGES))
    assert not missing, "untranslated: " + repr(missing)


def test_no_stale_french_entries():
    stale = sorted(set(MESSAGES) - source_keys() - EXTRA_KEYS)
    assert not stale, "unused translations: " + repr(stale)


def test_placeholders_match():
    rx = re.compile(r"\{(\w+)\}")
    for en, fr in MESSAGES.items():
        assert set(rx.findall(en)) == set(rx.findall(fr)), (en, fr)


def test_translation_and_fallback():
    assert t("Offline") == "Offline"
    set_language("fr")
    assert t("Offline") == "Hors ligne"
    assert t("Tunnel :{port} closed", port=1) == "Tunnel :1 fermé"
    assert t("not in the catalog") == "not in the catalog"
    set_language("xx")                       # unknown -> English
    assert t("Offline") == "Offline"


def test_localized_item():
    item = {"name": "Terminal", "name_fr": "Terminal FR", "description": "d"}
    set_language("fr")
    assert localized(item, "name") == "Terminal FR"
    assert localized(item, "description") == "d"
    set_language("en")
    assert localized(item, "name") == "Terminal"
