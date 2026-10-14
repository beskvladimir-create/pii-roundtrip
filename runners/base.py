"""Единый интерфейс инструментов.

Каждый раннер умеет detect(); обратимые инструменты дополнительно реализуют
anonymize() и deanonymize() своими средствами. Для инструментов, которые только
распознают, полный цикл идёт через общую подстановку меток (runners/placeholders.py),
это фиксируется в отчёте.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))

# Единая схема типов (совпадает с генератором и eval/external.py).
TYPES = {
    "PERSON", "ADDRESS", "ORG", "PHONE", "EMAIL", "DATE_OF_BIRTH",
    "PASSPORT_RU", "SNILS", "INN", "BANK_ACCOUNT_RU", "CARD",
    "NHS", "NINO", "IBAN",
}


@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int

    def as_dict(self) -> dict:
        return {"type": self.type, "start": self.start, "end": self.end}


class Runner:
    name: str = "base"
    langs: frozenset[str] = frozenset({"ru", "uk"})
    reversible: bool = False

    def config(self) -> dict:
        """Конфигурация запуска для отчёта."""
        return {}

    def detect(self, text: str, lang: str) -> list[Span]:
        raise NotImplementedError

    def anonymize(self, text: str, lang: str) -> tuple[str, object]:
        raise NotImplementedError

    def deanonymize(self, text: str, state: object) -> str:
        raise NotImplementedError


def offset_map(src: str, dst: str) -> list[int]:
    """Для каждой позиции src (включая len(src)) ближайшая позиция в dst.

    Нужна инструментам, которые возвращают спаны по нормализованному тексту.
    """
    from difflib import SequenceMatcher

    m = [0] * (len(src) + 1)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, src, dst, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                m[k] = j1 + (k - i1)
            else:  # пропорционально внутри изменённого участка
                m[k] = j1 + ((k - i1) * (j2 - j1)) // max(1, i2 - i1)
    m[len(src)] = len(dst)
    return m


def map_spans(spans: list[Span], src: str, dst: str) -> list[Span]:
    if src == dst:
        return spans
    m = offset_map(src, dst)
    out = []
    for s in spans:
        start = m[s.start]
        end = m[s.end - 1] + 1 if s.end > s.start else start
        out.append(Span(s.type, start, max(end, start + 1)))
    return out


def resolve_overlaps(spans: list[Span], text: str | None = None) -> list[Span]:
    """Объединяет пересекающиеся спаны (тип берётся у более длинного), чтобы ничего
    не потерять при маскировке. Если передан текст, спан, обрывающийся посреди
    слова, расширяется до границ слова: одинаково для всех инструментов."""
    if text is not None:
        snapped = []
        for s in spans:
            a, b = s.start, s.end
            while a > 0 and text[a - 1].isalnum() and a < len(text) and text[a].isalnum():
                a -= 1
            while b < len(text) and b > 0 and text[b - 1].isalnum() and text[b].isalnum():
                b += 1
            snapped.append(Span(s.type, a, b))
        spans = snapped
    out: list[Span] = []
    for s in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if out and s.start < out[-1].end:
            last = out[-1]
            t = last.type if last.end - last.start >= s.end - s.start else s.type
            out[-1] = Span(t, last.start, max(last.end, s.end))
            continue
        out.append(s)
    return out
