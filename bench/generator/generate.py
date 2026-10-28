"""Generates the synthetic set: python -m bench.generator.generate [--seed N] [--out DIR]."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
from collections import Counter
from pathlib import Path

from bench.generator import templates_ru, templates_uk
from bench.generator.persons import DEFAULT_NOW, World
from bench.generator.render import STRUCTURED, Doc, Noise

DEFAULT_SEED = 20261012
PER_TYPE = 20
NOISY_SHARE = 0.4

LANGS = {"ru": templates_ru.DOC_TYPES, "uk": templates_uk.DOC_TYPES}


def make_noise(rng: random.Random, hard: float = 0.0) -> Noise:
    if rng.random() >= NOISY_SHARE:
        return Noise()
    return Noise(double_space=0.03, typo=0.01, name_typo=0.05, alt_format=0.5, hard_format=hard)


def generate(
    seed: int = DEFAULT_SEED, per_type: int = PER_TYPE, hard: float = 0.0, now: dt.date = DEFAULT_NOW
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for lang_i, (lang, types) in enumerate(LANGS.items()):
        world = World(seed + lang_i * 1000, now)
        docs = []
        for doc_type, build in types.items():
            for i in range(per_type):
                noise = make_noise(world.rng, hard)
                d = Doc(world.rng, noise, lang)
                build(world, d)
                docs.append(
                    {
                        "id": f"{lang}-{doc_type}-{i:03d}",
                        "lang": lang,
                        "doc_type": doc_type,
                        "noisy": noise != Noise(),
                        "text": d.text(),
                        "entities": d.entities,
                    }
                )
        out[lang] = docs
    return out


def stats(docs: list[dict]) -> Counter:
    return Counter(e["type"] for doc in docs for e in doc["entities"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--hard", type=float, default=0.0, help="share of hard number formats in noisy documents")
    ap.add_argument("--per-type", type=int, default=PER_TYPE, help="documents of each type per language")
    ap.add_argument(
        "--now",
        type=dt.date.fromisoformat,
        default=DEFAULT_NOW,
        help="the date Faker treats as today (YYYY-MM-DD)",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for lang, docs in generate(args.seed, per_type=args.per_type, hard=args.hard, now=args.now).items():
        path = args.out / f"{lang}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        c = stats(docs)
        print(f"{path}: {len(docs)} documents")
        for t, n in sorted(c.items()):
            mark = " *" if t in STRUCTURED else ""
            print(f"  {t:16s} {n:5d}{mark}")
    (args.out / "SEED").write_text(str(args.seed) + "\n")


if __name__ == "__main__":
    main()
