"""Синтетические лица и организации для RU и UK."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from functools import lru_cache

from faker import Faker

from bench.generator import ids

CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")


@lru_cache(maxsize=1)
def _morph():
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


# Faker draws some values (the year in an e-mail address, for example) between 1970 and
# "now", so with the real clock the output depends on the day of the run. The generator
# fixes "now" to a given date; each set records its date (see HOLDOUT.md).
DEFAULT_NOW = dt.date(2026, 10, 13)


def _fix_faker_now(day: dt.date) -> None:
    import faker.providers.date_time as faker_dates

    moment = dt.datetime(day.year, day.month, day.day)

    class FixedNow(dt.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return moment.replace(tzinfo=tz)

    faker_dates.datetime = FixedNow  # type: ignore[misc]


def _fakers(seed: int, now: dt.date) -> tuple[Faker, Faker]:
    _fix_faker_now(now)
    ru, uk = Faker("ru_RU"), Faker("en_GB")
    ru.seed_instance(seed)
    uk.seed_instance(seed + 1)
    return ru, uk


RU_MOBILE = (
    "900",
    "903",
    "905",
    "909",
    "910",
    "915",
    "916",
    "917",
    "920",
    "925",
    "926",
    "929",
    "950",
    "951",
    "952",
    "960",
    "961",
    "962",
    "977",
    "980",
    "985",
    "999",
)
RU_CITY = ("495", "499", "812", "343", "383", "843", "863", "846")


def phone_ru(r: random.Random, mobile: bool = True) -> str:
    """Телефон РФ из реально существующих кодов (Faker даёт несуществующие)."""
    code = r.choice(RU_MOBILE if mobile else RU_CITY)
    n = f"{r.randint(0, 9999999):07d}"
    a, b, c = n[:3], n[3:5], n[5:]
    return r.choice(
        (
            f"+7 {code} {a}-{b}-{c}",
            f"8 ({code}) {a}-{b}-{c}",
            f"+7{code}{n}",
            f"8-{code}-{a}-{b}-{c}",
            f"+7 ({code}) {a} {b} {c}",
        )
    )


def phone_uk(r: random.Random) -> str:
    """Телефон UK из диапазонов Ofcom, зарезервированных для художественных произведений.

    Мобильный 07700 900xxx и 01632 960xxx не используются: библиотека phonenumbers
    считает их недействительными, и инструменты были бы наказаны за артефакт набора.
    """
    x = f"{r.randint(0, 999):03d}"
    return r.choice(
        (
            f"020 7946 0{x}",
            f"+44 20 7946 0{x}",
            f"0{r.choice(('113', '114', '115', '116', '117', '118', '121', '131', '141', '151', '161'))} 496 0{x}",
            f"029 2018 0{x}",
        )
    )


def _add_years(d: dt.date, years: int) -> dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 февраля
        return d.replace(year=d.year + years, day=28)


def _cap(word: str, like: str) -> str:
    return word[:1].upper() + word[1:] if like[:1].isupper() else word


def inflect_ru(word: str, case: str, gender: str, kind: str) -> str:
    """Склоняет часть ФИО. kind: Surn, Name, Patr. При неудаче возвращает исходное."""
    if case == "nomn":
        return word
    if "-" in word:
        return "-".join(inflect_ru(w, case, gender, kind) for w in word.split("-"))
    parses = _morph().parse(word)
    candidates = [p for p in parses if kind in p.tag and gender in p.tag]
    candidates = candidates or [p for p in parses if kind in p.tag] or parses
    form = candidates[0].inflect({case})
    return _cap(form.word, word) if form else word


@dataclass
class PersonRU:
    last: str
    first: str
    middle: str
    gender: str  # masc / femn
    dob: dt.date
    passport: str
    passport_issued: dt.date
    snils: str
    inn: str
    card: str
    bik: str
    rs: str
    address: str
    phone: str
    email: str
    pid: str = ""

    def parts(self, case: str) -> tuple[str, str, str]:
        g = self.gender
        return (
            inflect_ru(self.last, case, g, "Surn"),
            inflect_ru(self.first, case, g, "Name"),
            inflect_ru(self.middle, case, g, "Patr"),
        )

    def fio(self, case: str = "nomn", form: str = "full") -> str:
        last, first, middle = self.parts(case)
        if form == "full":
            return f"{last} {first} {middle}"
        if form == "short":
            return f"{last} {self.first[0]}.{self.middle[0]}."
        if form == "short_space":
            return f"{last} {self.first[0]}. {self.middle[0]}."
        if form == "short_pre":
            return f"{self.first[0]}.{self.middle[0]}. {last}"
        if form == "first_middle":
            return f"{first} {middle}"
        if form == "first_last":
            return f"{first} {last}"
        raise ValueError(form)


@dataclass
class OrgRU:
    name: str
    inn: str
    ogrn: str
    bik: str
    rs: str
    address: str
    phone: str


@dataclass
class PersonUK:
    first: str
    last: str
    gender: str
    title: str
    dob: dt.date
    nino: str
    nhs: str
    card: str
    iban: str
    address: str
    postcode: str
    phone: str
    email: str
    pid: str = ""

    def name(self, form: str = "full") -> str:
        if form == "full":
            return f"{self.first} {self.last}"
        if form == "titled":
            return f"{self.title} {self.last}"
        if form == "titled_full":
            return f"{self.title} {self.first} {self.last}"
        if form == "initial":
            return f"{self.first[0]}. {self.last}"
        if form == "formal":
            return f"{self.last.upper()}, {self.first}"
        if form == "first":
            return self.first
        raise ValueError(form)


@dataclass
class OrgUK:
    name: str
    company_no: str
    address: str
    phone: str


@dataclass
class World:
    """Источник лиц и организаций с общим seed."""

    seed: int
    now: dt.date = DEFAULT_NOW
    rng: random.Random = field(init=False)

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.ru, self.uk = _fakers(self.seed, self.now)
        self._n = 0

    def _pid(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n:05d}"

    def _dob(self) -> dt.date:
        return dt.date(1950, 1, 1) + dt.timedelta(days=self.rng.randint(0, 365 * 55))

    def person_ru(self) -> PersonRU:
        r, f = self.rng, self.ru
        gender = r.choice(("masc", "femn"))
        if gender == "masc":
            last, first, middle = f.last_name_male(), f.first_name_male(), f.middle_name_male()
        else:
            last, first, middle = f.last_name_female(), f.first_name_female(), f.middle_name_female()
        dob = self._dob()
        bik = ids.gen_bik(r)
        translit = f.user_name()
        # паспорт РФ выдаётся с 01.10.1997; замена в 20 и 45 лет
        due = [_add_years(dob, a) for a in (14, 20, 45)]
        due = [d for d in due if dt.date(1997, 10, 1) <= d <= dt.date(2025, 12, 31)]
        issued = (due[-1] if due else dt.date(1997, 10, 1)) + dt.timedelta(days=r.randint(5, 60))
        return PersonRU(
            last=last,
            first=first,
            middle=middle,
            gender=gender,
            dob=dob,
            passport=ids.gen_passport_ru(r, issued.year),
            passport_issued=issued,
            snils=ids.gen_snils(r),
            inn=ids.gen_inn12(r),
            card=ids.gen_card(r, r.choice(("mir", "mir", "visa", "mastercard"))),
            bik=bik,
            rs=ids.gen_rs(r, bik),
            address=f.address().replace("\n", ", "),
            phone=phone_ru(r),
            email=f"{translit}@{f.free_email_domain()}",
            pid=self._pid("ru-p"),
        )

    def org_ru(self) -> OrgRU:
        r, f = self.rng, self.ru
        bik = ids.gen_bik(r)
        return OrgRU(
            name=f.company(),
            inn=ids.gen_inn10(r),
            ogrn=str(r.choice((1, 5))) + "".join(r.choice("0123456789") for _ in range(12)),
            bik=bik,
            rs=ids.gen_rs(r, bik),
            address=f.address().replace("\n", ", "),
            phone=phone_ru(r, mobile=False),
        )

    def person_uk(self) -> PersonUK:
        r, f = self.rng, self.uk
        gender = r.choice(("m", "f"))
        first = f.first_name_male() if gender == "m" else f.first_name_female()
        title = "Mr" if gender == "m" else r.choice(("Ms", "Mrs", "Miss"))
        postcode = f.postcode()
        addr = f"{f.building_number()} {f.street_name()}, {f.city()} {postcode}"
        return PersonUK(
            first=first,
            last=f.last_name(),
            gender=gender,
            title=title,
            dob=self._dob(),
            nino=ids.gen_nino(r),
            nhs=ids.gen_nhs(r),
            card=ids.gen_card(r, r.choice(("visa", "mastercard"))),
            iban=ids.gen_iban_gb(r),
            address=addr,
            postcode=postcode,
            phone=phone_uk(r),
            email=f.free_email(),
            pid=self._pid("uk-p"),
        )

    def org_uk(self) -> OrgUK:
        r, f = self.rng, self.uk
        return OrgUK(
            name=f.company(),
            company_no=f"{r.randint(1000000, 15999999):08d}",
            address=f"{f.building_number()} {f.street_name()}, {f.city()} {f.postcode()}",
            phone=phone_uk(r),
        )
