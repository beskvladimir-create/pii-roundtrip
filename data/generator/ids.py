"""Генераторы и валидаторы структурированных номеров с контрольными суммами.

Все генераторы принимают random.Random, чтобы набор был детерминированным.
Генераторы возвращают канонический вид без разделителей; варианты записи
с разделителями даёт format_variants().
"""

from __future__ import annotations

import random
import string

# ---------- общие ----------


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def _only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


# ---------- ИНН ----------

_INN10_W = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN11_W = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_W = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _inn_check(digits: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(d) * w for d, w in zip(digits, weights)) % 11 % 10)


def gen_inn10(rng: random.Random) -> str:
    """ИНН юридического лица (10 знаков)."""
    region = f"{rng.randint(1, 99):02d}"
    body = region + _digits(rng, 7)
    return body + _inn_check(body, _INN10_W)


def gen_inn12(rng: random.Random) -> str:
    """ИНН физического лица (12 знаков)."""
    region = f"{rng.randint(1, 99):02d}"
    body = region + _digits(rng, 8)
    body += _inn_check(body, _INN11_W)
    return body + _inn_check(body, _INN12_W)


def is_valid_inn(value: str) -> bool:
    d = _only_digits(value)
    if len(d) == 10:
        return d[9] == _inn_check(d[:9], _INN10_W)
    if len(d) == 12:
        return d[10] == _inn_check(d[:10], _INN11_W) and d[11] == _inn_check(
            d[:11], _INN12_W
        )
    return False


# ---------- СНИЛС ----------


def _snils_check(body: str) -> str:
    s = sum(int(d) * w for d, w in zip(body, range(9, 0, -1)))
    if s < 100:
        return f"{s:02d}"
    if s in (100, 101):
        return "00"
    r = s % 101
    return "00" if r == 100 else f"{r:02d}"


def gen_snils(rng: random.Random) -> str:
    """СНИЛС, 11 цифр. Контрольная сумма определена для номеров больше 001-001-998."""
    while True:
        body = _digits(rng, 9)
        if int(body) > 1001998 and not _has_triple_repeat(body):
            return body + _snils_check(body)


def _has_triple_repeat(body: str) -> bool:
    return any(body[i] == body[i + 1] == body[i + 2] for i in range(len(body) - 2))


def is_valid_snils(value: str) -> bool:
    d = _only_digits(value)
    return len(d) == 11 and d[9:] == _snils_check(d[:9])


# ---------- паспорт РФ ----------

# Коды субъектов по ОКАТО, которые используются в серии паспорта (выборка).
_OKATO = (
    "01", "03", "04", "05", "07", "08", "10", "11", "12", "14", "15", "17",
    "18", "19", "20", "22", "24", "25", "26", "27", "28", "29", "32", "33",
    "34", "36", "37", "38", "40", "41", "42", "44", "45", "46", "47", "49",
    "50", "52", "53", "54", "56", "57", "58", "60", "61", "63", "64", "65",
    "66", "68", "69", "70", "71", "73", "75", "76", "77", "78", "79", "80",
    "81", "82", "83", "84", "85", "86", "87", "88", "89", "90", "92", "93",
    "94", "95", "96", "97", "98", "99",
)


def gen_passport_ru(rng: random.Random, issue_year: int | None = None) -> str:
    """Паспорт РФ: серия (код региона + год изготовления бланка) и номер. Контрольной суммы нет."""
    year = rng.randint(1997, 2025) if issue_year is None else issue_year - rng.randint(0, 2)
    series = rng.choice(_OKATO) + f"{max(year, 1997) % 100:02d}"
    number = f"{rng.randint(100001, 999999)}"
    return series + number


def is_valid_passport_ru(value: str) -> bool:
    d = _only_digits(value)
    return len(d) == 10 and d[:2] in _OKATO


# ---------- расчётный счёт и БИК ----------

_RS_W = (7, 1, 3)


def gen_bik(rng: random.Random) -> str:
    """БИК банка: 04 + код региона + номер подразделения + условный номер >= 050."""
    return "04" + rng.choice(_OKATO) + f"{rng.randint(0, 99):02d}" + f"{rng.randint(50, 999):03d}"


def _rs_sum(bik: str, account: str) -> int:
    s = bik[-3:] + account
    return sum(int(d) * _RS_W[i % 3] for i, d in enumerate(s))


def gen_rs(rng: random.Random, bik: str) -> str:
    """Расчётный счёт (20 цифр) с контрольным ключом в 9-й позиции."""
    prefix = rng.choice(("40702", "40701", "40802", "40817"))
    account = prefix + "810" + "0" + _digits(rng, 11)
    key = (_rs_sum(bik, account) % 10) * 3 % 10
    return account[:8] + str(key) + account[9:]


def is_valid_rs(account: str, bik: str) -> bool:
    a, b = _only_digits(account), _only_digits(bik)
    return len(a) == 20 and len(b) == 9 and _rs_sum(b, a) % 10 == 0


# ---------- NHS number ----------


def _nhs_check(body: str) -> int:
    r = sum(int(d) * w for d, w in zip(body, range(10, 1, -1))) % 11
    return 11 - r  # 11 означает 0, 10 означает недопустимый номер


def gen_nhs(rng: random.Random) -> str:
    """NHS number, 10 цифр, контрольная сумма по модулю 11."""
    while True:
        body = str(rng.randint(4, 9)) + _digits(rng, 8)
        c = _nhs_check(body)
        if c == 10:
            continue
        return body + ("0" if c == 11 else str(c))


def is_valid_nhs(value: str) -> bool:
    d = _only_digits(value)
    if len(d) != 10:
        return False
    c = _nhs_check(d[:9])
    return c != 10 and d[9] == ("0" if c == 11 else str(c))


# ---------- National Insurance number ----------

_NINO_BAD_FIRST = set("DFIQUV")
_NINO_BAD_SECOND = set("DFIOQUV")
_NINO_BAD_PREFIX = {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}
_NINO_FIRST = [c for c in string.ascii_uppercase if c not in _NINO_BAD_FIRST]
_NINO_SECOND = [c for c in string.ascii_uppercase if c not in _NINO_BAD_SECOND]


def gen_nino(rng: random.Random) -> str:
    """NI number: две буквы с допустимым префиксом, 6 цифр, суффикс A-D."""
    while True:
        prefix = rng.choice(_NINO_FIRST) + rng.choice(_NINO_SECOND)
        if prefix not in _NINO_BAD_PREFIX:
            return prefix + _digits(rng, 6) + rng.choice("ABCD")


def is_valid_nino(value: str) -> bool:
    v = "".join(value.split()).upper()
    return (
        len(v) == 9
        and v[0] not in _NINO_BAD_FIRST
        and v[1] not in _NINO_BAD_SECOND
        and v[0].isalpha()
        and v[1].isalpha()
        and v[:2] not in _NINO_BAD_PREFIX
        and v[2:8].isdigit()
        and v[8] in "ABCD"
    )


# ---------- банковская карта ----------


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
    """Карта из 16 цифр с проверкой по Луну. Схемы: visa, mastercard, mir."""
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


def is_valid_card(value: str) -> bool:
    d = _only_digits(value)
    return 13 <= len(d) <= 19 and _luhn_sum(d) % 10 == 0


# ---------- IBAN ----------


def _iban_numeric(s: str) -> int:
    return int("".join(str(int(c, 36)) for c in s))


def _iban_check_digits(country: str, bban: str) -> str:
    return f"{98 - _iban_numeric(bban + country + '00') % 97:02d}"


def gen_iban_gb(rng: random.Random) -> str:
    """Британский IBAN: GBkk + 4 буквы банка + sort code (6) + счёт (8)."""
    bank = "".join(rng.choice(string.ascii_uppercase) for _ in range(4))
    bban = bank + _digits(rng, 6) + _digits(rng, 8)
    return "GB" + _iban_check_digits("GB", bban) + bban


def is_valid_iban(value: str) -> bool:
    v = "".join(value.split()).upper()
    if len(v) < 15 or not v[:2].isalpha() or not v[2:4].isdigit() or not v.isalnum():
        return False
    return _iban_numeric(v[4:] + v[:4]) % 97 == 1


# ---------- варианты записи (шум) ----------


def format_variants(kind: str, value: str) -> list[str]:
    """Типичные варианты записи номера в документах. Первый вариант канонический."""
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
