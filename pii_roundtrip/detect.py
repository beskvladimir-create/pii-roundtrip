"""Detection pipeline.

Spans come from detectors (pii-guard for Russian, GLiNER Guard for both languages) and
from rules. The pipeline then runs fixed stages, in this order:

1. ``clean``: drop non-personal types and well-known names, attach house numbers;
2. ``merge``: union overlapping spans, glue adjacent parts of one name or address;
3. ``extend_persons``: extend names to neighbouring capitalised words and initials;
   ``extend_addresses``: extend an address to the house, building, postcode and region
   next to it on the same line;
4. ``propagate``: find every found name, organisation and number elsewhere in the
   document and in earlier messages of the session, including Russian case forms;
5. ``attach_initials`` and a final ``merge``.

Recall is preferred over precision: overlapping spans are merged into their union.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from pii_roundtrip import lexicon, names, rules
from pii_roundtrip.langs import RU

# Which type wins when overlapping spans of different types are merged.
PRIORITY = {
    "PASSPORT_RU": 9,
    "SNILS": 9,
    "INN": 9,
    "BANK_ACCOUNT_RU": 9,
    "CARD": 9,
    "NHS": 9,
    "NINO": 9,
    "IBAN": 9,
    "EMAIL": 8,
    "PHONE": 7,
    "ID": 6,
    "ACCOUNT": 6,
    "DATE_OF_BIRTH": 6,
    "SOCIAL": 6,
    "PERSON": 5,
    "ORG": 4,
    "ADDRESS": 3,
    "DATE": 2,
}

_OPF_PROPAGATE = re.compile(r"^" + lexicon.LEGAL_FORM_RU_RE + r"\s*")


@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int
    source: str = ""


class Detector(Protocol):
    """Anything that returns spans of personal data for a text."""

    name: str
    languages: frozenset[str]

    def detect(self, text: str, lang: str) -> list[Span]: ...


class Models:
    """The default set of detectors, loaded lazily on first use.

    By default only local files are used (``offline=True``); download the models once
    with ``pii-roundtrip download-models``. ``use_pii_guard=False, use_gliner=False``
    gives a rules-only engine that needs no models.
    """

    def __init__(
        self, use_pii_guard: bool = True, use_gliner: bool = True, offline: bool = True, device: str | None = None
    ):
        self.use_pii_guard, self.use_gliner, self.offline = use_pii_guard, use_gliner, offline
        self.device = device
        self._detectors: list[Detector] | None = None
        self._lock = threading.Lock()

    @property
    def detectors(self) -> list[Detector]:
        with self._lock:
            if self._detectors is None:
                from pii_roundtrip.adapters import GlinerDetector, PiiGuardDetector

                found: list[Detector] = []
                if self.use_pii_guard:
                    found.append(PiiGuardDetector(offline=self.offline, device=self.device))
                if self.use_gliner:
                    found.append(GlinerDetector(offline=self.offline))
                self._detectors = found
        return self._detectors

    def detect(self, text: str, lang: str) -> list[Span]:
        spans: list[Span] = []
        for d in self.detectors:
            if lang in d.languages:
                spans += d.detect(text, lang)
        return spans


# ---------- propagation across the document ----------


@lru_cache(maxsize=20000)
def word_forms_ru(word: str) -> tuple[str, ...]:
    """All case forms of a word as a first name, surname or patronymic (both genders)."""
    w = names.cap(word)
    if "-" in w:  # double-barrelled surname: inflect every part in the same case and gender
        parts = w.split("-")
        out = {w}
        for case in ("nomn", "gent", "datv", "accs", "ablt", "loct"):
            for g in ("masc", "femn"):
                forms_p = []
                for part in parts:
                    p = next(
                        (q for q in names.morph().parse(part) if "Surn" in names._tags(q) or q.tag.POS == "ADJF"), None
                    )
                    f = p.inflect({case, g, "sing"}) if p else None
                    forms_p.append(names.cap(f.word) if f else part)
                out.add("-".join(forms_p))
        return tuple(out)
    forms = {w}
    for p in names.morph().parse(w)[:4]:
        tags = names._tags(p)
        if not ({"Name", "Surn", "Patr"} & tags) and p.tag.POS != "NOUN":
            continue
        for lex in p.lexeme:
            if lex.tag.number == "plur":
                continue
            forms.add(names.cap(lex.word))
    return tuple(f for f in forms if len(f) >= 2)


def clear_caches() -> None:
    """Drop cached word forms. The cache holds names from processed documents; a
    long-running service may call this between unrelated documents."""
    word_forms_ru.cache_clear()


def _needle_regex(value: str) -> re.Pattern:
    """A pattern for a value that tolerates ё/е, apostrophe variants and case."""
    parts = []
    for ch in value:
        low = ch.lower()
        if low in "её":
            parts.append("[её]" if ch.islower() else "[ЕЁ]")
        elif ch in "'’":
            parts.append("['’]")
        elif ch == "-":
            parts.append("[-‐]")
        elif ch.isspace():
            parts.append(r"\s+")
        else:
            parts.append(re.escape(ch))
    return re.compile(r"(?<![\w])" + "".join(parts) + r"(?![\w])", re.I)


def _name_like(match: str) -> bool:
    """A match counts as a name only if it is capitalised or all capitals."""
    return match[:1].isupper()


def propagate(text: str, spans: list[Span], lang: str, known: list[tuple[str, str]] | None = None) -> list[Span]:
    """Search the whole document for every found name, organisation and number
    (case-insensitive, tolerant to ё/е and apostrophes), including Russian case forms
    and values already known from earlier messages of the session."""
    found = [(s.type, text[s.start : s.end], s.source) for s in spans]
    found += [(t, v, "known") for t, v in (known or [])]
    needles: dict[str, set[str]] = {}
    for t, v, source in found:
        if t == "PERSON":
            parsed = names.parse(v, lang)
            for w in re.findall(r"[\w'’-]+", v):
                low = names.norm(w)
                if (
                    len(w) < 2
                    or low in lexicon.TITLES
                    or low in lexicon.ROLES
                    or low in lexicon.ALLOW
                    or not w[:1].isupper()
                ):
                    continue
                if len(w) == 2 and source == "propagate":
                    continue
                is_first = low == parsed.first or (lang == RU and names._ru_word_role(w)[0] == "Name")
                if is_first and (
                    low in lexicon.NOT_PROPAGATED or (lang == RU and parsed.first in lexicon.NOT_PROPAGATED)
                ):
                    continue
                if lang == RU and re.match(r"[А-ЯЁ]", w):
                    needles.setdefault("PERSON", set()).update(word_forms_ru(w))
                else:
                    needles.setdefault("PERSON", set()).update({w, w + "'s", w + "s'"})
        elif t == "ORG":
            core = _OPF_PROPAGATE.sub("", v).strip("«»\"' ")
            if len(core) >= 4 and core.lower() not in lexicon.ALLOW:
                needles.setdefault("ORG", set()).add(core)
        elif PRIORITY.get(t, 0) >= 8 and len(v) >= 6:
            needles.setdefault(t, set()).add(v)
    extra: list[Span] = []
    for t, values in needles.items():
        for v in sorted(values, key=len, reverse=True):
            for m in _needle_regex(v).finditer(text):
                if t in ("PERSON", "ORG") and not _name_like(m.group()):
                    continue
                extra.append(Span(t, m.start(), m.end(), "propagate"))
    return spans + extra


_INITIALS_AFTER = re.compile(r"[ \t]{1,2}[A-ZА-ЯЁ]\.(?:[ \t]?[A-ZА-ЯЁ]\.){0,2}")
_INITIALS_BEFORE = re.compile(r"(?:[A-ZА-ЯЁ]\.[ \t]?){1,3}[ \t]?$")


def _with_initials(text: str, start: int, end: int) -> tuple[int, int]:
    m = _INITIALS_AFTER.match(text, end)
    if m:
        end = m.end()
    m = _INITIALS_BEFORE.search(text[max(0, start - 12) : start])
    if m:
        start = max(0, start - 12) + m.start()
    return start, end


def extend_persons(text: str, spans: list[Span]) -> list[Span]:
    """Extend a name to neighbouring capitalised words and initials on the same line
    ("Miss Rachael [Rowe]" -> "Rachael Rowe", "[Иванов] И.И."), at most four words.
    Titles and role words ("Mr", "Истец", "Claimant") are not included."""
    stop = lexicon.TITLES | lexicon.ROLES | lexicon.ALLOW

    def not_name(word: str) -> bool:
        # role words, well-known names and short abbreviations ("РФ", "ООО", "NHS") are not part of a name
        return names.norm(word) in stop or (len(word) <= 4 and word.isupper())

    out = []
    for s in spans:
        if s.type != "PERSON":
            out.append(s)
            continue
        start, end = s.start, s.end
        for _ in range(2):
            seg = text[max(0, start - 30) : start]
            m = re.search(r"([A-ZА-ЯЁ][\w'’-]+)[ \t]+$", seg)
            if not m or not_name(m.group(1)) or len(text[start:end].split()) >= 4:
                break
            before = seg[: m.start()]
            if not before.strip() or before.rstrip().endswith((".", "!", "?", ":", "\n")):
                break  # start of a line or sentence: a capital letter does not mean a name
            start = max(0, start - 30) + m.start(1)
        for _ in range(2):
            m = re.match(r"[ \t]+([A-ZА-ЯЁ][\w'’-]+)", text[end : end + 30])
            if not m or not_name(m.group(1)) or len(text[start:end].split()) >= 4:
                break
            end += m.end(1)
        start, end = _with_initials(text, start, end)
        out.append(Span(s.type, start, end, s.source))
    return out


_UK_POSTCODE = r"[A-Z]{1,2}\d[A-Z\d]?[ \t]?\d[A-Z]{2}\b"
_CAP_WORDS_EN = r"(?:[A-Z][\w'’-]+[ \t]+){0,2}[A-Z][\w'’-]+"
# Parts of an address that follow the found part on the same line.
_ADDRESS_TAIL = re.compile(
    r"(?:[ \t]*\([А-ЯЁа-яё][а-яё]{1,12}\.?\)"  # region or note in brackets: "(Томск.)", "(метеост.)"
    r"|[ \t]*,?[ \t]*(?:д|дом|к|корп|стр|кв|оф|пом)\.?[ \t]*\d[\w/-]*"  # house, building, flat
    # a street, also one named with a number: ", ш. 9 Января", ", алл. Марта 8"
    r"|[ \t]*,[ \t]*(?:ул|ш|пер|пр|просп|бул|алл|наб|пл|туп|проезд|мкр)\.[ \t]*(?:\d{1,2}[ \t]+)?"
    r"[А-ЯЁа-яё][\w.-]*(?:[ \t]+\d{1,2}(?=[ \t]*,))?"
    r"|[ \t]*,[ \t]*\d{6}(?!\d)"  # Russian postcode
    r"|[ \t]*,?[ \t]*" + _UK_POSTCODE + r""  # UK postcode
    # the UK town between the street and the postcode: ", West Mathewhaven B7 9LL"
    r"|[ \t]*,[ \t]*" + _CAP_WORDS_EN + r"(?=[ \t]*,?[ \t]*" + _UK_POSTCODE + r"))"
)
# The number of a house or building cut off after its abbreviation: "д. 486 к." + " 50".
_ADDRESS_ABBR_END = re.compile(r"(?<![\w])(?:д|дом|к|корп|стр|кв|оф|пом)\.?$")
_ADDRESS_ABBR_NUMBER = re.compile(r"\.?[ \t]*\d[\w/-]*")
# A street named with a number after the word, cut off before the number: "алл. Марта" + " 8".
_ADDRESS_STREET_END = re.compile(
    r"(?<![\w])(?:ул|ш|пер|пр|просп|бул|алл|наб|пл|туп|проезд|мкр)\.[ \t]*[А-ЯЁа-яё][\w.-]*$"
)
_ADDRESS_STREET_NUMBER = re.compile(r"[ \t]+\d{1,2}(?=[ \t]*,)")
# A UK house number and street before the found town: "4 Conor Motorway, [Julialand]".
_ADDRESS_HEAD_EN = re.compile(r"(?<![\w])\d{1,5}[A-Za-z]?[ \t]+(?:[A-Z][\w'’-]+[ \t]+){0,3}[A-Z][\w'’-]+,[ \t]*$")
# A UK house number, street and town before the found postcode: "45 Harding Dam, West Mathewhaven [B7 9LL]".
_ADDRESS_HEAD_EN_TOWN = re.compile(
    r"(?<![\w])\d{1,5}[A-Za-z]?[ \t]+(?:[A-Z][\w'’-]+[ \t]+){0,3}[A-Z][\w'’-]+,[ \t]*" + _CAP_WORDS_EN + r",?[ \t]*$"
)


def extend_addresses(text: str, spans: list[Span], lang: str) -> list[Span]:
    """Extend an address to the parts next to it on the same line that detectors often miss."""
    out = []
    for s in spans:
        if s.type == "ADDRESS":
            start, end = s.start, s.end
            while True:
                if _ADDRESS_ABBR_END.search(text[start:end]) and (m := _ADDRESS_ABBR_NUMBER.match(text, end)):
                    end = m.end()
                    continue
                if _ADDRESS_STREET_END.search(text[start:end]) and (m := _ADDRESS_STREET_NUMBER.match(text, end)):
                    end = m.end()
                    continue
                if m := _ADDRESS_TAIL.match(text, end):
                    end = m.end()
                    continue
                break
            if lang != RU:
                line_start = text.rfind("\n", 0, start) + 1
                head = text[line_start:start]
                m = _ADDRESS_HEAD_EN.search(head) or _ADDRESS_HEAD_EN_TOWN.search(head)
                if m:
                    start = line_start + m.start()
            s = Span(s.type, start, end, s.source)
        out.append(s)
    return out


# A generic word before an organisation's name: "Компания Адамас".
_ORG_HEAD_RU = re.compile(r"(?<![\w-])(?:Компания|Компании|Компанию|Компанией|Фирма|Фирмы|Группа компаний)[ \t]+$")
# A name given in brackets after the organisation: "Hoff (Домашний интерьер)"; not "(далее Исполнитель)".
_ORG_BRACKET = re.compile(r"[ \t]*\(([A-ZА-ЯЁ][^()\n\d]{1,40})\)")
# "ГКНПЦ им. М.В.Хруничева", "Лобанова и партнеры"
_ORG_TAIL_RU = re.compile(r"[ \t]+им\.[ \t]*(?:[А-ЯЁ]\.[ \t]?){0,3}[А-ЯЁ][\w-]+" r"|[ \t]+(?:и|&)[ \t]+[Пп]артн[её]ры")


def extend_orgs(text: str, spans: list[Span], lang: str) -> list[Span]:
    """Extend an organisation to the parts of its name next to it that detectors often miss."""
    if lang != RU:
        return spans
    out = []
    for s in spans:
        if s.type in ("ORG", "PERSON"):
            start, end, etype = s.start, s.end, s.type
            m = _ORG_TAIL_RU.match(text, end)
            if m and (etype == "ORG" or "артн" in m.group()):
                end, etype = m.end(), "ORG"
            if etype == "ORG":
                m = _ORG_HEAD_RU.search(text[max(0, start - 25) : start])
                if m:
                    start = max(0, start - 25) + m.start()
                m = _ORG_BRACKET.match(text, end)
                if m and names.norm(m.group(1).split()[0].strip(".,")) not in lexicon.ROLES | {"далее"}:
                    end = m.end()
            s = Span(etype, start, end, s.source)
        out.append(s)
    return out


def attach_initials(text: str, spans: list[Span]) -> list[Span]:
    """Initials next to a name are masked with it: "[Иванов] Н.А.", "А.Б. [Петров]"."""
    out = []
    for s in spans:
        if s.type == "PERSON":
            start, end = _with_initials(text, s.start, s.end)
            s = Span(s.type, start, end, s.source)
        out.append(s)
    return out


_NUMBER_TYPES = {
    "ID",
    "ACCOUNT",
    "CARD",
    "PHONE",
    "PASSPORT_RU",
    "SNILS",
    "INN",
    "BANK_ACCOUNT_RU",
    "NHS",
    "NINO",
    "IBAN",
}


@lru_cache(maxsize=20000)
def _dictionary_word_ru(word: str) -> bool:
    """A known Russian word that is not a first name, surname or patronymic."""
    parses = names.morph().parse(word)
    if not parses or not parses[0].is_known:
        return False
    return not any({"Name", "Surn", "Patr"} & names._tags(p) for p in parses)


def _plausible(etype: str, v: str) -> bool:
    """Reject model spans that cannot be what their type says: a number without digits
    ("паспорт", "CVC"), an organisation of ordinary lower-case words ("налоговой",
    "нашей компании"), a one-word lower-case "name" that is an ordinary word or not a word
    at all ("плз"). Rule spans, including numbers written in words, are not checked here."""
    if etype in _NUMBER_TYPES:
        return any(c.isdigit() for c in v)
    words = re.findall(r"[^\W\d_]+", v)
    if not words or any(w[:1].isupper() for w in words):
        return True
    if etype == "ORG":
        return not all(re.fullmatch(r"[а-яё]+", w) and _dictionary_word_ru(w) for w in words)
    if etype == "PERSON" and len(words) == 1:
        w = words[0]
        if re.fullmatch(r"[а-яё]+", w):
            parses = names.morph().parse(w)
            return any({"Name", "Surn", "Patr"} & names._tags(p) for p in parses)
    return True


def clean(text: str, spans: list[Span], mask_dates: bool) -> list[Span]:
    """Drop bank codes, document dates (unless ``mask_dates``) and well-known names;
    drop letter-only address fragments; attach a house number to the street after it."""
    out = []
    for s in spans:
        if s.type == "BIK" or (s.type == "DATE" and not mask_dates):
            continue
        v = " ".join(text[s.start : s.end].strip(' .,«»"').split())
        if v.lower() in lexicon.ALLOW and PRIORITY.get(s.type, 0) < 8:
            continue
        if PRIORITY.get(s.type, 0) < 8 and rules.registry_number(text, s.start, s.end):
            continue
        if s.source != "rules" and not _plausible(s.type, v):
            continue
        if s.type == "ADDRESS":
            if s.end - s.start < 3 and not any(c.isdigit() for c in v):
                continue  # a letter fragment such as "NI"; a house number such as "34" is kept
            seg = text[max(0, s.start - 8) : s.start]
            m = re.search(r"(?<![\w])\d{1,5}[A-Za-zА-Яа-я]?\s+$", seg)  # "12 Baker Street"
            if m:
                s = Span(s.type, s.start - (len(seg) - m.start()), s.end, s.source)
        out.append(s)
    return out


def _stronger(a: Span, b: Span) -> Span:
    pa, pb = PRIORITY.get(a.type, 1), PRIORITY.get(b.type, 1)
    # the same text found by a rule and by a model as a weaker generic type: the rule's type wins
    # (a UK postcode found by the rule is an address even if GLiNER calls it an ID)
    if (a.start, a.end) == (b.start, b.end) and max(pa, pb) < 8 and (a.source == "rules") != (b.source == "rules"):
        return a if a.source == "rules" else b
    if pa != pb:
        return a if pa > pb else b
    return b if b.source == "rules" and a.source != "rules" else a  # a checksum rule beats a model


def merge(spans: list[Span], text: str = "") -> list[Span]:
    """Merge overlapping spans into their union, typed by the stronger span; glue
    adjacent parts of one name or address on the same line."""
    spans = sorted((s for s in spans if s.end > s.start), key=lambda s: (s.start, -s.end))
    out: list[Span] = []
    for s in spans:
        if out and s.start < out[-1].end:
            last = out[-1]
            w = _stronger(last, s)
            # a name inside an address or an organisation ("475 Michelle Lodge", "Лобанова и
            # партнеры") does not turn the whole address or organisation into a person
            if last.type in ("ADDRESS", "ORG") and s.type == "PERSON" and s.end <= last.end:
                w = last
            elif s.type in ("ADDRESS", "ORG") and last.type == "PERSON" and s.start <= last.start and s.end >= last.end:
                w = s
            out[-1] = Span(w.type, last.start, max(last.end, s.end), w.source)
            continue
        if out and text and out[-1].type == s.type and s.type in ("PERSON", "ADDRESS"):
            gap = text[out[-1].end : s.start]
            if (s.type == "PERSON" and gap.strip() == "" and "\n" not in gap) or (
                s.type == "ADDRESS" and gap.strip(" ,") == "" and "\n" not in gap
            ):
                out[-1] = Span(s.type, out[-1].start, s.end, out[-1].source)
                continue
        out.append(s)
    return out


def _inside(text: str, s: Span) -> Span | None:
    """A detector span limited to the text and without surrounding whitespace, whatever the model returned."""
    start, end = max(0, s.start), min(len(text), s.end)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return Span(s.type, start, end, s.source) if start < end else None


def _split_lines(text: str, spans: list[Span]) -> list[Span]:
    """A name from a detector never continues on the next line: a span such as "А.Ф. Рыбакову\n\n
    Уважаемый Аверкий Фомич" is split into its lines, which are then treated as separate mentions."""
    out = []
    for s in spans:
        if s.type == "PERSON" and "\n" in text[max(0, s.start) : s.end]:
            pos = max(0, s.start)
            for part in text[pos : s.end].split("\n"):
                if part.strip():
                    out.append(Span(s.type, pos, pos + len(part), s.source))
                pos += len(part) + 1
        else:
            out.append(s)
    return out


def detect(
    text: str, lang: str, models: Models, known: list[tuple[str, str]] | None = None, mask_dates: bool = False
) -> list[Span]:
    """Run detectors and rules, then the pipeline stages described in the module docstring."""
    spans = [s for s in (_inside(text, s) for s in _split_lines(text, models.detect(text, lang))) if s]
    spans += [Span(h.type, h.start, h.end, "rules") for h in rules.find(text, lang)]
    spans = merge(clean(text, spans, mask_dates), text)
    spans = merge(extend_orgs(text, extend_addresses(text, extend_persons(text, spans), lang), lang), text)
    spans = propagate(text, spans, lang, known)
    return merge(attach_initials(text, merge(spans, text)), text)
