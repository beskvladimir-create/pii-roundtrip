"""Разбор упоминаний людей и сопоставление их между собой.

Ключ человека не одно слово, а набор частей: фамилия в именительном падеже с учётом
рода, имя, отчество, инициалы, род. Два упоминания относятся к одному человеку,
только если все известные части согласованы. При неоднозначности (две «Ивановы»,
упоминание только по фамилии) лучше дать отдельную метку, чем слить разных людей:
слияние незаметно для пользователя и подставит в ответ не того человека.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache

TITLES = {"mr", "mrs", "ms", "miss", "dr", "sir", "lady", "prof", "professor", "господин", "госпожа", "г-н", "г-жа"}
ROLES = {
    # RU
    "ип", "гражданин", "гражданка", "истец", "истица", "ответчик", "ответчица", "заявитель", "заявительница",
    "арендатор", "арендодатель", "продавец", "покупатель", "заказчик", "исполнитель", "работник", "работодатель",
    "пациент", "пациентка", "свидетель", "представитель", "доверитель", "поверенный", "директор", "врач",
    "исп", "уважаемый", "уважаемая", "сторона",
    # EN
    "claimant", "defendant", "respondent", "applicant", "appellant", "witness", "patient", "tenant", "landlord",
    "employee", "employer", "buyer", "seller", "party", "dear", "signed", "the", "and", "of",
}
FEMALE_TITLES = {"mrs", "ms", "miss", "lady", "госпожа", "г-жа", "гражданка"}
MALE_TITLES = {"mr", "sir", "господин", "г-н", "гражданин"}

_INITIALS = re.compile(r"^(?:[A-ZА-ЯЁ]\.){1,3}$|^[A-ZА-ЯЁ]\.?$")
_WORD = re.compile(r"[A-Za-zА-Яа-яЁё][\w'’.-]*")


def norm(s: str) -> str:
    return s.lower().replace("ё", "е").replace("’", "'")


def cap(word: str) -> str:
    """«римский-корсаков» -> «Римский-Корсаков», «o'brien» -> «O'Brien»."""
    return "-".join("'".join(p[:1].upper() + p[1:].lower() for p in part.split("'")) for part in word.split("-"))


@lru_cache(maxsize=1)
def morph():
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


def _tags(p) -> set[str]:
    return set(str(p.tag).replace(" ", ",").split(","))


@dataclass
class Name:
    surname: str = ""  # нормализовано: именительный падеж, нижний регистр, ё->е
    first: str = ""
    patronymic: str = ""
    initials: str = ""  # первые буквы имени и отчества из записи вида «И.И.»
    gender: str = ""  # male / female / ""
    display: str = ""  # как показывать при восстановлении

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


_SURN_END = re.compile(r"(ов|ев|ёв|ин|ын|ский|цкий|ской|цкой|ова|ева|ёва|ина|ына|ская|цкая)(а|у|ым|ом|е|ой|ую|ых|ыми)?$")
_PATR_END = re.compile(r"(вич|вн|ичн|ьич)(а|у|ем|ом|е|ы|ой|ну|ам)?$")


def _ru_word_role(word: str) -> tuple[str, object | None]:
    """Определяет, чем является слово: имя, отчество или фамилия.

    Порядок важен: «Иванов» морфология разбирает и как имя («Иван» в притяжательной
    форме), поэтому окончания фамилий проверяются раньше имён."""
    w = cap(word)
    low = norm(w)
    parses = morph().parse(w)
    by = {k: next((p for p in parses if k in _tags(p)), None) for k in ("Patr", "Name", "Surn")}
    if by["Patr"] and _PATR_END.search(low):
        return "Patr", by["Patr"]
    if _SURN_END.search(low) and not (by["Name"] and not by["Surn"]):
        return "Surn", by["Surn"]
    if by["Name"]:
        return "Name", by["Name"]
    if by["Surn"]:
        return "Surn", by["Surn"]
    return "Surn", None  # слово вне словаря: скорее всего редкая фамилия


def _gender_from_surname(s: str) -> str:
    s = norm(s)
    if re.search(r"(ова|ева|ина|ына|ая|ская|цкая)$", s):
        return "female"
    if re.search(r"(ов|ев|ин|ын|ий|ский|цкий|ой)$", s):
        return "male"
    return ""


def _nominative(word: str, p, gender: str) -> str:
    """Именительный падеж в нижнем регистре, буква ё сохраняется (для показа)."""
    if p is None:
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
    """pymorphy возвращает «петр»; если в исходном слове было ё, возвращаем его."""
    if "ё" in original.lower() and "ё" not in form:
        i = original.lower().find("ё")
        if i < len(form) and form[i] == "е":
            return form[:i] + "ё" + form[i + 1 :]
    return form


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
    if lang == "ru":
        roles = [(w,) + _ru_word_role(w) for w in words]
        g = ""
        for w, kind, p in roles:
            if kind == "Patr":
                g = "female" if norm(w).endswith(("вна", "чна", "вны", "вне", "вной", "вну", "чны", "чне", "чной", "чну")) else "male"
                break
        if not g:
            for w, kind, p in roles:
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
        for w, kind, p in roles:
            nom = _nominative(w, p, n.gender)
            if kind == "Patr" and not n.patronymic:
                n.patronymic, shown["p"] = norm(nom), nom
            elif kind == "Name" and not n.first:
                n.first, shown["f"] = norm(nom), nom
            elif not n.surname:
                n.surname, shown["s"] = norm(nom), nom
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
    """Могут ли два упоминания относиться к одному человеку."""
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
    # без общей фамилии допускаем совпадение только по полному имени
    if not (a.surname and b.surname) and not (a.first and b.first):
        return False
    return True


def merge_into(base: Name, other: Name) -> Name:
    for f in ("surname", "first", "patronymic", "gender"):
        if not getattr(base, f) and getattr(other, f):
            setattr(base, f, getattr(other, f))
    if len(other.initials) > len(base.initials):
        base.initials = other.initials
    if other.richness() > base.richness() or (other.richness() == base.richness() and len(other.display) > len(base.display)):
        base.display = other.display
    return base
