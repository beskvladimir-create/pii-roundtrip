"""GLiNER Guard Omni (hivetrace) through GLiNER2: detector for Russian and English."""

from __future__ import annotations

import threading

from pii_roundtrip.adapters._hub import local_snapshot
from pii_roundtrip.errors import ModelsNotAvailableError

MODEL = "hivetrace/gliner-guard-omni"
REVISION = "763f8aa9a7714dd2c3264f3751acdd5d854c5ac4"
THRESHOLD = 0.4
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
LABELS = [
    "person",
    "first_name",
    "last_name",
    "alias",
    "region",
    "city",
    "district",
    "street",
    "building",
    "unit",
    "postal_code",
    "address",
    "company",
    "government",
    "education",
    "media",
    "email",
    "phone",
    "passport",
    "national_id",
    "document_id",
    "date_of_birth",
    "card_number",
    "bank_account",
]
TYPE_MAP = {
    **{k: "PERSON" for k in ("person", "first_name", "last_name", "alias")},
    **{k: "ADDRESS" for k in ("region", "city", "district", "street", "building", "unit", "postal_code", "address")},
    **{k: "ORG" for k in ("company", "government", "education", "media")},
    "email": "EMAIL",
    "phone": "PHONE",
    "passport": "ID",
    "national_id": "ID",
    "document_id": "ID",
    "date_of_birth": "DATE_OF_BIRTH",
    "card_number": "CARD",
    "bank_account": "ACCOUNT",
}


def chunks(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[tuple[int, str]]:
    """Windows of at most ``size`` characters with an overlap, cut at a newline or space."""
    if len(text) <= size:
        return [(0, text)]
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start + size // 2, end), text.rfind(" ", start + size // 2, end))
            end = cut if cut > start else end
        out.append((start, text[start:end]))
        if end >= len(text):
            break
        sp = text.find(" ", end - overlap, end)
        start = sp + 1 if sp != -1 else end - overlap
    return out


class GlinerDetector:
    """Zero-shot span extraction with the 24 PII labels above."""

    name = "gliner"
    languages = frozenset({"ru", "en-GB"})

    def __init__(self, offline: bool = True, threshold: float = THRESHOLD, revision: str = REVISION):
        self.offline, self.threshold, self.revision = offline, threshold, revision
        self._model = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._model is None:
                try:
                    from gliner2 import GLiNER2
                except ImportError as e:
                    raise ModelsNotAvailableError(
                        "gliner2 is not installed: pip install 'pii-roundtrip[gliner]'"
                    ) from e
                path = local_snapshot(MODEL, self.revision, self.offline)
                self._model = GLiNER2.from_pretrained(path)
        return self._model

    def detect(self, text: str, lang: str):
        from pii_roundtrip.detect import Span

        model = self._get()
        spans = []
        for off, part in chunks(text):
            res = model.extract_entities(part, LABELS, threshold=self.threshold, include_spans=True)
            for label, items in res.get("entities", {}).items():
                for it in items:
                    if isinstance(it, dict) and "start" in it:
                        # GLiNER can report an end one past a trailing newline: keep spans inside the chunk
                        start, end = max(0, it["start"]), min(len(part), it["end"])
                        if start < end:
                            spans.append(Span(TYPE_MAP.get(label, label.upper()), off + start, off + end, self.name))
        return spans
