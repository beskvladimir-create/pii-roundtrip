"""Общая подстановка меток для инструментов, которые только распознают.

Согласованные метки по документу: одно значение (после нормализации) всегда
получает одну метку [TYPE_n]. Восстановление терпимо к регистру и потере скобок.
Это нейтральная обвязка бенчмарка, а не часть инструментов; в отчёте помечается.
"""

from __future__ import annotations

import re

from bench.runners.base import Runner

LABEL_RE = re.compile(r"\[?\b([A-Z][A-Z_]*?)_(\d+)\b\]?", re.I)


def _norm(v: str) -> str:
    return re.sub(r"[\s\-().]+", "", v).lower()


class PlaceholderWrapper(Runner):
    reversible = True

    def __init__(self, detector: Runner):
        self.detector = detector
        self.name = f"{detector.name}+placeholders"
        self.langs = detector.langs

    def config(self) -> dict:
        return {"detector": self.detector.name, "labels": "[TYPE_n], консистентные по документу"}

    def anonymize(self, text: str, lang: str) -> tuple[str, object]:
        spans = sorted(self.detector.detect(text, lang), key=lambda s: s.start)
        mapping: dict[str, str] = {}
        by_value: dict[tuple[str, str], str] = {}
        counters: dict[str, int] = {}
        out, pos = [], 0
        for s in spans:
            value = text[s.start : s.end]
            key = (s.type, _norm(value))
            if key not in by_value:
                counters[s.type] = counters.get(s.type, 0) + 1
                label = f"[{s.type}_{counters[s.type]}]"
                by_value[key] = label
                mapping[label] = value
            out.append(text[pos : s.start])
            out.append(by_value[key])
            pos = s.end
        out.append(text[pos:])
        return "".join(out), mapping

    def deanonymize(self, text: str, state: object) -> str:
        mapping: dict[str, str] = state  # type: ignore[assignment]
        canon = {k.strip("[]").upper(): v for k, v in mapping.items()}

        def sub(m: re.Match) -> str:
            key = f"{m.group(1).upper()}_{m.group(2)}"
            return canon.get(key, m.group(0))

        return LABEL_RE.sub(sub, text)

    def system_prompt(self) -> str:
        return (
            "The text contains placeholders like [PERSON_1], [ADDRESS_2], [NHS_1]. "
            "Keep every placeholder you use exactly as written, including the square brackets. "
            "Never invent real-looking values instead of placeholders."
        )
