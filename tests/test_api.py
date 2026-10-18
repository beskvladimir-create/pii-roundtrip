"""Public API contracts: language codes, session format, errors, checksum validators."""

import random
import warnings

import pytest

from pii_roundtrip import Session, SessionError, UnsupportedLanguageError
from pii_roundtrip import checksums as c
from pii_roundtrip.core import Engine
from pii_roundtrip.detect import Models
from pii_roundtrip.langs import canonical


def test_language_codes():
    assert canonical("ru") == "ru" and canonical("en-GB") == "en-GB" and canonical("en") == "en-GB"
    with pytest.warns(DeprecationWarning, match="Ukrainian"):
        assert canonical("uk") == "en-GB"
    with pytest.raises(UnsupportedLanguageError):
        canonical("de")


def test_session_round_trip_and_format_version():
    eng = Engine(Models(use_pii_guard=False, use_gliner=False))
    _, s = eng.anonymize("Mr John Smith, NI AB 12 34 56 C", "en-GB")
    d = s.to_dict()
    assert Session.from_dict(d).mapping == s.mapping
    d["people"][0][1]["future_field"] = 1  # unknown fields from a newer minor version are ignored
    assert Session.from_dict(d).mapping == s.mapping
    with pytest.raises(SessionError):
        Session.from_dict({**d, "version": 99})


def test_old_uk_sessions_load_without_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert Session.from_dict({"version": 2, "lang": "uk", "mapping": {}}).lang == "en-GB"


def test_session_language_mismatch_is_a_session_error():
    eng = Engine(Models(use_pii_guard=False, use_gliner=False))
    _, s = eng.anonymize("Mr John Smith", "en-GB")
    with pytest.raises(SessionError):
        eng.anonymize("Иванов", "ru", s)


def test_failed_anonymize_leaves_session_unchanged(monkeypatch):
    eng = Engine(Models(use_pii_guard=False, use_gliner=False))
    _, s = eng.anonymize("Mr John Smith", "en-GB")
    before = s.to_dict()

    def boom(*a, **k):
        raise RuntimeError("detector failure")

    monkeypatch.setattr(eng, "spans", boom)
    with pytest.raises(RuntimeError):
        eng.anonymize("Mr [PERSON_9] and Mrs Mary Jones", "en-GB", s)
    assert s.to_dict() == before


VALID = {
    c.is_valid_inn: ["7707083893", "500100732259"],
    c.is_valid_snils: ["112-233-445 95"],
    c.is_valid_nhs: ["943 476 5919"],
    c.is_valid_nino: ["AB 12 34 56 C"],
    c.is_valid_card: ["4111 1111 1111 1111"],
    c.is_valid_iban: ["GB82 WEST 1234 5698 7654 32"],
}


@pytest.mark.parametrize("fn", list(VALID))
def test_checksums_known_values(fn):
    for v in VALID[fn]:
        assert fn(v), v
    if fn is c.is_valid_nino:
        # NINO has no check digit; only the format and the prefix are checked
        assert not fn("BG 12 34 56 C") and not fn("AB 12 34 56 E")
        return
    v = VALID[fn][0]
    i = max(i for i, ch in enumerate(v) if ch.isdigit())
    assert not fn(v[:i] + str((int(v[i]) + 1) % 10) + v[i + 1 :])


def test_library_validators_match_generator():
    from bench.generator import ids

    rng = random.Random(3)
    for gen, name in [
        (ids.gen_inn12, "is_valid_inn"),
        (ids.gen_snils, "is_valid_snils"),
        (ids.gen_nhs, "is_valid_nhs"),
        (ids.gen_nino, "is_valid_nino"),
        (ids.gen_card, "is_valid_card"),
        (ids.gen_iban_gb, "is_valid_iban"),
    ]:
        for _ in range(300):
            v = gen(rng)
            assert getattr(c, name)(v)
