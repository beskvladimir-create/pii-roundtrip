"""Эталон поведения движка: выходы на выборке документов до рефакторинга.

uv run python -m scripts.golden save  golden.json   # снять эталон
uv run python -m scripts.golden check golden.json   # сравнить текущий код с эталоном

Сравниваются очищенный текст, таблица меток и восстановленный ответ, в котором
каждая метка стоит в разных падежных контекстах (проверка склонения русских имён).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

SETS = {
    "data/synthetic/ru.jsonl": "ru",
    "data/synthetic/uk.jsonl": "en-GB",
    "data/holdout2/ru.jsonl": "ru",
    "data/holdout2/uk.jsonl": "en-GB",
    "data/external/hivetrace_pii_bench.jsonl": "ru",
    "data/external/redmadrobot_pii_benchmark.jsonl": "ru",
    "data/external/nemotron_uk_ids.jsonl": "en-GB",
}
PER_SET = 40


def answer_for(mapping: dict, lang: str) -> str:
    labels = sorted(mapping)
    if lang == "ru":
        return " ".join(f"Письмо направлено {lab}. Встреча с {lab}. Подпись: {lab}." for lab in labels)
    return " ".join(f"Dear {lab}, we confirm {lab}." for lab in labels)


def run() -> dict:
    from pii_roundtrip.core import Engine

    eng = Engine()
    out = {}
    for path, lang in SETS.items():
        with open(path, encoding="utf-8") as f:
            docs = [json.loads(line) for line in f]
        for d in random.Random(7).sample(docs, min(PER_SET, len(docs))):
            text, session = eng.anonymize(d["text"], lang)
            restored = eng.deanonymize(answer_for(session.mapping, lang), session)
            out[f"{path}#{d['id']}"] = {"text": text, "mapping": session.mapping, "restored": restored}
    return out


def main() -> None:
    mode, path = sys.argv[1], Path(sys.argv[2])
    cur = run()
    if mode == "save":
        path.write_text(json.dumps(cur, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"сохранено {len(cur)} документов")
        return
    ref = json.loads(path.read_text(encoding="utf-8"))
    diff = [k for k in ref if ref[k] != cur.get(k)]
    print(f"проверено {len(ref)}, расхождений {len(diff)}")
    for k in diff[:5]:
        for f in ("text", "mapping", "restored"):
            if ref[k][f] != cur[k][f]:
                print(" ", k, f, "\n    было:", str(ref[k][f])[:300], "\n    стало:", str(cur[k][f])[:300])
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
