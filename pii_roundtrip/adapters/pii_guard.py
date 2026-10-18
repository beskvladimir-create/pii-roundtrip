"""pii-guard (redmadrobot): Russian detector and Russian name inflection.

pii-guard is pinned to commit 24230ab in pyproject.toml. Two parts of it are used:

* :class:`pii_guard.Anonymizer` for detection (public API);
* ``pii_guard.pseudonymize.deanonymize_batch`` for restoring Russian names in the
  grammatical case that the context requires. This function is not part of
  ``pii_guard.__all__``; it is called only from :class:`PiiGuardInflector`, and the
  contract (tag format and signature) is checked by ``tests/test_contracts.py``.
"""

from __future__ import annotations

import threading
from difflib import SequenceMatcher

from pii_roundtrip.adapters._hub import local_snapshot
from pii_roundtrip.errors import InflectionError, ModelsNotAvailableError

NER_MODEL = "redmadrobot-rnd/rubert-base-pii-ner"
NER_REVISION = "c802e8cd26f85d1cf920973ea6f83965a0618d63"
SPACY_MODEL = "ru_core_news_sm"

TYPE_MAP = {
    "PERSON": "PERSON",
    "LOCATION": "ADDRESS",
    "POSTAL_CODE": "ADDRESS",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "INN": "INN",
    "SNILS": "SNILS",
    "PASSPORT": "PASSPORT_RU",
    "CREDIT_CARD": "CARD",
    "BANK_ACCOUNT": "BANK_ACCOUNT_RU",
    "DATE_TIME": "DATE",
    "OMS": "ID",
    "DRIVER_LICENSE": "ID",
    "MILITARY_ID": "ID",
    "BIRTH_CERTIFICATE": "ID",
    "BIK": "BIK",
    "URL": "URL",
    "TELEGRAM": "SOCIAL",
    "IP_ADDRESS": "IP",
    "IP_PORT": "IP",
}


def default_device() -> str | None:
    """Apple GPU when available; otherwise None lets pii-guard choose (CUDA or CPU)."""
    try:
        import torch

        return "mps" if torch.backends.mps.is_available() else None
    except Exception:
        return None


def _locate(fragment: str, text: str, approx: int, window: int = 400) -> int | None:
    """Find a fragment of the normalised text in the original text near the expected
    position. Linear in the document length, unlike a full alignment."""
    lo = max(0, approx - window)
    hi = min(len(text), approx + window + len(fragment))
    i = text.find(fragment, lo, hi)
    if i == -1:
        i = text.lower().find(fragment.lower(), lo, hi)
    return None if i == -1 else i


def _align_local(norm: str, text: str, s: int, t: int, approx: int, pad: int = 300) -> tuple[int, int] | None:
    """Map a span of the normalised text to the original by aligning a small window
    around the expected position (not the whole document)."""
    ns, ne = max(0, s - pad), min(len(norm), t + pad)
    ts, te = max(0, approx - pad), min(len(text), approx + (t - s) * 4 + pad)
    a, b = norm[ns:ne], text[ts:te]
    m: list[int | None] = [None] * (len(a) + 1)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            m[k] = j1 + (k - i1) if tag == "equal" else j1 + ((k - i1) * (j2 - j1)) // max(1, i2 - i1)
    m[len(a)] = len(b)
    i, j = s - ns, t - ns
    first, last = m[i], m[j - 1]
    if first is None or last is None:
        return None
    start = ts + first
    end = ts + max(last + 1, first + 1)
    # the edges of a changed region can fall inside words: extend to word boundaries
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    return start, end


class PiiGuardDetector:
    """Russian detector: checksum rules and a ruBERT token classifier."""

    name = "pii_guard"
    languages = frozenset({"ru"})

    def __init__(self, offline: bool = True, device: str | None = None, revision: str = NER_REVISION):
        self.offline, self.revision = offline, revision
        self.device = device if device is not None else default_device()
        self._anonymizer = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._anonymizer is None:
                try:
                    from pii_guard import Anonymizer
                    from pii_guard.config import Config
                except ImportError as e:
                    raise ModelsNotAvailableError("pii-guard is not installed: pip install 'pii-roundtrip[ru]'") from e
                path = local_snapshot(NER_MODEL, self.revision, self.offline)
                config = Config.load(ner_model=path, ner_revision=None, device=self.device)
                self._anonymizer = Anonymizer(config)
        return self._anonymizer

    def detect(self, text: str, lang: str):
        from pii_roundtrip.detect import Span

        r = self._get().anonymize(text, mode="tag")
        norm = r.normalized_texts[0]
        spans = []
        for e in r.entities[0]:
            s, t = e["start"], e["end"]
            if norm != text:
                frag = norm[s:t]
                approx = int(s * len(text) / max(1, len(norm)))
                i = _locate(frag, text, approx)
                if i is not None:
                    s, t = i, i + len(frag)
                else:  # fragment changed by normalisation (numbers in words, transliteration)
                    mapped = _align_local(norm, text, s, t, approx)
                    if mapped is None:
                        continue
                    s, t = mapped
            spans.append(Span(TYPE_MAP.get(e["entity_type"], e["entity_type"]), s, t, self.name))
        return spans


class PiiGuardInflector:
    """Restores Russian names in the grammatical case required by the context.

    Placeholders for people are first converted to pii-guard's tag format
    ``<PII type="PERSON" gender="..." id="..." />``; pii-guard then inflects each name
    using a spaCy dependency parse.
    """

    def __init__(self, spacy_model: str = SPACY_MODEL):
        self.spacy_model = spacy_model

    @staticmethod
    def tag(gender: str, index: int) -> str:
        return f'<PII type="PERSON" gender="{gender}" id="{index}" />'

    @staticmethod
    def available() -> bool:
        try:
            import pii_guard.pseudonymize  # noqa: F401
        except ImportError:
            return False
        return True

    def restore(self, text: str, tagmap: dict[str, str]) -> str:
        from pii_guard import pseudonymize

        try:
            return pseudonymize.deanonymize_batch([text], tagmap, self.spacy_model)[0]
        except Exception as e:
            raise InflectionError(f"Russian name inflection failed: {e}") from e
