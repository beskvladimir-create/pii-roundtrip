"""Правила: номера с контрольными суммами и шаблоны, которых не хватает моделям.

Правила дают страховку, когда модель пропускает. Номер с ошибкой в контрольной сумме
(опечатка) тоже скрывается, если рядом есть слово-подсказка: «карта», «СНИЛС», «NHS».
Все шаблоны ограничены по длине, без вложенных неограниченных повторений.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pii_roundtrip import checksums as ids


@dataclass(frozen=True)
class Hit:
    type: str
    start: int
    end: int
    source: str = "rules"


D, E = r"(?<![\w])", r"(?![\w])"
SEP = r"[ \-]?"

# (тип, шаблон, валидатор, контекст, при котором номер скрывается и без валидной суммы)
COMMON = [
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}"), None, None),
    ("CARD", re.compile(D + r"\d{4}" + SEP + r"\d{4}" + SEP + r"\d{4}" + SEP + r"\d{4}(?:" + SEP + r"\d{3})?" + E), ids.is_valid_card,
     re.compile(r"карт|card|visa|mastercard|мир\b", re.I)),
    ("CARD", re.compile(D + r"3[47]\d{2}[ -]?\d{6}[ -]?\d{5}" + E), ids.is_valid_card, None),  # Amex 15
    ("IBAN", re.compile(r"\b[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{4}){3,7}(?: ?[A-Za-z0-9]{1,3})?\b"), ids.is_valid_iban, re.compile(r"iban", re.I)),
    ("SOCIAL", re.compile(r"(?<![\w.@])@[A-Za-z][\w]{4,31}\b"), None, None),
    ("PHONE", re.compile(r"(?<![\w+])(?:\+|00)(?!7\b|44\b)\d{1,3}[ (-]{0,2}\d{2,4}[ )-]{0,2}\d{2,4}[ -]?\d{2,4}(?:[ -]?\d{1,4})?" + E), None, None),
]

RU = [
    ("SNILS", re.compile(D + r"\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{2}" + E), ids.is_valid_snils, re.compile(r"снилс|страхов", re.I)),
    ("BANK_ACCOUNT_RU", re.compile(D + r"(?:[34]\d{19}|[34]\d{4}(?: \d{5}){3})" + E), None, None),
    ("INN", re.compile(D + r"(?:\d{12}|\d{10})" + E), ids.is_valid_inn, re.compile(r"\bинн\b", re.I)),
    ("ID", re.compile(D + r"\d{15}" + E), None, re.compile(r"огрнип|огрн", re.I)),
    ("ID", re.compile(D + r"\d{13}" + E), None, re.compile(r"огрн", re.I)),
    ("ID", re.compile(D + r"\d{16}" + E), None, re.compile(r"полис|омс", re.I)),
    ("PASSPORT_RU", re.compile(D + r"\d{2} ?\d{2}(?: ?№)? ?\d{6}" + E), None, None),
    ("PHONE", re.compile(r"(?<![\w+])(?:\+7|8|7)[\s(-]{0,2}\d{3}[\s)-]{0,2}\d{3}[\s-]?\d{2}[\s-]?\d{2}" + E), None, None),
]

UK = [
    ("NHS", re.compile(D + r"\d{3}[ -]?\d{3}[ -]?\d{4}" + E), ids.is_valid_nhs, re.compile(r"\bnhs\b", re.I)),
    ("NINO", re.compile(r"\b[A-CEGHJ-PR-TW-Za-ceghj-pr-tw-z][A-CEGHJ-NPR-TW-Za-ceghj-npr-tw-z] ?\d{2} ?\d{2} ?\d{2} ?[A-Da-d]\b"), ids.is_valid_nino, None),
    ("PHONE", re.compile(r"(?<![\w+])(?:(?:\+|00)44 ?\(?0?\)? ?|\(?0)\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}" + E), None, None),
    ("ADDRESS", re.compile(r"\b[A-Za-z]{1,2}\d[A-Za-z\d]? ?\d[A-Za-z]{2}\b"), None, None),  # почтовый индекс
    ("ACCOUNT", re.compile(r"(?<=sort code)[:\s]{1,3}(\d{2}-\d{2}-\d{2})\b", re.I), None, None),
    ("ACCOUNT", re.compile(r"(?:account number|account no\.?)[:\s]{1,3}(\d{8})\b", re.I), None, None),
    ("ID", re.compile(r"passport(?: number| no\.?)?[:\s]{1,3}(\d{9})\b", re.I), None, None),
    ("ID", re.compile(r"\b[A-Z9]{5}\d{6}[A-Z9]{2}\d[A-Z]{2}\b"), None, None),  # водительское удостоверение
]

# Организации.
_OPF = r"(?:ООО|ОАО|ЗАО|ПАО|АО|НАО|НКО|АНО|ТОО|ФГУП|ГУП|МУП|ГБУЗ|ГАУЗ|ГБУ|ГКУ|ФГБУ|МБУ|МАУ)"
RU_ORG = [
    re.compile(_OPF + r"\s*«[^»\n]{1,80}»"),
    re.compile(_OPF + r"\s*\"[^\"\n]{1,80}\""),
    re.compile(r"\b" + _OPF + r"[ \t]+[А-ЯЁ][\w-]{1,40}(?:[ \t]+[А-ЯЁ][\w-]{1,40}){0,2}"),
]
UK_ORG = [
    re.compile(
        r"\b(?!(?:Employer|Dear|Signed|Re|The|Our|Your|To|From|By|At|For)\b)"
        r"(?:[A-Z][\w&'’-]{0,40}(?:,? (?:and |& )?)){1,4}(?:Ltd|Limited|LLP|PLC|plc|Inc|Group|Partners|Associates)\b\.?"
    ),
    re.compile(r"\b[A-Z][A-Z&'’-]{1,40}(?: [A-Z&'’-]{1,40}){0,4} (?:LIMITED|LTD|LLP|PLC)\b"),
    # британские фирмы вида «Wright, Middleton and Francis»
    re.compile(r"\b[A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})?, [A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})? (?:and|&) [A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})?\b"),
]

# Имя индивидуального предпринимателя: это человек, а не организация.
_RU_WORD = r"[А-ЯЁ][а-яё]{1,30}(?:-[А-ЯЁ][а-яё]{1,30})?"
RU_IP = re.compile(r"\bИП[ \t]+(" + _RU_WORD + r"(?:[ \t]+(?:[А-ЯЁ]\.[ \t]?[А-ЯЁ]\.|" + _RU_WORD + r")){0,2})")
# Имя после обращения, в том числе с инициалами: «Mr John Smith», «Dr A Patel», «Mr J. Smith».
TITLED = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Sir|Lady|Prof)\.?[ \t]+((?:[A-Z]\.?[ \t]{0,2}){0,3}[A-Z][\w'’-]{1,40}(?:[ \t]+[A-Z][\w'’-]{1,40}){0,2})"
)
# Паспорт РФ, записанный раздельно: «серия 45 10 номер 123456», «серии 4510 № 123456».
RU_PASSPORT_SPLIT = re.compile(r"сери[яи][:\s]{1,3}(\d{2} ?\d{2})[,\s]{1,3}(?:номер|№)[:\s]{1,3}(\d{6})\b", re.I)

# Дата рождения по контексту.
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
_DATE = (
    r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}(?:st|nd|rd|th)? " + _MONTHS + r",? \d{4}|" + _MONTHS + r" \d{1,2}(?:st|nd|rd|th)?,? \d{4}"
    r"|«?\d{1,2}»? [а-я]{3,8} \d{4}(?: г\.)?)"
)
DOB = [
    re.compile(
        r"(?:рождения|родил(?:ся|ась)|\bд\.\s?р\.|\bДР\b|\bр\.|born|\bDOB\b|D\.O\.B\.?|date of birth|birth ?date)[:\s,]{0,4}(?:on\s+)?(" + _DATE + ")",
        re.I,
    ),
    re.compile("(" + _DATE + r")\s{0,2}(?:г\.\s?р\.|года рождения)"),
]

# Длинная последовательность цифр с любыми разделителями: в документах это почти всегда
# идентификатор, даже если контрольная сумма не сходится (опечатка) или разделители точки.
LONG_NUMBER = re.compile(r"(?<![\w.])\d(?:[ .\-]?\d){8,24}(?![\w])")
# Номер, записанный словами: не меньше шести цифр подряд словами.
_RU_DIGITS = r"(?:ноль|нуль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять)"
_EN_DIGITS = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
WORD_NUMBER = {
    "ru": re.compile(r"\b" + _RU_DIGITS + r"(?:[\s,.\-]{1,4}" + _RU_DIGITS + r"){5,24}\b", re.I),
    "uk": re.compile(r"\b" + _EN_DIGITS + r"(?:[\s,.\-]{1,4}" + _EN_DIGITS + r"){5,24}\b", re.I),
}
UK_IBAN_LOOSE = re.compile(r"\bGB\d{2}[ .]?[A-Z]{4}(?:[ .]?\d{4}){3}[ .]?\d{2}\b", re.I)
NINO_LOOSE = re.compile(r"\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][ .]?\d{2}[ .]?\d{2}[ .]?\d{2}[ .]?[A-D]\b", re.I)

_PASSPORT_CTX = re.compile(r"паспорт|серия|сер\.|№", re.I)
_INN_CTX = re.compile(r"ИНН|налогоплательщик", re.I)


def find(text: str, lang: str) -> list[Hit]:
    hits: list[Hit] = []
    taken: list[tuple[int, int]] = []
    for etype, rx, valid, ctx in COMMON + (RU if lang == "ru" else UK):
        for m in rx.finditer(text):
            s, e = m.span(1) if m.groups() and m.group(1) else m.span()
            if any(s < te and ts < e for ts, te in taken):
                continue
            v = text[s:e]
            left = text[max(0, s - 40) : s]
            if ctx is not None and valid is None and not ctx.search(left):
                continue  # шаблон без проверки суммы работает только при подсказке рядом
            if valid and not valid(v) and not (ctx and ctx.search(left)):
                continue
            if etype == "INN" and len(re.sub(r"\D", "", v)) == 10 and _PASSPORT_CTX.search(left) and not _INN_CTX.search(left):
                continue
            if etype == "PASSPORT_RU" and " " not in v and not _PASSPORT_CTX.search(left):
                continue
            hits.append(Hit(etype, s, e))
            taken.append((s, e))
    for rx in RU_ORG if lang == "ru" else UK_ORG:
        for m in rx.finditer(text):
            hits.append(Hit("ORG", m.start(), m.end()))
    if lang == "ru":
        for m in RU_IP.finditer(text):
            hits.append(Hit("PERSON", m.start(1), m.end(1)))
        for m in RU_PASSPORT_SPLIT.finditer(text):
            hits.append(Hit("PASSPORT_RU", m.start(1), m.end(1)))
            hits.append(Hit("PASSPORT_RU", m.start(2), m.end(2)))
    else:
        for m in TITLED.finditer(text):
            hits.append(Hit("PERSON", m.start(1), m.end(1)))
    for rx in DOB:
        for m in rx.finditer(text):
            hits.append(Hit("DATE_OF_BIRTH", m.start(1), m.end(1)))
    for m in WORD_NUMBER[lang].finditer(text):
        hits.append(Hit("ID", m.start(), m.end()))
    if lang == "uk":
        for rx, t in ((UK_IBAN_LOOSE, "IBAN"), (NINO_LOOSE, "NINO")):
            for m in rx.finditer(text):
                hits.append(Hit(t, m.start(), m.end()))
    for m in LONG_NUMBER.finditer(text):
        if not any(h.start <= m.start() and m.end() <= h.end for h in hits):
            hits.append(Hit("ID", m.start(), m.end()))
    return hits
