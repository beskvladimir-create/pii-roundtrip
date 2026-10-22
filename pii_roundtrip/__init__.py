"""pii-roundtrip: local reversible anonymisation of Russian and British English documents
for use with external LLMs."""

from importlib.metadata import PackageNotFoundError, version

from pii_roundtrip.core import Engine, Session, anonymize, deanonymize
from pii_roundtrip.detect import Models, clear_caches
from pii_roundtrip.errors import (
    InflectionError,
    ModelsNotAvailableError,
    PiiRoundtripError,
    SessionError,
    UnsupportedLanguageError,
    VaultError,
)

try:
    __version__ = version("pii-roundtrip")
except PackageNotFoundError:  # running from a source checkout without installation
    __version__ = "0.3.1"

__all__ = [
    "Engine",
    "Session",
    "Models",
    "anonymize",
    "deanonymize",
    "clear_caches",
    "PiiRoundtripError",
    "UnsupportedLanguageError",
    "SessionError",
    "ModelsNotAvailableError",
    "InflectionError",
    "VaultError",
]
