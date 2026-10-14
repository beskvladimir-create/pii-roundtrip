"""Публичный API: anonymize() и deanonymize().

Метки вида [PERSON_1]. Одно лицо, одна организация, один номер всегда получают одну
метку во всём документе и во всех последующих сообщениях той же сессии. Разные люди
никогда не сливаются в одну метку: при неоднозначности упоминание получает свою.

Восстановление принимает метку в квадратных скобках в любом регистре и с лишними
пробелами; метку без скобок только в точном виде PERSON_1 и только если такого слова
не было в исходном тексте. Русские имена склоняются по контексту (морфология
pii-guard), остальные значения возвращаются как есть.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field

from pii_roundtrip import names
from pii_roundtrip.detect import Models, Span, detect

log = logging.getLogger("pii_roundtrip")

BRACKETED = re.compile(r"\[\s*([A-Za-z]+(?:_[A-Za-z]+)*)[\s_-]*(\d+)\s*\]")
BARE = re.compile(r"(?<![\w\[])([A-Z]+(?:_[A-Z]+)*)_(\d+)(?![\w\]])")
LABEL_LIKE = re.compile(r"\[?\b[A-Za-z]+(?:_[A-Za-z]+)*_\d+\b\]?")

_OPF = re.compile(r"^(?:ООО|ОАО|ЗАО|ПАО|АО|НАО|НКО|АНО|ФГУП|ГУП|МУП|ГБУЗ|ГАУЗ|ГБУ|ФГБУ)\s*", re.I)
_ORG_TAIL = re.compile(r"[\s,]*(?:ltd|limited|llp|plc|inc|group)\.?$", re.I)


def _org_key(value: str) -> str:
    v = _OPF.sub("", value.strip())
    v = _ORG_TAIL.sub("", v)
    return re.sub(r"[\W_]+", "", names.norm(v))


def _value_key(value: str) -> str:
    return re.sub(r"[\s\-().]+", "", names.norm(value))


@dataclass
class Session:
    """Соответствия меток и исходных значений для документа или диалога."""

    lang: str
    mapping: dict[str, str] = field(default_factory=dict)  # "[PERSON_1]" -> "Иванов Пётр Сергеевич"
    genders: dict[str, str] = field(default_factory=dict)
    people: list[tuple[str, names.Name]] = field(default_factory=list)
    keys: dict[str, str] = field(default_factory=dict)  # "ORG|ромашка" -> "[ORG_1]"
    counters: dict[str, int] = field(default_factory=dict)
    reserved: set[str] = field(default_factory=set)  # похожие на метки слова из исходных текстов

    def to_dict(self) -> dict:
        return {
            "version": 2,
            "lang": self.lang,
            "mapping": self.mapping,
            "genders": self.genders,
            "people": [[lab, n.to_dict()] for lab, n in self.people],
            "keys": self.keys,
            "counters": self.counters,
            "reserved": sorted(self.reserved),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        s = cls(d["lang"], dict(d["mapping"]), dict(d.get("genders", {})))
        s.people = [(lab, names.Name(**n)) for lab, n in d.get("people", [])]
        s.keys = dict(d.get("keys", {}))
        s.counters = dict(d.get("counters", {}))
        s.reserved = set(d.get("reserved", []))
        return s

    def known(self) -> list[tuple[str, str]]:
        """Уже известные значения: по ним скрываются повторы в следующих сообщениях."""
        out = []
        for lab, v in self.mapping.items():
            t = lab.strip("[]").rsplit("_", 1)[0]
            out.append((t, v))
        return out


class Engine:
    def __init__(self, models: Models | None = None, mask_dates: bool = False):
        self.models = models or Models()
        self.mask_dates = mask_dates
        self._lock = threading.Lock()

    def spans(self, text: str, lang: str, known: list[tuple[str, str]] | None = None) -> list[Span]:
        return detect(text, _lang(lang), self.models, known=known, mask_dates=self.mask_dates)

    # ---------- очистка ----------

    def anonymize(self, text: str, lang: str, session: Session | None = None) -> tuple[str, Session]:
        lang = _lang(lang)
        session = session or Session(lang)
        if session.lang != lang:
            raise ValueError(f"The session was created for {session.lang}, but the text is {lang}")
        session.reserved.update(m.group().strip("[]").upper() for m in LABEL_LIKE.finditer(text))
        with self._lock:
            spans = self.spans(text, lang, known=session.known())
        out, pos = [], 0
        for s in spans:
            value = text[s.start : s.end]
            out.append(text[pos : s.start])
            out.append(self._label(session, s.type, value, lang))
            pos = s.end
        out.append(text[pos:])
        return "".join(out), session

    def _new_label(self, session: Session, etype: str) -> str:
        while True:
            n = session.counters.get(etype, 0) + 1
            session.counters[etype] = n
            if f"{etype}_{n}" not in session.reserved:
                return f"[{etype}_{n}]"

    def _label(self, session: Session, etype: str, value: str, lang: str) -> str:
        if etype == "PERSON":
            return self._person_label(session, value, lang)
        key = f"{etype}|{_org_key(value) if etype == 'ORG' else _value_key(value)}"
        label = session.keys.get(key)
        if label is None:
            label = self._new_label(session, etype)
            session.keys[key] = label
            session.mapping[label] = value.strip()
        elif etype == "ORG" and len(value.strip()) > len(session.mapping[label]):
            session.mapping[label] = value.strip()  # храним полную форму с ООО
        return label

    def _person_label(self, session: Session, value: str, lang: str) -> str:
        mention = names.parse(value, lang)
        candidates = [(lab, n) for lab, n in session.people if names.compatible(n, mention)]
        if len(candidates) > 1:
            # при нескольких подходящих людях берём только однозначно совпавшего по имени
            exact = [(lab, n) for lab, n in candidates if mention.first and n.first == mention.first]
            candidates = exact if len(exact) == 1 else []
        if len(candidates) == 1:
            lab, n = candidates[0]
            names.merge_into(n, mention)
            session.mapping[lab] = n.display or session.mapping[lab]
            if n.gender:
                session.genders[lab] = n.gender
            return lab
        lab = self._new_label(session, "PERSON")
        session.people.append((lab, mention))
        session.mapping[lab] = mention.display or value.strip()
        session.genders[lab] = mention.gender or "unknown"
        return lab

    # ---------- восстановление ----------

    def deanonymize(self, text: str, session: Session) -> str:
        canon = {k.strip("[]").upper(): k for k in session.mapping}

        def lookup(t: str, n: str) -> str | None:
            t = t.upper()
            if f"{t}_{n}" in canon:
                return canon[f"{t}_{n}"]
            # нейросеть дописывает к метке пояснение: [ORG_NAME_ORG_1], [PERSON_NAME_PERSON_2]
            parts = t.split("_")
            for i in range(1, len(parts)):
                if f"{'_'.join(parts[i:])}_{n}" in canon:
                    return canon[f"{'_'.join(parts[i:])}_{n}"]
            return None

        def resolve(m: re.Match, bare: bool) -> str | None:
            t, n = m.group(1), m.group(2)
            if bare and f"{t}_{n}" in session.reserved:
                return None  # такое слово было в исходном тексте: не трогаем
            return lookup(t, n)

        if session.lang == "ru":
            return self._restore_ru(text, session, resolve)

        def sub(bare: bool):
            return lambda m: session.mapping[lab] if (lab := resolve(m, bare)) else m.group(0)

        return BARE.sub(sub(True), BRACKETED.sub(sub(False), text))

    def _restore_ru(self, text: str, session: Session, resolve) -> str:
        """Имена склоняются по контексту морфологией pii-guard; остальное как есть."""
        tagmap: dict[str, str] = {}
        ids: dict[str, int] = {}

        def sub(bare: bool):
            def f(m: re.Match) -> str:
                lab = resolve(m, bare)
                if not lab:
                    return m.group(0)
                if lab.startswith("[PERSON_"):
                    i = ids.setdefault(lab, len(ids) + 1)
                    tag = f'<PII type="PERSON" gender="{session.genders.get(lab, "unknown")}" id="{i}" />'
                    tagmap[tag] = session.mapping[lab]
                    return tag
                return session.mapping[lab]

            return f

        # литеральные теги pii-guard в ответе экранируем, чтобы их не затёрло
        guard = "⁣"
        staged = text.replace("<PII", "<" + guard + "PII")
        staged = BARE.sub(sub(True), BRACKETED.sub(sub(False), staged))
        if tagmap:
            try:
                from pii_guard import pseudonymize as P

                P.configure_nlp("ru_core_news_sm")
                staged = P.deanonymize_batch([staged], tagmap, "ru_core_news_sm")[0]
            except Exception as e:  # без морфологии: именительный падеж
                log.warning("Russian name inflection is unavailable (%s); names restored in the nominative case", e)
                for tag, v in tagmap.items():
                    staged = staged.replace(tag, v)
        return staged.replace("<" + guard + "PII", "<PII")


def _lang(lang: str) -> str:
    lang = lang.lower()
    if lang in ("ru", "rus", "russian"):
        return "ru"
    if lang in ("uk", "en", "en-gb", "gb", "english"):
        return "uk"
    raise ValueError(f"Unsupported language: {lang} (use ru or uk)")


_default: Engine | None = None
_default_lock = threading.Lock()


def _engine() -> Engine:
    global _default
    with _default_lock:
        if _default is None:
            _default = Engine()
    return _default


def anonymize(text: str, lang: str, session: Session | None = None) -> tuple[str, Session]:
    """Заменяет персональные данные метками. Возвращает очищенный текст и сессию.

    Передайте ту же сессию для следующих сообщений диалога: повторы уже известных
    людей и номеров будут скрыты теми же метками."""
    return _engine().anonymize(text, lang, session)


def deanonymize(text: str, session: Session) -> str:
    """Возвращает исходные значения в ответ нейросети по сессии."""
    return _engine().deanonymize(text, session)


__all__ = ["Engine", "Session", "anonymize", "deanonymize"]
