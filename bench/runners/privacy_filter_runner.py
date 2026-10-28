"""openai/privacy-filter via the official opf package: Viterbi decoding,
context up to 128k tokens (no chunking). 8 categories, no "organisation" type."""

from __future__ import annotations

from bench.runners.base import Runner, Span, map_spans, resolve_overlaps

TYPE_MAP = {
    "private_person": "PERSON",
    "private_address": "ADDRESS",
    "private_email": "EMAIL",
    "private_phone": "PHONE",
    "private_url": "URL",
    "private_date": "DATE",
    "account_number": "ACCOUNT_NUMBER",
    "secret": "SECRET",
}


class PrivacyFilterRunner(Runner):
    name = "privacy_filter"

    def __init__(self):
        from opf._api import OPF

        self.opf = OPF(device="cpu", decode_mode="viterbi", output_mode="typed")

    def config(self) -> dict:
        return {
            "package": "github.com/openai/privacy-filter (opf)",
            "commit": "f7f00ca7fb869683eb732c010299d901457f19c3",
            "model": "openai/privacy-filter",
            "decode_mode": "viterbi",
            "device": "cpu",
            "note": "нет типа ORG; account_number засчитывается для IBAN, карт, счетов в режиме masked",
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        r = self.opf.redact(text)
        spans = [Span(TYPE_MAP.get(s.label, s.label.upper()), s.start, s.end) for s in r.detected_spans]
        return resolve_overlaps(map_spans(spans, r.text, text))
