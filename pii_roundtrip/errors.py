"""Exception hierarchy of pii-roundtrip."""

from __future__ import annotations


class PiiRoundtripError(Exception):
    """Base class for all errors raised by pii-roundtrip."""


class UnsupportedLanguageError(PiiRoundtripError, ValueError):
    """The language code is not supported (use "ru" or "en-GB")."""


class SessionError(PiiRoundtripError, ValueError):
    """A session is used with another language or has an unknown format."""


class ModelsNotAvailableError(PiiRoundtripError):
    """A model is not in the local cache. Run `pii-roundtrip download-models` once."""


class InflectionError(PiiRoundtripError):
    """Russian name inflection failed while restoring an answer."""


class VaultError(PiiRoundtripError):
    """The vault cannot be read or written: wrong password, damaged file, refused overwrite."""
