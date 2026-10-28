"""Loading external datasets and converting them to the synthetic dataset's schema.

Run: python -m bench.eval.external  (writes data/external/*.jsonl)

The type schema matches the generator: PERSON, ADDRESS, PHONE, EMAIL, PASSPORT_RU,
SNILS, INN, CARD, etc. Types absent from the synthetic data are kept under their own
names and are not counted towards the thresholds.
"""

from __future__ import annotations

import ast
import csv
import json
import os
import random
import re
from pathlib import Path

from bench import ROOT

EXT = Path("data/external")

SOURCES = {
    "hivetrace/pii-bench": "pii-bench",
    "redmadrobot-rnd/pii_benchmark": "pii_benchmark",
}
# Revisions on which the published results were obtained.
REVISIONS = {
    "hivetrace/pii-bench": "cd6a18ace16daf23e79247ccf1e2b245d4054654",
    "redmadrobot-rnd/pii_benchmark": "f77ea831274daf980cc45c61a93c226be9d978d6",
    "nvidia/Nemotron-PII": "b70ffaf5ff39e079776134c5bf4381f00a9fd1ed",
}

# Dataset authors whose tool takes part in the benchmark: on its "own" dataset the tool is
# not scored for the verdict (the "no home dataset" rule, see REPORT.md).
HOME_TOOL = {
    "hivetrace_pii_bench": "gliner_guard",
    "redmadrobot_pii_benchmark": "pii_guard",
}

HIVETRACE_TYPES = {
    "NAME": "PERSON",
    "PHONE_NUMBER": "PHONE",
    "EMAIL": "EMAIL",
    "ADDRESS": "ADDRESS",
    "BANK_CARD_NUMBER": "CARD",
    "INN": "INN",
    "SNILS": "SNILS",
    "PASSPORT_NUMBER": "PASSPORT_RU",
    "CVC": "CVC",
    "KPP": "KPP",
    "OGRN": "OGRN",
    "OGRNIP": "OGRNIP",
    "TOKEN": "SECRET",
}

REDMADROBOT_TYPES = {
    "FIRST_NAME": "PERSON",
    "LAST_NAME": "PERSON",
    "MIDDLE_NAME": "PERSON",
    "COUNTRY": "ADDRESS",
    "REGION": "ADDRESS",
    "DISTRICT": "ADDRESS",
    "CITY": "ADDRESS",
    "STREET": "ADDRESS",
    "HOUSE": "ADDRESS",
    "PASSPORT": "PASSPORT_RU",
    "CREDIT_CARD": "CARD",
}


def download() -> None:
    from huggingface_hub import snapshot_download

    for repo, local in SOURCES.items():
        snapshot_download(repo, repo_type="dataset", revision=REVISIONS[repo], local_dir=EXT / local)


def load_hivetrace() -> list[dict]:
    import pyarrow.parquet as pq

    docs = []
    for split in ("entity", "domain"):
        for f in sorted((EXT / "pii-bench" / "data").glob(f"{split}-*.parquet")):
            for row in pq.read_table(f).to_pylist():
                text = row["text"]
                ents = []
                for e in sorted(row["entities"] or [], key=lambda e: e["start"]):
                    ents.append(
                        {
                            "type": HIVETRACE_TYPES.get(e["type"], e["type"]),
                            "start": e["start"],
                            "end": e["end"],
                            "value": text[e["start"] : e["end"]],
                        }
                    )
                docs.append(
                    {
                        "id": f"hivetrace-{split}-{row['id']}",
                        "lang": "ru",
                        "doc_type": f"{split}:{row['domain']}",
                        "text": text,
                        "entities": ents,
                    }
                )
    return docs


def _align(text: str, tokens: list[str]) -> list[tuple[int, int]] | None:
    """Token positions in the source text; the case in the tokens may differ."""

    def low(s: str) -> str:  # lower() without changing the string length (İ → i̇, etc.)
        return "".join(c.lower() if len(c.lower()) == 1 else c for c in s)

    text_low, pos, spans = low(text), 0, []
    for tok in tokens:
        i = text_low.find(low(tok), pos)
        if i < 0:
            return None
        spans.append((i, i + len(tok)))
        pos = i + len(tok)
    return spans


def bio_to_spans(text: str, tokens: list[str], tags: list[str]) -> list[dict] | None:
    """BIO tagging to character spans. Adjacent parts of one name
    (surname, first name, patronymic separated by spaces) are merged into one PERSON,
    as in the synthetic dataset. An address stays in parts."""
    pos = _align(text, tokens)
    if pos is None:
        return None
    spans: list[dict] = []
    for (s, e), tag in zip(pos, tags, strict=False):
        if tag == "O":
            continue
        bio, fine = tag.split("-", 1)
        etype = REDMADROBOT_TYPES.get(fine, fine)
        last = spans[-1] if spans else None
        if last and last["fine"] == fine and bio == "I":
            last["end"] = e
            continue
        if last and etype == "PERSON" and last["type"] == "PERSON" and text[last["end"] : s].strip() == "":
            last["end"] = e
            last["fine"] = fine
            continue
        spans.append({"type": etype, "fine": fine, "start": s, "end": e})
    for sp in spans:
        sp["value"] = text[sp["start"] : sp["end"]]
    return spans


def load_redmadrobot() -> tuple[list[dict], int]:
    docs, skipped = [], 0
    with open(EXT / "pii_benchmark" / "test.csv", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            spans = bio_to_spans(row["text"], json.loads(row["tokens"]), json.loads(row["ner_tags"]))
            if spans is None:
                skipped += 1
                continue
            docs.append(
                {
                    "id": f"redmadrobot-{i:05d}",
                    "lang": "ru",
                    "doc_type": "sentence",
                    "text": row["text"],
                    "entities": spans,
                }
            )
    return docs, skipped


# ---------- Nemotron-PII (English, CC-BY-4.0) ----------

NEMOTRON_FILE = "data/test-00000-of-00001.parquet"

NEMOTRON_TYPES = {
    "first_name": "PERSON",
    "last_name": "PERSON",
    "street_address": "ADDRESS",
    "postcode": "ADDRESS",
    "city": "ADDRESS_PART",
    "county": "ADDRESS_PART",
    "state": "ADDRESS_PART",
    "country": "ADDRESS_PART",
    "company_name": "ORG",
    "email": "EMAIL",
    "phone_number": "PHONE",
    "date_of_birth": "DATE_OF_BIRTH",
    "credit_debit_card": "CARD",
}

# Nemotron labels that are replaced with UK numbers.
INJECT = {"national_id": "NINO", "health_plan_beneficiary_number": "NHS", "account_number": "IBAN"}
INJECT_TARGET = 450  # occurrences of each type

_UK_HINT = re.compile(
    r"United Kingdom|\bUK\b|England|Scotland|Wales|London|NHS|National Insurance|£"
    r"|\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b"
)


def _nemotron_rows() -> list[dict]:
    import pyarrow.parquet as pq

    path = EXT / "nemotron-pii" / NEMOTRON_FILE
    if not path.exists():
        from huggingface_hub import hf_hub_download

        hf_hub_download(
            "nvidia/Nemotron-PII",
            NEMOTRON_FILE,
            repo_type="dataset",
            revision=REVISIONS["nvidia/Nemotron-PII"],
            local_dir=EXT / "nemotron-pii",
        )
    cols = ["uid", "locale", "document_type", "text", "spans"]
    return [r for r in pq.read_table(path, columns=cols).to_pylist() if r["locale"] == "intl"]


def _merge(text: str, spans: list[dict]) -> list[dict]:
    """Merges adjacent parts of a name and of an address separated by spaces and commas."""
    out: list[dict] = []
    for sp in spans:
        last = out[-1] if out else None
        gap = text[last["end"] : sp["start"]] if last else ""
        addr = {"ADDRESS", "ADDRESS_PART"}
        same = last and (
            (last["type"] == sp["type"] == "PERSON" and gap.strip() == "" and "\n" not in gap)
            or (last["type"] in addr and sp["type"] in addr and gap.strip(" ,\n") == "")
        )
        if same:
            last["end"] = sp["end"]
            if sp["type"] == "ADDRESS":
                last["type"] = "ADDRESS"
        else:
            out.append(dict(sp))
    for sp in out:
        if sp["type"] == "ADDRESS_PART":
            sp["type"] = "LOCATION"  # a standalone city or country: not counted towards the thresholds
        sp["value"] = text[sp["start"] : sp["end"]]
    return out


def _nemotron_doc(row: dict, text: str, spans: list[dict], prefix: str) -> dict:
    return {
        "id": f"{prefix}-{row['uid']}",
        "lang": "uk",
        "doc_type": row["document_type"],
        "text": text,
        "entities": _merge(text, spans),
    }


def _raw_spans(row: dict) -> list[dict]:
    spans = sorted(ast.literal_eval(row["spans"]), key=lambda s: (s["start"], -s["end"]))
    out: list[dict] = []
    for s in spans:
        if out and s["start"] < out[-1]["end"]:
            continue  # nested and overlapping labels: keep the outer one
        out.append(
            {
                "type": NEMOTRON_TYPES.get(s["label"], s["label"].upper()),
                "start": s["start"],
                "end": s["end"],
                "label": s["label"],
            }
        )
    return out


def load_nemotron_uk(seed: int = 20261012) -> tuple[list[dict], list[dict]]:
    """Two subsets: UK texts as they are (names, addresses, organisations)
    and texts with injected NI, NHS and IBAN numbers."""
    from bench.generator import ids
    from bench.generator.render import ids_canonical

    rows = _nemotron_rows()
    plain = [_nemotron_doc(r, r["text"], _raw_spans(r), "nemotron-uk") for r in rows if _UK_HINT.search(r["text"])]

    rng = random.Random(seed)
    gens = {"NINO": ids.gen_nino, "NHS": ids.gen_nhs, "IBAN": ids.gen_iban_gb}
    kinds = {"NINO": "nino", "NHS": "nhs", "IBAN": "iban"}
    counts = {t: 0 for t in gens}
    candidates = [r for r in rows if any(f"'{lab}'" in r["spans"] for lab in INJECT)]
    rng.shuffle(candidates)
    injected = []
    for r in candidates:
        if all(c >= INJECT_TARGET for c in counts.values()):
            break
        spans = _raw_spans(r)
        text = r["text"]
        originals = {text[s["start"] : s["end"]] for s in spans if s["label"] in INJECT}
        labelled = sum(1 for s in spans if text[s["start"] : s["end"]] in originals)
        if sum(text.count(o) for o in originals) != labelled:
            continue  # source number occurs outside the annotation: substituting would leave a trace
        new_text, new_spans, shift, mapping = [], [], 0, {}
        pos = 0
        for s in spans:
            orig = text[s["start"] : s["end"]]
            new_text.append(text[pos : s["start"]])
            start = s["start"] + shift
            if s["label"] in INJECT:
                t = INJECT[s["label"]]
                if orig not in mapping:
                    canon = gens[t](rng)
                    mapping[orig] = rng.choice(ids.format_variants(kinds[t], canon)[:2])
                    counts[t] += 1
                repl = mapping[orig]
                new_spans.append(
                    {"type": t, "start": start, "end": start + len(repl), "canonical": ids_canonical(t, repl)}
                )
                new_text.append(repl)
                shift += len(repl) - len(orig)
            else:
                new_spans.append({"type": s["type"], "start": start, "end": start + len(orig)})
                new_text.append(orig)
            pos = s["end"]
        new_text.append(text[pos:])
        injected.append(_nemotron_doc(r, "".join(new_text), new_spans, "nemotron-uk-ids"))
    return plain, injected


def main() -> None:
    os.chdir(ROOT)  # paths below are relative to the repository root
    if not (EXT / "pii-bench").exists() or not (EXT / "pii_benchmark").exists():
        download()
    hv = load_hivetrace()
    rr, skipped = load_redmadrobot()
    uk_plain, uk_ids = load_nemotron_uk()
    for name, docs in (
        ("hivetrace_pii_bench", hv),
        ("redmadrobot_pii_benchmark", rr),
        ("nemotron_uk", uk_plain),
        ("nemotron_uk_ids", uk_ids),
    ):
        with (EXT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        from collections import Counter

        c = Counter(e["type"] for d in docs for e in d["entities"])
        print(f"{name}: {len(docs)} texts, {sum(c.values())} entities")
        print("  " + ", ".join(f"{t} {n}" for t, n in c.most_common()))
    print(f"redmadrobot: {skipped} sentences skipped (tokens could not be aligned with the text)")


if __name__ == "__main__":
    main()
