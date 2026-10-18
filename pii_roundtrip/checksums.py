"""Checksum validators from public specifications: Russian INN, SNILS, passport and bank
account (with the bank BIK key), UK NHS number (mod 11) and NI number (prefix rules),
bank cards (Luhn) and IBAN (mod 97)."""

from __future__ import annotations

import string


def _only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


_INN10_W = (2, 4, 10, 3, 5, 9, 4, 6, 8)


_INN11_W = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


_INN12_W = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _inn_check(digits: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(d) * w for d, w in zip(digits, weights, strict=False)) % 11 % 10)


def is_valid_inn(value: str) -> bool:
    d = _only_digits(value)
    if len(d) == 10:
        return d[9] == _inn_check(d[:9], _INN10_W)
    if len(d) == 12:
        return d[10] == _inn_check(d[:10], _INN11_W) and d[11] == _inn_check(d[:11], _INN12_W)
    return False


def _snils_check(body: str) -> str:
    s = sum(int(d) * w for d, w in zip(body, range(9, 0, -1), strict=False))
    if s < 100:
        return f"{s:02d}"
    if s in (100, 101):
        return "00"
    r = s % 101
    return "00" if r == 100 else f"{r:02d}"


def is_valid_snils(value: str) -> bool:
    d = _only_digits(value)
    return len(d) == 11 and d[9:] == _snils_check(d[:9])


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


def is_valid_passport_ru(value: str) -> bool:
    d = _only_digits(value)
    return len(d) == 10 and d[:2] in _OKATO


_RS_W = (7, 1, 3)


def _rs_sum(bik: str, account: str) -> int:
    s = bik[-3:] + account
    return sum(int(d) * _RS_W[i % 3] for i, d in enumerate(s))


def is_valid_rs(account: str, bik: str) -> bool:
    a, b = _only_digits(account), _only_digits(bik)
    return len(a) == 20 and len(b) == 9 and _rs_sum(b, a) % 10 == 0


def _nhs_check(body: str) -> int:
    r = sum(int(d) * w for d, w in zip(body, range(10, 1, -1), strict=False)) % 11
    return 11 - r  # 11 means 0, 10 means the number is invalid


def is_valid_nhs(value: str) -> bool:
    d = _only_digits(value)
    if len(d) != 10:
        return False
    c = _nhs_check(d[:9])
    return c != 10 and d[9] == ("0" if c == 11 else str(c))


_NINO_BAD_FIRST = set("DFIQUV")


_NINO_BAD_SECOND = set("DFIOQUV")


_NINO_BAD_PREFIX = {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}


_NINO_FIRST = [c for c in string.ascii_uppercase if c not in _NINO_BAD_FIRST]


_NINO_SECOND = [c for c in string.ascii_uppercase if c not in _NINO_BAD_SECOND]


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


def is_valid_card(value: str) -> bool:
    d = _only_digits(value)
    return 13 <= len(d) <= 19 and _luhn_sum(d) % 10 == 0


def _iban_numeric(s: str) -> int:
    return int("".join(str(int(c, 36)) for c in s))


def is_valid_iban(value: str) -> bool:
    v = "".join(value.split()).upper()
    if len(v) < 15 or not v[:2].isalpha() or not v[2:4].isdigit() or not v.isalnum():
        return False
    return _iban_numeric(v[4:] + v[:4]) % 97 == 1
