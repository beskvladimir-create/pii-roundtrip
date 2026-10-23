"""The engine's restoration on a held-out set scored with every version of the round-trip
evaluator (bench/eval/cycle.py, EVALUATOR), from the saved answers; no model is asked.

python -m bench.eval.evaluator_versions holdout6 > results/evaluator_versions.holdout6.json
python -m bench.eval.evaluator_versions holdout5 > results/evaluator_versions.holdout5.json   # engine 0.3

Version 1 is the evaluator of held-out sets 4 and 5 as run; version 2 adds surname and first-name
case forms by rule and was fixed before set 6. The saved answers are found by a hash of the prompt,
so a set can be scored only with the engine version that produced its answers (set 5: engine 0.3,
for example in a worktree of release 0.3.1 with this file and bench/eval/cycle.py copied in).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys

from bench import ROOT
from bench.eval import cycle

MODELS = ["qwen3.5:9b", "gemma4:12b"]
KEYS = (
    "labels_in_answer",
    "occurrences_failed",
    "restore_rate",
    "restore_ci",
    "answers_with_failure",
    "answers_with_labels",
    "person_labels",
    "restore_rate_person",
    "restore_ci_person",
)


def main() -> None:
    os.chdir(ROOT)
    data = sys.argv[1]
    versions = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else range(1, cycle.EVALUATOR + 1)
    out: dict = {}
    failures: dict = {}
    for ev in versions:
        cycle.EVALUATOR = ev
        cycle._ru_forms.cache_clear()
        rows: dict = {}
        with contextlib.redirect_stdout(sys.stderr):
            cycle.run(MODELS, 38, {"pii_roundtrip"}, data, rescore=True, rows_out=rows)
        for (_tool, lang, model), rs in sorted(rows.items()):
            a = cycle.aggregate(rs)
            out.setdefault(f"{lang}/{model}", {})[f"evaluator_{ev}"] = {k: a[k] for k in KEYS}
            if ev == min(versions):
                failures[f"{lang}/{model}"] = [
                    {"id": r["id"], "task": r["task"], "label": k, "value": v}
                    for r in rs
                    for k, v, bad in r["occurrence_detail"]
                    if bad
                ]
    out["_failures_evaluator_1"] = failures
    out["_note"] = (
        f"Held-out {data}: the engine's restoration from the saved answers scored with evaluator versions "
        f"{', '.join(map(str, versions))} (bench/eval/evaluator_versions.py). Both compare the answer with the "
        "value the tool stored; an error in the stored value is not visible to them (see results/stored_names.*.json)."
    )
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
