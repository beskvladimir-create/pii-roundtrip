"""Полный цикл: очистка → ответ локальной нейросети → восстановление → проверка.

python -m bench.eval.cycle --models qwen3.5:9b,gemma4:12b --per-type 4 [--data holdout3]

Участники:
- RU: pii_guard (собственная очистка и восстановление), лучший детектор + общие метки;
- UK: prompt_anonymizer (собственные), лучший детектор + общие метки.

Ответы нейросети кешируются в results/cycle/[<набор>/]<tool>/<model>.jsonl. Ключ кеша включает
хеш запроса: после изменения очистки ответ запрашивается заново, а не берётся старый.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import urllib.request
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from bench import ROOT
from bench.eval import metrics
from bench.eval.run import load_docs, load_tool

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
    # also in square brackets: a model may rewrite <PII … /> as [PII …] or <Name_2> as [Name_2];
    # such occurrences are issued labels the model altered, not labels it invented
    "pii_guard": re.compile(
        r'[<\[]\s*PII\b(?:\s+[\w-]+\s*=\s*\\?"[^"<>\[\]]*\\?")+\s*(?:/\s*>|>|/\s*\]|\]|\*/|/?»|/)?', re.I
    ),
    "prompt_anonymizer": re.compile(r"<\s*[A-Za-z]+_\d+\s*>|\[\s*[A-Za-z]+_\d+\s*\]"),
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


DATA = {
    "synthetic": "data/synthetic",
    "holdout3": "data/holdout3",
    "holdout4": "data/holdout4",
    "holdout5": "data/holdout5",
}


def pick_docs(lang: str, per_type: int, data: str = "synthetic") -> list[dict]:
    docs = load_docs(f"{DATA[data]}/{lang}.jsonl")
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

    def norm(s: str) -> str:
        return re.sub(r"[\s\-]", "", s).lower()

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
    # Each occurrence the tool issued is judged once. It fails if it is still in the text after
    # restoration, if its value is not in the restored text, or if the tool's restorer scrubbed
    # it ("****"; scrubs beyond the number of invented labels are the tool's own altered tags).
    # The previous count added residual occurrences to lost unique values, so a label left in
    # the text was counted twice.
    lost_set = set(lost)
    residual_left = defaultdict(int)
    for r in residual:
        residual_left[_identity(family, r, types)] += 1
    scrubs_left = max(0, (restored.count("****") - answer.count("****")) - len(invented))
    bad = [False] * len(issued)
    for n, (_, i) in enumerate(issued):
        bad[n] = key_ids[i] in lost_set
    # a label still in the text is charged to an altered occurrence of that label first: the
    # model's spelling, not an intact neighbour, is what the restorer failed to recognise
    for want_altered in (True, False):
        for n, (f, i) in enumerate(issued):
            if not bad[n] and residual_left[i] > 0 and (f not in mapping) == want_altered:
                residual_left[i] -= 1
                bad[n] = True
    for n, (f, _) in enumerate(issued):
        if not bad[n] and f not in mapping and scrubs_left > 0:
            scrubs_left -= 1
            bad[n] = True
    occ_bad = sum(bad)
    occ_bad_altered = sum(1 for n, (f, _) in enumerate(issued) if bad[n] and f not in mapping)
    return {
        # per issued occurrence: its label in the tool's table and whether it failed (not aggregated)
        "occurrence_detail": [(key_ids[i], mapping[key_ids[i]], bad[n]) for n, (_, i) in enumerate(issued)],
        "occurrences_ok": len(issued) - occ_bad,
        # failed occurrences that the model altered, and intact ones lost with them (a restorer
        # that swallows a broken tag together with the next one)
        "failed_altered": occ_bad_altered,
        "failed_intact": occ_bad - occ_bad_altered,
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


def run(
    models: list[str],
    per_type: int,
    only: set[str] | None = None,
    data: str = "synthetic",
    rescore: bool = False,
    rows_out: dict | None = None,
) -> dict:
    """With rescore=True only saved answers are scored: a missing answer is an error, no model is asked.
    rows_out, if given, receives the per-answer rows under (tool, lang, model)."""
    from bench.runners.placeholders import PlaceholderWrapper

    plan = {
        "ru": [
            ("pii_guard", "pii_guard"),
            # те же XML-теги pii-guard, но с общим системным промптом: отделяет формат меток от промпта
            ("pii_guard@generic", "pii_guard"),
            ("pii_guard+placeholders", "placeholders"),
            # простые метки с тем же общим промптом: вместе с pii_guard@generic даёт формат × промпт
            ("pii_guard+placeholders@generic", "placeholders"),
            ("pii_roundtrip", "placeholders"),
        ],
        "uk": [
            ("prompt_anonymizer", "prompt_anonymizer"),
            ("gliner_guard+placeholders", "placeholders"),
            ("gliner_guard+placeholders@generic", "placeholders"),
            ("pii_roundtrip", "placeholders"),
        ],
    }
    report: dict = {}
    for lang, tools in plan.items():
        docs = pick_docs(lang, per_type, data)
        for tool_name, family in tools:
            if only and tool_name not in only:
                continue
            base_name = tool_name.split("@")[0]  # "@generic" only changes the system prompt
            if base_name.endswith("+placeholders"):
                tool = PlaceholderWrapper(load_tool(base_name.split("+")[0]))
            else:
                tool = load_tool(base_name)
            if tool_name.endswith("@generic"):
                system = GENERIC_SYSTEM
            else:
                system = tool.system_prompt() if hasattr(tool, "system_prompt") else GENERIC_SYSTEM
            for model in models:
                base = OUT if data == "synthetic" else OUT / data
                path = base / tool_name / f"{lang}_{model.replace(':', '_')}.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                cache = {}
                if path.exists():
                    for line in path.open(encoding="utf-8"):
                        r = json.loads(line)
                        cache[(r["id"], r["task"], r.get("q"))] = r
                rows, rows_tolerant = [], []
                with path.open("a", encoding="utf-8") as f:
                    for d in docs:
                        anon, mapping = tool.anonymize(d["text"], lang)
                        for task, instruction in TASKS[lang].items():
                            prompt = f"{instruction}\n\n{anon}"
                            q = hashlib.sha256(f"{system}\n{prompt}".encode()).hexdigest()[:16]
                            key = (d["id"], task, q)
                            if key in cache:
                                answer = cache[key]["answer"]
                            elif rescore:
                                raise SystemExit(f"no saved answer: {tool_name} {lang} {model} {d['id']} {task}")
                            else:
                                answer = ask(model, system, prompt)
                                f.write(
                                    json.dumps(
                                        {"id": d["id"], "task": task, "q": q, "answer": answer}, ensure_ascii=False
                                    )
                                    + "\n"
                                )
                                f.flush()
                            restored = tool.deanonymize(answer, mapping)
                            plain = getattr(mapping, "mapping", mapping)  # движок отдаёт Session
                            ev = evaluate_answer(family, plain, answer, restored, lang)
                            ev["input_leaked_values"] = metrics.leaked_values(d, anon)
                            ev["input_leaks"] = len(ev["input_leaked_values"])
                            ev.update({"id": d["id"], "task": task})
                            rows.append(ev)
                            if family == "pii_guard":
                                # the same answer restored by label type and number, not by pii-guard
                                ev_t = evaluate_answer(
                                    family, plain, answer, tolerant_restore(family, plain, answer), lang
                                )
                                ev_t.update({k: ev[k] for k in ("input_leaked_values", "input_leaks", "id", "task")})
                                rows_tolerant.append(ev_t)
                agg = aggregate(rows)
                if rows_out is not None:
                    rows_out[(tool_name, lang, model)] = rows
                    if rows_tolerant:
                        rows_out[(f"{tool_name}~tolerant", lang, model)] = rows_tolerant
                report.setdefault(tool_name, {})[f"{lang}/{model}"] = agg
                if rows_tolerant:
                    report.setdefault(f"{tool_name}~tolerant", {})[f"{lang}/{model}"] = aggregate(rows_tolerant)
                print(
                    f"{tool_name:28s} {lang} {model:12s} {json.dumps({k: v for k, v in agg.items() if k != 'examples'}, ensure_ascii=False)}"
                )
    return report


def _answer_ok(r: dict) -> tuple[int, int]:
    """Сколько выданных инструментом вхождений меток восстановлено верно и сколько их всего:
    каждое вхождение оценивается один раз (см. evaluate_answer)."""
    return r["occurrences_ok"], r["labels_in_answer"]


def tolerant_restore(family: str, mapping: dict, answer: str) -> str:
    """Restoration by the label's type and number, whatever the model did to its spelling
    (for pii-guard tags: a missing slash, a stray «»», changed attribute order). Used to score
    the same saved answers with a lenient restorer, so that the tag format can be compared with
    simple labels without the difference between the tools' own restorers."""
    pat = LABEL_PATTERNS[family]
    key_ids = {i: k for k in mapping if (i := _identity(family, k))}
    types = {t for t, _ in key_ids}

    def sub(m: re.Match) -> str:
        i = _identity(family, m.group(0), types)
        return mapping[key_ids[i]] if i in key_ids else m.group(0)

    return pat.sub(sub, answer)


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
    def s(k: str) -> int:
        return sum(r[k] for r in rows)

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
        "occurrences_failed": labels - ok,
        "failed_altered": s("failed_altered"),
        "failed_intact": s("failed_intact"),
        "answers_with_altered": sum(1 for r in rows if r["altered"]),
        "docs_with_altered": sorted({r["id"] for r in rows if r["altered"]}),
        "answers_with_failure": sum(1 for r in rows if r["labels_in_answer"] > r["occurrences_ok"]),
        "docs_with_failure": sorted({r["id"] for r in rows if r["labels_in_answer"] > r["occurrences_ok"]}),
        "values_lost": s("values_lost"),
        "used_values": s("used_values"),
        "docs_with_input_leak": sum(1 for r in rows if r["input_leaks"] and r["task"] == "summary"),
        "examples": [
            {
                k: r[k]
                for k in ("id", "task", "lost_examples", "residual_examples", "altered_examples", "invented_examples")
            }
            for r in rows
            if r["lost_examples"] or r["residual_examples"] or r["altered_examples"] or r["invented_examples"]
        ][:15],
    }


def main() -> None:
    os.chdir(ROOT)  # paths below are relative to the repository root
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3.5:9b,gemma4:12b")
    ap.add_argument("--per-type", type=int, default=4)
    ap.add_argument("--tools", default="", help="через запятую; по умолчанию все")
    ap.add_argument("--data", choices=sorted(DATA), default="synthetic")
    ap.add_argument("--rescore", action="store_true", help="score saved answers only, never ask a model")
    args = ap.parse_args()
    if args.data.startswith("holdout"):
        from bench.eval.holdout import check_hashes

        check_hashes(DATA[args.data])
    only = set(args.tools.split(",")) if args.tools else None
    report = run(args.models.split(","), args.per_type, only, args.data, args.rescore)
    p = Path("results/cycle_metrics.json" if args.data == "synthetic" else f"results/cycle_metrics.{args.data}.json")
    cur = json.loads(p.read_text()) if p.exists() else {}
    for k, v in report.items():
        cur.setdefault(k, {}).update(v)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
