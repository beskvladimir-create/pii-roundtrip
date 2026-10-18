"""Движок pii-roundtrip через тот же интерфейс, что и остальные инструменты."""

from __future__ import annotations

from bench.runners.base import Runner, Span


def _lang(lang: str) -> str:
    """В данных бенчмарка британский английский помечен как "uk"; библиотека ждёт "en-GB"."""
    return "en-GB" if lang == "uk" else lang


class PiiRoundtripRunner(Runner):
    name = "pii_roundtrip"
    reversible = True

    def __init__(self):
        from pii_roundtrip import Engine

        self.engine = Engine()

    def config(self) -> dict:
        import pii_roundtrip
        from pii_roundtrip.adapters import gliner, pii_guard

        return {
            "version": pii_roundtrip.__version__,
            "components": {
                "pii_guard_model": f"{pii_guard.NER_MODEL}@{pii_guard.NER_REVISION}",
                "gliner": f"{gliner.MODEL}@{gliner.REVISION} thr={gliner.THRESHOLD}",
            },
            "labels": "[TYPE_n], согласованные по документу",
            "note": "компоненты pii-guard и GLiNER Guard выпущены авторами обоих русских внешних наборов",
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        return [Span(s.type, s.start, s.end) for s in self.engine.spans(text, _lang(lang))]

    def anonymize(self, text: str, lang: str):
        return self.engine.anonymize(text, _lang(lang))

    def deanonymize(self, text: str, state) -> str:
        return self.engine.deanonymize(text, state)

    def system_prompt(self) -> str:
        return (
            "The text contains placeholders like [PERSON_1], [ORG_2], [NHS_1] that replace personal data. "
            "Keep every placeholder you use exactly as written, including the square brackets. "
            "Never invent real-looking values instead of placeholders."
        )
