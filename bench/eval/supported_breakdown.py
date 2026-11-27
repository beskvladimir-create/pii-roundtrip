"""Leaks on held-out set 7 by number format, counting only some entity types (descriptive).

python -m bench.eval.supported_breakdown > results/leak_breakdown_supported.holdout7.json

For every tool and language, from the saved predictions (results/<tool>/holdout7_<lang>.jsonl)
and the documents (data/holdout7/<lang>.jsonl), the share of documents with a leak in documents
without and with a hard-format identifier (leak_breakdown.hard_format: digits in words, dots
between the groups, or a typo that breaks the checksum), and in all documents, in two variants:

- supported_types_only: leaks of types the tool does not support are not counted
  (leak_breakdown.UNSUPPORTED: pii-guard and OpenAI privacy-filter have no organisations,
  Prompt Anonymizer has no NHS, NI numbers or organisations);
- without_org: leaks of organisations are not counted for any tool, so that tools are compared on
  the same types as pii-guard and privacy-filter. For a tool that does support organisations
  (GLiNER Guard Omni, Presidio, pii-roundtrip) this leaves out leaks the tool did make.

The leak rule is metrics.leaked_values, the one used for the reported leak rate; every share comes
with a 95% Wilson interval. Descriptive only: no threshold applies to these figures.
"""

from __future__ import annotations

import ast
import json
import os
import sys

from bench import ROOT
from bench.eval import metrics
from bench.eval.leak_breakdown import UNSUPPORTED, hard_format, share
from bench.eval.run import load_docs

DATA = "holdout7"


def breakdown(tool: str, lang: str) -> dict | None:
    path = ROOT / "results" / tool / f"{DATA}_{lang}.jsonl"
    if not path.exists():
        return None
    docs = {d["id"]: d for d in load_docs(f"data/{DATA}/{lang}.jsonl")}
    variants = {"supported_types_only": UNSUPPORTED.get(tool, set()), "without_org": {"ORG"}}
    counts = {v: {"no_hard_format": [0, 0], "hard_format": [0, 0], "all": [0, 0]} for v in variants}
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        d = docs.get(r["id"])
        if d is None:
            continue
        preds = r["pred"] if isinstance(r["pred"], list) else ast.literal_eval(r["pred"])
        leaked = set(metrics.leaked_values(d, metrics.mask_text(d["text"], preds)))
        leaked_types = {e["type"] for e in d["entities"] if e["value"] in leaked}
        group = "hard_format" if any(hard_format(e) for e in d["entities"]) else "no_hard_format"
        for v, skip in variants.items():
            for key in (group, "all"):
                counts[v][key][0] += bool(leaked_types - skip)
                counts[v][key][1] += 1
    return {v: {"not_counted": sorted(variants[v]), **{k: share(*c) for k, c in counts[v].items()}} for v in variants}


def main() -> None:
    os.chdir(ROOT)
    out: dict = {}
    for tool in sorted(p.name for p in (ROOT / "results").iterdir() if p.is_dir() and p.name != "cycle"):
        for lang in ("ru", "uk"):
            b = breakdown(tool, lang)
            if b:
                out.setdefault(tool, {})[lang] = b
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
