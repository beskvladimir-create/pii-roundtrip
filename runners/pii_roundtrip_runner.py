"""Движок pii-roundtrip через тот же интерфейс, что и остальные инструменты."""

from __future__ import annotations

from runners.base import Runner, Span


class PiiRoundtripRunner(Runner):
    name = "pii_roundtrip"
    reversible = True

    def __init__(self):
        from pii_roundtrip import Engine

        self.engine = Engine()

    def config(self) -> dict:
        import pii_roundtrip
        from pii_roundtrip import detect

        return {
            "version": pii_roundtrip.__version__,
            "components": {
                "pii_guard_model_revision": detect.PII_GUARD_REVISION,
                "gliner": f"{detect.GLINER_MODEL}@{detect.GLINER_REVISION} thr={detect.GLINER_THRESHOLD}",
            },
            "labels": "[TYPE_n], согласованные по документу",
            "note": "компоненты pii-guard и GLiNER Guard выпущены авторами обоих русских внешних наборов",
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        return [Span(s.type, s.start, s.end) for s in self.engine.spans(text, lang)]

    def anonymize(self, text: str, lang: str):
        return self.engine.anonymize(text, lang)

    def deanonymize(self, text: str, state) -> str:
        return self.engine.deanonymize(text, state)

    def system_prompt(self) -> str:
        return (
            "The text contains placeholders like [PERSON_1], [ORG_2], [NHS_1] that replace personal data. "
            "Keep every placeholder you use exactly as written, including the square brackets. "
            "Never invent real-looking values instead of placeholders."
        )
