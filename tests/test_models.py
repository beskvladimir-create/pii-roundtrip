"""Tests with the real models. They need the models in the local cache:
run `pii-roundtrip download-models` once, then `pytest -m models`."""

import socket

import pytest

pytestmark = pytest.mark.models


@pytest.fixture(scope="module")
def engine():
    from pii_roundtrip import Engine

    return Engine()


def test_works_without_network(engine, monkeypatch):
    real = socket.socket.connect

    def guard(self, addr):
        if isinstance(addr, tuple) and addr[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"network access to {addr}")
        return real(self, addr)

    monkeypatch.setattr(socket.socket, "connect", guard)
    text, _ = engine.anonymize("Договор с Ивановым Петром Сергеевичем, СНИЛС 112-233-445 95.", "ru")
    assert "Иванов" not in text and "112-233" not in text
    text, _ = engine.anonymize("Dear Mr John Smith, NHS 943 476 5919.", "en-GB")
    assert "Smith" not in text and "943" not in text


def test_pii_guard_inflection_contract(engine):
    """Pinned pii-guard: our tag format and deanonymize_batch signature still work."""
    _, s = engine.anonymize("Арендатор Иванов Пётр Сергеевич подписал договор.", "ru")
    out = engine.deanonymize("Договор заключён с [PERSON_1].", s)
    assert out == "Договор заключён с Ивановым Петром Сергеевичем."
