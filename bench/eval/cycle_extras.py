"""Additional round-trip figures, added after review and not pre-registered, computed from the
saved answers only (no model is asked).

python -m bench.eval.cycle_extras holdout4 holdout5 > results/cycle_extras.json   # engine 0.3 (release 0.3.1)
python -m bench.eval.cycle_extras holdout6 > results/cycle_extras.holdout6.json  # engine 0.4

The saved answers are found by a hash of the prompt, so a set can be scored only with the engine
version that produced its answers.

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
import re
import sys

from bench import ROOT
from bench.eval import cycle

# documents per type in each run, as in the run scripts and results/cycle_metrics.<set>.json
PER_TYPE = {
    "holdout4": {"pii_roundtrip": 4, "other": 4},
    "holdout5": {"pii_roundtrip": 38, "other": 4},
    # set 6: only the engine; the other configurations were not run again (their detection is unchanged)
    "holdout6": {"pii_roundtrip": 38, "other": 0},
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


_LABEL = re.compile(r"\[[A-Z]+(?:_[A-Z]+)*_\d+\]")


def value_fidelity(data: str, lang: str, per_type: int) -> dict:
    """Pre-registered for held-out set 6 as a companion measure: for every name the engine masked in
    the round-trip documents, does the value it stored keep every word of the source mention (in some
    case form)? The round-trip evaluator compares answers with the stored value, so a word dropped from
    the stored value ("Большакова Милан Андреевича" stored as "Большаков Андреевич") is invisible to it."""
    from bench.eval.run import load_tool
    from pii_roundtrip import lexicon, names

    tool = load_tool("pii_roundtrip")
    elang = "en-GB" if lang == "uk" else lang
    total, lost = 0, []
    for d in cycle.pick_docs(lang, per_type, data):
        text = d["text"]
        spans = tool.engine.spans(text, elang)
        anon, session = tool.engine.anonymize(text, elang)
        labels = _LABEL.findall(anon)
        if len(labels) != len(spans):
            continue  # a label-like word in the source text; not aligned, skipped
        for sp, lab in zip(spans, labels, strict=True):
            if sp.type != "PERSON":
                continue
            stored = session.mapping[lab]
            stored_words = {w.lower().replace("ё", "е") for w in re.findall(r"[\w'’-]+", stored)}
            words = [
                w
                for w in re.findall(r"[\w'’-]+", text[sp.start : sp.end])
                if len(w) > 1
                and w[:1].isupper()
                and w.lower().strip(".") not in lexicon.TITLES | lexicon.ROLES | {"уважаемый", "уважаемая"}
                and not (lang == "ru" and names._not_a_name_ru(w))
            ]
            total += 1
            if lang == "ru":
                missing = [w for w in words if not (cycle._ru_forms(w) & stored_words)]
            else:
                missing = [w for w in words if w.lower() not in stored_words]
            if missing:
                lost.append({"id": d["id"], "mention": text[sp.start : sp.end], "stored": stored, "missing": missing})
    return {"mentions": total, "lost": len(lost), "examples": lost[:20], "_all": lost}


def main() -> None:
    os.chdir(ROOT)
    out: dict = {}
    fails: dict = {}
    for data in sys.argv[1:] or ["holdout6"]:
        per = PER_TYPE[data]
        rows: dict = {}
        other: dict = {}
        with contextlib.redirect_stdout(sys.stderr):  # cycle.run prints its summary lines
            cycle.run(MODELS, per["pii_roundtrip"], {"pii_roundtrip"}, data, rescore=True, rows_out=rows)
            if per["other"]:
                cycle.run(MODELS, per["other"], OTHER, data, rescore=True, rows_out=other)
        rows.update(other)
        for (tool, lang, model), rs in sorted(rows.items()):
            out.setdefault(data, {}).setdefault(tool, {})[f"{lang}/{model}"] = summarise(rs)
            if tool.split("@")[0] in ("pii_roundtrip", "pii_guard"):
                f = failures(rs)
                if f:
                    fails.setdefault(data, {}).setdefault(tool, {})[f"{lang}/{model}"] = f
        overlap = {}
        for lang in ("ru", "uk") if per["other"] else ():
            a = {d["id"] for d in cycle.pick_docs(lang, per["other"], data)}
            b = {d["id"] for d in cycle.pick_docs(lang, per["pii_roundtrip"], data)}
            overlap[lang] = {"competitor_docs": len(a), "engine_docs": len(b), "shared": sorted(a & b)}
        out[data]["_overlap"] = overlap
        if data == "holdout6":
            with contextlib.redirect_stdout(sys.stderr):
                out[data]["_value_fidelity"] = {
                    lang: value_fidelity(data, lang, per["pii_roundtrip"]) for lang in ("ru", "uk")
                }
    out["_failures"] = fails
    out["_note"] = (
        "Computed from the saved answers; no model was asked. Held-out set 6: answers with a failure "
        "(Clopper-Pearson) and value fidelity were pre-registered as companion measures (HOLDOUT.md); "
        "restoration without values leaked into the input was not. Held-out sets 4 and 5: added after "
        "review, not pre-registered."
    )
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
