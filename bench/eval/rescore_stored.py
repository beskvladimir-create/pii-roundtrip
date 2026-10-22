"""Recompute results/metrics.json from the stored predictions only, for every tool and dataset
already in it, after a change of the metric (not of a tool).

python -m bench.eval.rescore_stored [--check]

Covered: the external datasets and held-out sets 4 and 5.

For each (tool, dataset) the last stored prediction per document (id and text hash) is used,
the same choice as bench/eval/cluster_ci.py. No tool is run and no model is loaded. With
--check nothing is written: the script reports every entry whose recomputed figures differ
from results/metrics.json (used to confirm that a rescore reproduces the stored figures before
a metric is changed).
"""

from __future__ import annotations

import argparse
import json
import sys

from bench import ROOT
from bench.eval.run import DATASETS, evaluate, load_docs, text_hash

SETS = dict(DATASETS)
for name, folder in (
    ("holdout", "holdout"),
    ("holdout2", "holdout2"),
    ("holdout3", "holdout3"),
    ("holdout4", "holdout4"),
    ("holdout5", "holdout5"),
):
    for lang in ("ru", "uk"):
        SETS[f"{name}_{lang}"] = (str(ROOT / "data" / folder / f"{lang}.jsonl"), lang)

# held-out sets 1 to 3 and the synthetic development set keep the figures of their own reports
OLD = {f"{n}_{lang}" for n in ("holdout", "holdout2", "holdout3", "synthetic") for lang in ("ru", "uk")}
KEYS = ("structured", "names", "leak_rate", "docs", "masked_fragments", "masked_fragments_ok")


def rescore(tool: str, ds: str) -> dict | None:
    if ds not in SETS:
        return None
    path, lang = SETS[ds]
    pf = ROOT / "results" / tool / f"{ds}.jsonl"
    try:
        docs = load_docs(path)
    except FileNotFoundError:
        return None
    if not pf.exists():
        return None
    last = {(c["id"], c.get("h")): c["pred"] for c in load_docs(str(pf))}
    preds = [last.get((d["id"], text_hash(d["text"]))) for d in docs]
    if any(p is None for p in preds):
        print(f"skip {tool}/{ds}: missing predictions", file=sys.stderr)
        return None
    return evaluate(docs, preds, lang)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    p = ROOT / "results" / "metrics.json"
    m = json.loads(p.read_text())
    changed = []
    for tool, sets in m.items():
        for ds in list(sets):
            if ds.startswith("_") or "@" in ds or ds in OLD:
                continue
            new = rescore(tool, ds)
            if new is None:
                continue
            old = sets[ds]
            diff = {k: (old.get(k), new.get(k)) for k in KEYS if json.dumps(old.get(k)) != json.dumps(new.get(k))}
            if diff:
                changed.append((tool, ds, diff))
            if not args.check:
                sets[ds] = new
    for tool, ds, diff in changed:
        brief = {k: (o, n) for k, (o, n) in diff.items() if k == "leak_rate"}
        print(f"{tool:18s} {ds:28s} changed: {sorted(diff)} {brief}")
    if not args.check:
        p.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    print(f"{len(changed)} entries differ")


if __name__ == "__main__":
    main()
