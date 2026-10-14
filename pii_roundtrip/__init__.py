"""pii-roundtrip: локальная обратимая анонимизация документов (RU / UK) для работы с внешними нейросетями."""

from pii_roundtrip.core import Engine, Session, anonymize, deanonymize

__all__ = ["Engine", "Session", "anonymize", "deanonymize"]
__version__ = "0.1.0"
