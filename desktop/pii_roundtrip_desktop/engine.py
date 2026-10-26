"""The engine for the app: with models when they are installed, otherwise rules only."""

from __future__ import annotations

import re
import threading
from dataclasses import replace

from pii_roundtrip import langs
from pii_roundtrip.core import BRACKETED, LABEL_LIKE, Engine, Session
from pii_roundtrip.detect import Models
from pii_roundtrip.errors import ModelsNotAvailableError


class AppEngine:
    def __init__(self) -> None:
        self._engine: Engine | None = None
        self.rules_only = False
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._engine is not None

    def load(self) -> None:
        """Load the models (slow, call off the interface thread); fall back to rules."""
        with self._lock:
            if self._engine is not None:
                return
            detectors = []
            for name, probe in (("pii_guard", ("Иван Петров", "ru")), ("gliner", ("John Smith", "en-GB"))):
                models = Models(use_pii_guard=name == "pii_guard", use_gliner=name == "gliner", offline=True)
                try:
                    models.detect(*probe)  # loads the model once
                    detectors += models.detectors
                except ModelsNotAvailableError:
                    pass
            self.rules_only = not detectors
            models = Models(use_pii_guard=False, use_gliner=False, offline=True)
            models._detectors = detectors
            self._engine = Engine(models, strict_inflection=False)

    def anonymize(self, text: str, lang: str, session: Session | None) -> tuple[str, Session]:
        self.load()
        assert self._engine is not None
        return self._engine.anonymize(text, lang, session)

    def deanonymize(self, text: str, session: Session, forms: dict[str, str] | None = None) -> str:
        """``forms``: a label and the exact text it replaced in the source document."""
        self.load()
        assert self._engine is not None
        written = {k.strip("[]").upper(): " ".join(v.split()) for k, v in (forms or {}).items()}

        def as_written(m: re.Match) -> str:
            # values other than names are not inflected: they come back exactly as in the source
            key = f"{m.group(1).upper()}_{m.group(2)}"
            if key not in written:
                return m.group(0)
            if key.startswith("PERSON") and _NAME.fullmatch(written[key]):
                return m.group(0)  # a person's name: the engine inflects it for its place
            return written[key]

        if session.lang != "ru":
            return self._engine.deanonymize(BRACKETED.sub(as_written, text), session)
        # Russian names are inflected from the words around them; a line break ends the context,
        # otherwise "г. Москва" above a name reads as "Москва Иванова" and puts it in the genitive
        engine = self._engine

        def line_back(line: str) -> str:
            if not line.strip():
                return line
            alone = _ALONE.fullmatch(line)
            if alone:
                # a name alone on its line (a signature, a heading) has no case to agree with:
                # the inflector would only guess, so the value comes back as it was written
                label = engine.deanonymize(alone.group(2), session)
                if label != alone.group(2):
                    key = alone.group(2).strip("[]").upper()
                    canon = {k.strip("[]").upper(): v for k, v in (forms or {}).items()}
                    stored = next((v for k, v in session.mapping.items() if k.strip("[]").upper() == key), label)
                    value = canon.get(key) or stored
                    if key.startswith("PERSON") and stored.split():
                        # the form written in the source only if it is the nominative ("Д.И. Харитонов"),
                        # not "Зиминой Ираидой Павловной" from "между ... и Зиминой Ираидой Павловной"
                        surname = stored.split()[0].lower().replace("ё", "е")
                        words = [w.lower().replace("ё", "е") for w in re.findall(r"[\w-]+", value)]
                        if surname not in words:
                            value = stored
                    return alone.group(1) + value + alone.group(3)
            return engine.deanonymize(BRACKETED.sub(as_written, line), session)

        return "\n".join(line_back(line) for line in text.split("\n"))

    def anonymize_with_spans(
        self, text: str, lang: str, session: Session | None
    ) -> tuple[str, Session, list[tuple[int, int, str]]]:
        """Like anonymize, and also where each placeholder replaced the original text, so a
        Word file can be cleaned in place with its formatting. The steps mirror
        Engine.anonymize; tests check that both give the same text and session."""
        self.load()
        assert self._engine is not None
        eng = self._engine
        lang = langs.canonical(lang)
        base = session or Session(lang)
        work = Session.from_dict(base.to_dict())
        work.reserved.update(m.group().strip("[]").upper() for m in LABEL_LIKE.finditer(text))
        spans = _everywhere(text, eng.spans(text, lang, known=work.known()))
        out, pos, placed = [], 0, []
        for s in spans:
            out.append(text[pos : s.start])
            label = eng._label(work, s.type, text[s.start : s.end], lang)
            out.append(label)
            placed.append((s.start, s.end, label))
            pos = s.end
        out.append(text[pos:])
        if session is None:
            return "".join(out), work, placed
        with session._lock:  # commit like Engine.anonymize does
            session._replace_with(work)
        return "".join(out), session, placed


# a line that is one placeholder, maybe with signature slashes, underscores or punctuation around it
_ALONE = re.compile(r"([\s_/«\"(:\-–—]*)(\[\s*[A-Za-z]+(?:_[A-Za-z]+)*[\s_-]*\d+\s*\])([\s_/»\")\.,;:\-–—]*)")


# what reads as a person's name: two or three capitalised words or initials, nothing else
_NAME = re.compile(r"(?:[A-ZА-ЯЁ][a-zа-яё'’-]+|[A-ZА-ЯЁ]\.)(?:\s+(?:[A-ZА-ЯЁ][a-zа-яё'’-]+|[A-ZА-ЯЁ]\.)){0,3}")


def _everywhere(text: str, spans: list) -> list:
    """A value masked in one place is masked wherever else it occurs as a whole word,
    including across a line break: a document must not keep in one paragraph what it hides
    in another. Desktop only; the benchmarked engine is unchanged."""
    taken = [(s.start, s.end) for s in spans]
    extra = []
    seen = set()
    for s in sorted(spans, key=lambda s: s.end - s.start, reverse=True):
        value = text[s.start : s.end].strip()
        if len(value) < 4 or value in seen:
            continue
        seen.add(value)
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in value.split()) + r"(?!\w)"
        for m in re.finditer(pattern, text):
            if any(m.start() < b and m.end() > a for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            extra.append(replace(s, start=m.start(), end=m.end()))
    return sorted(spans + extra, key=lambda s: s.start)
