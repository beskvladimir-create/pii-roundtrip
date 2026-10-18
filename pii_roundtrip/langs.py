"""Language codes.

The library supports Russian ("ru") and British English ("en-GB"). The code "uk" was
used in version 0.1.0 for British English; it is the ISO 639-1 code for Ukrainian, so
it is accepted only as a deprecated alias and will be removed in a later version.
"""

from __future__ import annotations

import warnings

from pii_roundtrip.errors import UnsupportedLanguageError

RU = "ru"
EN_GB = "en-GB"
SUPPORTED = (RU, EN_GB)

_ALIASES = {
    "ru": RU,
    "rus": RU,
    "russian": RU,
    "en-gb": EN_GB,
    "en_gb": EN_GB,
    "en": EN_GB,
    "eng": EN_GB,
    "gb": EN_GB,
    "english": EN_GB,
    "british": EN_GB,
}


def canonical(lang: str) -> str:
    """Return "ru" or "en-GB" for a supported language code."""
    key = (lang or "").strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    if key == "uk":
        warnings.warn(
            '"uk" is the ISO 639-1 code for Ukrainian; use "en-GB" for British English. '
            'The alias "uk" will be removed in a future version.',
            DeprecationWarning,
            stacklevel=3,
        )
        return EN_GB
    raise UnsupportedLanguageError(f"Unsupported language: {lang!r} (use 'ru' or 'en-GB')")
