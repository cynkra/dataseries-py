"""Helpers for the API's translated label objects.

Most human-readable fields come as a translation map, e.g.
``{"en": "GDP", "de": "BIP", "fr": "PIB", "it": "PIL"}``. ``label()`` picks
the requested language, falling back to English, then to whatever is there.
"""

from __future__ import annotations

LANGUAGES = ("en", "de", "fr", "it")


def check_lang(lang: str) -> str:
    if lang not in LANGUAGES:
        raise ValueError(f"lang must be one of {LANGUAGES}, got {lang!r}")
    return lang


def label(x, lang: str = "en"):
    """Pick a label from a translated map, preferring `lang`, then English.

    Passes a bare string through; returns None for an absent value.
    """
    if x is None:
        return None
    if isinstance(x, dict):
        if not x:
            return None
        return x.get(lang) or x.get("en") or next(iter(x.values()))
    return str(x)


def scalar(x):
    """Collapse a string-or-empty-object field to a string or None.

    Several catalog fields are a string when meaningful and an empty object
    ``{}`` when absent.
    """
    if x is None or isinstance(x, (dict, list)):
        return None
    return str(x)


def source_name(x, lang: str = "en"):
    """`source` is a plain string in the catalog but a {name, url} object in a meta."""
    if x is None:
        return None
    if isinstance(x, dict):
        return label(x.get("name"), lang)
    return str(x)
