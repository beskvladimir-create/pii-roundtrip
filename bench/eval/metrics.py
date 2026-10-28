"""Detection and leak metrics.

Three modes of matching a gold entity against predictions:
- exact: the same type and the same boundaries;
- partial: the same type and an overlap;
- masked: the entity is fully covered by predicted spans of any type.
  This is the main mode for the thresholds: for anonymization what matters is that the value
  is hidden, not which type it was labelled with.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from functools import lru_cache

from bench.runners.base import TYPES

STRUCTURED = {
    "ru": ("PASSPORT_RU", "SNILS", "INN", "CARD", "BANK_ACCOUNT_RU"),
    "uk": ("NHS", "NINO", "CARD", "IBAN"),
}
NAMES = ("PERSON", "ADDRESS", "ORG")

THRESHOLDS = {"structured": 0.99, "names": 0.95, "leak": 0.02, "restore": 0.99}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def _covered(start: int, end: int, preds: list[dict]) -> bool:
    pos = start
    for p in sorted(preds, key=lambda p: p["start"]):
        if p["start"] <= pos < p["end"]:
            pos = p["end"]
            if pos >= end:
                return True
    # whitespace and punctuation at the edges do not count as a leak
    return False


# Service words inside an entity that by themselves identify no one:
# street and settlement types, «г.р.», initials (a single letter).
NON_IDENTIFYING = {
    "г",
    "гор",
    "с",
    "п",
    "пос",
    "пгт",
    "ст",
    "д",
    "дер",
    "х",
    "обл",
    "р",
    "рн",
    "мкр",
    "ул",
    "пр",
    "пр-т",
    "просп",
    "пер",
    "наб",
    "бул",
    "алл",
    "ш",
    "пл",
    "туп",
    "проезд",
    "дом",
    "кв",
    "корп",
    "к",
    "стр",
    "оф",
    "офис",
    "литер",
    "серия",
    "сер",
    "номер",
    "no",
    "nr",
    "этаж",
    "подъезд",
    "подьезд",
    "под",
    "корпус",
    "квартира",
    "клх",
    "свх",
    "рп",
    "аул",
    "сл",
    "нп",
    "снт",
    "днп",
    "тер",
    "б-р",
    "пр-д",
    "ст-ца",
    "дп",
    "кп",
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "sir",
    "господин",
    "госпожа",
    "гражданин",
    "гражданка",
}


def _essential_positions(text: str, start: int, end: int) -> list[int]:
    pos = []
    for m in re.finditer(r"\w+", text[start:end]):
        w = m.group().lower()
        if len(w) == 1 and w.isalpha() or w in NON_IDENTIFYING:
            continue
        pos.extend(range(start + m.start(), start + m.end()))
    return pos


def _covered_loose(text: str, start: int, end: int, preds: list[dict]) -> bool:
    if _covered(start, end, preds):
        return True
    inner = _essential_positions(text, start, end)
    mask = set()
    for p in preds:
        mask.update(range(p["start"], p["end"]))
    return all(i in mask for i in inner)


def score_doc(doc: dict, preds: list[dict], acc: dict) -> None:
    text = doc["text"]
    gold = [g for g in doc["entities"] if g["type"] in TYPES]
    for g in gold:
        t = g["type"]
        if not _essential_positions(text, g["start"], g["end"]):
            continue  # entity of function words and initials only: counts neither for nor against
        same = [p for p in preds if p["type"] == t]
        acc[t]["n"] += 1
        acc[t]["exact"] += any(p["start"] == g["start"] and p["end"] == g["end"] for p in same)
        acc[t]["partial"] += any(p["start"] < g["end"] and g["start"] < p["end"] for p in same)
        ok = _covered_loose(text, g["start"], g["end"], preds)
        acc[t]["masked"] += ok
        if not ok:
            acc[t]["misses"].append((doc["id"], g["value"]))
    all_gold = doc["entities"]
    for p in preds:
        t = p["type"]
        acc[t]["pred"] += 1
        acc[t]["pred_ok"] += any(g["type"] == t and p["start"] < g["end"] and g["start"] < p["end"] for g in gold)
        # for masking precision, only a label over text without personal data counts as false
        acc["_any"]["pred"] += 1
        acc["_any"]["pred_ok"] += any(p["start"] < g["end"] and g["start"] < p["end"] for g in all_gold)
    # character-level precision: what share of the hidden text (without whitespace) lies inside
    # the annotated data
    gold_pos = {i for g in all_gold for i in range(g["start"], g["end"])}
    masked_pos = {
        i for p in preds for i in range(max(0, p["start"]), min(len(text), p["end"])) if not text[i].isspace()
    }
    acc["_chars"]["pred"] += len(masked_pos)
    acc["_chars"]["pred_ok"] += len(masked_pos & gold_pos)


def new_acc() -> dict:
    return defaultdict(lambda: {"n": 0, "exact": 0, "partial": 0, "masked": 0, "pred": 0, "pred_ok": 0, "misses": []})


# ---------- leaks ----------


def mask_text(text: str, preds: list[dict]) -> str:
    """Replaces the union of all predicted spans with [PII] (overlaps are not lost)."""
    out, pos = [], 0
    for p in sorted(preds, key=lambda p: (p["start"], -p["end"])):
        if p["end"] <= pos:
            continue
        start = max(p["start"], pos)
        out.append(text[pos:start])
        if not (out and out[-1] == "" and len(out) > 1 and out[-2] == "[PII]"):
            out.append("[PII]")
        pos = p["end"]
    out.append(text[pos:])
    return "".join(out)


@lru_cache(maxsize=50000)
def _surname_forms(surname: str) -> tuple[str, ...]:
    from bench.generator.persons import CASES, _morph

    forms = {surname}
    for p in _morph().parse(surname)[:3]:
        for c in CASES:
            f = p.inflect({c})
            if f:
                forms.add(f.word.capitalize())
    return tuple(forms)


def _count_word(haystack: str, needle: str, case_sensitive: bool = False) -> int:
    if len(needle) < 3:
        return 0
    flags = 0 if case_sensitive else re.I
    return len(re.findall(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack, flags))


def _outside_pii(doc: dict) -> str:
    """The source text without the annotated values: the words left in it are not personal
    data, and the tool is not obliged to hide them (the month June next to the name June)."""
    text, out, pos = doc["text"], [], 0
    for g in sorted(doc["entities"], key=lambda g: g["start"]):
        if g["start"] >= pos:
            out.append(text[pos : g["start"]])
            out.append("\n")
            pos = g["end"]
        else:
            pos = max(pos, g["end"])
    out.append(text[pos:])
    return "".join(out)


def _word_leaked(masked: str, base: str, word: str, case_sensitive: bool = False) -> bool:
    """A word has leaked if it occurs more often in the sanitized text than in the source text
    outside personal data."""
    return _count_word(masked, word, case_sensitive) > _count_word(base, word, case_sensitive)


def _number_regex(canon: str) -> re.Pattern:
    """A number with spaces and hyphens between characters (the rule before 0.3.1); boundaries are
    checked against the original sanitized text, without merging with adjacent words."""
    chars = [re.escape(c) for c in re.sub(r"[\s\-]", "", canon)]
    return re.compile(r"(?<![\dA-Za-z])" + r"[ \-]?".join(chars) + r"(?![\dA-Za-z])", re.I)


def _number_regex_sep(canon: str) -> re.Pattern:
    """The same number with other separators: up to three consecutive spaces, hyphens, dots or
    slashes («5223.2630.1023.1078», «45...12...123456», «123 - 456 - 789 01»), if the number is not
    part of a longer number (no digit adjacent or across a separator). Added in 0.3.1: the previous
    rule did not see a number left in the clear when written with dots."""
    chars = [re.escape(c) for c in re.sub(r"[\s\-./]", "", canon)]
    left = r"(?<![\dA-Za-z])(?<!\d[ \-./])(?<!\d[ \-./]{2})(?<!\d[ \-./]{3})"
    right = r"(?![\dA-Za-z])(?![ \-./]{1,3}\d)"
    return re.compile(left + r"[ \-./]{0,3}".join(chars) + right, re.I)


def _number_left(canon: str, masked: str) -> bool:
    """A leak under the rule before 0.3.1 or under the separator rule: the fix only adds leaks."""
    return bool(_number_regex(canon).search(masked) or _number_regex_sep(canon).search(masked))


def leaked_values(doc: dict, masked: str) -> list[str]:
    """Source values that remained in the sanitized text."""
    leaks = []
    base = _outside_pii(doc)
    for g in doc["entities"]:
        t = g["type"]
        if t not in TYPES:
            continue
        canon = g.get("canonical", g["value"])
        if t in STRUCTURED["ru"] + STRUCTURED["uk"]:
            if _number_left(canon, masked):
                leaks.append(g["value"])
            elif (
                re.search(r"[A-Za-zА-Яа-яЁё]{3}", g["value"])
                and re.sub(r"[\s\-.]", "", g["value"]).lower() in re.sub(r"[\s\-.]", "", masked).lower()
            ):
                leaks.append(g["value"])  # a number written out in words
        elif t == "PERSON":
            words = [w for w in re.findall(r"\w+", canon) if len(w) > 2]
            forms: set[str] = {w for w in re.findall(r"\w+", g["value"]) if w.lower() not in NON_IDENTIFYING}
            # the surname (RU: the first word of the canonical form, UK: the last) is checked strictly,
            # in all cases: its repetition is often not annotated; the first name and patronymic may be
            # ordinary words of the text (June in a date), so for them a leak counts only beyond the
            # number of such words outside personal data
            surname = (words[0] if doc["lang"] == "ru" else words[-1]) if words else ""
            strict = set(_surname_forms(surname)) if doc["lang"] == "ru" and surname else set()
            strict |= {f for f in forms if f.lower() == surname.lower()}

            def leaked(w: str, strict: set[str] = strict) -> bool:
                if w in strict:
                    return _count_word(masked, w, True) > 0 or _count_word(masked, w.upper(), True) > 0
                return _word_leaked(masked, base, w, True) or _word_leaked(masked, base, w.upper(), True)

            if any(leaked(w) for w in forms | strict if len(w) > 2):
                leaks.append(g["value"])
        elif _word_leaked(masked, base, g["value"]):
            leaks.append(g["value"])
    return leaks


# ---------- summary ----------


def summarize(acc: dict, leak_docs: int, n_docs: int, lang: str) -> dict:
    per_type = {}
    for t, a in sorted(acc.items()):
        if t.startswith("_"):
            continue
        n = a["n"]
        per_type[t] = {
            "n": n,
            "recall_masked": a["masked"] / n if n else None,
            "recall_masked_ci": wilson(a["masked"], n) if n else None,
            "recall_exact": a["exact"] / n if n else None,
            "recall_partial": a["partial"] / n if n else None,
            "precision_partial": a["pred_ok"] / a["pred"] if a["pred"] else None,
            "pred": a["pred"],
            "misses": a["misses"][:20],
        }

    def group(types):
        k = sum(acc[t]["masked"] for t in types if t in acc)
        n = sum(acc[t]["n"] for t in types if t in acc)
        return {"n": n, "recall": k / n if n else None, "ci": wilson(k, n) if n else None}

    anyp = acc["_any"]
    return {
        "per_type": per_type,
        "structured": group(STRUCTURED[lang]),
        "names": group(NAMES),
        # share of hidden fragments touching annotated data (with an interval), and the same by
        # characters
        "precision_any": anyp["pred_ok"] / anyp["pred"] if anyp["pred"] else None,
        "precision_any_ci": wilson(anyp["pred_ok"], anyp["pred"]) if anyp["pred"] else None,
        "masked_fragments": anyp["pred"],
        "masked_fragments_ok": anyp["pred_ok"],
        "precision_chars": acc["_chars"]["pred_ok"] / acc["_chars"]["pred"] if acc["_chars"]["pred"] else None,
        "leak_rate": leak_docs / n_docs if n_docs else None,
        "leak_ci": wilson(leak_docs, n_docs),
        "docs": n_docs,
    }
