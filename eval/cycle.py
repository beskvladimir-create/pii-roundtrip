"""Полный цикл: очистка → ответ локальной нейросети → восстановление → проверка.

python -m eval.cycle --models qwen3.5:9b,gemma4:12b --per-type 4

Участники:
- RU: pii_guard (собственная очистка и восстановление), лучший детектор + общие метки;
- UK: prompt_anonymizer (собственные), лучший детектор + общие метки.

Ответы нейросети кешируются в results/cycle/<tool>/<model>.jsonl.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import json
import random
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

from eval import metrics
from eval.run import load_docs, load_tool

OUT = Path("results/cycle")
OLLAMA = "http://127.0.0.1:11434/api/chat"

TASKS = {
    "ru": {
        "summary": "Сделай краткое содержание документа (5–7 предложений). Обязательно назови всех участников по именам и укажи их контакты и реквизиты (паспорт, СНИЛС, ИНН, счёт, карта, адрес), если они есть.",
        "reply": "Напиши ответное деловое письмо по этому документу от имени получателя. Обратись к участникам по имени и повтори в письме реквизиты, которые нужно подтвердить.",
    },
    "uk": {
        "summary": "Write a short summary of this document (5-7 sentences). Name every party and give their contact details and identifiers (NI, NHS, account, card, address) where present.",
        "reply": "Write a formal reply letter to this document on behalf of the recipient. Address the people by name and repeat the details that need to be confirmed.",
    },
}

GENERIC_SYSTEM = (
    "The text contains placeholders that replace personal data. Keep every placeholder you use "
    "exactly as written. Never replace placeholders with invented values."
)

# Шаблоны меток каждого инструмента: дословные и «похожие» (искажённые нейросетью).
LABEL_PATTERNS = {
    # тег ищется по атрибутам: испорченное закрытие («»», «*/», «>») не склеивает соседние теги
    "pii_guard": re.compile(r'<\s*PII\b(?:\s+[\w-]+\s*=\s*\\?"[^"<>]*\\?")+\s*(?:/\s*>|>|\*/|/?»|/)?', re.I),
    "prompt_anonymizer": re.compile(r"<\s*[A-Za-z]+_\d+\s*>"),
    "placeholders": re.compile(r"\[?\b[A-Z][A-Z_]*_\d+\b\]?"),
}


def ask(model: str, system: str, user: str) -> str:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "seed": 0, "num_ctx": 16384},
    }
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())["message"]["content"]


def pick_docs(lang: str, per_type: int) -> list[dict]:
    docs = load_docs(f"data/synthetic/{lang}.jsonl")
    rng = random.Random(1)
    by_type = defaultdict(list)
    for d in docs:
        by_type[d["doc_type"]].append(d)
    return [d for t in sorted(by_type) for d in rng.sample(by_type[t], per_type)]


@lru_cache(maxsize=50000)
def _ru_forms(word: str) -> frozenset[str]:
    from pii_roundtrip.names import morph

    forms = {word.lower()}
    for p in morph().parse(word)[:3]:
        forms.update(lex.word for lex in p.lexeme)
    return frozenset(f.replace("ё", "е") for f in forms)


def _value_restored(value: str, restored: str, lang: str, is_person: bool = False) -> bool:
    """Значение считается восстановленным, если оно есть в ответе. Для русского текста
    слова могут стоять в другом падеже («Тула» -> «в Туле»), цифры совпадают точно."""
    if value in restored:
        return True
    norm = lambda s: re.sub(r"[\s\-]", "", s).lower()
    if norm(value) and norm(value) in norm(restored):
        return True
    if lang != "ru":
        return False
    digits = re.findall(r"\d+", value)
    if digits and not all(d in restored for d in digits):
        return False
    words = [w for w in re.findall(r"[А-Яа-яЁё]{3,}", value)]
    if not words:
        return bool(digits)
    text_words = {w.lower().replace("ё", "е") for w in re.findall(r"[А-Яа-яЁё-]+", restored)}
    text_words |= {p for w in list(text_words) for p in w.split("-")}
    return all(_ru_forms(w) & text_words for w in words)


def _identity(family: str, label: str, known_types: set[str] | None = None) -> tuple[str, str] | None:
    """Кому принадлежит метка: (тип, номер). Для тегов pii-guard по атрибутам type и id,
    для меток вида [TYPE_n] по типу (с отбрасыванием приписок вроде ORG_NAME_ORG_1)."""
    if family == "pii_guard":
        t = re.search(r'type\s*=\s*\\?"(\w+)', label)
        i = re.search(r'id\s*=\s*\\?"(\d+)', label)
        return (t.group(1).upper(), i.group(1)) if t and i else None
    m = re.search(r"([A-Za-z]+(?:_[A-Za-z]+)*)[\s_-]*(\d+)", label)
    if not m:
        return None
    t, n = m.group(1).upper(), m.group(2)
    if known_types:
        parts = t.split("_")
        for i in range(len(parts)):
            if "_".join(parts[i:]) in known_types:
                return ("_".join(parts[i:]), n)
    return (t, n)


def evaluate_answer(family: str, mapping: dict, answer: str, restored: str, lang: str) -> dict:
    """Метки делятся на выданные инструментом (их тип и номер есть в таблице) и выдуманные
    нейросетью. Доля восстановления считается по выданным: дословным и искажённым."""
    pat = LABEL_PATTERNS[family]
    key_ids = {}
    for k in mapping:
        i = _identity(family, k)
        if i:
            key_ids[i] = k
    types = {t for t, _ in key_ids}
    found = pat.findall(answer)
    ident = [(f, _identity(family, f, types)) for f in found]
    issued = [(f, i) for f, i in ident if i in key_ids]
    invented = [f for f, i in ident if i not in key_ids]
    exact = [f for f, _ in issued if f in mapping]
    altered = [f for f, _ in issued if f not in mapping]
    issued_ids = {i for _, i in issued}
    residual = [r for r in pat.findall(restored) if _identity(family, r, types) in issued_ids]
    used_keys = {key_ids[i] for i in issued_ids}
    lost = [k for k in used_keys if not _value_restored(mapping[k], restored, lang, "PERSON" in k.upper())]
    return {
        "labels_in_answer": len(issued),
        "exact": len(exact),
        "altered": len(altered),
        "altered_recoverable": len(altered) - sum(1 for r in residual if r not in mapping),
        "invented": len(invented),
        "residual_after_restore": len(residual),
        "scrubbed": restored.count("****") - answer.count("****"),
        "values_lost": len(lost),
        "used_values": len(used_keys),
        "lost_examples": [mapping[k] for k in lost][:3],
        "residual_examples": residual[:3],
        "altered_examples": altered[:3],
        "invented_examples": invented[:3],
    }


def run(models: list[str], per_type: int, only: set[str] | None = None) -> dict:
    from runners.placeholders import PlaceholderWrapper

    plan = {
        "ru": [("pii_guard", "pii_guard"), ("pii_guard+placeholders", "placeholders"), ("pii_roundtrip", "placeholders")],
        "uk": [("prompt_anonymizer", "prompt_anonymizer"), ("gliner_guard+placeholders", "placeholders"), ("pii_roundtrip", "placeholders")],
    }
    report: dict = {}
    for lang, tools in plan.items():
        docs = pick_docs(lang, per_type)
        for tool_name, family in tools:
            if only and tool_name not in only:
                continue
            if tool_name.endswith("+placeholders"):
                tool = PlaceholderWrapper(load_tool(tool_name.split("+")[0]))
            else:
                tool = load_tool(tool_name)
            system = tool.system_prompt() if hasattr(tool, "system_prompt") else GENERIC_SYSTEM
            for model in models:
                path = OUT / tool_name / f"{lang}_{model.replace(':', '_')}.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                cache = {}
                if path.exists():
                    for line in path.open(encoding="utf-8"):
                        r = json.loads(line)
                        cache[(r["id"], r["task"])] = r
                rows = []
                with path.open("a", encoding="utf-8") as f:
                    for d in docs:
                        anon, mapping = tool.anonymize(d["text"], lang)
                        for task, instruction in TASKS[lang].items():
                            key = (d["id"], task)
                            if key in cache:
                                answer = cache[key]["answer"]
                            else:
                                answer = ask(model, system, f"{instruction}\n\n{anon}")
                                f.write(json.dumps({"id": d["id"], "task": task, "answer": answer}, ensure_ascii=False) + "\n")
                                f.flush()
                            restored = tool.deanonymize(answer, mapping)
                            plain = getattr(mapping, "mapping", mapping)  # движок отдаёт Session
                            ev = evaluate_answer(family, plain, answer, restored, lang)
                            ev["input_leaks"] = len(metrics.leaked_values(d, anon))
                            ev.update({"id": d["id"], "task": task})
                            rows.append(ev)
                agg = aggregate(rows)
                report.setdefault(tool_name, {})[f"{lang}/{model}"] = agg
                print(f"{tool_name:28s} {lang} {model:12s} {json.dumps({k: v for k, v in agg.items() if k != 'examples'}, ensure_ascii=False)}")
    return report


def _answer_ok(r: dict) -> tuple[int, int]:
    """Сколько меток ответа восстановлено верно и сколько их всего."""
    # pii-guard затирает в «****» и свои испорченные теги, и выдуманные нейросетью:
    # ошибкой считается только затёртое сверх числа выдуманных, без двойного счёта с потерями
    own_scrubbed = max(0, r["scrubbed"] - r.get("invented", 0))
    bad = r["residual_after_restore"] + max(r["values_lost"], own_scrubbed)
    return max(0, r["labels_in_answer"] - bad), r["labels_in_answer"]


def bootstrap_ci(rows: list[dict], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% интервал бутстрепом по ответам: метки внутри одного ответа не независимы."""
    rng = random.Random(seed)
    pairs = [_answer_ok(r) for r in rows if r["labels_in_answer"]]
    if not pairs:
        return (0.0, 1.0)
    stats = []
    for _ in range(n):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        tot = sum(t for _, t in sample)
        stats.append(sum(k for k, _ in sample) / tot if tot else 1.0)
    stats.sort()
    return (stats[int(0.025 * n)], stats[int(0.975 * n) - 1])


def aggregate(rows: list[dict]) -> dict:
    s = lambda k: sum(r[k] for r in rows)
    labels = s("labels_in_answer")
    ok = sum(_answer_ok(r)[0] for r in rows)
    return {
        "answers": len(rows),
        "answers_with_labels": sum(1 for r in rows if r["labels_in_answer"]),
        "labels_in_answer": labels,
        "exact_share": s("exact") / labels if labels else None,
        "altered": s("altered"),
        "altered_recoverable": s("altered_recoverable"),
        "invented": s("invented"),
        "restore_rate": ok / labels if labels else None,
        "restore_ci": bootstrap_ci(rows),
        "restore_ci_method": "bootstrap по ответам, 2000 повторов",
        "residual_labels": s("residual_after_restore"),
        "scrubbed": max(0, s("scrubbed")),
        "values_lost": s("values_lost"),
        "used_values": s("used_values"),
        "docs_with_input_leak": sum(1 for r in rows if r["input_leaks"] and r["task"] == "summary"),
        "examples": [
            {k: r[k] for k in ("id", "task", "lost_examples", "residual_examples", "altered_examples", "invented_examples")}
            for r in rows
            if r["lost_examples"] or r["residual_examples"] or r["altered_examples"] or r["invented_examples"]
        ][:15],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3.5:9b,gemma4:12b")
    ap.add_argument("--per-type", type=int, default=4)
    ap.add_argument("--tools", default="", help="через запятую; по умолчанию все")
    args = ap.parse_args()
    report = run(args.models.split(","), args.per_type, set(args.tools.split(",")) if args.tools else None)
    p = Path("results/cycle_metrics.json")
    cur = json.loads(p.read_text()) if p.exists() else {}
    for k, v in report.items():
        cur.setdefault(k, {}).update(v)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
