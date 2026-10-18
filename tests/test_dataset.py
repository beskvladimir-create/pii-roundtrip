import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from bench.generator import ids
from bench.generator.generate import generate
from bench.generator.render import STRUCTURED, ids_canonical


@pytest.fixture(scope="module")
def data():
    return generate(seed=123)


VALIDATORS = {
    "INN": ids.is_valid_inn,
    "SNILS": ids.is_valid_snils,
    "PASSPORT_RU": ids.is_valid_passport_ru,
    "NHS": ids.is_valid_nhs,
    "NINO": ids.is_valid_nino,
    "CARD": ids.is_valid_card,
    "IBAN": ids.is_valid_iban,
}


def test_counts(data):
    for docs in data.values():
        assert len(docs) == 100
        assert set(Counter(d["doc_type"] for d in docs).values()) == {20}
        assert len({d["id"] for d in docs}) == 100


def test_spans_match_text(data):
    for docs in data.values():
        for d in docs:
            prev_end = 0
            for e in d["entities"]:
                assert d["text"][e["start"] : e["end"]] == e["value"], (d["id"], e)
                assert e["start"] >= prev_end, (d["id"], e)  # без перекрытий
                prev_end = e["end"]


def test_structured_density(data):
    want = {
        "ru": {"PASSPORT_RU", "SNILS", "INN", "BANK_ACCOUNT_RU", "CARD"},
        "uk": {"NHS", "NINO", "CARD", "IBAN"},
    }
    for lang, docs in data.items():
        c = Counter(e["type"] for d in docs for e in d["entities"])
        for t in want[lang]:
            assert c[t] >= 300, (lang, t, c[t])


def test_structured_values_valid(data):
    for docs in data.values():
        for d in docs:
            for e in d["entities"]:
                if e["type"] in VALIDATORS:
                    assert VALIDATORS[e["type"]](e["value"]), e
                if e["type"] in STRUCTURED:
                    assert ids_canonical(e["type"], e["value"]) == e["canonical"], e


def test_russian_names_in_cases(data):
    persons = [e for d in data["ru"] for e in d["entities"] if e["type"] == "PERSON"]
    inflected = [e for e in persons if e["value"] != e["canonical"]]
    assert len(inflected) / len(persons) > 0.3
    assert any("." in e["value"] for e in persons)  # формы вида «Иванов И.И.»


def test_noise_present(data):
    for docs in data.values():
        share = sum(d["noisy"] for d in docs) / len(docs)
        assert 0.2 < share < 0.6


def test_deterministic():
    a = generate(seed=5, per_type=2)
    b = generate(seed=5, per_type=2)
    assert a == b
    assert generate(seed=6, per_type=2) != a


def test_hard_formats_in_holdout_generation():
    import re

    data = generate(seed=99, per_type=4, hard=1.0)
    vals = [e for docs in data.values() for d in docs for e in d["entities"] if e["type"] in STRUCTURED]
    assert any(re.search(r"[а-я]{3}", e["value"]) for e in vals)  # словами
    assert any("." in e["value"] for e in vals)  # через точки
    for docs in data.values():
        for d in docs:
            for e in d["entities"]:
                assert d["text"][e["start"] : e["end"]] == e["value"]


@pytest.mark.parametrize(
    "folder,kwargs", [("holdout", {"seed": 20261013}), ("holdout2", {"seed": 20261014, "hard": 0.3})]
)
def test_generator_reproduces_frozen_holdouts(folder, kwargs):
    """The generator must not depend on the day it runs: the frozen sets regenerate byte for byte."""
    holdout = (Path(__file__).resolve().parents[1] / "HOLDOUT.md").read_text(encoding="utf-8")
    expected = dict(re.findall(r"\| data/" + folder + r"/(\w+)\.jsonl \| `([0-9a-f]{64})` \|", holdout))
    for lang, docs in generate(**kwargs).items():
        body = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs).encode("utf-8")
        assert hashlib.sha256(body).hexdigest() == expected[lang], f"{folder}/{lang}"
