"""Document-level cluster bootstrap for recall and masking precision.

Values and masked fragments inside one document are not independent, so the
Wilson intervals in metrics.json are too narrow. This script resamples whole
documents (2,000 resamples, seed 0) using the saved predictions.
Each entry is [k, n, k/n, 2.5th percentile, 97.5th percentile].

python -m bench.eval.cluster_ci > results/cluster_ci.json
"""

from __future__ import annotations

import json
import random
import sys

from bench import ROOT
from bench.eval import metrics
from bench.eval.run import DATASETS, load_docs

SETS = dict(DATASETS)
SETS["holdout4_ru"] = (str(ROOT / "data/holdout4/ru.jsonl"), "ru")
SETS["holdout4_uk"] = (str(ROOT / "data/holdout4/uk.jsonl"), "uk")
TOOLS = [
    "regex_baseline",
    "presidio",
    "pii_guard",
    "gliner_guard",
    "privacy_filter",
    "prompt_anonymizer",
    "pii_roundtrip",
]


def per_doc(doc: dict, pred: list[dict], lang: str) -> tuple:
    acc = metrics.new_acc()
    metrics.score_doc(doc, pred, acc)
    s = [sum(acc[t][k] for t in metrics.STRUCTURED[lang] if t in acc) for k in ("masked", "n")]
    n = [sum(acc[t][k] for t in metrics.NAMES if t in acc) for k in ("masked", "n")]
    return (*s, *n, acc["_any"]["pred_ok"], acc["_any"]["pred"], acc["_chars"]["pred_ok"], acc["_chars"]["pred"])


def boot(rows: list[tuple], i: int, j: int, reps: int = 2000) -> list | None:
    tot = sum(r[j] for r in rows)
    if not tot:
        return None
    rng = random.Random(0)
    vals = []
    for _ in range(reps):
        smp = [rows[rng.randrange(len(rows))] for _ in rows]
        d = sum(r[j] for r in smp)
        vals.append(sum(r[i] for r in smp) / d if d else 1.0)
    vals.sort()
    return [
        sum(r[i] for r in rows),
        tot,
        sum(r[i] for r in rows) / tot,
        vals[int(0.025 * reps)],
        vals[int(0.975 * reps) - 1],
    ]


def main() -> None:
    out: dict = {}
    for ds, (path, lang) in SETS.items():
        try:
            docs = load_docs(path)
        except FileNotFoundError:
            continue
        for tool in TOOLS:
            pf = ROOT / "results" / tool / f"{ds}.jsonl"
            if not pf.exists():
                continue
            last = {}
            for c in load_docs(str(pf)):
                last[(c["id"], c.get("h"))] = c["pred"]
            from bench.eval.run import text_hash

            preds = [last.get((d["id"], text_hash(d["text"]))) for d in docs]
            if any(p is None for p in preds):
                print(f"skip {tool}/{ds}: missing predictions", file=sys.stderr)
                continue
            rows = [per_doc(d, p, lang) for d, p in zip(docs, preds, strict=True)]
            out.setdefault(tool, {})[ds] = {
                "docs": len(docs),
                "structured": boot(rows, 0, 1),
                "names": boot(rows, 2, 3),
                "precision_fragments": boot(rows, 4, 5),
                "precision_chars": boot(rows, 6, 7),
            }
            out[tool][ds]["_rows"] = rows
            out[tool][ds]["_ids"] = [d["id"] for d in docs]
            print(f"done {tool}/{ds}", file=sys.stderr)
    # UK external datasets pooled, as in the report tables. The two subsets share source texts
    # (the id after the last hyphen is the same): such a pair is one cluster, so that one text
    # is not resampled as two independent documents.
    for sets in out.values():
        if "nemotron_uk" in sets and "nemotron_uk_ids" in sets:
            clusters: dict[str, list] = {}
            for part in ("nemotron_uk", "nemotron_uk_ids"):
                for doc_id, r in zip(sets[part]["_ids"], sets[part]["_rows"], strict=True):
                    key = doc_id.rsplit("-", 1)[-1]
                    clusters[key] = (
                        [a + b for a, b in zip(clusters[key], r, strict=True)] if key in clusters else list(r)
                    )
            rows = [tuple(c) for c in clusters.values()]
            n_docs = len(sets["nemotron_uk"]["_ids"]) + len(sets["nemotron_uk_ids"]["_ids"])
            sets["nemotron_uk+ids"] = {
                "docs": n_docs,
                "clusters": len(rows),
                "structured": boot(rows, 0, 1),
                "names": boot(rows, 2, 3),
                "precision_fragments": boot(rows, 4, 5),
                "precision_chars": boot(rows, 6, 7),
            }
    for sets in out.values():
        for m in sets.values():
            m.pop("_rows", None)
            m.pop("_ids", None)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
