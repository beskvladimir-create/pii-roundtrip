"""hivetrace/gliner-guard-omni (GLiNER2, multilingual deberta v3): полная PII таксономия
из карточки модели (32 метки), порог 0.4 как в примере карточки. Длинные документы
режутся на окна с перекрытием."""

from __future__ import annotations

from runners.base import Runner, Span, resolve_overlaps
from runners.chunking import chunks

MODEL = "hivetrace/gliner-guard-omni"
REVISION = "763f8aa9a7714dd2c3264f3751acdd5d854c5ac4"
THRESHOLD = 0.4

PII_LABELS = [
    "person", "first_name", "last_name", "alias", "title",
    "country", "region", "city", "district", "street",
    "building", "unit", "postal_code", "landmark", "address",
    "company", "government", "education", "media", "product",
    "email", "phone", "social_account", "messenger",
    "passport", "national_id", "document_id",
    "date_of_birth", "event_date",
    "card_number", "bank_account", "crypto_wallet",
]

COMMON = {
    **{k: "PERSON" for k in ("person", "first_name", "last_name", "alias", "title")},
    **{k: "ADDRESS" for k in ("country", "region", "city", "district", "street", "building", "unit", "postal_code", "landmark", "address")},
    **{k: "ORG" for k in ("company", "government", "education", "media")},
    "product": "PRODUCT",
    "email": "EMAIL",
    "phone": "PHONE",
    "social_account": "SOCIAL",
    "messenger": "SOCIAL",
    "national_id": "NATIONAL_ID",
    "document_id": "DOCUMENT_ID",
    "date_of_birth": "DATE_OF_BIRTH",
    "event_date": "DATE",
    "card_number": "CARD",
    "crypto_wallet": "CRYPTO",
}
BY_LANG = {
    "ru": {"passport": "PASSPORT_RU", "bank_account": "BANK_ACCOUNT_RU"},
    "uk": {"passport": "PASSPORT", "bank_account": "IBAN"},
}


class GlinerGuardRunner(Runner):
    name = "gliner_guard"

    def __init__(self):
        from gliner2 import GLiNER2

        self.model = GLiNER2.from_pretrained(MODEL, revision=REVISION) if _accepts_revision() else GLiNER2.from_pretrained(MODEL)

    def config(self) -> dict:
        return {"model": MODEL, "revision": REVISION, "threshold": THRESHOLD, "labels": PII_LABELS, "chunk_chars": 1200, "overlap": 200}

    def detect(self, text: str, lang: str) -> list[Span]:
        mapping = {**COMMON, **BY_LANG[lang]}
        spans: list[Span] = []
        for off, part in chunks(text):
            res = self.model.extract_entities(part, PII_LABELS, threshold=THRESHOLD, include_spans=True)
            for label, items in res.get("entities", {}).items():
                for it in items:
                    if isinstance(it, dict) and "start" in it:
                        spans.append(Span(mapping.get(label, label.upper()), off + it["start"], off + it["end"]))
        return resolve_overlaps(spans)


def _accepts_revision() -> bool:
    import inspect

    from gliner2 import GLiNER2

    try:
        sig = inspect.signature(GLiNER2.from_pretrained)
    except (TypeError, ValueError):
        return False
    return "revision" in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
