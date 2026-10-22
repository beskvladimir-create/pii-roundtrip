"""Fast development loop for the engine's rules: the detectors' raw spans are computed once per
document and cached, so that a change of the rules and pipeline stages is scored in minutes.

python -m bench.eval.dev_cache build holdout5_ru holdout5_uk ...   # runs the models once
python -m bench.eval.dev_cache score holdout5_ru holdout5_uk ...   # rules and stages only

The cache is valid only while the detectors and their settings are unchanged; it holds spans,
not texts. Used for development data only (never for a held-out set before its run).
"""

from __future__ import annotations

import json
import pickle
import sys

from bench import ROOT
from bench.eval import metrics
from bench.eval.rescore_stored import SETS
from bench.eval.run import evaluate, load_docs, text_hash
from bench.eval.strict_leaks import THRESHOLD_TYPES

CACHE = ROOT / "build" / "dev_cache"


class CachedModels:
    """Stands in for pii_roundtrip.detect.Models: returns the cached raw spans of a text."""

    def __init__(self, spans: dict[str, list]):
        self.spans = spans

    def detect(self, text: str, lang: str) -> list:
        return self.spans[text_hash(text)]


def build(ds: str) -> None:
    from pii_roundtrip.detect import Models

    path, lang = SETS[ds]
    lang = "en-GB" if lang == "uk" else lang
    models = Models()
    out = {}
    for d in load_docs(path):
        out[text_hash(d["text"])] = models.detect(d["text"], lang)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{ds}.pkl").write_bytes(pickle.dumps(out))
    print(f"cached {ds}: {len(out)} documents", file=sys.stderr)


def strict_docs(docs: list[dict], preds: list[list[dict]]) -> dict:
    """Documents with at least one value of the threshold types not fully masked, per group."""
    total, by = 0, {}
    for d, p in zip(docs, preds, strict=True):
        t = d["text"]
        open_ = {
            g["type"]
            for g in d["entities"]
            if g["type"] in THRESHOLD_TYPES
            and metrics._essential_positions(t, g["start"], g["end"])
            and not metrics._covered_loose(t, g["start"], g["end"], p)
        }
        total += bool(open_)
        for ty in open_:
            by[ty] = by.get(ty, 0) + 1
    return {"strict": total, "by_type": by}


def score(ds: str, verbose: bool = False) -> dict:
    from pii_roundtrip.detect import detect

    path, lang = SETS[ds]
    elang = "en-GB" if lang == "uk" else lang
    cached = CachedModels(pickle.loads((CACHE / f"{ds}.pkl").read_bytes()))
    docs = load_docs(path)
    preds = [[{"type": s.type, "start": s.start, "end": s.end} for s in detect(d["text"], elang, cached)] for d in docs]
    r = evaluate(docs, preds, lang)
    out = {
        "docs": r["docs"],
        "struct": round(100 * r["structured"]["recall"], 2),
        "names": round(100 * r["names"]["recall"], 2),
        "leak": round(100 * r["leak_rate"], 2),
        "prec": round(100 * r["masked_fragments_ok"] / r["masked_fragments"], 2),
        **strict_docs(docs, preds),
    }
    if verbose:
        out["_preds"] = preds
    return out


if __name__ == "__main__":
    cmd, *sets = sys.argv[1:]
    for ds in sets:
        if cmd == "build":
            build(ds)
        else:
            print(ds, json.dumps(score(ds), ensure_ascii=False))
