"""Adapters to third-party detectors and morphology.

Each adapter hides one external library behind a small interface:
detectors return a list of :class:`pii_roundtrip.detect.Span` for a text, and the
inflector restores Russian names in the grammatical case required by the context.
"""

from pii_roundtrip.adapters.gliner import GlinerDetector
from pii_roundtrip.adapters.pii_guard import PiiGuardDetector, PiiGuardInflector

__all__ = ["GlinerDetector", "PiiGuardDetector", "PiiGuardInflector"]
