"""Распознавание: модели (pii-guard для RU, GLiNER Guard для обоих языков) плюс правила,
объединение с приоритетом полноты и распространение найденного на весь документ."""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from functools import lru_cache

from pii_roundtrip import names, rules

log = logging.getLogger("pii_roundtrip")

PII_GUARD_REVISION = "c802e8cd26f85d1cf920973ea6f83965a0618d63"
GLINER_MODEL = "hivetrace/gliner-guard-omni"
GLINER_REVISION = "763f8aa9a7714dd2c3264f3751acdd5d854c5ac4"
GLINER_THRESHOLD = 0.4
GLINER_LABELS = [
    "person", "first_name", "last_name", "alias",
    "region", "city", "district", "street",
    "building", "unit", "postal_code", "address",
    "company", "government", "education", "media",
    "email", "phone", "passport", "national_id", "document_id",
    "date_of_birth", "card_number", "bank_account",
]
GLINER_MAP = {
    **{k: "PERSON" for k in ("person", "first_name", "last_name", "alias")},
    **{k: "ADDRESS" for k in ("region", "city", "district", "street", "building", "unit", "postal_code", "address")},
    **{k: "ORG" for k in ("company", "government", "education", "media")},
    "email": "EMAIL", "phone": "PHONE", "passport": "ID", "national_id": "ID", "document_id": "ID",
    "date_of_birth": "DATE_OF_BIRTH", "card_number": "CARD", "bank_account": "ACCOUNT",
}
PII_GUARD_MAP = {
    "PERSON": "PERSON", "LOCATION": "ADDRESS", "POSTAL_CODE": "ADDRESS", "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL", "INN": "INN", "SNILS": "SNILS", "PASSPORT": "PASSPORT_RU",
    "CREDIT_CARD": "CARD", "BANK_ACCOUNT": "BANK_ACCOUNT_RU", "DATE_TIME": "DATE", "OMS": "ID",
    "DRIVER_LICENSE": "ID", "MILITARY_ID": "ID", "BIRTH_CERTIFICATE": "ID", "BIK": "BIK",
    "URL": "URL", "TELEGRAM": "SOCIAL", "IP_ADDRESS": "IP", "IP_PORT": "IP",
}

# Насколько тип «сильный» при конфликте пересекающихся спанов.
PRIORITY = {
    "PASSPORT_RU": 9, "SNILS": 9, "INN": 9, "BANK_ACCOUNT_RU": 9, "CARD": 9, "NHS": 9, "NINO": 9, "IBAN": 9,
    "EMAIL": 8, "PHONE": 7, "ID": 6, "ACCOUNT": 6, "DATE_OF_BIRTH": 6, "SOCIAL": 6,
    "PERSON": 5, "ORG": 4, "ADDRESS": 3, "DATE": 2,
}

# Общеизвестные названия, которые не являются персональными данными.
ALLOW = {
    "рф", "россия", "российская федерация", "ссср",
    "nhs", "hmrc", "uk", "united kingdom", "england", "scotland", "wales", "gb", "great britain", "dvla", "nhs england",
}

# Имена (не фамилии), которые при распространении не ищутся по документу: они совпадают
# с месяцами и обычными словами («May», «Will», «Вера»). Фамилия распространяется всегда.
NOT_PROPAGATED = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "will", "bill", "mark", "grace", "hope", "faith", "rose", "joy", "dawn",
    "summer", "pat", "sue", "frank", "rich", "art", "dean", "ray", "april",
    "вера", "надежда", "любовь", "роза", "лев", "мир", "слава",
}


@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int
    source: str = ""


def _chunks(text: str, size: int = 1200, overlap: int = 200) -> list[tuple[int, str]]:
    if len(text) <= size:
        return [(0, text)]
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start + size // 2, end), text.rfind(" ", start + size // 2, end))
            end = cut if cut > start else end
        out.append((start, text[start:end]))
        if end >= len(text):
            break
        sp = text.find(" ", end - overlap, end)
        start = sp + 1 if sp != -1 else end - overlap
    return out


def _locate(fragment: str, text: str, approx: int, window: int = 400) -> int | None:
    """Находит фрагмент нормализованного текста в исходном рядом с ожидаемой позицией.
    Линейно по длине документа, в отличие от полного выравнивания строк."""
    lo = max(0, approx - window)
    hi = min(len(text), approx + window + len(fragment))
    i = text.find(fragment, lo, hi)
    if i == -1:
        i = text.lower().find(fragment.lower(), lo, hi)
    return None if i == -1 else i


def _align_local(norm: str, text: str, s: int, t: int, approx: int, pad: int = 300) -> tuple[int, int] | None:
    """Перенос спана нормализованного текста на исходный выравниванием небольшого окна
    вокруг ожидаемой позиции (не всего документа)."""
    from difflib import SequenceMatcher

    ns, ne = max(0, s - pad), min(len(norm), t + pad)
    ts, te = max(0, approx - pad), min(len(text), approx + (t - s) * 4 + pad)
    a, b = norm[ns:ne], text[ts:te]
    m = [None] * (len(a) + 1)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            m[k] = j1 + (k - i1) if tag == "equal" else j1 + ((k - i1) * (j2 - j1)) // max(1, i2 - i1)
    m[len(a)] = len(b)
    i, j = s - ns, t - ns
    if m[i] is None or m[j - 1] is None:
        return None
    start = ts + m[i]
    end = ts + max(m[j - 1] + 1, m[i] + 1)
    # концы изменённого участка могут уйти внутрь слов: расширяем до границ слов
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    return start, end


class Models:
    """Ленивая загрузка моделей. По умолчанию работает только с локальными файлами:
    скачать модели заранее можно командой `pii-roundtrip download-models`."""

    def __init__(self, use_pii_guard: bool = True, use_gliner: bool = True, offline: bool = True):
        self.use_pii_guard, self.use_gliner, self.offline = use_pii_guard, use_gliner, offline
        self._pg = self._gl = None
        self._lock = threading.Lock()

    def _env(self) -> None:
        if self.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ.setdefault("PII_GUARD_NER_REVISION", PII_GUARD_REVISION)
        if "PII_GUARD_DEVICE" not in os.environ:
            try:
                import torch

                if torch.backends.mps.is_available():
                    os.environ["PII_GUARD_DEVICE"] = "mps"
            except Exception:  # без torch pii-guard сам выберет CPU
                pass

    @property
    def pii_guard(self):
        with self._lock:
            if self._pg is None:
                self._env()
                from pii_guard import Anonymizer

                self._pg = Anonymizer()
        return self._pg

    @property
    def gliner(self):
        with self._lock:
            if self._gl is None:
                self._env()
                from gliner2 import GLiNER2

                self._gl = GLiNER2.from_pretrained(GLINER_MODEL, revision=GLINER_REVISION, local_files_only=self.offline)
        return self._gl

    def detect(self, text: str, lang: str) -> list[Span]:
        spans: list[Span] = []
        if lang == "ru" and self.use_pii_guard:
            r = self.pii_guard.anonymize(text, mode="tag")
            norm = r.normalized_texts[0]
            for e in r.entities[0]:
                s, t = e["start"], e["end"]
                if norm != text:
                    frag = norm[s:t]
                    approx = int(s * len(text) / max(1, len(norm)))
                    i = _locate(frag, text, approx)
                    if i is not None:
                        s, t = i, i + len(frag)
                    else:  # фрагмент изменён нормализацией (числа словами, транслит)
                        mapped = _align_local(norm, text, s, t, approx)
                        if mapped is None:
                            continue
                        s, t = mapped
                spans.append(Span(PII_GUARD_MAP.get(e["entity_type"], e["entity_type"]), s, t, "pii_guard"))
        if self.use_gliner:
            for off, part in _chunks(text):
                res = self.gliner.extract_entities(part, GLINER_LABELS, threshold=GLINER_THRESHOLD, include_spans=True)
                for label, items in res.get("entities", {}).items():
                    for it in items:
                        if isinstance(it, dict) and "start" in it:
                            spans.append(Span(GLINER_MAP.get(label, label.upper()), off + it["start"], off + it["end"], "gliner"))
        return spans


# ---------- распространение на весь документ ----------


@lru_cache(maxsize=20000)
def word_forms_ru(word: str) -> tuple[str, ...]:
    """Все падежные формы слова как имени, фамилии или отчества (оба рода)."""
    w = names.cap(word)
    if "-" in w:  # двойная фамилия: склоняем каждую часть в одном и том же падеже и роде
        parts = w.split("-")
        out = {w}
        for case in ("nomn", "gent", "datv", "accs", "ablt", "loct"):
            for g in ("masc", "femn"):
                forms_p = []
                for part in parts:
                    p = next((q for q in names.morph().parse(part) if "Surn" in names._tags(q) or q.tag.POS == "ADJF"), None)
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


def _needle_regex(value: str) -> re.Pattern:
    """Шаблон для поиска значения с учётом ё/е, апострофов и регистра."""
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
    """Совпадение считается именем, только если оно с заглавной или целиком заглавными."""
    return match[:1].isupper()


def propagate(text: str, spans: list[Span], lang: str, known: list[tuple[str, str]] | None = None) -> list[Span]:
    """Каждое найденное имя, организацию и номер ищем по всему документу (без учёта
    регистра, с ё/е и апострофами), включая падежные формы русских имён и значения,
    уже известные по предыдущим сообщениям сессии."""
    found = [(s.type, text[s.start : s.end], s.source) for s in spans]
    found += [(t, v, "known") for t, v in (known or [])]
    needles: dict[str, set[str]] = {}
    for t, v, source in found:
        if t == "PERSON":
            parsed = names.parse(v, lang)
            for w in re.findall(r"[\w'’-]+", v):
                low = names.norm(w)
                if len(w) < 2 or low in names.TITLES or low in names.ROLES or not w[:1].isupper():
                    continue
                if len(w) == 2 and source == "propagate":
                    continue
                is_first = low == parsed.first or (lang == "ru" and names._ru_word_role(w)[0] == "Name")
                if is_first and (low in NOT_PROPAGATED or (lang == "ru" and parsed.first in NOT_PROPAGATED)):
                    continue
                if lang == "ru" and re.match(r"[А-ЯЁ]", w):
                    needles.setdefault("PERSON", set()).update(word_forms_ru(w))
                else:
                    needles.setdefault("PERSON", set()).update({w, w + "'s", w + "s'"})
        elif t == "ORG":
            core = re.sub(r"^(?:ООО|ОАО|ЗАО|ПАО|АО|ГБУЗ|ГАУЗ)\s*", "", v).strip("«»\"' ")
            if len(core) >= 4 and core.lower() not in ALLOW:
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


def extend_persons(text: str, spans: list[Span]) -> list[Span]:
    """Расширяет имя на соседние слова с заглавной буквы и инициалы в той же строке
    («Miss Rachael [Rowe]» -> «Rachael Rowe», «[Иванов] И.И.»), не более 4 слов.
    Обращения и роли («Mr», «Истец», «Claimant») в имя не включаются."""
    out = []
    for s in spans:
        if s.type != "PERSON":
            out.append(s)
            continue
        start, end = s.start, s.end
        for _ in range(2):
            seg = text[max(0, start - 30) : start]
            m = re.search(r"([A-ZА-ЯЁ][\w'’-]+)[ \t]+$", seg)
            if not m or names.norm(m.group(1)) in names.TITLES | names.ROLES or len(text[start:end].split()) >= 4:
                break
            before = seg[: m.start()]
            if not before.strip() or before.rstrip().endswith((".", "!", "?", ":", "\n")):
                break  # начало строки или предложения: заглавная буква не означает имя
            start = max(0, start - 30) + m.start(1)
        for _ in range(2):
            m = re.match(r"[ \t]+([A-ZА-ЯЁ][\w'’-]+)", text[end : end + 30])
            if not m or names.norm(m.group(1)) in names.TITLES | names.ROLES or len(text[start:end].split()) >= 4:
                break
            end += m.end(1)
        m = _INITIALS_AFTER.match(text, end)
        if m:
            end = m.end()
        m = _INITIALS_BEFORE.search(text[max(0, start - 12) : start])
        if m:
            start = max(0, start - 12) + m.start()
        out.append(Span(s.type, start, end, s.source))
    return out


def attach_initials(text: str, spans: list[Span]) -> list[Span]:
    """Инициалы рядом с именем скрываются вместе с ним: «[Иванов] Н.А.», «А.Б. [Петров]»."""
    out = []
    for s in spans:
        if s.type == "PERSON":
            start, end = s.start, s.end
            m = _INITIALS_AFTER.match(text, end)
            if m:
                end = m.end()
            m = _INITIALS_BEFORE.search(text[max(0, start - 12) : start])
            if m:
                start = max(0, start - 12) + m.start()
            s = Span(s.type, start, end, s.source)
        out.append(s)
    return out


def _clean(text: str, spans: list[Span], mask_dates: bool) -> list[Span]:
    out = []
    for s in spans:
        if s.type == "BIK" or (s.type == "DATE" and not mask_dates):
            continue  # БИК банка и даты документа не персональные данные
        v = text[s.start : s.end].strip(" .,«»\"")
        if v.lower() in ALLOW and PRIORITY.get(s.type, 0) < 8:
            continue
        if s.type == "ADDRESS":
            if s.end - s.start < 3 and not any(c.isdigit() for c in v):
                continue  # буквенный обрывок вроде «NI»; номер дома «34» оставляем
            seg = text[max(0, s.start - 8) : s.start]
            m = re.search(r"(?<![\w])\d{1,5}[A-Za-zА-Яа-я]?\s+$", seg)  # номер дома слева: «12 Baker Street»
            if m:
                s = Span(s.type, s.start - (len(seg) - m.start()), s.end, s.source)
        out.append(s)
    return out


def _stronger(a: Span, b: Span) -> Span:
    pa, pb = PRIORITY.get(a.type, 1), PRIORITY.get(b.type, 1)
    if pa != pb:
        return a if pa > pb else b
    return b if b.source == "rules" and a.source != "rules" else a  # правило с контрольной суммой важнее модели


def merge(spans: list[Span], text: str = "") -> list[Span]:
    """Объединение с приоритетом полноты: пересекающиеся спаны сливаются в объединение,
    тип берётся у более «сильного»; соседние части одного имени или адреса склеиваются."""
    spans = sorted((s for s in spans if s.end > s.start), key=lambda s: (s.start, -s.end))
    out: list[Span] = []
    for s in spans:
        if out and s.start < out[-1].end:
            last = out[-1]
            w = _stronger(last, s)
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


def detect(
    text: str, lang: str, models: Models, known: list[tuple[str, str]] | None = None, mask_dates: bool = False
) -> list[Span]:
    spans = models.detect(text, lang)
    spans += [Span(h.type, h.start, h.end, "rules") for h in rules.find(text, lang)]
    spans = merge(_clean(text, spans, mask_dates), text)
    spans = merge(extend_persons(text, spans), text)
    spans = propagate(text, spans, lang, known)
    return merge(attach_initials(text, merge(spans, text)), text)
