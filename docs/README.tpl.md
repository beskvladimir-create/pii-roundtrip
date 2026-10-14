# pii-roundtrip

Local reversible anonymisation of Russian and UK English documents for use with external LLMs, and an independent benchmark of existing tools.

pii-roundtrip replaces personal data in a document with consistent placeholders such as `[PERSON_1]` or `[NHS_1]`, keeps the mapping in an encrypted local vault, and restores the original values in the model's answer. The document can be sent to any external LLM, while the personal data stay on the machine. After the models are downloaded once, everything runs offline.

[Русская версия](README.ru.md)

## Why

Existing open-source tools work well on short messages but leak personal data in real documents such as contracts, letters, HR files and discharge summaries. On a held-out set of synthetic documents with numbers written in digits, with dots, with typos and in words, the share of documents in which at least one original value remained after anonymisation was:

| Tool | Russian | UK English |
|---|---|---|
| **pii-roundtrip** | **1%** | **4%** |
| pii-guard | 54% | n/a |
| GLiNER Guard Omni | 100% | 57% |
| Presidio | 78% | 60% |
| OpenAI privacy-filter | 92% | 86% |
| Prompt Anonymizer | n/a | 100% |

Full results, method and limitations are in [REPORT.en.md](REPORT.en.md). The complete tables in Russian are in [REPORT.md](REPORT.md).

## Results against the thresholds

The thresholds are recall of at least 99% for structured identifiers, recall of at least 95% for names, addresses and organisations, leaks in at most 2% of documents, and correct restoration of at least 99% of placeholders after an LLM answer.

External datasets: hivetrace/pii-bench and redmadrobot pii_benchmark for Russian; Nemotron-PII with UK texts and injected UK identifiers for English.

| Threshold | Best existing tool, RU (pii-guard) | pii-roundtrip, RU | Best existing tool, UK (GLiNER Guard) | pii-roundtrip, UK |
|---|---|---|---|---|
| Structured identifiers ≥ 99% | 97.7% | {RU_STRUCT} | 96.4% | {UK_STRUCT} |
| Names, addresses, organisations ≥ 95% | 99.5% | {RU_NAMES} | 98.7% | {UK_NAMES} |
| Documents with a leak ≤ 2% | 0.7% | {RU_LEAK} | 4.0% | {UK_LEAK} |
| Restoration ≥ 99% (worse of two LLMs) | 92.0% | {RU_RESTORE} | no restore step | {UK_RESTORE} |

The restoration figures come from a round trip with qwen3.5:9b and gemma4:12b at temperature 0. Intervals and per-dataset numbers are in the report.

## Quick start

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/). pii-roundtrip is installed from source; it depends on pii-guard pinned to a GitHub commit and is not published on PyPI.

```bash
git clone https://github.com/beskvladimir-create/pii-roundtrip.git && cd pii-roundtrip
uv sync
uv run pii-roundtrip download-models          # once, needs network
```

Command line:

```bash
uv run pii-roundtrip anonymize -l uk -i letter.txt -o letter.clean.txt --vault letter.vault
# send letter.clean.txt to an LLM, save its answer to answer.txt
uv run pii-roundtrip restore -i answer.txt -o answer.restored.txt --vault letter.vault
```

The vault password is read from `PII_ROUNDTRIP_PASSWORD` or asked interactively. Use `-l ru` for Russian, `--append` to continue the same conversation, `--force` to overwrite an existing vault, and `--encoding cp1251` for legacy files.

Python:

```python
from pii_roundtrip import anonymize, deanonymize

clean, session = anonymize(text, "uk")
answer = call_your_llm(clean)          # the LLM sees only placeholders
print(deanonymize(answer, session))   # originals restored locally
```

Pass the same `session` to `anonymize` for follow-up messages so that known people and numbers keep their placeholders.

## How it works

- **Detection.** pii-guard (rules with checksums and ruBERT) for Russian, GLiNER Guard Omni for both languages, plus own rules: checksum-validated identifiers (SNILS, INN, passport, cards, NHS, NI, IBAN), long numbers with any separators, numbers written in words, organisations, sole proprietors, names with titles and initials, dates of birth by context.
- **Whole-document consistency.** Every name, organisation and number found once is masked everywhere in the document and in later messages of the session, including Russian case forms, capitals, ё/е, hyphenated surnames and apostrophes. Different people never share a placeholder; ambiguous mentions get their own.
- **Restoration.** Placeholders are accepted with changed case, extra spaces or a prefix added by the model. Russian names are put back in the grammatical case the context requires.
- **Vault.** AES-256-GCM with a key derived by scrypt, atomic writes, file mode 0600, no symlink following.

Placeholders show the type of each value, for example `[PASSPORT_RU_1]` or `[NHS_1]`, and their numbering shows how many values of each type a document contains.

## Benchmark

Requirements in addition to the above: [Ollama](https://ollama.com) with `qwen3.5:9b` and `gemma4:12b`, and about 20 GB of free disk. The full run takes several hours on a laptop.

```bash
ollama pull qwen3.5:9b && ollama pull gemma4:12b
scripts/reproduce.sh
```

Method in brief:
- **No home datasets.** Each tool is evaluated for the verdict only on datasets its own authors did not build.
- **Held-out sets.** Two synthetic sets were generated before the corresponding engine changes and frozen by SHA-256 ([HOLDOUT.en.md](HOLDOUT.en.md)); each was run once.
- **What counts as hidden.** A value counts as hidden when all of its meaningful words are masked. A leak is an original value remaining in the cleaned text, with numbers matched across any separators and Russian surnames in all cases.
- **Round trip.** Placeholders issued by the tool and placeholders invented by the LLM are counted separately, and confidence intervals are bootstrapped over answers.

## Limitations

- UK held-out set: 4 of 100 documents still leaked, above the 2% threshold.
- The synthetic documents come from this project's own generator. The held-out sets protect against tuning to specific documents, not to the generator's style.
- pii-guard and GLiNER Guard, which pii-roundtrip builds on, were released by the authors of the two Russian external datasets.
- UK NHS numbers in the external set were injected into US-style contexts.
- promptShield, a browser-only tool, was not measured.

## Licence and attribution

Apache License 2.0, see [LICENSE](LICENSE). pii-roundtrip uses pii-guard, GLiNER2 with the model hivetrace/gliner-guard-omni, and pymorphy3; see [NOTICE](NOTICE).

Author: Vladimir Beskorovainyi, Besk Tech ([besk.tech](https://besk.tech)).
