"""Однократный прогон на отложенном наборе (data/holdout*, хеши в HOLDOUT.md).

python -m bench.eval.holdout --set 3 --tools pii_roundtrip,pii_guard,gliner_guard,presidio,privacy_filter,prompt_anonymizer,regex_baseline

Перед запуском сверяет SHA-256 файлов с HOLDOUT.md. Каждый прогон записывается в
results/holdout_runs.jsonl (инструмент, набор, коммит, время). Повторный прогон того же
инструмента на том же наборе запрещён; если он нужен, причина указывается явно
(--rerun-reason) и попадает в журнал, а отчёт обязан её упомянуть.

--rescore пересчитывает метрики по уже сохранённым предсказаниям (например, после
исправления метрики) и не запускает инструменты: если хоть одного предсказания текущей
версии кода нет, пересчёт не выполняется.
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
SETS = {"1": "holdout", "2": "holdout2", "3": "holdout3", "4": "holdout4", "5": "holdout5", "6": "holdout6"}


def check_hashes(folder: str) -> None:
    expected = dict(
        re.findall(r"\| (" + folder + r"/\w+\.jsonl) \| `([0-9a-f]{64})` \|", (ROOT / "HOLDOUT.md").read_text())
    )
    if not expected:
        sys.exit(f"В HOLDOUT.md нет хешей для {folder}")
    for path, h in expected.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != h:
            sys.exit(f"{path}: хеш не совпадает с HOLDOUT.md")
    print(f"Хеши {folder} совпадают с HOLDOUT.md")


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
                sys.exit(f"{t} / {name}_{lang}: нет {len(missing)} предсказаний текущей версии; пересчёт невозможен")
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
    ap.add_argument("--set2", action="store_true", help="то же, что --set 2 (старый ключ)")
    ap.add_argument("--tools", required=True)
    ap.add_argument("--rerun-reason", default="", help="обязательно, если инструмент уже прогонялся на этом наборе")
    ap.add_argument("--rescore", action="store_true", help="только пересчёт метрик по сохранённым предсказаниям")
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
        sys.exit(f"Уже прогонялись на {name}: {', '.join(again)}. Повтор только с --rerun-reason.")
    commit, dirty = _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain", "--untracked-files=no"))
    if dirty:
        sys.exit("Рабочее дерево не закоммичено: прогон на отложенном наборе делается только с чистого коммита.")
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
