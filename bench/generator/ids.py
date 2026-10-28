"""Generators and validators for structured identifiers with checksums.

All generators take a random.Random so that the set is deterministic.
Generators return the canonical form without separators; format_variants()
gives the written variants with separators.
"""

from __future__ import annotations

import random
import string

# Validators are shared with the library, so that there is one implementation of each checksum.
from pii_roundtrip.checksums import (  # noqa: F401
    is_valid_card,
    is_valid_iban,
    is_valid_inn,
    is_valid_nhs,
    is_valid_nino,
    is_valid_passport_ru,
    is_valid_rs,
    is_valid_snils,
)

# ---------- common ----------


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


# ---------- INN ----------

_INN10_W = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN11_W = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_W = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _inn_check(digits: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(d) * w for d, w in zip(digits, weights, strict=False)) % 11 % 10)


def gen_inn10(rng: random.Random) -> str:
    """INN of a legal entity (10 digits)."""
    region = f"{rng.randint(1, 99):02d}"
    body = region + _digits(rng, 7)
    return body + _inn_check(body, _INN10_W)


def gen_inn12(rng: random.Random) -> str:
    """INN of an individual (12 digits)."""
    region = f"{rng.randint(1, 99):02d}"
    body = region + _digits(rng, 8)
    body += _inn_check(body, _INN11_W)
    return body + _inn_check(body, _INN12_W)


# ---------- SNILS ----------


def _snils_check(body: str) -> str:
    s = sum(int(d) * w for d, w in zip(body, range(9, 0, -1), strict=False))
    if s < 100:
        return f"{s:02d}"
    if s in (100, 101):
        return "00"
    r = s % 101
    return "00" if r == 100 else f"{r:02d}"


def gen_snils(rng: random.Random) -> str:
    """SNILS, 11 digits. The checksum is defined for numbers greater than 001-001-998."""
    while True:
        body = _digits(rng, 9)
        if int(body) > 1001998 and not _has_triple_repeat(body):
            return body + _snils_check(body)


def _has_triple_repeat(body: str) -> bool:
    return any(body[i] == body[i + 1] == body[i + 2] for i in range(len(body) - 2))


# ---------- Russian passport ----------

# OKATO codes of federal subjects that are used in the passport series (a sample).
_OKATO = (
    "01",
    "03",
    "04",
    "05",
    "07",
    "08",
    "10",
    "11",
    "12",
    "14",
    "15",
    "17",
    "18",
    "19",
    "20",
    "22",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "32",
    "33",
    "34",
    "36",
    "37",
    "38",
    "40",
    "41",
    "42",
    "44",
    "45",
    "46",
    "47",
    "49",
    "50",
    "52",
    "53",
    "54",
    "56",
    "57",
    "58",
    "60",
    "61",
    "63",
    "64",
    "65",
    "66",
    "68",
    "69",
    "70",
    "71",
    "73",
    "75",
    "76",
    "77",
    "78",
    "79",
    "80",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "87",
    "88",
    "89",
    "90",
    "92",
    "93",
    "94",
    "95",
    "96",
    "97",
    "98",
    "99",
)


def gen_passport_ru(rng: random.Random, issue_year: int | None = None) -> str:
    """Russian passport: series (region code + year the blank was made) and number. No checksum."""
    year = rng.randint(1997, 2025) if issue_year is None else issue_year - rng.randint(0, 2)
    series = rng.choice(_OKATO) + f"{max(year, 1997) % 100:02d}"
    number = f"{rng.randint(100001, 999999)}"
    return series + number


# ---------- settlement account and BIK ----------

_RS_W = (7, 1, 3)


def gen_bik(rng: random.Random) -> str:
    """Bank BIK: 04 + region code + branch number + conventional number >= 050."""
    return "04" + rng.choice(_OKATO) + f"{rng.randint(0, 99):02d}" + f"{rng.randint(50, 999):03d}"


def _rs_sum(bik: str, account: str) -> int:
    s = bik[-3:] + account
    return sum(int(d) * _RS_W[i % 3] for i, d in enumerate(s))


def gen_rs(rng: random.Random, bik: str) -> str:
    """Settlement account (20 digits) with the check key in the 9th position."""
    prefix = rng.choice(("40702", "40701", "40802", "40817"))
    account = prefix + "810" + "0" + _digits(rng, 11)
    key = (_rs_sum(bik, account) % 10) * 3 % 10
    return account[:8] + str(key) + account[9:]


# ---------- NHS number ----------


def _nhs_check(body: str) -> int:
    r = sum(int(d) * w for d, w in zip(body, range(10, 1, -1), strict=False)) % 11
    return 11 - r  # 11 means 0, 10 means an invalid number


def gen_nhs(rng: random.Random) -> str:
    """NHS number, 10 digits, modulo-11 checksum."""
    while True:
        body = str(rng.randint(4, 9)) + _digits(rng, 8)
        c = _nhs_check(body)
        if c == 10:
            continue
        return body + ("0" if c == 11 else str(c))


# ---------- National Insurance number ----------

_NINO_BAD_FIRST = set("DFIQUV")
_NINO_BAD_SECOND = set("DFIOQUV")
_NINO_BAD_PREFIX = {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}
_NINO_FIRST = [c for c in string.ascii_uppercase if c not in _NINO_BAD_FIRST]
_NINO_SECOND = [c for c in string.ascii_uppercase if c not in _NINO_BAD_SECOND]


def gen_nino(rng: random.Random) -> str:
    """NI number: two letters forming an allowed prefix, 6 digits, suffix A-D."""
    while True:
        prefix = rng.choice(_NINO_FIRST) + rng.choice(_NINO_SECOND)
        if prefix not in _NINO_BAD_PREFIX:
            return prefix + _digits(rng, 6) + rng.choice("ABCD")


# ---------- bank card ----------


def _luhn_sum(digits: str) -> int:
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total


def gen_card(rng: random.Random, scheme: str | None = None) -> str:
    """16-digit card with a Luhn check. Schemes: visa, mastercard, mir."""
    scheme = scheme or rng.choice(("visa", "mastercard", "mir"))
    if scheme == "visa":
        prefix = "4"
    elif scheme == "mastercard":
        prefix = str(rng.randint(51, 55))
    elif scheme == "mir":
        prefix = f"220{rng.randint(0, 4)}"
    else:
        raise ValueError(scheme)
    body = prefix + _digits(rng, 15 - len(prefix))
    check = (10 - _luhn_sum(body + "0") % 10) % 10
    return body + str(check)


# ---------- IBAN ----------


def _iban_numeric(s: str) -> int:
    return int("".join(str(int(c, 36)) for c in s))


def _iban_check_digits(country: str, bban: str) -> str:
    return f"{98 - _iban_numeric(bban + country + '00') % 97:02d}"


def gen_iban_gb(rng: random.Random) -> str:
    """British IBAN: GBkk + 4 bank letters + sort code (6) + account (8)."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    bban = bank + _digits(rng, 6) + _digits(rng, 8)
    return "GB" + _iban_check_digits("GB", bban) + bban


# ---------- written variants (noise) ----------


def format_variants(kind: str, value: str) -> list[str]:
    """Typical ways a number is written in documents. The first variant is canonical."""
    v = value
    if kind == "inn":
        return [v, " ".join([v[:4], v[4:]]) if len(v) == 10 else v]
    if kind == "snils":
        return [f"{v[:3]}-{v[3:6]}-{v[6:9]} {v[9:]}", f"{v[:3]}-{v[3:6]}-{v[6:9]}-{v[9:]}", v]
    if kind == "passport_ru":
        return [f"{v[:2]} {v[2:4]} {v[4:]}", f"{v[:4]} {v[4:]}", f"{v[:4]} № {v[4:]}", v]
    if kind == "rs":
        return [v, " ".join(v[i : i + 5] for i in range(0, 20, 5))]
    if kind == "nhs":
        return [f"{v[:3]} {v[3:6]} {v[6:]}", f"{v[:3]}-{v[3:6]}-{v[6:]}", v]
    if kind == "nino":
        return [f"{v[:2]} {v[2:4]} {v[4:6]} {v[6:8]} {v[8]}", v, f"{v[:2]}{v[2:8]} {v[8]}"]
    if kind == "card":
        return [" ".join(v[i : i + 4] for i in range(0, 16, 4)), "-".join(v[i : i + 4] for i in range(0, 16, 4)), v]
    if kind == "iban":
        return [" ".join(v[i : i + 4] for i in range(0, len(v), 4)), v]
    raise ValueError(kind)
