"""Rules: identifiers with checksums and patterns that models miss.

Rules are the safety net when a model misses something. An identifier whose checksum
fails (a typo) is still masked when a hint word is nearby ("карта", "СНИЛС", "NHS").
Every pattern is length-bounded, without nested unbounded repetition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pii_roundtrip import checksums as ids
from pii_roundtrip.langs import EN_GB, RU
from pii_roundtrip.lexicon import LEGAL_FORM_RU_RE


@dataclass(frozen=True)
class Hit:
    type: str
    start: int
    end: int
    source: str = "rules"


D, E = r"(?<![\w])", r"(?![\w])"
SEP = r"[ \-]?"

# (type, pattern, validator, hint context that allows masking even without a valid checksum)
COMMON = [
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}"), None, None),
    (
        "CARD",
        re.compile(D + r"\d{4}" + SEP + r"\d{4}" + SEP + r"\d{4}" + SEP + r"\d{4}(?:" + SEP + r"\d{3})?" + E),
        ids.is_valid_card,
        re.compile(r"карт|card|visa|mastercard|мир\b", re.I),
    ),
    ("CARD", re.compile(D + r"3[47]\d{2}[ -]?\d{6}[ -]?\d{5}" + E), ids.is_valid_card, None),  # Amex 15
    (
        "IBAN",
        re.compile(r"\b[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]{4}){3,7}(?: ?[A-Za-z0-9]{1,3})?\b"),
        ids.is_valid_iban,
        re.compile(r"iban", re.I),
    ),
    ("SOCIAL", re.compile(r"(?<![\w.@])@[A-Za-z][\w]{4,31}\b"), None, None),
    (
        "PHONE",
        re.compile(
            r"(?<![\w+])(?:\+|00)(?!7\b|44\b)\d{1,3}[ (-]{0,2}\d{2,4}[ )-]{0,2}\d{2,4}[ -]?\d{2,4}(?:[ -]?\d{1,4})?" + E
        ),
        None,
        None,
    ),
]

RU_RULES = [
    (
        "SNILS",
        re.compile(D + r"\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{2}" + E),
        ids.is_valid_snils,
        re.compile(r"снилс|страхов", re.I),
    ),
    ("BANK_ACCOUNT_RU", re.compile(D + r"(?:[34]\d{19}|[34]\d{4}(?: \d{5}){3})" + E), None, None),
    ("INN", re.compile(D + r"(?:\d{12}|\d{10})" + E), ids.is_valid_inn, re.compile(r"\bинн\b", re.I)),
    ("ID", re.compile(D + r"\d{15}" + E), None, re.compile(r"огрнип|огрн", re.I)),
    ("ID", re.compile(D + r"\d{13}" + E), None, re.compile(r"огрн", re.I)),
    ("ID", re.compile(D + r"\d{16}" + E), None, re.compile(r"полис|омс", re.I)),
    ("PASSPORT_RU", re.compile(D + r"\d{2} ?\d{2}(?: ?№)? ?\d{6}" + E), None, None),
    (
        "PHONE",
        re.compile(r"(?<![\w+])(?:\+7|8|7)[\s(-]{0,2}\d{3}[\s)-]{0,2}\d{3}[\s-]?\d{2}[\s-]?\d{2}" + E),
        None,
        None,
    ),
]

UK = [
    ("NHS", re.compile(D + r"\d{3}[ -]?\d{3}[ -]?\d{4}" + E), ids.is_valid_nhs, re.compile(r"\bnhs\b", re.I)),
    (
        "NINO",
        re.compile(
            r"\b[A-CEGHJ-PR-TW-Za-ceghj-pr-tw-z][A-CEGHJ-NPR-TW-Za-ceghj-npr-tw-z] ?\d{2} ?\d{2} ?\d{2} ?[A-Da-d]\b"
        ),
        ids.is_valid_nino,
        None,
    ),
    (
        "PHONE",
        re.compile(r"(?<![\w+])(?:(?:\+|00)44 ?\(?0?\)? ?|\(?0)\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}" + E),
        None,
        None,
    ),
    ("ADDRESS", re.compile(r"\b[A-Za-z]{1,2}\d[A-Za-z\d]? ?\d[A-Za-z]{2}\b"), None, None),  # postcode
    ("ACCOUNT", re.compile(r"(?<=sort code)[:\s]{1,3}(\d{2}-\d{2}-\d{2})\b", re.I), None, None),
    ("ACCOUNT", re.compile(r"(?:account number|account no\.?)[:\s]{1,3}(\d{8})\b", re.I), None, None),
    ("ID", re.compile(r"passport(?: number| no\.?)?[:\s]{1,3}(\d{9})\b", re.I), None, None),
    ("ID", re.compile(r"\b[A-Z9]{5}\d{6}[A-Z9]{2}\d[A-Z]{2}\b"), None, None),  # driving licence
]

# Organisations.
_OPF = LEGAL_FORM_RU_RE
RU_ORG = [
    re.compile(_OPF + r"\s*«[^»\n]{1,80}»"),
    re.compile(r"(?<![\w-])ИП\s*«[^»\n]{1,80}»"),  # a trade name of a sole proprietor
    re.compile(_OPF + r"\s*\"[^\"\n]{1,80}\""),
    re.compile(_OPF + r"[ \t]+[А-ЯЁ][\w-]{1,40}(?:[ \t]+[А-ЯЁ][\w-]{1,40}){0,2}"),
]
UK_ORG = [
    re.compile(
        r"\b(?!(?:Employer|Dear|Signed|Re|The|Our|Your|To|From|By|At|For)\b)"
        r"(?:[A-Z][\w&'’-]{0,40}(?:,? (?:and |& )?)){1,4}(?:Ltd|Limited|LLP|LLC|PLC|plc|Inc|Group|Partners|Associates)\b\.?"
    ),
    re.compile(r"\b[A-Z][A-Z&'’-]{1,40}(?: [A-Z&'’-]{1,40}){0,4} (?:LIMITED|LTD|LLP|PLC)\b"),
    # family firms: "Lewis and Sons", "Hale & Co"
    re.compile(r"\b[A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})? (?:and|&) (?:Sons|Daughters|Co)\b\.?"),
    # UK firm names such as "Wright, Middleton and Francis"
    re.compile(
        r"\b[A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})?, [A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})? (?:and|&) [A-Z][a-z'’-]{1,30}(?:-[A-Z][a-z'’-]{1,30})?\b"
    ),
]

# A sole proprietor (ИП) is a person, not an organisation.
_RU_WORD = r"[А-ЯЁ][а-яё]{1,30}(?:-[А-ЯЁ][а-яё]{1,30})?"
RU_IP = re.compile(r"\bИП[ \t]+(" + _RU_WORD + r"(?:[ \t]+(?:[А-ЯЁ]\.[ \t]?[А-ЯЁ]\.|" + _RU_WORD + r")){0,2})")
# A name after a title, including initials: "Mr John Smith", "Dr A Patel", "Mr J. Smith".
_EN_WORD = r"(?:[A-Z][\w'’-]{1,40}|[a-z][A-Z][a-z'’-]{1,40})"  # also a typo that swaps the first two letters
TITLED = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Sir|Lady|Prof)\.?[ \t]+((?:[A-Z]\.?[ \t]{0,2}){0,3}"
    + _EN_WORD
    + r"(?:[ \t]+"
    + _EN_WORD
    + r"){0,2})"
)
# Initials next to a capitalised word are a person even when the surname has a typo
# ("А.О. Нкионовой", "Петров И.И.", "V. Rcie", "L. Talyor").
RU_INITIALS_NAME = re.compile(
    r"(?<![\w.])(?:[А-ЯЁ]\.[ \t]?[А-ЯЁ]\.[ \t]?" + _RU_WORD + r"|" + _RU_WORD + r"[ \t]+[А-ЯЁ]\.[ \t]?[А-ЯЁ]\.)(?![\w])"
)
EN_INITIALS_NAME = re.compile(
    r"(?<![\w.])(?:[A-Z]\.[ \t]?){1,2}((?:[A-Z][a-z'’]{1,30}|[a-z][A-Z][a-z'’]{1,30})(?:-[A-Z][a-z'’]{1,30})?)(?![\w])"
)
# A person named by context: "chaired by Leon Ford", "point of contact is Glen Bailey",
# "site passes for Glen Wright and Owen Cook", and list entries "Colin Llody, born 26/07/1965".
_EN_FULL_NAME = r"[A-Z][a-z'’-]{1,30}(?:[ \t]+[A-Z][a-z'’-]{1,30}){1,2}"
EN_CONTEXT_NAME = re.compile(
    r"(?:\b(?:chaired|signed|prepared|approved|witnessed|countersigned|reviewed) by|\bcontact is|\bpasses for|\bpass for)[ \t]+"
    r"(" + _EN_FULL_NAME + r")(?:[ \t]+and[ \t]+(" + _EN_FULL_NAME + r"))?"
)
EN_BORN_NAME = re.compile(r"(?m)^(?:[ \t]*\d{1,3}\.)?[ \t]*(" + _EN_FULL_NAME + r"),[ \t]+born\b")
# The organisation on the line under the addressee in a UK letter: "Mr Ross Harvey\nThomas and Sons\n72 Brown Manor".
EN_ADDRESSEE_ORG = re.compile(
    r"(?m)^(?:Mr|Mrs|Ms|Miss|Dr|Sir|Lady|Prof)\.?[ \t]+[^\n]{2,60}\n([A-Z][\w'’&-]*(?:[ \t]+(?:[A-Z][\w'’&-]*|and|&|of))*)[ \t]*\n[ \t]*\d"
)
# A word after an initial that is not a surname: "Appendix A. The", "Plan B. Please".
_NOT_SURNAME_EN = frozenset(
    """the this that these those their there they then we our you your he she his her it its in on at
    for from to by with and or but if as of please dear yours signed sign date dated ref re see note notes
    section clause part schedule appendix annex total street road lane avenue page item no all any
    a an is are was were be been has have had will shall may must can new old same such""".split()
)
# A medical or HR record name: "LAWRENCE, Maureen" at the start of a line or after a colon.
SURNAME_FIRST_EN = re.compile(r"(?:^|(?<=:)[ \t]{0,3}|(?<=\n))([A-Z][A-Z'’-]{2,30}, [A-Z][a-z'’-]{1,30})(?![\w])", re.M)
# A firm named after partners on the first lines of a letterhead: "Adams-O'Brien".
LETTERHEAD_FIRM_EN = re.compile(r"\A\s*(?:[^\n]*\n\s*)?([A-Z][a-z'’]+(?:-[A-Z][A-Za-z'’]+)+)[ \t]*$", re.M)
# The addressee organisation in a Russian business letter: the line after "Генеральному директору"
# (unless it is a person with initials), and "работает в ... в должности".
RU_ADDRESSEE_ORG = re.compile(
    r"(?m)^(?:Генеральному директору|Исполнительному директору|Директору|Руководителю|Председателю правления|"
    r"Председателю|Начальнику|Управляющему)(?:[ \t]*\n[ \t]*|[ \t]+)([^\n]{3,80}?)[ \t]*$"
)
# The organisation heading an order: "СК Согласие\n\nПРИКАЗ № 359-к".
RU_ORDER_HEAD_ORG = re.compile(r"\A[ \t]*([^\n]{2,80}?)[ \t]*\n\s*(?:ПРИКАЗ|РАСПОРЯЖЕНИЕ|ПОСТАНОВЛЕНИЕ)\b")
RU_WORKPLACE_ORG = re.compile(r"\bработа(?:ет|л|ла)[ \t]+в[ \t]+([А-ЯЁ«\"][^\n,.;]{2,60}?)[ \t]+в[ \t]+должности\b")

# A Russian passport written in two parts: "серия 45 10 номер 123456", "серии 4510 № 123456".
RU_PASSPORT_SPLIT = re.compile(r"сери[яи][:\s]{1,3}(\d{2} ?\d{2})[,\s]{1,3}(?:номер|№)[:\s]{1,3}(\d{6})\b", re.I)

# Date of birth, recognised by context.
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
_DATE = (
    r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}(?:st|nd|rd|th)? " + _MONTHS + r",? \d{4}|" + _MONTHS + r" \d{1,2}(?:st|nd|rd|th)?,? \d{4}"
    r"|«?\d{1,2}»? [а-я]{3,8} \d{4}(?: г\.)?)"
)
DOB = [
    re.compile(
        r"(?:рождения|родил(?:ся|ась)|\bд\.\s?р\.|\bДР\b|\bр\.|born|\bDOB\b|D\.O\.B\.?|date of birth|birth ?date)[:\s,]{0,4}(?:on\s+)?("
        + _DATE
        + ")",
        re.I,
    ),
    re.compile("(" + _DATE + r")\s{0,2}(?:г\.\s?р\.|года рождения)"),
]

# A long digit sequence with any separators is almost always an identifier in documents,
# even when its checksum fails (a typo) or it is written with dots.
LONG_NUMBER = re.compile(r"(?<![\w.])\d(?:[ .\-]?\d){8,24}(?![\w])")
# An identifier written in words: at least six digits in a row.
_RU_DIGITS = r"(?:ноль|нуль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять)"
_EN_DIGITS = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
WORD_NUMBER = {
    RU: re.compile(r"\b" + _RU_DIGITS + r"(?:[\s,.\-]{1,4}" + _RU_DIGITS + r"){5,24}\b", re.I),
    EN_GB: re.compile(r"\b" + _EN_DIGITS + r"(?:[\s,.\-]{1,4}" + _EN_DIGITS + r"){5,24}\b", re.I),
}
UK_IBAN_LOOSE = re.compile(r"\bGB\d{2}[ .]?[A-Z]{4}(?:[ .]?\d{4}){3}[ .]?\d{2}\b", re.I)
NINO_LOOSE = re.compile(r"\b[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][ .]?\d{2}[ .]?\d{2}[ .]?\d{2}[ .]?[A-D]\b", re.I)

_PASSPORT_CTX = re.compile(r"паспорт|серия|сер\.|№", re.I)
_INN_CTX = re.compile(r"ИНН|налогоплательщик", re.I)


# Numbers of banks and companies in public registers are not personal data:
# a bank code (БИК) and a Companies House number.
_REGISTRY_CTX = re.compile(
    r"(?:\bБИК|company (?:number|no\.?|registration number)|registered in [A-Za-z ]{3,30}? no\.?)[:\s]*$", re.I
)


def registry_number(text: str, start: int, end: int) -> bool:
    """True if text[start:end] is a bare number right after a bank-code or company-number label."""
    return bool(re.fullmatch(r"[\d ]{6,12}", text[start:end])) and bool(
        _REGISTRY_CTX.search(text[max(0, start - 40) : start])
    )


def find(text: str, lang: str) -> list[Hit]:
    """All rule hits in ``text``; ``lang`` is "ru" or "en-GB"."""
    hits: list[Hit] = []
    taken: list[tuple[int, int]] = []
    for etype, rx, valid, ctx in COMMON + (RU_RULES if lang == RU else UK):
        for m in rx.finditer(text):
            s, e = m.span(1) if m.groups() and m.group(1) else m.span()
            if any(s < te and ts < e for ts, te in taken):
                continue
            v = text[s:e]
            left = text[max(0, s - 40) : s]
            if ctx is not None and valid is None and not ctx.search(left):
                continue  # a pattern without a checksum is used only with a hint word nearby
            if valid and not valid(v) and not (ctx and ctx.search(left)):
                continue
            if (
                etype == "INN"
                and len(re.sub(r"\D", "", v)) == 10
                and _PASSPORT_CTX.search(left)
                and not _INN_CTX.search(left)
            ):
                continue
            if etype == "PASSPORT_RU" and " " not in v and not _PASSPORT_CTX.search(left):
                continue
            hits.append(Hit(etype, s, e))
            taken.append((s, e))
    for rx in RU_ORG if lang == RU else UK_ORG:
        for m in rx.finditer(text):
            hits.append(Hit("ORG", m.start(), m.end()))
    if lang == RU:
        for m in RU_IP.finditer(text):
            hits.append(Hit("PERSON", m.start(1), m.end(1)))
        for m in RU_INITIALS_NAME.finditer(text):
            hits.append(Hit("PERSON", m.start(), m.end()))
        for m in RU_ADDRESSEE_ORG.finditer(text):
            if not re.search(r"[А-ЯЁ]\.", m.group(1)):
                hits.append(Hit("ORG", m.start(1), m.end(1)))
        for m in RU_WORKPLACE_ORG.finditer(text):
            hits.append(Hit("ORG", m.start(1), m.end(1)))
        head_ru = RU_ORDER_HEAD_ORG.search(text)
        if head_ru and not re.search(r"\d|[А-ЯЁ]\.", head_ru.group(1)):
            hits.append(Hit("ORG", head_ru.start(1), head_ru.end(1)))
        for m in RU_PASSPORT_SPLIT.finditer(text):
            hits.append(Hit("PASSPORT_RU", m.start(1), m.end(1)))
            hits.append(Hit("PASSPORT_RU", m.start(2), m.end(2)))
    else:
        for m in TITLED.finditer(text):
            hits.append(Hit("PERSON", m.start(1), m.end(1)))
        for m in EN_INITIALS_NAME.finditer(text):
            if m.group(1).lower() not in _NOT_SURNAME_EN:
                hits.append(Hit("PERSON", m.start(), m.end()))
        for m in SURNAME_FIRST_EN.finditer(text):
            if m.group(1).split(", ")[1].lower() not in _NOT_SURNAME_EN:
                hits.append(Hit("PERSON", m.start(1), m.end(1)))
        head = LETTERHEAD_FIRM_EN.search(text)
        if head:
            hits.append(Hit("ORG", head.start(1), head.end(1)))
        for m in EN_CONTEXT_NAME.finditer(text):
            for g in (1, 2):
                if m.group(g):
                    hits.append(Hit("PERSON", m.start(g), m.end(g)))
        for m in EN_BORN_NAME.finditer(text):
            hits.append(Hit("PERSON", m.start(1), m.end(1)))
        for m in EN_ADDRESSEE_ORG.finditer(text):
            if m.group(1).lower() not in _NOT_SURNAME_EN:
                hits.append(Hit("ORG", m.start(1), m.end(1)))
    for rx in DOB:
        for m in rx.finditer(text):
            hits.append(Hit("DATE_OF_BIRTH", m.start(1), m.end(1)))
    for m in WORD_NUMBER[lang].finditer(text):
        hits.append(Hit("ID", m.start(), m.end()))
    if lang == EN_GB:
        for rx, t in ((UK_IBAN_LOOSE, "IBAN"), (NINO_LOOSE, "NINO")):
            for m in rx.finditer(text):
                hits.append(Hit(t, m.start(), m.end()))
    for m in LONG_NUMBER.finditer(text):
        if registry_number(text, m.start(), m.end()):
            continue
        if not any(h.start <= m.start() and m.end() <= h.end for h in hits):
            hits.append(Hit("ID", m.start(), m.end()))
    return hits
