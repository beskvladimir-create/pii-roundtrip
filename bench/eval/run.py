"""Запуск инструментов на наборах и подсчёт метрик распознавания и утечек.

python -m bench.eval.run --tools regex_baseline,presidio --datasets all
Предсказания кешируются в results/<tool>/<dataset>.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import time
from pathlib import Path

from bench import ROOT
from bench.eval import metrics
from bench.runners.base import resolve_overlaps

RESULTS = ROOT / "results"

DATASETS = {
    "synthetic_ru": (str(ROOT / "data/synthetic/ru.jsonl"), "ru"),
    "synthetic_uk": (str(ROOT / "data/synthetic/uk.jsonl"), "uk"),
    "hivetrace_pii_bench": (str(ROOT / "data/external/hivetrace_pii_bench.jsonl"), "ru"),
    "redmadrobot_pii_benchmark": (str(ROOT / "data/external/redmadrobot_pii_benchmark.jsonl"), "ru"),
    "nemotron_uk": (str(ROOT / "data/external/nemotron_uk.jsonl"), "uk"),
    "nemotron_uk_ids": (str(ROOT / "data/external/nemotron_uk_ids.jsonl"), "uk"),
}

TOOLS = {
    "regex_baseline": "bench.runners.regex_baseline:RegexBaseline",
    "presidio": "bench.runners.presidio_runner:PresidioRunner",
    "pii_guard": "bench.runners.pii_guard_runner:PiiGuardRunner",
    "gliner_guard": "bench.runners.gliner_guard_runner:GlinerGuardRunner",
    "privacy_filter": "bench.runners.privacy_filter_runner:PrivacyFilterRunner",
    "prompt_anonymizer": "bench.runners.prompt_anonymizer_runner:PromptAnonymizerRunner",
    "llm_detector": "bench.runners.llm_detector:LlmDetector",
    "pii_roundtrip": "bench.runners.pii_roundtrip_runner:PiiRoundtripRunner",
}


def load_tool(name: str):
    mod, cls = TOOLS[name].split(":")
    return getattr(importlib.import_module(mod), cls)()


class LazyTool:
    """Загружает модель, только если предсказаний нет в кеше."""

    def __init__(self, name: str):
        self.name, self._tool = name, None
        mod, cls = TOOLS[name].split(":")
        self._langs = getattr(getattr(importlib.import_module(mod), cls), "langs", frozenset({"ru", "uk"}))

    @property
    def loaded(self) -> bool:
        return self._tool is not None

    def supports(self, lang: str) -> bool:
        return lang in self._langs

    def __getattr__(self, attr):
        if self._tool is None:
            self._tool = load_tool(self.name)
        return getattr(self._tool, attr)


def load_docs(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# Код, от которого зависят предсказания каждого инструмента: при его изменении кеш сбрасывается.
CODE_DEPS = {
    "regex_baseline": ["bench/runners/regex_baseline.py", "pii_roundtrip/checksums.py"],
    "presidio": ["bench/runners/presidio_runner.py", "pii_roundtrip/checksums.py"],
    "pii_guard": ["bench/runners/pii_guard_runner.py", "pii_roundtrip/adapters/pii_guard.py"],
    "gliner_guard": ["bench/runners/gliner_guard_runner.py", "bench/runners/chunking.py"],
    "privacy_filter": ["bench/runners/privacy_filter_runner.py"],
    "prompt_anonymizer": ["bench/runners/prompt_anonymizer_runner.py"],
    "llm_detector": ["bench/runners/llm_detector.py", "bench/runners/chunking.py"],
    "pii_roundtrip": ["bench/runners/pii_roundtrip_runner.py", "pii_roundtrip/*.py", "pii_roundtrip/adapters/*.py"],
}


def code_version(name: str) -> str:
    h = hashlib.sha256()
    # code of the tool adapter, the shared post-processing and the locked dependency versions
    for pattern in ["bench/runners/base.py", "bench/eval/run.py", "uv.lock", *CODE_DEPS.get(name, [])]:
        for f in sorted(ROOT.glob(pattern)):
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def postprocess(spans: list, text: str) -> list[dict]:
    """Одинаково для всех: объединение пересечений и расширение до границ слова."""
    return [s.as_dict() for s in resolve_overlaps(list(spans), text)]


def predict(tool, name: str, ds: str, docs: list[dict], lang: str, force: bool) -> list[list[dict]]:
    out = RESULTS / name / f"{ds}.jsonl"
    version = code_version(name)
    done: dict[str, list[dict]] = {}
    if out.exists() and not force:
        for c in load_docs(str(out)):
            if c.get("v") == version and c.get("h"):
                done[(c["id"], c["h"])] = c["pred"]
        if all((d["id"], text_hash(d["text"])) in done for d in docs):
            return [done[(d["id"], text_hash(d["text"]))] for d in docs]
    out.parent.mkdir(parents=True, exist_ok=True)
    preds = []
    t0 = time.time()
    with out.open("a" if done else "w", encoding="utf-8") as f:  # продолжение с места остановки
        for d in docs:
            key = (d["id"], text_hash(d["text"]))
            if key in done:
                preds.append(done[key])
                continue
            p = postprocess(tool.detect(d["text"], lang), d["text"])
            preds.append(p)
            f.write(json.dumps({"id": d["id"], "h": key[1], "v": version, "pred": p}, ensure_ascii=False) + "\n")
            f.flush()
    print(f"  {name} / {ds}: {len(docs)} текстов за {time.time() - t0:.0f} с")
    return preds


def evaluate(docs: list[dict], preds: list[list[dict]], lang: str) -> dict:
    acc = metrics.new_acc()
    leak_docs = 0
    leak_examples = []
    for d, p in zip(docs, preds, strict=False):
        metrics.score_doc(d, p, acc)
        leaks = metrics.leaked_values(d, metrics.mask_text(d["text"], p))
        if leaks:
            leak_docs += 1
            leak_examples.append((d["id"], leaks[:3]))
    s = metrics.summarize(acc, leak_docs, len(docs), lang)
    s["leak_examples"] = leak_examples[:20]
    return s


def fmt(g: dict) -> str:
    return f"{g['recall']:.3f} [{g['ci'][0]:.3f}; {g['ci'][1]:.3f}] n={g['n']}" if g["n"] else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default="regex_baseline")
    ap.add_argument("--datasets", default="all")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sample", type=int, default=0, help="случайная выборка N текстов из внешних наборов (seed 0)")
    args = ap.parse_args()
    tools = list(TOOLS) if args.tools == "all" else args.tools.split(",")
    dsets = list(DATASETS) if args.datasets == "all" else args.datasets.split(",")
    summary_path = RESULTS / "metrics.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in tools:
        tool = LazyTool(name)
        for ds in dsets:
            path, lang = DATASETS[ds]
            if not tool.supports(lang) or not Path(path).exists():
                continue
            docs = load_docs(path)
            key = ds
            if args.sample and not ds.startswith("synthetic") and len(docs) > args.sample:
                import random

                docs = random.Random(0).sample(docs, args.sample)
                key = f"{ds}@{args.sample}"
            preds = predict(tool, name, key, docs, lang, args.force)
            res = evaluate(docs, preds, lang)
            summary.setdefault(name, {})[key] = res
            if tool.loaded:
                summary[name]["_config"] = tool.config()
            st, nm = res["structured"], res["names"]
            print(
                f"{name:16s} {key:28s} номера {fmt(st):34s} имена/адреса/орг {fmt(nm):34s} утечки {res['leak_rate']:.3f}"
            )
    RESULTS.mkdir(exist_ok=True)
    # слияние с тем, что успели записать параллельные запуски
    current = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    for name in tools:
        current.setdefault(name, {}).update(summary.get(name, {}))
    summary_path.write_text(json.dumps(current, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
