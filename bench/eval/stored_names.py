"""Stored names and the restoration they allow (not pre-registered for sets 5 and 6; added after
review). For every name pii-roundtrip masked in the round-trip documents of a held-out set, the
value it stored is compared with the generator's annotation; then restoration is recomputed from
the saved answers with every occurrence of a wrongly stored name counted as a failure.

python -m bench.eval.stored_names holdout6 > results/stored_names.holdout6.json
python -m bench.eval.stored_names holdout6 --review   # the names to check by hand, with their mentions

The saved answers are found by a hash of the prompt, so a set can be scored only with the engine
version that produced its answers (set 5: engine 0.3, set 6: engine 0.4).

A name is stored correctly when its surname is the annotation's nominative surname, or, when the
document mentions the person without a surname (first name and patronymic only, or only a first
name), when the stored value keeps what the text has. Typos in the document's own text are stored as
they are and count as correct. Verdicts made by hand are read from
results/stored_names_review.<set>.json ({"<doc id> <label>": "wrong" | "right"}) and override the
rule. Denominators are the occurrences the tool issued, as in bench/eval/cycle.py (placeholders the
LLM invented are not counted).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import re
import sys
from collections import defaultdict

from bench import ROOT
from bench.eval import cycle
from bench.eval.cycle_extras import clopper_pearson

LABEL = re.compile(r"\[[A-Z]+(?:_[A-Z]+)*_\d+\]")
MODELS = ["qwen3.5:9b", "gemma4:12b"]


def norm(w: str) -> str:
    return w.lower().replace("ё", "е")


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[\w'’-]+", s) if len(w) > 1 and not re.fullmatch(r"[A-ZА-ЯЁ]\.?", w)]


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def classify(lang: str, canonical: str, stored: str, mentions: list[str]) -> str:
    """right | plural_form | gender_or_case | no_surname_in_text | typo_in_source_text | other"""
    cw = words(canonical)
    if not cw:
        return "right"
    surname = norm(cw[0] if lang == "ru" else cw[-1])
    sw = [norm(w) for w in words(stored)]
    if surname in sw:
        return "right"
    in_text = any(lev(norm(w), surname) <= 2 or norm(w)[:4] == surname[:4] for m in mentions for w in words(m))
    if not in_text:
        return "no_surname_in_text"
    s0 = sw[0] if sw else ""
    if lang == "ru" and re.search(r"(ов|ев|ин|ын)$", surname) and s0 in (surname[:-2] + "ы", surname[:-2] + "и"):
        return "plural_form"
    if lang == "ru" and (
        s0 in (surname + "а", surname[:-1], surname + "у", surname[:-1] + "у", surname[:-1] + "ой", surname + "ой")
        or s0 + "а" == surname
    ):
        return "gender_or_case"
    if any(lev(norm(w), norm(x)) <= 2 for m in mentions for w in words(m) for x in sw) and any(
        lev(x, surname) <= 2 for x in sw
    ):
        return "typo_in_source_text"
    return "other"


def names(data: str, lang: str) -> list[dict]:
    from bench.eval.run import load_tool

    tool = load_tool("pii_roundtrip")
    elang = "en-GB" if lang == "uk" else lang
    out = []
    for d in cycle.pick_docs(lang, 38, data):
        text = d["text"]
        spans = tool.engine.spans(text, elang)
        anon, session = tool.engine.anonymize(text, elang)
        labels = LABEL.findall(anon)
        if len(labels) != len(spans):
            continue
        mentions: dict[str, list[str]] = defaultdict(list)
        gold: dict[str, list[str]] = defaultdict(list)
        for sp, lab in zip(spans, labels, strict=True):
            if sp.type != "PERSON":
                continue
            mentions[lab].append(text[sp.start : sp.end])
            gold[lab] += [
                g.get("canonical", g["value"])
                for g in d["entities"]
                if g["type"] == "PERSON" and g["start"] < sp.end and g["end"] > sp.start
            ]
        for lab, ms in mentions.items():
            if not gold[lab]:
                continue
            canonical = max(set(gold[lab]), key=gold[lab].count)
            stored = session.mapping[lab]
            out.append(
                {
                    "id": d["id"],
                    "label": lab,
                    "canonical": canonical,
                    "stored": stored,
                    "mentions": sorted(set(ms)),
                    "category": classify(lang, canonical, stored, ms),
                }
            )
    return out


WRONG = {"plural_form", "gender_or_case", "other"}


def restoration(data: str, wrong: dict[str, set[str]], inflection: list[dict] | None = None) -> dict:
    """Restoration from the saved answers with every occurrence of a wrongly stored name counted as
    a failure: all issued occurrences, and name placeholders only; bootstrap over answers."""
    rows: dict = {}
    with contextlib.redirect_stdout(sys.stderr):
        cycle.run(MODELS, 38, {"pii_roundtrip"}, data, rescore=True, rows_out=rows)
    out = {}
    for (_tool, lang, model), rs in sorted(rows.items()):
        per = {"all": [], "person": []}
        answers_wrong = 0
        extra = {(e["id"], e["task"], e["label"]): e["occurrences"] for e in inflection or [] if e["model"] == model}
        for r in rs:
            bad_doc = wrong.get(r["id"], set())
            left = {lab: k for (i, t, lab), k in extra.items() if i == r["id"] and t == r["task"]}
            a_ok = a_n = p_ok = p_n = 0
            hit = False
            for key, _value, bad in r["occurrence_detail"]:
                w = key in bad_doc
                if not w and not bad and left.get(key, 0) > 0:  # a name inflected wrongly, checked by hand
                    left[key] -= 1
                    w = True
                hit |= w
                ok = not bad and not w
                a_ok, a_n = a_ok + ok, a_n + 1
                if key.startswith("[PERSON_"):
                    p_ok, p_n = p_ok + ok, p_n + 1
            per["all"].append((a_ok, a_n))
            per["person"].append((p_ok, p_n))
            answers_wrong += hit
        entry = {}
        for k, pairs in per.items():
            pairs = [p for p in pairs if p[1]]
            ok, n = sum(p[0] for p in pairs), sum(p[1] for p in pairs)
            entry[k] = {
                "occurrences": n,
                "ok": ok,
                "rate": ok / n if n else None,
                "ci": boot(pairs),
                "answers": len(pairs),
            }
        n_ans = sum(1 for r in rs if r["labels_in_answer"])
        entry["answers_with_a_wrong_name"] = answers_wrong
        entry["answers_with_a_wrong_name_ci"] = clopper_pearson(answers_wrong, n_ans)
        out[f"{lang}/{model}"] = entry
    return out


def boot(pairs: list[tuple[int, int]], reps: int = 2000, seed: int = 0) -> list[float]:
    """The bootstrap over answers of bench/eval/cycle.py, with the bound 0.025^(1/n) at no error."""
    if not pairs:
        return [0.0, 1.0]
    if all(k == n for k, n in pairs):
        return [0.025 ** (1 / len(pairs)), 1.0]
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        tot = sum(n for _, n in sample)
        stats.append(sum(k for k, _ in sample) / tot if tot else 1.0)
    stats.sort()
    return [stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1]]


def main() -> None:
    os.chdir(ROOT)
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--review", action="store_true")
    args = ap.parse_args()
    review_file = ROOT / "results" / f"stored_names_review.{args.data}.json"
    review = json.loads(review_file.read_text()) if review_file.exists() else {}
    out: dict = {"_note": __doc__.split("\n\n")[0].replace("\n", " ")}
    wrong: dict[str, set[str]] = defaultdict(set)
    for lang in ("ru", "uk"):
        with contextlib.redirect_stdout(sys.stderr):
            rows = names(args.data, lang)
        counts: dict[str, int] = defaultdict(int)
        for r in rows:
            v = review.get(f"{r['id']} {r['label']}")
            r["verdict"] = v or ("wrong" if r["category"] in WRONG else "right")
            r["verdict_by"] = "hand" if v else "rule"
            counts[r["category"]] += 1
            if r["verdict"] == "wrong":
                wrong[r["id"]].add(r["label"])
        out[lang] = {
            "names": len(rows),
            "categories": dict(counts),
            "wrong": sum(1 for r in rows if r["verdict"] == "wrong"),
            "reviewed_by_hand": sum(1 for r in rows if r["verdict_by"] == "hand"),
            "names_list": rows if not args.review else [r for r in rows if r["category"] != "right"],
        }
    if not args.review:
        out["restoration"] = restoration(args.data, wrong, review.get("_inflection_errors"))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
