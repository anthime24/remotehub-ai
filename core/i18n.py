"""Tiny gettext-like helper.

Source strings are English; `core/locales/<lang>.py` maps them to other languages.
    t("Hello {name}", name="x")  ->  "Bonjour x" when the language is French.
Missing translations fall back to the English text, so adding a language is incremental.
"""
from __future__ import annotations

import importlib
import locale

_catalog: dict[str, str] = {}
_lang = "en"
SUPPORTED = ("en", "fr")


def detect_language() -> str:
    try:
        code = (locale.getdefaultlocale()[0] or "en")[:2].lower()
    except Exception:
        code = "en"
    return code if code in SUPPORTED else "en"


def set_language(code: str | None) -> str:
    """Select the UI language ("auto" or None = system language). Returns the language actually used."""
    global _lang, _catalog
    code = (code or "auto").lower()
    if code == "auto":
        code = detect_language()
    if code not in SUPPORTED:
        code = "en"
    _lang = code
    _catalog = {}
    if code != "en":
        _catalog = importlib.import_module(f"core.locales.{code}").MESSAGES
    return code


def language() -> str:
    return _lang


def localized(item: dict, key: str, default: str = "") -> str:
    """item[key_<lang>] if present (e.g. description_fr), else item[key]."""
    return str(item.get(f"{key}_{_lang}") or item.get(key) or default)


def t(msg: str, **kw) -> str:
    text = _catalog.get(msg, msg)
    return text.format(**kw) if kw else text
