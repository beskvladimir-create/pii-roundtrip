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
# a patronymic with a typo ("Елисевеич", "Власоивч"), read as an unknown surname after a first name
_MISSPELT_PATR = re.compile(r"(?:[еиоа][вй]?[еиоа]?[ив]?ч|[вч]н[аыеу]|[вч]ной)$")


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
    name_nominative = any(
        "Name" in _tags(p) and p.tag.case == "nomn" and p.tag.number == "sing" and p.word == low for p in parses
    )
    bare = bool(re.search(r"(ов|ев|ёв|ин|ын)$", low))  # a surname in the nominative, no case ending
    if _SURN_END.search(low) and not (by["Name"] and not by["Surn"] and (name_nominative or not bare)):
        # "Кириллов", "Абрамов": the dictionary also reads them as the plural of a first name
        return "Surn", by["Surn"]
    if by["Name"]:
        return "Name", by["Name"]
    if by["Surn"]:
        return "Surn", by["Surn"]
    return "Surn", None  # out-of-vocabulary word: most likely a rare surname


def _gender_from_surname(s: str) -> str:
    """The gender a surname's form decides; "" when it does not ("Субботина" is the genitive of
    "Субботин" or the nominative of "Субботина")."""
    s = norm(s)
    m = _SURN_FAMILY.match(s)
    if m:
        return _FAMILY_GENDER.get(m.group("end") or "", "")
    if re.search(r"(ая|ская|цкая)$", s):
        return "female"
    if re.search(r"(ий|ский|цкий|ой)$", s):
        return "male"
    return ""


# Surnames in -ов/-ев/-ин/-ын and their case endings. The nominative is built from the ending,
# not from the dictionary, which reads "Абрамов" as the plural of the first name "Абрам".
_SURN_FAMILY = re.compile(r"^(?P<base>[а-яё-]{2,}?(?:ов|ев|ёв|ин|ын))(?P<end>а|у|ым|ом|е|ой|ую|ою)?$")
_FAMILY_GENDER = {"": "male", "ым": "male", "ом": "male", "е": "male", "ой": "female", "ую": "female", "ою": "female"}


def first_name_nominative(word: str) -> str | None:
    """A first name in an oblique case the dictionary does not lemmatise as a name ("Анне" is read
    as the indeclinable "Анне", "Софии" as the city): the candidate nominative it knows as a name."""
    low = norm(word)
    for cut, add in ((1, "а"), (1, "я"), (2, "ия"), (2, "а"), (2, "я"), (1, "")):
        cand = low[:-cut] + add if len(low) > cut + 1 else ""
        if cand and cand != low:
            for q in morph().parse(cand):
                tags = _tags(q)
                is_name = "Name" in tags and "Fixd" not in tags and q.tag.case == "nomn" and q.tag.number == "sing"
                if is_name and q.word == cand and low in {f.word for f in q.lexeme}:
                    return _restore_yo(cand, word)
    if low.endswith("ии") and len(low) > 4:  # "Софии": the dictionary knows "София" only as a city
        return _restore_yo(low[:-2] + "ия", word)
    return None


def surname_nominative(word: str, gender: str) -> str | None:
    """The nominative of a surname in -ов/-ев/-ин/-ын for the given gender, or None when its
    form and the gender do not decide it (then the surname is stored as written)."""
    m = _SURN_FAMILY.match(norm(word))
    if not m:
        return None
    base, end = m.group("base"), m.group("end") or ""
    certain = _FAMILY_GENDER.get(end)
    g = certain or gender
    if not g or (certain and gender and certain != gender):
        return None
    nom = base if g == "male" else base + "а"
    return _restore_yo(nom, word)


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
    if _SURN_FAMILY.match(norm(word)):
        return False  # "Ситникова" is also read as a short adjective ("ситниковый")
    parses = morph().parse(cap(word))
    return (
        bool(parses)
        and all(p.is_known and str(p.tag.POS) in _NOT_NAME_POS for p in parses)
        and not any({"Name", "Surn", "Patr"} & _tags(p) for p in parses)
    )


# Words before a surname with initials that decide its case when its form does not ("Кононова Л.Г."
# is the genitive of "Кононов" or the nominative of "Кононова"): a preposition or noun that takes the
# genitive, or the place of a signature, where the nominative stands.
_GENITIVE_BEFORE = re.compile(
    r"(?:^|[\s(«\"])(?:у|от|для|без|до|из|со стороны|в лице|заявлени[ея]|заявлению|согласи[ея]|подпись|подписью)\s*$",
    re.I,
)
_NOMINATIVE_BEFORE = re.compile(r"(?:_{3,}|\bисп\.|\n|^)\s*$", re.I)
_ACCUSATIVE_BEFORE = re.compile(
    r"(?:^|[\s(«\"])(?:принять|назначить|уволить|перевести|освободить|на|через|про)\s*$", re.I
)
_DATIVE_BEFORE = re.compile(r"(?:^|[\s(«\"])(?:к|выдана?|выдано|предоставить|направить|сообщить|уважаемому)\s*$", re.I)


def _case_from_context(left: str) -> str:
    """ "gent", "nomn", "datv" or "" from the words before a name."""
    if _GENITIVE_BEFORE.search(left):
        return "gent"
    if _DATIVE_BEFORE.search(left):
        return "datv"
    if _NOMINATIVE_BEFORE.search(left):
        return "nomn"
    return ""


def _patronymic_case(word: str) -> str:
    low = norm(word)
    for pattern, case in (
        (r"(ич|на)$", "nomn"),
        (r"(ича|ны)$", "gent"),
        (r"(ичу|не)$", "datv"),
        (r"ну$", "accs"),
        (r"(ичем|ичом|ной)$", "ablt"),
        (r"иче$", "loct"),
    ):
        if re.search(pattern, low):
            return case
    return ""


def _is_nominative_name(word: str) -> bool:
    low = norm(word)
    return any(
        "Name" in _tags(q)
        and "Fixd" not in _tags(q)
        and q.tag.case == "nomn"
        and q.tag.number == "sing"
        and q.word == low
        for q in morph().parse(low)
    )


def first_name_from_case(word: str, case: str, gender: str) -> str | None:
    """The nominative of a first name whose case and gender are known from the patronymic."""
    low = norm(word)
    if case == "nomn":
        return _restore_yo(low, word)
    g = {"male": "masc", "female": "femn"}[gender]
    for q in morph().parse(low):
        tags = _tags(q)
        if (
            "Name" in tags
            and "Fixd" not in tags
            and g in tags
            and q.tag.number == "sing"
            and q.tag.case == case
            and norm(q.word) == low
        ):
            f = q.inflect({"nomn"})
            if f:
                return _restore_yo(f.word, word)
    cands = []  # (length of the matched ending, nominative)
    for (gd, end), table in _FIRST_ENDINGS.items():
        if gd != gender:
            continue
        for form_end in {table[case], _spell("к" + table[case])[1:]}:
            if form_end and low.endswith(form_end) and len(low) > len(form_end) + 1:
                cands.append((len(form_end), low[: len(low) - len(form_end)] + end))
    if not cands:
        return None
    # the candidate the dictionary knows as a first name ("Анне" -> "Анна", not "Анния"); otherwise
    # the longest matched ending ("Софии" -> "София", not "Софиа")
    known = [c for _, c in cands if _is_nominative_name(c)]
    best = known[0] if known else max(cands, key=lambda c: c[0])[1]
    return _restore_yo(best, word)


def parse(value: str, lang: str, left: str = "") -> Name:
    """``left``: the text before the mention, used only when the form of a surname with initials
    does not decide its gender."""
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
        # only at the edges: a rare first name inside a name may also be a verb form ("Милован")
        kept = list(words)
        while kept and _not_a_name_ru(kept[0]):
            kept.pop(0)
        while kept and _not_a_name_ru(kept[-1]):
            kept.pop()
        words = kept or words
        roles = [(w, *_ru_word_role(w)) for w in words]
        if initials and len(roles) == 1 and roles[0][1] != "Surn":
            roles = [(roles[0][0], "Surn", None)]  # one word with initials is a surname: "Горбачеав А.В."
        # an unknown word ending like a short patronymic right after a first name: "Нестор Фокич"
        roles = [
            (w, "Patr", None)
            if kind == "Surn"
            and p is None
            and i > 0
            and roles[i - 1][1] == "Name"
            and (_PATR_SHORT_END.search(norm(w)) or _MISSPELT_PATR.search(norm(w)))
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
            # a surname whose ending decides the gender ("Петровой") comes before a first name the
            # dictionary reads both ways ("Лидии" as "Лидия" or "Лидий")
            for w, kind, _ in roles:
                if kind == "Surn":
                    g = _gender_from_surname(w)
                    if g:
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
        if not g and left:
            # only the surname decides, and its form does not: the words before it decide the case
            case = _case_from_context(left)
            for w, kind, _ in roles:
                m = _SURN_FAMILY.match(norm(w)) if kind == "Surn" else None
                if m:
                    end = m.group("end") or ""
                    if end == "а":  # genitive of a man's surname or nominative of a woman's
                        g = {"gent": "male", "nomn": "female"}.get(case, "")
                    elif end == "у":  # dative of a man's surname, or accusative of a woman's after a verb
                        g = "female" if _ACCUSATIVE_BEFORE.search(left) else "male"
                    break
        n.gender = n.gender or g
        # the case of the name, from the patronymic: a first name is put in the nominative from that
        # case ("Тимофей" stays, "Фортунату" -> "Фортунат", "Силы" -> "Сила", "Данила" stays "Данила")
        name_case = next((_patronymic_case(w) for w, kind, _ in roles if kind == "Patr"), "")
        shown: dict[str, str] = {}
        surname_oov = False
        for w, kind, p in roles:
            nom = _nominative(w, p, n.gender)
            if kind == "Surn" and _SURN_FAMILY.match(norm(w)):
                nom = surname_nominative(w, n.gender) or w.lower()  # as written when undecided
            elif kind == "Name" and name_case and n.gender:
                nom = first_name_from_case(w, name_case, n.gender) or w.lower()  # no case ending: as written
            elif kind == "Name" and _is_nominative_name(w):
                nom = w.lower()
            elif kind == "Name" and norm(nom) == norm(w) and re.search(r"(е|и|у|ю|ой|ей)$", norm(w)):
                nom = first_name_nominative(w) or nom
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
                    if name_case and n.gender:
                        nom = first_name_from_case(w, name_case, n.gender) or w.lower()  # "Милован"
                    elif norm(nom) == norm(w) and re.search(r"(е|и|у|ю|ой|ей)$", norm(w)):
                        nom = first_name_nominative(w) or nom  # "Софии", read by the dictionary as a city
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


def _same_first_name(a: str, b: str) -> bool:
    """One first name is a case form of the other ("данил" and "данила": the genitive of "Данил"
    and the nominative of "Данила" are written alike, and a document may use both)."""

    def forms(x: str) -> set[str]:
        return {norm(f.word) for q in morph().parse(x) if "Name" in _tags(q) for f in q.lexeme}

    return a in forms(b) or b in forms(a)


def compatible(a: Name, b: Name) -> bool:
    """Whether two mentions can refer to the same person."""
    if a.gender and b.gender and a.gender != b.gender:
        return False
    if a.surname and b.surname and a.surname != b.surname:
        return False
    if a.first and b.first and a.first != b.first and not _same_first_name(a.first, b.first):
        # the same surname and patronymic and the same beginning of the first name: one person
        # whose first name the text misspelt or misdeclined ("Милованного", "Баженам")
        same_rest = a.surname and a.surname == b.surname and a.patronymic and a.patronymic == b.patronymic
        if not (same_rest and a.first[:4] == b.first[:4]):
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


# Proxy first names, one per declension class, rare enough not to clash with the text.
_PROXIES = {
    "masc_consonant": ["Агафон", "Филимон", "Ерофей"],
    "masc_й": ["Евсей", "Тимофей"],
    "fem_а": ["Глафира", "Таисия"],
    "fem_я": ["Олимпия", "Евдокия"],
}


def _known_first_name(word: str) -> bool:
    return any(
        "Name" in _tags(q) and q.tag.case == "nomn" and q.tag.number == "sing" and norm(q.word) == norm(word)
        for q in morph().parse(cap(word))
    )


def _declension(word: str, gender: str) -> str | None:
    low = norm(word)
    if gender == "female":
        return "fem_я" if low.endswith("я") else "fem_а" if low.endswith("а") else None
    if low.endswith("й"):
        return "masc_й"
    if re.search(r"[бвгджзклмнпрстфхцчшщ]$", low):
        return "masc_consonant"
    return None


def proxy_first_names(tagmap: dict[str, str], text: str) -> dict[str, tuple[str, tuple[str, str]]]:
    """For each name tag whose first name the dictionary does not know: the value with a proxy first
    name of the same declension, and (proxy, real) first names to carry the endings back."""
    out: dict = {}
    used: set[str] = set()
    for tag, value in tagmap.items():
        n = parse(value, RU)
        if not n.first or _known_first_name(n.first):
            continue
        gender = "female" if 'gender="female"' in tag else "male" if 'gender="male"' in tag else n.gender
        cls = _declension(n.first, gender)
        if not cls:
            continue
        real = next((w for w in re.findall(r"[А-ЯЁа-яё-]+", value) if norm(w) == n.first), None)
        proxy = next((p for p in _PROXIES[cls] if p[:-1].lower() not in text.lower() and p not in used), None)
        if real and proxy:
            used.add(proxy)
            out[tag] = (re.sub(rf"(?<![\w-]){re.escape(real)}(?![\w-])", proxy, value, count=1), (proxy, real))
    return out


def carry_back(text: str, proxies: dict) -> str:
    """Replace the inflected proxy first names by the real ones with the same ending."""
    for _tag, (_value, (proxy, real)) in proxies.items():
        if proxy[-1] in "аяй":
            stem_p, stem_r = proxy[:-1], real[:-1]
        else:
            stem_p, stem_r = proxy, real

        def sub(m: re.Match, stem_r: str = stem_r) -> str:
            end = m.group(1)
            if end == "ы" and stem_r[-1:].lower() in "гкхжшчщ":
                end = "и"  # spelling rule: "Фоки", not "Фокы"
            return stem_r + end

        text = re.sub(rf"(?<![\w-]){re.escape(stem_p)}(а|у|ом|е|ы|и|ой|ю|ей|ем|я|ий|)(?![\w-])", sub, text)
    return text


# Inflection of a stored Russian name for restoration. pii-guard decides the case from the
# syntax; the forms are built here. pii-guard took the first dictionary parse of each word, which
# for "Харитонов" is the plural of the first name "Харитон" ("Харитоны Дмитрий Измаилович").
_CASE = {"gen2": "gent", "acc2": "accs", "loc2": "loct", "voct": "nomn"}
_SURN_ENDINGS = {
    "male": {"nomn": "", "gent": "а", "datv": "у", "accs": "а", "ablt": "ым", "loct": "е"},
    "female": {"nomn": "а", "gent": "ой", "datv": "ой", "accs": "у", "ablt": "ой", "loct": "ой"},
}
_PATR_ENDINGS = {
    "male": {"nomn": "", "gent": "а", "datv": "у", "accs": "а", "ablt": "ем", "loct": "е"},
    "female": {"nomn": "а", "gent": "ы", "datv": "е", "accs": "у", "ablt": "ой", "loct": "е"},
}
# first names the dictionary does not know, by the last letters of the nominative
_FIRST_ENDINGS = {
    ("male", "й"): {"nomn": "й", "gent": "я", "datv": "ю", "accs": "я", "ablt": "ем", "loct": "е"},
    ("male", "а"): {"nomn": "а", "gent": "ы", "datv": "е", "accs": "у", "ablt": "ой", "loct": "е"},
    ("male", "я"): {"nomn": "я", "gent": "и", "datv": "е", "accs": "ю", "ablt": "ей", "loct": "е"},
    ("male", ""): {"nomn": "", "gent": "а", "datv": "у", "accs": "а", "ablt": "ом", "loct": "е"},
    ("female", "ия"): {"nomn": "ия", "gent": "ии", "datv": "ии", "accs": "ию", "ablt": "ией", "loct": "ии"},
    ("female", "я"): {"nomn": "я", "gent": "и", "datv": "е", "accs": "ю", "ablt": "ей", "loct": "е"},
    ("female", "а"): {"nomn": "а", "gent": "ы", "datv": "е", "accs": "у", "ablt": "ой", "loct": "е"},
}


def _keep_case(form: str, original: str, yo: bool = True) -> str:
    if yo:  # a dictionary form has its own ё ("Пётр" -> "Петра"); a form built by rule keeps it
        form = _restore_yo(form, original)
    if original.isupper() and len(original) > 1:
        return form.upper()
    return form[:1].upper() + form[1:] if original[:1].isupper() else form


def _first_endings(low: str, gender: str) -> tuple[str, dict] | None:
    if gender == "female":
        for end in ("ия", "я", "а"):
            if low.endswith(end):
                return end, _FIRST_ENDINGS[("female", end)]
        return None
    if low.endswith("й"):
        return "й", _FIRST_ENDINGS[("male", "й")]
    if low.endswith("а"):
        return "а", _FIRST_ENDINGS[("male", "а")]
    if low.endswith("я"):
        return "я", _FIRST_ENDINGS[("male", "я")]
    if re.search(r"[бвгджзклмнпрстфхцчшщ]$", low):
        return "", _FIRST_ENDINGS[("male", "")]
    return None


def _spell(word: str) -> str:
    """ "ы" after г/к/х/ж/ш/ч/щ is written "и": "Ольги", "Луки"."""
    return re.sub(r"(?<=[гкхжшчщ])ы$", "и", word)


def _dictionary_form(low: str, kind: str, case: str, gender: str) -> str | None:
    """The form from a singular nominative parse of this very word, of the right kind and gender."""
    g = {"male": "masc", "female": "femn"}.get(gender)
    for q in morph().parse(low):
        tags = _tags(q)
        if kind not in tags or "Fixd" in tags or q.tag.number != "sing" or q.tag.case != "nomn" or norm(q.word) != low:
            continue
        if g and g not in tags:
            continue
        f = q.inflect({case})
        if f:
            return f.word
    return None


def _name_gender(words: list[str]) -> str:
    for w in words:
        low = norm(w)
        if _PATR_END.search(low) or _PATR_SHORT_END.search(low):
            return "female" if re.search(r"(вна|чна)$", low) else "male"
    for w in words:
        m = _SURN_FAMILY.match(norm(w))
        if m and m.group("end") in ("", "а"):  # the stored value is a nominative
            return "male" if not m.group("end") else "female"
        if re.search(r"(ская|цкая|ая)$", norm(w)):
            return "female"
        if re.search(r"(ский|цкий)$", norm(w)):
            return "male"
    for w in words:
        low = norm(w)
        for q in morph().parse(low):
            tags = _tags(q)
            if "Name" in tags and q.tag.case == "nomn" and q.tag.number == "sing" and q.word == low:
                return "female" if "femn" in tags else "male"
    return ""


def inflect_word(word: str, case: str, gender: str, role: str) -> str:
    """One word of a stored (nominative) name in the given case, singular."""
    case = _CASE.get(case, case)
    low = norm(word)
    if case == "nomn" or not re.fullmatch(r"[а-яё-]+", low) or len(low) < 2:
        return word
    if "-" in low:  # a double-barrelled surname: each part on its own
        return "-".join(inflect_word(p, case, gender, role) for p in word.split("-"))
    # a dictionary form has its own ё ("Пётр" -> "Петра"); a form built by rule keeps the word's ё
    form, by_rule = None, False
    if role == "Surn":
        m = _SURN_FAMILY.match(low)
        if m and gender and (m.group("end") or "") == ("а" if gender == "female" else ""):
            form, by_rule = m.group("base") + _SURN_ENDINGS[gender][case], True
        else:
            form = _dictionary_form(low, "Surn", case, gender)
            if form is None and re.search(r"(ский|цкий|ская|цкая|ой|ый|ий|ая)$", low):
                form = _dictionary_form(low, "ADJF", case, gender)
            if form is None and gender == "male" and re.search(r"[бвгджзклмнпрстфхцчшщ]$", low):
                form, by_rule = low + _FIRST_ENDINGS[("male", "")][case], True  # "Шевчук" -> "Шевчука"
    elif role == "Patr":
        if gender and re.search(r"(ич|на)$", low):
            base = low[:-1] if gender == "female" else low
            end = _PATR_ENDINGS[gender][case]
            if gender == "male" and case == "ablt" and low.endswith("ьич"):
                end = "ом"  # "Ильич" -> "Ильичом"
            form, by_rule = base + end, True
        else:
            form = _dictionary_form(low, "Patr", case, gender)
    else:
        fe = _first_endings(low, gender)
        # women's names in -а/-я decline regularly; the dictionary gives odd forms for some ("Наиной")
        form = None if gender == "female" and fe else _dictionary_form(low, "Name", case, gender)
        if form is None and fe:
            end, table = fe
            form, by_rule = _spell(low[: len(low) - len(end)] + table[case]), True
    return _keep_case(form, word, yo=by_rule) if form else word


def inflect_name_tokens(tokens: list[str], case: str) -> str:
    """A stored nominative name in the given case: surname by rule, first name and patronymic by the
    dictionary in the singular of the name's gender, by rule when the dictionary does not know them."""
    words = [t for t in tokens if re.search(r"[А-Яа-яЁё]", t) and not _INITIALS.match(t)]
    gender = _name_gender(words)
    # the engine stores "Surname First Patronymic", "Surname I.O." or "First Patronymic"
    roles: dict[int, str] = {}
    patr = next((i for i, w in enumerate(words) if _PATR_END.search(norm(w)) or _PATR_SHORT_END.search(norm(w))), None)
    if patr is not None:
        roles[patr] = "Patr"
        if patr >= 1:
            roles[patr - 1] = "Name"
        if patr >= 2:
            roles[patr - 2] = "Surn"
    elif len(words) >= 2:
        roles[0], roles[1] = "Surn", "Name"
    elif words:
        low = norm(words[0])
        known = any("Name" in _tags(q) and q.word == low and q.tag.case == "nomn" for q in morph().parse(low))
        initials = len(words) < len([t for t in tokens if re.search(r"[А-Яа-яЁё]", t)])
        roles[0] = "Name" if known and not initials else "Surn"  # "Ирина" alone is a first name
    out, k = [], 0
    for t in tokens:
        if t not in words:
            out.append(t)
            continue
        out.append(inflect_word(t, case, gender, roles.get(k, "Surn")))
        k += 1
    return " ".join(out)


# The case of a restored name from the words right before it, where pii-guard's parse of the
# sentence often errs (held-out set 7: "Уважаемый Силиной Г.Э.", "1. Харитоны ...", "Кому: Ефимову").
_LEFT_CASE = [
    (re.compile(r"(?:уважаем(?:ый|ая|ые|ый\(ая\)|ый\(а\))|дорог(?:ой|ая|ие))[\s*]*$", re.I), "nomn"),
    (re.compile(r"(?:^|\n|\*)[\s*]*(?:кому|адресат|получатель)[\s*]*:[\s*]*$", re.I), "datv"),
    (
        re.compile(
            r"(?:^|\n|\*)[\s*]*(?:фио|ф\.\s?и\.\s?о\.|от|исполнитель|пациент(?:ка)?|работник|сотрудник|заявитель|"
            r"контактное лицо|законный представитель|представитель|свидетель|подпись|подписант)[\s*]*:[\s*]*$",
            re.I,
        ),
        "nomn",
    ),
    (re.compile(r"(?:^|\n)[\s*]*(?:\d{1,2}[.)]|[-•–])[\s*]*$"), "nomn"),  # a list item
    (re.compile(r"с уважением,?[\s*]*$", re.I), "nomn"),  # a signature
    (re.compile(r"(?:^|\n)[\s*]*$"), "nomn"),  # the start of a line
]


def case_from_left(left: str) -> str:
    """The case a name takes after these words, or "" when the syntax has to decide."""
    tail = left[-80:]
    for pattern, case in _LEFT_CASE:
        if pattern.search(tail):
            return case
    return ""
