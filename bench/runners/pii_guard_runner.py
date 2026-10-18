"""redmadrobot pii-guard: правила с контрольными суммами + ruBERT, обратимый режим
pseudonymize с восстановлением в нужном падеже. Только русский.

Спаны pii-guard указывают на нормализованный текст; они переносятся на исходный
выравниванием строк (runners.base.map_spans).
"""

from __future__ import annotations

from bench.runners.base import Runner, Span, map_spans, resolve_overlaps
from pii_roundtrip.adapters._hub import local_snapshot
from pii_roundtrip.adapters.pii_guard import NER_MODEL, NER_REVISION, default_device

TYPE_MAP = {
    "PERSON": "PERSON",
    "LOCATION": "ADDRESS",
    "POSTAL_CODE": "ADDRESS",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "INN": "INN",
    "SNILS": "SNILS",
    "PASSPORT": "PASSPORT_RU",
    "CREDIT_CARD": "CARD",
    "BANK_ACCOUNT": "BANK_ACCOUNT_RU",
    "DATE_TIME": "DATE",
}


class PiiGuardRunner(Runner):
    name = "pii_guard"
    langs = frozenset({"ru"})
    reversible = True

    def __init__(self):
        from pii_guard import Anonymizer
        from pii_guard.config import Config

        # настройки передаются явно, без переменных окружения; модель из локального кеша
        self.device = default_device()
        path = local_snapshot(NER_MODEL, NER_REVISION, offline=True)
        self.a = Anonymizer(Config.load(ner_model=path, ner_revision=None, device=self.device))

    def config(self) -> dict:
        return {
            "commit": "24230abb72949a9f85499244dd4f15a0ad0cdd9e",
            "model": NER_MODEL,
            "device": self.device,
            "model_revision": NER_REVISION,
            "ner_enabled": self.a.ner_enabled,
            "entities": sorted(self.a.config.entities),
            "mode_for_cycle": "pseudonymize",
            "note": "нет типа ORG; спаны перенесены с normalized_text на исходный текст",
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        r = self.a.anonymize(text, mode="tag")
        norm = r.normalized_texts[0]
        spans = [Span(TYPE_MAP.get(e["entity_type"], e["entity_type"]), e["start"], e["end"]) for e in r.entities[0]]
        return resolve_overlaps(map_spans(spans, norm, text))

    def anonymize(self, text: str, lang: str) -> tuple[str, object]:
        r = self.a.anonymize(text, mode="pseudonymize")
        return r.texts[0], r.mapping

    def deanonymize(self, text: str, state: object) -> str:
        return self.a.deanonymize(text, state)[0]

    def system_prompt(self) -> str:
        return self.a.pseudonymize_system_prompt()
