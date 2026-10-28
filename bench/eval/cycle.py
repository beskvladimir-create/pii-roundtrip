"""Full cycle: sanitization → local LLM answer → restoration → check.

python -m bench.eval.cycle --models qwen3.5:9b,gemma4:12b --per-type 4 [--data holdout3]

Participants:
- RU: pii_guard (its own sanitization and restoration), best detector + shared placeholders [TYPE_n];
- UK: prompt_anonymizer (its own), best detector + shared placeholders [TYPE_n].

LLM answers are cached in results/cycle/[<set>/]<tool>/<model>.jsonl. The cache key includes
the request hash: after the sanitization changes, the answer is requested again rather than
reusing the old one.
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

# Label patterns for each tool: verbatim and "look-alike" (altered by the LLM).
LABEL_PATTERNS = {
    # the tag is matched by its attributes: a broken closing ("»", "*/", ">") does not merge
    # adjacent tags
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
    "holdout6": "data/holdout6",
    "holdout7": "data/holdout7",
}


def pick_docs(lang: str, per_type: int, data: str = "synthetic") -> list[dict]:
    docs = load_docs(f"{DATA[data]}/{lang}.jsonl")
    rng = random.Random(1)
    by_type = defaultdict(list)
    for d in docs:
        by_type[d["doc_type"]].append(d)
    return [d for t in sorted(by_type) for d in rng.sample(by_type[t], per_type)]


# Case endings added to a surname or a first name by rule (evaluator version 2, fixed on
# 22.10.2026 before held-out set 6 was generated): the dictionary reads "Третьяков" as a form of
# "третьяк" and gives no forms of "Майя", so correctly restored "Третьякова" and "Майи" were
# counted as failures on held-out set 5.
EVALUATOR = 3  # the version of name matching; 1: sets 4 and 5 as run, 2: set 6 as run, 3: fixed before set 7
_SURNAME_FORMS = {
    r"(ов|ев|ёв|ин|ын)$": ("а", "у", "ым", "ом", "е", "ы", "ых", "ыми"),
    r"(ова|ева|ёва|ина|ына)$": ("ой", "у", "ы"),
}
_NAME_FORMS = {
    r"[^и]я$": ("и", "е", "ю", "ей", "ею"),
    r"ия$": ("ии", "ию", "ией"),
    r"[^ая]а$": ("ы", "и", "е", "у", "ой"),
}


@lru_cache(maxsize=50000)
def _ru_forms(word: str, evaluator: int = 2) -> frozenset[str]:
    """Case forms of a word of a value. Version 1 (held-out sets 4 and 5 as run): the lexemes of the
    first three dictionary parses. Version 2 adds every parse and the case endings above."""
    from pii_roundtrip.names import morph

    forms = {word.lower()}
    parses = morph().parse(word)
    for p in parses[:3] if evaluator == 1 else parses:
        forms.update(lex.word for lex in p.lexeme)
    if evaluator >= 2:
        low = word.lower()
        for rules in (_SURNAME_FORMS, _NAME_FORMS):
            for rx, ends in rules.items():
                if re.search(rx, low):
                    stem = low[:-1] if rules is _NAME_FORMS or not re.search(r"(ов|ев|ёв|ин|ын)$", low) else low
                    forms.update(stem + e for e in ends)
                    break
    return frozenset(f.replace("ё", "е") for f in forms)


def _value_restored(value: str, restored: str, lang: str, is_person: bool = False) -> bool:
    """A value counts as restored if it is present in the answer. For Russian text the words
    may be in a different case («Тула» -> «в Туле»); digits must match exactly."""
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
    return all(_ru_forms(w, EVALUATOR) & text_words for w in words)


def _identity(family: str, label: str, known_types: set[str] | None = None) -> tuple[str, str] | None:
    """Whom a label belongs to: (type, number). For pii-guard tags, by the type and id attributes;
    for labels of the form [TYPE_n], by the type (dropping suffixes such as ORG_NAME_ORG_1)."""
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


_PERSON_LABEL = re.compile(r"PERSON|\bNAME\b|_NAME|\bPER\b", re.I)
_FAMILY = re.compile(r"^(?P<base>[а-яё-]{2,}?(?:ов|ев|ёв|ин|ын))(?:а|у|ым|ом|е|ой|ую|ою)?$")


def _canon_forms(word: str, role: str) -> set[str]:
    """Evaluator 3: the correct case forms of a word of the annotated name, by its role in the
    annotation ("surname", "first", "patronymic" for Russian; "en" for English). A surname in
    -ов/-ев/-ин/-ын and a man's first name in a consonant by rule (the dictionary reads "Абрамов"
    as the plural of "Абрам" and gives "Провым"); other words: the singular forms of their
    dictionary name, surname or patronymic parses."""
    from pii_roundtrip.names import morph

    low = word.lower().replace("ё", "е")
    if role == "en":
        return {low, low + "'s", low + "’s", low + "s'"}
    m = _FAMILY.match(low)
    if role == "surname" and m:
        b = m.group("base")
        return {b, b + "а", b + "у", b + "ым", b + "ом", b + "е", b + "ой", b + "ую", b + "ою"}
    if role == "first" and re.search(r"[бвгджзклмнпрстфхцчшщ]$", low):
        return {low, low + "а", low + "у", low + "ом", low + "е"}
    if role == "patronymic" and re.search(r"ич$", low):
        return {low, low + "а", low + "у", low + "ем", low + "е"}
    if role == "patronymic" and re.search(r"на$", low):
        b = low[:-1]
        return {low, b + "ы", b + "е", b + "у", b + "ой", b + "ою"}
    forms = {low}
    tag = {"surname": "Surn", "first": "Name", "patronymic": "Patr"}.get(role, "Name")
    for p in morph().parse(word):
        if tag in p.tag.grammemes:
            forms.update(x.word.replace("ё", "е") for x in p.lexeme if x.tag.number != "plur")
    for rx, ends in _NAME_FORMS.items():
        if role == "first" and re.search(rx, low):
            forms.update(low[:-1] + e for e in ends)
            break
    return forms


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _words(s: str) -> list[str]:
    return [w.lower().replace("ё", "е") for w in re.findall(r"[А-Яа-яЁёA-Za-z'’-]{2,}", s)]


def _close(a: str, b: str) -> bool:
    return a[:4] == b[:4] or _lev(a, b) <= 2


def person_canonicals(value: str, entities: list[dict], text: str) -> tuple[list[tuple[str, str]], set[str]] | None:
    """Evaluator 3: the words of the annotated name that the mention a stored value stands for
    actually has (a mention "N. Johnston" or "Lucy" does not require the full name), with their
    roles, and the words of that mention as the document wrote them; None if no annotated name
    matches the value. The mention is the annotated one most similar to the stored value."""
    vw = _words(value)
    best, key = None, (0, 0)
    for g in entities:
        if g["type"] != "PERSON":
            continue
        gw = _words(g["value"])
        sc = sum(1 for w in vw if any(_close(w, x) for x in gw))
        k = (sc, -abs(len(gw) - len(vw)))
        if sc and k > key:
            best, key = g, k
    if not best:
        return None
    canon = best.get("canonical", best["value"])
    mention = _words(best["value"])
    cw = re.findall(r"[А-Яа-яЁёA-Za-z'’-]{2,}", canon)
    cyr = bool(re.search(r"[А-Яа-яЁё]", canon))
    roles = (["surname", "first", "patronymic"] + ["first"] * len(cw))[: len(cw)] if cyr else ["en"] * len(cw)
    required = [
        (w, r) for w, r in zip(cw, roles, strict=True) if any(_close(w.lower().replace("ё", "е"), x) for x in mention)
    ]
    # how the document wrote this person anywhere (a typo of the text counts as written)
    written = {
        x
        for g in entities
        if g["type"] == "PERSON" and g.get("canonical", g["value"]) == canon
        for x in _words(g["value"])
    }
    return required, written


def _name_matches_annotation(words: list[tuple[str, str]], restored: str, source_words: set[str]) -> bool:
    """Every annotated word is in the restored text in a correct form, or exactly as the document
    wrote it (a typo of the document's own text is kept)."""
    text_words = {w.lower().replace("ё", "е") for w in re.findall(r"[А-Яа-яЁёA-Za-z'’-]+", restored)}
    for w, role in words:
        low = w.lower().replace("ё", "е")
        as_written = {x for x in source_words if _close(x, low)}
        if not (_canon_forms(w, role) & text_words) and not (as_written & text_words):
            return False
    return True


def evaluate_answer(family: str, mapping: dict, answer: str, restored: str, lang: str, doc: dict | None = None) -> dict:
    """Labels are split into those issued by the tool (their type and number are in the table)
    and those invented by the LLM. The restoration rate is computed over issued labels: verbatim
    and altered."""
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
    if EVALUATOR >= 3 and doc is not None:
        # a name must also be the annotated person's name, not only the value the tool stored
        for k in used_keys:
            if k in lost or not _PERSON_LABEL.search(k):
                continue
            found = person_canonicals(mapping[k], doc["entities"], doc["text"])
            if found and found[0]:
                words, as_written = found
                if not _name_matches_annotation(words, restored, as_written):
                    lost.append(k)
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
            # the same pii-guard XML tags, but with the generic system prompt: separates the label
            # format from the prompt
            ("pii_guard@generic", "pii_guard"),
            ("pii_guard+placeholders", "placeholders"),
            # plain placeholders with the same generic prompt: together with pii_guard@generic
            # gives format × prompt
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
                            plain = getattr(mapping, "mapping", mapping)  # the engine returns a Session
                            ev = evaluate_answer(family, plain, answer, restored, lang, d)
                            ev["input_leaked_values"] = metrics.leaked_values(d, anon)
                            ev["input_leaks"] = len(ev["input_leaked_values"])
                            ev.update({"id": d["id"], "task": task})
                            rows.append(ev)
                            if family == "pii_guard":
                                # the same answer restored by label type and number, not by pii-guard
                                ev_t = evaluate_answer(
                                    family, plain, answer, tolerant_restore(family, plain, answer), lang, d
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
    """How many occurrences of tool-issued labels were restored correctly, and how many there are
    in total: each occurrence is scored once (see evaluate_answer)."""
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
    """95% interval by bootstrap over answers: labels within one answer are not independent."""
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


def _person_rate(rows: list[dict]) -> dict:
    pairs = []
    for r in rows:
        det = [bad for key, _v, bad in r.get("occurrence_detail", []) if _PERSON_LABEL.search(key)]
        if det:
            pairs.append((sum(1 for b in det if not b), len(det)))
    ok, n = sum(k for k, _ in pairs), sum(t for _, t in pairs)
    if not n:
        return {"person_labels": 0, "restore_rate_person": None, "restore_ci_person": None, "answers_with_person": 0}
    rng, stats = random.Random(0), []
    for _ in range(2000):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        tot = sum(t for _, t in sample)
        stats.append(sum(k for k, _ in sample) / tot if tot else 1.0)
    stats.sort()
    return {
        "person_labels": n,
        "restore_rate_person": ok / n,
        "restore_ci_person": (stats[50], stats[1949]),
        "answers_with_person": len(pairs),
    }


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
        # name placeholders only (evaluator 3; threshold from held-out set 7): occurrences issued for a
        # PERSON label, the same bootstrap over answers
        **_person_rate(rows),
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
    ap.add_argument("--tools", default="", help="comma-separated; all by default")
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
