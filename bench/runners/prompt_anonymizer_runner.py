"""Prompt Anonymizer (akazah, Python 0.3.3): Presidio + spaCy, reversible placeholders of
the form <Name_1>. No Russian, UK only. Best documented configuration:
model_size="lg", all default types plus the optional IBAN_CODE. It has no British
identifiers (NHS, NI) and no organisations."""

from __future__ import annotations

from bench.runners.base import Runner, Span, resolve_overlaps

TYPE_MAP = {
    "PERSON": "PERSON",
    "LOCATION": "ADDRESS",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CARD",
    "IBAN_CODE": "IBAN",
}


class PromptAnonymizerRunner(Runner):
    name = "prompt_anonymizer"
    langs = frozenset({"uk"})
    reversible = True

    def __init__(self):
        from prompt_anonymizer import DEFAULT_ENTITIES, OPTIONAL_ENTITIES, PromptAnonymizer

        self.entities = list(DEFAULT_ENTITIES) + [e for e in OPTIONAL_ENTITIES if e == "IBAN_CODE"]
        self.pa = PromptAnonymizer(languages=["en"], model_size="lg", entities=self.entities)

    def config(self) -> dict:
        return {
            "version": "0.3.3",
            "languages": ["en"],
            "model_size": "lg",
            "entities": self.entities,
            "score_threshold": 0.4,
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        r = self.pa.anonymize(text, language="en")
        return resolve_overlaps([Span(TYPE_MAP.get(e.entity_type, e.entity_type), e.start, e.end) for e in r.entities])

    def anonymize(self, text: str, lang: str) -> tuple[str, object]:
        r = self.pa.anonymize(text, language="en")
        return r.text, r.mapping

    def deanonymize(self, text: str, state: object) -> str:
        return self.pa.deanonymize(text, state)
