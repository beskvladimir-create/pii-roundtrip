"""Parsing person mentions and deciding whether two mentions are the same person.

A person is keyed by several parts, not one word: surname in the nominative case with
the right gender, first name, patronymic, initials and gender. Two mentions refer to
the same person only if every known part agrees. When a mention is ambiguous (two
people named Ivanova, or a surname alone), it gets its own placeholder: merging two
people is invisible to the user and would put the wrong person into the answer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache

from pii_roundtrip.langs import RU
from pii_roundtrip.lexicon import FEMALE_TITLES, MALE_TITLES, ROLES, TITLES

_INITIALS = re.compile(r"^(?:[A-ZА-ЯЁ]\.){1,3}$|^[A-ZА-ЯЁ]\.?$")
_WORD = re.compile(r"[A-Za-zА-Яа-яЁё][\w'’.-]*")


def norm(s: str) -> str:
    return s.lower().replace("ё", "е").replace("’", "'")


def cap(word: str) -> str:
    """Capitalise every part: "римский-корсаков" -> "Римский-Корсаков", "o'brien" -> "O'Brien"."""
    return "-".join("'".join(p[:1].upper() + p[1:].lower() for p in part.split("'")) for part in word.split("-"))


@lru_cache(maxsize=1)
def morph():
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


def _tags(p) -> set[str]:
    return set(str(p.tag).replace(" ", ",").split(","))


@dataclass
class Name:
    surname: str = ""  # normalised: nominative case, lower case, ё -> е
    first: str = ""
    patronymic: str = ""
    initials: str = ""  # first letters of first name and patronymic from forms like "И.И."
    gender: str = ""  # male / female / ""
    display: str = ""  # how the name is shown on restoration

    @property
    def first_initial(self) -> str:
        return self.first[:1] or self.initials[:1]

    @property
    def patronymic_initial(self) -> str:
        return self.patronymic[:1] or self.initials[1:2]

    def richness(self) -> int:
        return sum(bool(x) for x in (self.surname, self.first, self.patronymic)) * 2 + len(self.initials)

    def to_dict(self) -> dict:
        return asdict(self)


_SURN_END = re.compile(
    r"(ов|ев|ёв|ин|ын|ский|цкий|ской|цкой|ова|ева|ёва|ина|ына|ская|цкая)(а|у|ым|ом|е|ой|ую|ых|ыми)?$"
)
_PATR_END = re.compile(r"(вич|вн|ичн|ьич)(а|у|ем|ом|е|ы|ой|ну|ам)?$")
# short patronymics without "в": "Фомич", "Кузьмич", "Лукич"; also "Фокич", unknown to the dictionary,
# when it follows a first name (see parse)
_PATR_SHORT_END = re.compile(r"[мкл]ич(а|у|ем|е)?$")


def _ru_word_role(word: str) -> tuple[str, object | None]:
    """Classify a Russian word as first name, patronymic or surname.

    Order matters: the morphology also parses "Иванов" as a possessive form of the first
    name "Иван", so surname endings are checked before first names."""
    w = cap(word)
    low = norm(w)
    parses = morph().parse(w)
    by = {k: next((p for p in parses if k in _tags(p)), None) for k in ("Patr", "Name", "Surn")}
    if by["Patr"] and (_PATR_END.search(low) or _PATR_SHORT_END.search(low)):
        return "Patr", by["Patr"]
    if _SURN_END.search(low) and not (by["Name"] and not by["Surn"]):
        return "Surn", by["Surn"]
    if by["Name"]:
        return "Name", by["Name"]
    if by["Surn"]:
        return "Surn", by["Surn"]
    return "Surn", None  # out-of-vocabulary word: most likely a rare surname


def _gender_from_surname(s: str) -> str:
    s = norm(s)
    if re.search(r"(ова|ева|ина|ына|ая|ская|цкая)$", s):
        return "female"
    if re.search(r"(ов|ев|ин|ын|ий|ский|цкий|ой)$", s):
        return "male"
    return ""


def _nominative(word: str, p, gender: str) -> str:
    """Nominative case in lower case; the letter ё is kept for display."""
    if p is None:
        m = _PATR_SHORT_END.search(word.lower())
        if m and m.group(1):  # an unknown short patronymic in another case: "Фокича" -> "фокич"
            return word.lower()[: m.start(1)]
        return word.lower()
    g = {"male": "masc", "female": "femn"}.get(gender)
    parses = [q for q in morph().parse(cap(word)) if _tags(q) & {"Surn", "Name", "Patr"}]
    if g:
        parses = [q for q in parses if g in _tags(q)] or parses
    for q in parses:
        f = q.inflect({"nomn"} | ({g} if g and "Surn" in _tags(q) else set()))
        if f:
            return _restore_yo(f.word, word)
    return word.lower()


def _restore_yo(form: str, original: str) -> str:
    """pymorphy returns "петр"; if the original word had ё, put it back."""
    if "ё" in original.lower() and "ё" not in form:
        i = original.lower().find("ё")
        if i < len(form) and form[i] == "е":
            return form[:i] + "ё" + form[i + 1 :]
    return form


_NOT_NAME_POS = frozenset(
    {"PRTS", "PRTF", "VERB", "INFN", "GRND", "ADJS", "ADVB", "PREP", "CONJ", "PRCL", "NPRO", "INTJ", "COMP"}
)


def _not_a_name_ru(word: str) -> bool:
    parses = morph().parse(cap(word))
    return (
        bool(parses)
        and all(p.is_known and str(p.tag.POS) in _NOT_NAME_POS for p in parses)
        and not any({"Name", "Surn", "Patr"} & _tags(p) for p in parses)
    )


def parse(value: str, lang: str) -> Name:
    tokens = [t for t in _WORD.findall(value)]
    title_gender = ""
    words, initials = [], ""
    for t in tokens:
        low = norm(t.rstrip("."))
        if low in TITLES or low in ROLES:
            title_gender = title_gender or ("female" if low in FEMALE_TITLES else "male" if low in MALE_TITLES else "")
            continue
        if _INITIALS.match(t) or (len(t.rstrip(".")) == 1 and t[:1].isupper()):
            initials += re.sub(r"[^A-Za-zА-Яа-яЁё]", "", t).lower()
            continue
        words.append(t.rstrip("."))
    n = Name(gender=title_gender)
    if lang == RU:
        # a word the dictionary knows only as a verb form, adverb or function word is not part of the
        # name, even if a detector included it ("Выдана Крюковой Марине Никифоровне": "Выдана" used
        # to be stored as the first name and the real first name was dropped)
        words = [w for w in words if not _not_a_name_ru(w)] or words
        roles = [(w, *_ru_word_role(w)) for w in words]
        # an unknown word ending like a short patronymic right after a first name: "Нестор Фокич"
        roles = [
            (w, "Patr", None)
            if kind == "Surn" and p is None and i > 0 and roles[i - 1][1] == "Name" and _PATR_SHORT_END.search(norm(w))
            else (w, kind, p)
            for i, (w, kind, p) in enumerate(roles)
        ]
        g = ""
        for w, kind, _p in roles:
            if kind == "Patr":
                g = (
                    "female"
                    if norm(w).endswith(("вна", "чна", "вны", "вне", "вной", "вну", "чны", "чне", "чной", "чну"))
                    else "male"
                )
                break
        if not g:
            for _w, kind, p in roles:
                if kind == "Name" and p is not None:
                    tg = _tags(p)
                    if "femn" in tg and "masc" not in tg:
                        g = "female"
                    elif "masc" in tg:
                        g = "male"
                    if g:
                        break
        if not g:
            for w, kind, _ in roles:
                if kind == "Surn":
                    g = _gender_from_surname(w)
                    if g:
                        break
        n.gender = n.gender or g
        shown: dict[str, str] = {}
        surname_oov = False
        for w, kind, p in roles:
            nom = _nominative(w, p, n.gender)
            if kind == "Patr" and not n.patronymic:
                n.patronymic, shown["p"] = norm(nom), nom
            elif kind == "Name" and not n.first:
                n.first, shown["f"] = norm(nom), nom
            elif not n.surname:
                n.surname, shown["s"] = norm(nom), nom
                surname_oov = p is None
            elif not n.first:
                # a second word taken for a surname is the first name the dictionary does not know
                # ("Большакова Милан Андреевича"); it used to be dropped from the stored value. If the
                # surname so far was an unknown word and this one has a surname ending, they swap.
                if surname_oov and _SURN_END.search(norm(w)):
                    n.first, shown["f"] = n.surname, shown["s"]
                    n.surname, shown["s"] = norm(nom), nom
                else:
                    n.first, shown["f"] = norm(nom), nom
        parts = [cap(shown[k]) for k in ("s", "f", "p") if k in shown]
        if initials and not (n.first or n.patronymic):
            parts.append(".".join(c.upper() for c in initials) + ".")
        n.display = " ".join(parts)
    else:
        if words:
            n.surname = norm(words[-1])
            if len(words) > 1:
                n.first = norm(words[0])
        n.display = " ".join(cap(w) if w.isupper() else w for w in words) or value.strip()
        if initials and not n.first and words:
            n.display = f"{initials[0].upper()}. {n.display}"
    n.initials = initials
    return n


def compatible(a: Name, b: Name) -> bool:
    """Whether two mentions can refer to the same person."""
    if a.gender and b.gender and a.gender != b.gender:
        return False
    if a.surname and b.surname and a.surname != b.surname:
        return False
    if a.first and b.first and a.first != b.first:
        return False
    if a.first_initial and b.first_initial and a.first_initial != b.first_initial:
        return False
    if a.patronymic_initial and b.patronymic_initial and a.patronymic_initial != b.patronymic_initial:
        return False
    # without a shared surname, only a matching full first name can link two mentions
    return bool((a.surname and b.surname) or (a.first and b.first))


def merge_into(base: Name, other: Name) -> Name:
    """Add the parts known from ``other`` to ``base`` and keep the richest display form."""
    for f in ("surname", "first", "patronymic", "gender"):
        if not getattr(base, f) and getattr(other, f):
            setattr(base, f, getattr(other, f))
    if len(other.initials) > len(base.initials):
        base.initials = other.initials
    if other.richness() > base.richness() or (
        other.richness() == base.richness() and len(other.display) > len(base.display)
    ):
        base.display = other.display
    return base
