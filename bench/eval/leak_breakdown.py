"""Where the document-level leaks of held-out set 4 come from.

python -m bench.eval.leak_breakdown [holdout4|holdout5] > results/leak_breakdown[.holdout5].json

For every tool and language, from the saved predictions (results/<tool>/holdout4_<lang>.jsonl):
- the share of documents with a leak in clean and in noisy documents, and in documents with and
  without a hard-format identifier (written in words, grouped with dots, or with a typo that
  breaks its checksum);
- the number of documents with a leak of each entity type;
- the share of documents with a leak counting only the types the tool supports
  (pii-guard and OpenAI privacy-filter have no organisations; Prompt Anonymizer has no NHS, NI
  numbers or organisations).
Every share comes with a 95% Wilson interval. The leak rule is metrics.leaked_values, the one
used for the reported leak rate.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import defaultdict

from bench import ROOT
from bench.eval import metrics
from bench.eval.run import load_docs
from pii_roundtrip import checksums

# OpenAI privacy-filter has no organisation type (added 22.10.2026 after review)
UNSUPPORTED = {"pii_guard": {"ORG"}, "prompt_anonymizer": {"NHS", "NINO", "ORG"}, "privacy_filter": {"ORG"}}
VALID = {
    "INN": checksums.is_valid_inn,
    "SNILS": checksums.is_valid_snils,
    "PASSPORT_RU": checksums.is_valid_passport_ru,
    "NHS": checksums.is_valid_nhs,
    "NINO": checksums.is_valid_nino,
    "CARD": checksums.is_valid_card,
    "IBAN": checksums.is_valid_iban,
}


def hard_format(e: dict) -> bool:
    """An identifier written the hard way by the generator: digits in words, dots between the
    groups, or a typo in one digit (its checksum no longer holds)."""
    if e["type"] not in metrics.STRUCTURED["ru"] + metrics.STRUCTURED["uk"]:
        return False
    v, canon = e["value"], e.get("canonical", e["value"])
    if not re.search(r"[A-Za-z]", canon) and re.search(r"[A-Za-zА-Яа-яЁё]{3}", v):
        return True  # digits written as words (NI numbers and IBANs have letters of their own)
    if re.search(r"\d\.\d", v):
        return True
    check = VALID.get(e["type"])
    return bool(check and re.search(r"\d", canon) and not check(canon))


def share(k: int, n: int) -> dict:
    return {"docs": n, "leak_docs": k, "rate": k / n if n else None, "ci": metrics.wilson(k, n) if n else None}


def breakdown(tool: str, lang: str, data: str = "holdout4") -> dict | None:
    path = ROOT / "results" / tool / f"{data}_{lang}.jsonl"
    if not path.exists():
        return None
    docs = {d["id"]: d for d in load_docs(f"data/{data}/{lang}.jsonl")}
    skip = UNSUPPORTED.get(tool, set())
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    supported = [0, 0]
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        d = docs.get(r["id"])
        if d is None:
            continue
        preds = r["pred"] if isinstance(r["pred"], list) else ast.literal_eval(r["pred"])
        masked = metrics.mask_text(d["text"], preds)
        leaked = metrics.leaked_values(d, masked)
        leaked_set = set(leaked)
        leaked_types = {e["type"] for e in d["entities"] if e["value"] in leaked_set}
        hard = any(hard_format(e) for e in d["entities"])
        for key in ("all", "noisy" if d.get("noisy") else "clean", "hard_format" if hard else "no_hard_format"):
            groups[key][0] += bool(leaked)
            groups[key][1] += 1
        for t in {e["type"] for e in d["entities"] if e["type"] in metrics.TYPES}:
            by_type[t][0] += t in leaked_types
            by_type[t][1] += 1
        supported[0] += bool(leaked_types - skip)
        supported[1] += 1
    return {
        "groups": {k: share(*v) for k, v in sorted(groups.items())},
        "by_type": {t: share(*v) for t, v in sorted(by_type.items())},
        "supported_types_only": {"unsupported": sorted(skip), **share(*supported)},
    }


def main() -> None:
    os.chdir(ROOT)
    data = sys.argv[1] if len(sys.argv) > 1 else "holdout4"
    out: dict = {}
    for tool in sorted(p.name for p in (ROOT / "results").iterdir() if p.is_dir() and p.name != "cycle"):
        for lang in ("ru", "uk"):
            b = breakdown(tool, lang, data)
            if b:
                out.setdefault(tool, {})[lang] = b
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
