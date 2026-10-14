import random

import pytest

from generator import ids

N = 2000


# Публично известные корректные номера: проверяют валидаторы независимо от генераторов.
@pytest.mark.parametrize(
    "fn, value",
    [
        (ids.is_valid_inn, "7707083893"),  # ИНН ПАО Сбербанк
        (ids.is_valid_snils, "112-233-445 95"),  # пример из описания алгоритма
        (ids.is_valid_nhs, "943 476 5919"),  # пример NHS Digital
        (ids.is_valid_iban, "GB82 WEST 1234 5698 7654 32"),  # пример из ISO 13616
        (ids.is_valid_card, "4111 1111 1111 1111"),  # тестовая карта Visa
        (ids.is_valid_nino, "AB 12 34 56 C"),
    ],
)
def test_known_valid(fn, value):
    assert fn(value)


@pytest.mark.parametrize(
    "fn, value",
    [
        (ids.is_valid_inn, "7707083894"),
        (ids.is_valid_snils, "112-233-445 96"),
        (ids.is_valid_nhs, "943 476 5918"),
        (ids.is_valid_iban, "GB83 WEST 1234 5698 7654 32"),
        (ids.is_valid_card, "4111 1111 1111 1112"),
        (ids.is_valid_nino, "QQ 12 34 56 C"),  # Q недопустима первой
        (ids.is_valid_nino, "GB 12 34 56 C"),  # запрещённый префикс
        (ids.is_valid_nino, "AB 12 34 56 E"),  # суффикс только A-D
    ],
)
def test_known_invalid(fn, value):
    assert not fn(value)


GENERATORS = [
    ("inn10", ids.gen_inn10, ids.is_valid_inn, 10),
    ("inn12", ids.gen_inn12, ids.is_valid_inn, 12),
    ("snils", ids.gen_snils, ids.is_valid_snils, 11),
    ("passport_ru", ids.gen_passport_ru, ids.is_valid_passport_ru, 10),
    ("nhs", ids.gen_nhs, ids.is_valid_nhs, 10),
    ("nino", ids.gen_nino, ids.is_valid_nino, 9),
    ("card", ids.gen_card, ids.is_valid_card, 16),
    ("iban_gb", ids.gen_iban_gb, ids.is_valid_iban, 22),
]


@pytest.mark.parametrize("name, gen, valid, length", GENERATORS)
def test_generated_are_valid(name, gen, valid, length):
    rng = random.Random(42)
    for _ in range(N):
        v = gen(rng)
        assert len(v) == length, v
        assert valid(v), v


@pytest.mark.parametrize("name, gen, valid, length", GENERATORS)
def test_deterministic(name, gen, valid, length):
    a = [gen(random.Random(7)) for _ in range(5)]
    b = [gen(random.Random(7)) for _ in range(5)]
    assert a == b


CHECKED = [g for g in GENERATORS if g[0] not in ("passport_ru", "nino")]


@pytest.mark.parametrize("name, gen, valid, length", CHECKED)
def test_wrong_check_digit_rejected(name, gen, valid, length):
    rng = random.Random(1)
    for _ in range(N):
        v = gen(rng)
        last = v[-1]
        for d in "0123456789":
            if d != last:
                assert not valid(v[:-1] + d), (v, d)


def test_card_schemes():
    rng = random.Random(3)
    assert ids.gen_card(rng, "visa").startswith("4")
    assert ids.gen_card(rng, "mir")[:3] == "220"
    assert 51 <= int(ids.gen_card(rng, "mastercard")[:2]) <= 55


def test_card_luhn_catches_single_digit_errors():
    rng = random.Random(5)
    for _ in range(200):
        v = ids.gen_card(rng)
        for i in range(16):
            for d in "0123456789":
                if d != v[i]:
                    assert not ids.is_valid_card(v[:i] + d + v[i + 1 :])


def test_iban_catches_single_char_errors():
    rng = random.Random(6)
    for _ in range(200):
        v = ids.gen_iban_gb(rng)
        for i in range(4, len(v)):
            if v[i].isdigit():
                for d in "0123456789":
                    if d != v[i]:
                        assert not ids.is_valid_iban(v[:i] + d + v[i + 1 :])


def test_rs_key():
    rng = random.Random(9)
    for _ in range(N):
        bik = ids.gen_bik(rng)
        rs = ids.gen_rs(rng, bik)
        assert len(rs) == 20 and rs[5:8] == "810"
        assert ids.is_valid_rs(rs, bik)
        wrong = rs[:8] + str((int(rs[8]) + 1) % 10) + rs[9:]
        assert not ids.is_valid_rs(wrong, bik)


@pytest.mark.parametrize(
    "kind, gen, valid",
    [
        ("inn", ids.gen_inn10, ids.is_valid_inn),
        ("snils", ids.gen_snils, ids.is_valid_snils),
        ("passport_ru", ids.gen_passport_ru, ids.is_valid_passport_ru),
        ("nhs", ids.gen_nhs, ids.is_valid_nhs),
        ("nino", ids.gen_nino, ids.is_valid_nino),
        ("card", ids.gen_card, ids.is_valid_card),
        ("iban", ids.gen_iban_gb, ids.is_valid_iban),
    ],
)
def test_format_variants_stay_valid(kind, gen, valid):
    rng = random.Random(11)
    for _ in range(100):
        for variant in ids.format_variants(kind, gen(rng)):
            assert valid(variant), variant
