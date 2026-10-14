"""redmadrobot pii-guard: правила с контрольными суммами + ruBERT, обратимый режим
pseudonymize с восстановлением в нужном падеже. Только русский.

Спаны pii-guard указывают на нормализованный текст; они переносятся на исходный
выравниванием строк (runners.base.map_spans).
"""

from __future__ import annotations

import os

from runners.base import Runner, Span, map_spans, resolve_overlaps

try:  # графический процессор Apple, если он есть; иначе pii-guard выберет сам
    import torch

    if torch.backends.mps.is_available():
        os.environ.setdefault("PII_GUARD_DEVICE", "mps")
except Exception:
    pass
os.environ.setdefault("PII_GUARD_NER_REVISION", "c802e8cd26f85d1cf920973ea6f83965a0618d63")

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

        self.a = Anonymizer()

    def config(self) -> dict:
        return {
            "commit": "24230abb72949a9f85499244dd4f15a0ad0cdd9e",
            "model": "redmadrobot-rnd/rubert-base-pii-ner",
            "device": os.environ.get("PII_GUARD_DEVICE"),
            "model_revision": os.environ.get("PII_GUARD_NER_REVISION"),
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
