"""Additional round-trip figures, added after review and not pre-registered, computed from the
saved answers only (no model is asked).

python -m bench.eval.cycle_extras > results/cycle_extras.json

For held-out sets 4 and 5, every configuration and model:
- the share of answers with at least one failed occurrence, with a Clopper-Pearson 95% interval;
- restoration without the occurrences whose value had already leaked into the cleaned input: such
  a value can reach the restored text because the model copied it, not because it was restored;
- the overlap between the documents of the competitors' cycle (4 per type) and of the engine's
  cycle (38 per type on set 5);
- every failed occurrence of pii-roundtrip and of pii-guard, for manual checking.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sys

from bench import ROOT
from bench.eval import cycle

# documents per type in each run, as in the run scripts and results/cycle_metrics.<set>.json
PER_TYPE = {
    "holdout4": {"pii_roundtrip": 4, "other": 4},
    "holdout5": {"pii_roundtrip": 38, "other": 4},
}
MODELS = ["qwen3.5:9b", "gemma4:12b"]
OTHER = {
    "pii_guard",
    "pii_guard@generic",
    "pii_guard+placeholders",
    "pii_guard+placeholders@generic",
    "prompt_anonymizer",
    "gliner_guard+placeholders",
    "gliner_guard+placeholders@generic",
}


def _tail_ge(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial interval, by bisection on the binomial tails."""

    def solve(f, target: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else solve(lambda p: _tail_ge(k, n, p), alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: _tail_ge(k + 1, n, p), 1 - alpha / 2)
    return (lower, upper)


def summarise(rows: list[dict]) -> dict:
    with_labels = [r for r in rows if r["labels_in_answer"]]
    failed = [r for r in with_labels if r["labels_in_answer"] > r["occurrences_ok"]]
    occ = [o for r in rows for o in r["occurrence_detail"]]
    clean = [
        (key, ok)
        for r in rows
        for key, value, bad in r["occurrence_detail"]
        for ok in [not bad]
        if value not in r["input_leaked_values"]
    ]
    return {
        "answers": len(rows),
        "answers_with_labels": len(with_labels),
        "answers_with_failure": len(failed),
        "answers_with_failure_share": len(failed) / len(with_labels) if with_labels else None,
        "answers_with_failure_ci_clopper_pearson": clopper_pearson(len(failed), len(with_labels))
        if with_labels
        else None,
        "occurrences": len(occ),
        "occurrences_failed": sum(1 for o in occ if o[2]),
        "occurrences_without_input_leaks": len(clean),
        "occurrences_without_input_leaks_failed": sum(1 for _, ok in clean if not ok),
        "restore_rate_without_input_leaks": sum(1 for _, ok in clean if ok) / len(clean) if clean else None,
        "answers_with_input_leak": sum(1 for r in rows if r["input_leaked_values"]),
    }


def failures(rows: list[dict]) -> list[dict]:
    return [
        {"id": r["id"], "task": r["task"], "label": key, "value": value}
        for r in rows
        for key, value, bad in r["occurrence_detail"]
        if bad
    ]


def main() -> None:
    os.chdir(ROOT)
    out: dict = {}
    fails: dict = {}
    for data, per in PER_TYPE.items():
        rows: dict = {}
        other: dict = {}
        with contextlib.redirect_stdout(sys.stderr):  # cycle.run prints its summary lines
            cycle.run(MODELS, per["pii_roundtrip"], {"pii_roundtrip"}, data, rescore=True, rows_out=rows)
            cycle.run(MODELS, per["other"], OTHER, data, rescore=True, rows_out=other)
        rows.update(other)
        for (tool, lang, model), rs in sorted(rows.items()):
            out.setdefault(data, {}).setdefault(tool, {})[f"{lang}/{model}"] = summarise(rs)
            if tool.split("@")[0] in ("pii_roundtrip", "pii_guard"):
                f = failures(rs)
                if f:
                    fails.setdefault(data, {}).setdefault(tool, {})[f"{lang}/{model}"] = f
        overlap = {}
        for lang in ("ru", "uk"):
            a = {d["id"] for d in cycle.pick_docs(lang, per["other"], data)}
            b = {d["id"] for d in cycle.pick_docs(lang, per["pii_roundtrip"], data)}
            overlap[lang] = {"competitor_docs": len(a), "engine_docs": len(b), "shared": sorted(a & b)}
        out[data]["_overlap"] = overlap
    out["_failures"] = fails
    out["_note"] = "Added after review, not pre-registered. Computed from the saved answers; no model was asked."
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
