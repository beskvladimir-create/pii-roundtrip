"""Public API: :func:`anonymize` and :func:`deanonymize`.

Placeholders look like ``[PERSON_1]``. One person, organisation or number always gets
one placeholder across the document and across later messages of the same session.
Different people are never merged into one placeholder: an ambiguous mention gets its
own.

Restoration accepts a placeholder in square brackets in any case and with extra spaces
or a qualifier added by the model (``[ORG_NAME_ORG_1]``); a bare ``PERSON_1`` is
accepted only in upper case and only if no such word occurred in the source text.
Russian names are inflected for the context; other values are restored as they were.

Thread safety: an :class:`Engine` serialises detection. A :class:`Session` is updated
atomically under its own lock, so it may be shared between threads, but the order of
labels then depends on the order of calls.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Literal

from pii_roundtrip import langs, lexicon, names
from pii_roundtrip.detect import Models, Span, detect
from pii_roundtrip.errors import SessionError

if TYPE_CHECKING:
    from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

log = logging.getLogger("pii_roundtrip")

BRACKETED = re.compile(r"\[\s*([A-Za-z]+(?:_[A-Za-z]+)*)[\s_-]*(\d+)\s*\]")
BARE = re.compile(r"(?<![\w\[])([A-Z]+(?:_[A-Z]+)*)_(\d+)(?![\w\]])")
LABEL_LIKE = re.compile(r"\[?\b[A-Za-z]+(?:_[A-Za-z]+)*_\d+\b\]?")
# Every form in which a model may return a placeholder, in one pattern so that each occurrence is
# matched once: in brackets, with words the model put before the label inside the brackets
# ("[Company: ORG_1]", kept in the answer), with a lost closing or opening bracket ("[ORG_1",
# "ORG_1]"), and bare ("ORG_1"). The forms without both brackets are taken in capitals only.
PLACEHOLDER_ANY = re.compile(
    r"\[\s*(?P<pre>(?:(?![A-Za-z]+_\d)[^\[\]\n]){0,40}?[\s:]\s*)?(?P<t1>[A-Za-z]+(?:_[A-Za-z]+)*)[\s_-]*(?P<n1>\d+)\s*\]"
    r"|\[\s*(?P<t2>[A-Z]+(?:_[A-Z]+)*)_(?P<n2>\d+)(?![\w\]])"
    r"|(?<![\w\[])(?P<t3>[A-Z]+(?:_[A-Z]+)*)_(?P<n3>\d+)\s*\]"
    r"|(?<![\w\[])(?P<t4>[A-Z]+(?:_[A-Z]+)*)_(?P<n4>\d+)(?![\w\]])"
)


def placeholder_parts(m: re.Match) -> tuple[str, str, str, bool]:
    """(words kept before the label, type, number, whether the brackets are incomplete) of a
    PLACEHOLDER_ANY match."""
    for k in ("1", "2", "3", "4"):
        if m.group("t" + k):
            pre = (m.group("pre") or "") if k == "1" else ""
            return pre, m.group("t" + k), m.group("n" + k), k != "1"
    raise ValueError(m.group(0))


_OPF = re.compile(r"^" + lexicon.LEGAL_FORM_RU_RE + r"\s*", re.I)
_ORG_TAIL = re.compile(r"[\s,]*(?:ltd|limited|llp|plc|inc|group)\.?$", re.I)

SESSION_FORMAT = 2  # version 1 existed only before the first public release


def _org_key(value: str) -> str:
    v = _OPF.sub("", value.strip())
    v = _ORG_TAIL.sub("", v)
    return re.sub(r"[\W_]+", "", names.norm(v))


def _value_key(value: str) -> str:
    return re.sub(r"[\s\-().]+", "", names.norm(value))


@dataclass
class Session:
    """The mapping between placeholders and original values for a document or a conversation.

    ``mapping`` (placeholder -> original value) is the public part. The other fields are
    internal state that keeps placeholders consistent across messages; they are saved in
    the vault together with the mapping.
    """

    lang: str
    mapping: dict[str, str] = field(default_factory=dict)
    genders: dict[str, str] = field(default_factory=dict)
    people: list[tuple[str, names.Name]] = field(default_factory=list)
    keys: dict[str, str] = field(default_factory=dict)  # "ORG|romashka" -> "[ORG_1]"
    counters: dict[str, int] = field(default_factory=dict)
    reserved: set[str] = field(default_factory=set)  # label-like words seen in source texts
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.lang = langs.canonical(self.lang) if self.lang != "uk" else langs.EN_GB

    def to_dict(self) -> dict:
        return {
            "version": SESSION_FORMAT,
            "lang": self.lang,
            "mapping": self.mapping,
            "genders": self.genders,
            "people": [[lab, n.to_dict()] for lab, n in self.people],
            "keys": self.keys,
            "counters": self.counters,
            "reserved": sorted(self.reserved),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Session:
        version = d.get("version", SESSION_FORMAT)
        if version != SESSION_FORMAT:
            raise SessionError(f"Unsupported session format {version}; this version reads format {SESSION_FORMAT}")
        known = {f.name for f in fields(names.Name)}
        s = cls(d["lang"], dict(d["mapping"]), dict(d.get("genders", {})))
        s.people = [(lab, names.Name(**{k: v for k, v in n.items() if k in known})) for lab, n in d.get("people", [])]
        s.keys = dict(d.get("keys", {}))
        s.counters = dict(d.get("counters", {}))
        s.reserved = set(d.get("reserved", []))
        return s

    def _replace_with(self, other: Session) -> None:
        for name in ("mapping", "genders", "people", "keys", "counters", "reserved"):
            setattr(self, name, getattr(other, name))

    def known(self) -> list[tuple[str, str]]:
        """Known values; repeats of them in later messages are masked with the same placeholders."""
        return [(lab.strip("[]").rsplit("_", 1)[0], v) for lab, v in self.mapping.items()]


class Engine:
    """Anonymisation engine.

    ``models`` selects the detectors (see :class:`pii_roundtrip.detect.Models`).
    ``strict_inflection`` makes a failure of Russian name inflection raise
    :class:`pii_roundtrip.errors.InflectionError`; with ``False`` names are restored in
    the nominative case and a warning is logged. If pii-guard is not installed at all,
    names are always restored in the nominative case.
    """

    def __init__(self, models: Models | None = None, mask_dates: bool = False, strict_inflection: bool = True):
        self.models = models or Models()
        self.mask_dates = mask_dates
        self.strict_inflection = strict_inflection
        self._lock = threading.Lock()
        self._inflector: PiiGuardInflector | Literal[False] | None = None  # False: pii-guard is not installed

    def spans(self, text: str, lang: str, known: list[tuple[str, str]] | None = None) -> list[Span]:
        with self._lock:
            return detect(text, langs.canonical(lang), self.models, known=known, mask_dates=self.mask_dates)

    # ---------- anonymisation ----------

    def anonymize(self, text: str, lang: str, session: Session | None = None) -> tuple[str, Session]:
        lang = langs.canonical(lang)
        session = session or Session(lang)
        if session.lang != lang:
            raise SessionError(f"The session was created for {session.lang}, but the text is {lang}")
        with session._lock:
            work = Session.from_dict(session.to_dict())  # commit only if everything succeeds
            work.reserved.update(m.group().strip("[]").upper() for m in LABEL_LIKE.finditer(text))
            spans = self.spans(text, lang, known=work.known())
            out, pos = [], 0
            for s in spans:
                value = text[s.start : s.end]
                out.append(text[pos : s.start])
                out.append(self._label(work, s.type, value, lang))
                pos = s.end
            out.append(text[pos:])
            session._replace_with(work)
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
            session.mapping[label] = value.strip()  # keep the full form with the legal form
        return label

    def _person_label(self, session: Session, value: str, lang: str) -> str:
        mention = names.parse(value, lang)
        candidates = [(lab, n) for lab, n in session.people if names.compatible(n, mention)]
        if len(candidates) > 1:
            # with several compatible people, only an unambiguous first-name match is accepted
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

    # ---------- restoration ----------

    def deanonymize(self, text: str, session: Session) -> str:
        canon = {k.strip("[]").upper(): k for k in session.mapping}

        def lookup(t: str, n: str) -> str | None:
            t = t.upper()
            if f"{t}_{n}" in canon:
                return canon[f"{t}_{n}"]
            # the model adds a qualifier to the placeholder: [ORG_NAME_ORG_1], [PERSON_NAME_PERSON_2]
            parts = t.split("_")
            for i in range(1, len(parts)):
                if f"{'_'.join(parts[i:])}_{n}" in canon:
                    return canon[f"{'_'.join(parts[i:])}_{n}"]
            return None

        def resolve(m: re.Match) -> tuple[str, str | None]:
            pre, t, n, open_form = placeholder_parts(m)
            if open_form and f"{t}_{n}" in session.reserved:
                return pre, None  # the word occurred in the source text: leave it alone
            lab = lookup(t, n)
            if lab is None and pre:  # the words before were part of the label after all
                lab = lookup((pre.strip(" :") + "_" + t).replace(" ", "_"), n)
            return pre, lab

        if session.lang == langs.RU:
            return self._restore_ru(text, session, resolve)

        def sub(m: re.Match) -> str:
            pre, lab = resolve(m)
            return pre + session.mapping[lab] if lab else m.group(0)

        return PLACEHOLDER_ANY.sub(sub, text)

    def _get_inflector(self) -> PiiGuardInflector | Literal[False]:
        if self._inflector is None:
            from pii_roundtrip.adapters import pii_guard

            found: PiiGuardInflector | Literal[False] = False
            if pii_guard.PiiGuardInflector.available():
                found = pii_guard.PiiGuardInflector()
            else:
                log.warning("pii-guard is not installed; Russian names are restored in the nominative case")
            self._inflector = found
            return found
        return self._inflector

    def _restore_ru(self, text: str, session: Session, resolve) -> str:
        """Names are inflected for the context; other values are restored as they were."""
        from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

        tagmap: dict[str, str] = {}
        ids: dict[str, int] = {}

        def sub(m: re.Match) -> str:
            pre, lab = resolve(m)
            if not lab:
                return m.group(0)
            if lab.startswith("[PERSON_"):
                i = ids.setdefault(lab, len(ids) + 1)
                tag = PiiGuardInflector.tag(session.genders.get(lab, "unknown"), i)
                tagmap[tag] = session.mapping[lab]
                return pre + tag
            return pre + session.mapping[lab]

        # literal pii-guard tags in the answer are escaped so that they are not scrubbed
        guard = "⁣"
        staged = text.replace("<PII", "<" + guard + "PII")
        staged = PLACEHOLDER_ANY.sub(sub, staged)
        if tagmap:
            inflector = self._get_inflector()
            restored = None
            if inflector:
                try:
                    restored = inflector.restore(staged, tagmap)
                except Exception as e:
                    if self.strict_inflection:
                        raise
                    log.warning("%s; names restored in the nominative case", e)
            if restored is None:
                restored = staged
                for tag, v in tagmap.items():
                    restored = restored.replace(tag, v)
            staged = restored
        return staged.replace("<" + guard + "PII", "<PII")


_default: Engine | None = None
_default_lock = threading.Lock()


def _engine() -> Engine:
    global _default
    with _default_lock:
        if _default is None:
            _default = Engine()
    return _default


def anonymize(text: str, lang: str, session: Session | None = None) -> tuple[str, Session]:
    """Replace personal data with placeholders. Returns the cleaned text and the session.

    ``lang`` is "ru" or "en-GB". Pass the same session for later messages of a
    conversation: known people and numbers keep their placeholders."""
    return _engine().anonymize(text, lang, session)


def deanonymize(text: str, session: Session) -> str:
    """Put the original values back into an LLM answer using the session."""
    return _engine().deanonymize(text, session)


__all__ = ["Engine", "Session", "anonymize", "deanonymize"]
