"""One-time run on a held-out set (data/holdout*, hashes in HOLDOUT.md).

python -m bench.eval.holdout --set 3 --tools pii_roundtrip,pii_guard,gliner_guard,presidio,privacy_filter,prompt_anonymizer,regex_baseline

Before running, checks the files' SHA-256 against HOLDOUT.md. Each run is recorded in
results/holdout_runs.jsonl (tool, set, commit, time). Re-running the same tool on the same
set is forbidden; if it is needed, the reason is stated explicitly (--rerun-reason) and goes
into the log, and the report must mention it.

--rescore recomputes the metrics from already stored predictions (for example, after a
metric fix) and does not run the tools: if even one prediction for the current code version
is missing, the recomputation is not performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime

from bench import ROOT
from bench.eval import run

LOG = ROOT / "results" / "holdout_runs.jsonl"
SETS = {
    "1": "holdout",
    "2": "holdout2",
    "3": "holdout3",
    "4": "holdout4",
    "5": "holdout5",
    "6": "holdout6",
    "7": "holdout7",
}


def check_hashes(folder: str) -> None:
    expected = dict(
        re.findall(r"\| (" + folder + r"/\w+\.jsonl) \| `([0-9a-f]{64})` \|", (ROOT / "HOLDOUT.md").read_text())
    )
    if not expected:
        sys.exit(f"HOLDOUT.md has no hashes for {folder}")
    for path, h in expected.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != h:
            sys.exit(f"{path}: hash does not match HOLDOUT.md")
    print(f"Hashes of {folder} match HOLDOUT.md")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def previous_runs() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def rescore(name: str, folder: str, tools: list[str]) -> None:
    """Metrics from stored predictions only; refuses if any prediction is missing or stale."""
    for t in tools:
        version = run.code_version(t)
        for lang in ("ru", "uk"):
            if not run.LazyTool(t).supports(lang):
                continue
            docs = run.load_docs(str(ROOT / folder / f"{lang}.jsonl"))
            cache = ROOT / "results" / t / f"{name}_{lang}.jsonl"
            have = set()
            if cache.exists():
                have = {(c["id"], c["h"]) for c in run.load_docs(str(cache)) if c.get("v") == version}
            missing = [d["id"] for d in docs if (d["id"], run.text_hash(d["text"])) not in have]
            if missing:
                sys.exit(
                    f"{t} / {name}_{lang}: {len(missing)} predictions of the current version are missing; rescoring is not possible"
                )
    run.DATASETS.update({f"{name}_{lang}": (str(ROOT / folder / f"{lang}.jsonl"), lang) for lang in ("ru", "uk")})
    sys.argv = [sys.argv[0], "--tools", ",".join(tools), "--datasets", f"{name}_ru,{name}_uk"]
    run.main()
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        for t in tools:
            f.write(
                json.dumps(
                    {"set": name, "tool": t, "rescore": True, "commit": _git("rev-parse", "HEAD"), "time": stamp}
                )
                + "\n"
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="set_", choices=sorted(SETS), default="1")
    ap.add_argument("--set2", action="store_true", help="same as --set 2 (old option)")
    ap.add_argument("--tools", required=True)
    ap.add_argument("--rerun-reason", default="", help="required if the tool has already been run on this set")
    ap.add_argument("--rescore", action="store_true", help="only recompute the metrics from stored predictions")
    args, rest = ap.parse_known_args()
    name = SETS["2" if args.set2 else args.set_]
    folder = f"data/{name}"
    check_hashes(folder)
    tools = args.tools.split(",")
    if args.rescore:
        rescore(name, folder, tools)
        return
    done = {r["tool"] for r in previous_runs() if r["set"] == name and not r.get("rescore")}
    again = sorted(done & set(tools))
    if again and not args.rerun_reason:
        sys.exit(f"Already run on {name}: {', '.join(again)}. A repeat run requires --rerun-reason.")
    commit, dirty = _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain", "--untracked-files=no"))
    if dirty:
        sys.exit("The working tree is not committed: a run on a held-out set is made only from a clean commit.")
    run.DATASETS.update({f"{name}_{lang}": (str(ROOT / folder / f"{lang}.jsonl"), lang) for lang in ("ru", "uk")})
    sys.argv = [sys.argv[0], "--tools", args.tools, "--datasets", f"{name}_ru,{name}_uk", *rest]
    run.main()
    LOG.parent.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        for t in tools:
            entry = {"set": name, "tool": t, "commit": commit, "time": stamp}
            if t in again:
                entry["rerun_reason"] = args.rerun_reason
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
