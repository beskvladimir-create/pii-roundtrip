"""A stricter document-level measure, added after review and not pre-registered: the share of
documents in which at least one value of the threshold types is not fully masked.

python -m bench.eval.strict_leaks > results/strict_leaks.json

The pre-registered leak measure (metrics.leaked_values) counts an address or an organisation as
leaked only when its whole string stays in the masked text. Here a value counts as not fully
masked by the same criterion as recall: some identifying word of it (metrics._essential_positions)
is outside every masked span (metrics._covered_loose). A document with a postcode masked but the
street, house and town visible counts here and not in the leak measure.

For every tool and dataset (held-out sets 4 and 5, the external datasets), from the stored
predictions (the last one per document): the share of such documents with a Wilson interval,
the same share per group of types (ADDRESS, ORG, PERSON, numbers) among the documents that
contain that group, and for the held-out sets by noise. For pii-roundtrip on the UK part of
held-out set 5, 20 examples of what stayed visible.
"""

from __future__ import annotations

import json
import random
import sys

from bench import ROOT
from bench.eval import metrics
from bench.eval.rescore_stored import SETS
from bench.eval.run import load_docs, text_hash

DATA = [
    "holdout4_ru",
    "holdout4_uk",
    "holdout5_ru",
    "holdout5_uk",
    "holdout6_ru",
    "holdout6_uk",
    "hivetrace_pii_bench",
    "redmadrobot_pii_benchmark",
    "nemotron_uk",
    "nemotron_uk_ids",
]
EXAMPLES = "holdout6_uk"  # 20 examples of what stayed visible (held-out set 5 in release 0.3.1)
NUMBERS = set(metrics.STRUCTURED["ru"] + metrics.STRUCTURED["uk"])
# the types of the recall thresholds: structured identifiers, names, addresses, organisations
# (until 22.10.2026 every annotated type of the leak measure was counted, also phone, e-mail and
# date of birth; on held-out set 5 this changed no figure)
THRESHOLD_TYPES = NUMBERS | set(metrics.NAMES)


def group(t: str) -> str:
    return "numbers" if t in NUMBERS else t


def visible(text: str, g: dict, preds: list[dict]) -> str:
    """The identifying words of a value that no masked span covers."""
    mask = set()
    for p in preds:
        mask.update(range(p["start"], p["end"]))
    pos = [i for i in metrics._essential_positions(text, g["start"], g["end"]) if i not in mask]
    out, last = [], None
    for i in pos:
        if last is not None and i != last + 1:
            out.append(" ")
        out.append(text[i])
        last = i
    return "".join(out)


def share(k: int, n: int) -> dict:
    return {"docs": n, "strict_docs": k, "rate": k / n if n else None, "ci": metrics.wilson(k, n) if n else None}


def main() -> None:
    out: dict = {}
    examples = []
    for tool in sorted(p.name for p in (ROOT / "results").iterdir() if p.is_dir() and p.name != "cycle"):
        for ds in DATA:
            pf = ROOT / "results" / tool / f"{ds}.jsonl"
            if not pf.exists():
                continue
            path, _lang = SETS[ds]
            docs = load_docs(path)
            last = {(c["id"], c.get("h")): c["pred"] for c in load_docs(str(pf))}
            preds_all = [last.get((d["id"], text_hash(d["text"]))) for d in docs]
            if any(p is None for p in preds_all):
                print(f"skip {tool}/{ds}: missing predictions", file=sys.stderr)
                continue
            allc = [0, 0]
            by_group: dict[str, list[int]] = {}
            by_noise: dict[str, list[int]] = {}
            for d, preds in zip(docs, preds_all, strict=True):
                text = d["text"]
                gold = [
                    g
                    for g in d["entities"]
                    if g["type"] in THRESHOLD_TYPES and metrics._essential_positions(text, g["start"], g["end"])
                ]
                open_ = [g for g in gold if not metrics._covered_loose(text, g["start"], g["end"], preds)]
                allc[0] += bool(open_)
                allc[1] += 1
                for gr in {group(g["type"]) for g in gold}:
                    c = by_group.setdefault(gr, [0, 0])
                    c[0] += any(group(g["type"]) == gr for g in open_)
                    c[1] += 1
                if "noisy" in d:
                    c = by_noise.setdefault("noisy" if d["noisy"] else "clean", [0, 0])
                    c[0] += bool(open_)
                    c[1] += 1
                if tool == "pii_roundtrip" and ds == EXAMPLES:
                    for g in open_:
                        if g["type"] in ("ADDRESS", "ORG"):
                            examples.append(
                                {
                                    "id": d["id"],
                                    "type": g["type"],
                                    "value": g["value"],
                                    "visible": visible(text, g, preds),
                                }
                            )
            out.setdefault(tool, {})[ds] = {
                "all": share(*allc),
                "by_group": {k: share(*v) for k, v in sorted(by_group.items())},
                "by_noise": {k: share(*v) for k, v in sorted(by_noise.items())},
            }
            print(f"done {tool}/{ds}", file=sys.stderr)
    rng = random.Random(0)
    out[f"_examples_pii_roundtrip_{EXAMPLES}"] = {
        "total": len(examples),
        "sample": rng.sample(examples, min(20, len(examples))),
    }
    out["_note"] = (
        "Added after review, not pre-registered. The pre-registered leak measure is leak_rate in metrics.json."
    )
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
