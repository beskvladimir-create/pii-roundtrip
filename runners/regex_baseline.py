"""Базовая линия: регулярные выражения с проверкой контрольных сумм, без моделей."""

from __future__ import annotations

import re

from generator import ids
from runners.base import Runner, Span, resolve_overlaps

D = r"(?<![\d])"  # слева не цифра
E = r"(?![\d])"  # справа не цифра

PATTERNS = {
    "ru": [
        ("SNILS", re.compile(D + r"\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{2}" + E), ids.is_valid_snils),
        ("CARD", re.compile(D + r"(?:\d{4}[ -]?){3}\d{4}" + E), ids.is_valid_card),
        ("BANK_ACCOUNT_RU", re.compile(D + r"(?:4\d{19}|4\d{4}(?: \d{5}){3})" + E), None),
        ("INN", re.compile(D + r"(?:\d{12}|\d{10}|\d{4} \d{6})" + E), ids.is_valid_inn),
        ("PASSPORT_RU", re.compile(D + r"\d{2} ?\d{2}(?: ?№)? ?\d{6}" + E), None),
        ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
        ("PHONE", re.compile(r"(?<![\w+])(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}" + E), None),
    ],
    "uk": [
        ("CARD", re.compile(D + r"(?:\d{4}[ -]?){3}\d{4}" + E), ids.is_valid_card),
        ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"), ids.is_valid_iban),
        ("NHS", re.compile(D + r"\d{3}[ -]?\d{3}[ -]?\d{4}" + E), ids.is_valid_nhs),
        (
            "NINO",
            re.compile(r"\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z] ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"),
            ids.is_valid_nino,
        ),
        ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
        (
            "PHONE",
            re.compile(r"(?<![\w+])(?:\+44 ?\(?0?\)? ?|\(?0)\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}" + E),
            None,
        ),
    ],
}

_PASSPORT_CTX = re.compile(r"паспорт|серия|сер\.|№", re.I)
_INN_CTX = re.compile(r"ИНН|налогоплательщик", re.I)


class RegexBaseline(Runner):
    name = "regex_baseline"

    def config(self) -> dict:
        return {"types": {lang: [p[0] for p in pats] for lang, pats in PATTERNS.items()}}

    def detect(self, text: str, lang: str) -> list[Span]:
        found: list[Span] = []
        taken: list[tuple[int, int]] = []
        for etype, rx, valid in PATTERNS[lang]:
            for m in rx.finditer(text):
                s, e = m.span()
                if any(s < te and ts < e for ts, te in taken):
                    continue
                v = m.group()
                if valid and not valid(v):
                    continue
                if etype == "INN" and len(re.sub(r"\D", "", v)) == 10:
                    # 10 цифр бывают и ИНН, и паспортом; решает контекст слева
                    left = text[max(0, s - 40) : s]
                    if _PASSPORT_CTX.search(left) and not _INN_CTX.search(left):
                        continue
                if etype == "PASSPORT_RU" and " " not in v and not _PASSPORT_CTX.search(text[max(0, s - 40) : s]):
                    continue
                found.append(Span(etype, s, e))
                taken.append((s, e))
        return resolve_overlaps(found)
