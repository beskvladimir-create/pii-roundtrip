# pii-roundtrip

Local reversible anonymisation of Russian and UK English documents for use with external LLMs, and an open, reproducible benchmark of existing tools.

pii-roundtrip replaces personal data in a document with consistent placeholders such as `[PERSON_1]` or `[NHS_1]`, keeps the mapping in an encrypted local vault, and restores the original values in the model's answer. The document can be sent to any external LLM, while the personal data stay on the machine. After the models are downloaded once, everything runs offline.

[Русская версия](README.ru.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23478192.svg)](https://doi.org/10.5281/zenodo.23478192)

## Why

Existing open-source tools work well on short messages but leak personal data in synthetic documents such as contracts, letters, HR files and discharge summaries. The table shows the share of documents in which at least one original value remained after anonymisation. It was measured on held-out set 5: 1,000 synthetic documents per language with numbers written in digits, with dots, with typos and in words, generated before the final changes of version 0.2 and run once ([HOLDOUT.en.md](HOLDOUT.en.md)). No tool, including pii-roundtrip, was developed on it.

| Tool | Russian | UK English |
|---|---|---|
| **pii-roundtrip** | **0.2% [0.1; 0.7]** | **0.7% [0.3; 1.4]** |
| pii-guard | 53.2% [50.1; 56.3] | n/a |
| GLiNER Guard Omni | 99.7% [99.1; 99.9] | 56.7% [53.6; 59.7] |
| Presidio | 86.3% [84.0; 88.3] | 56.9% [53.8; 59.9] |
| OpenAI privacy-filter | 95.8% [94.4; 96.9] | 80.6% [78.0; 82.9] |
| Prompt Anonymizer | n/a | 100.0% [99.6; 100.0] |
| Regular expressions with checksums | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] |

Full results, method and limitations are in [REPORT.en.md](REPORT.en.md). The complete tables in Russian are in [REPORT.md](REPORT.md).

## Results against the thresholds

The thresholds are recall of at least 99% for structured identifiers, recall of at least 95% for names, addresses and organisations, leaks in at most 2% of documents, and correct restoration of at least 99% of placeholders after an LLM answer.

Each table compares the best existing tool with pii-roundtrip on the same data: the external datasets without the tool's own (home) dataset, and held-out set 5. The best existing tool is chosen on the external datasets. External datasets: hivetrace/pii-bench and redmadrobot pii_benchmark for Russian; Nemotron-PII with UK texts and injected UK identifiers for English.

Russian:

| Threshold | pii-guard, external | pii-roundtrip, same external sets | pii-guard, held-out set 5 | pii-roundtrip, held-out set 5 |
|---|---|---|---|---|
| Structured identifiers ≥ 99% | 97.7% [96.1; 99.0] undetermined, borderline | 100.0% [100.0; 100.0], for reference | 92.4% [91.6; 93.1] not met | 100.0% [100.0; 100.0] met |
| Names, addresses, organisations ≥ 95% | 99.5% [98.7; 100.0] met | 100.0% [100.0; 100.0], for reference | 73.8% [73.3; 74.4] not met | 99.7% [99.6; 99.8] met |
| Documents with a leak ≤ 2% | 0.7% [0.4; 1.2] met | 0.0% [0.0; 0.2], for reference | 53.2% [50.1; 56.3] not met | 0.2% [0.1; 0.7] met |
| Restoration ≥ 99% (worse of two LLMs) | not measured | not measured | 99.8% [99.4; 100.0] met | 99.9% [99.9; 100.0] met |
| Masked fragments that contain personal data | 96.5% [95.5; 97.5], no threshold | 89.2% [87.8; 90.7], no threshold | 87.6% [87.5; 87.7], no threshold | 98.5% [98.3; 98.6], no threshold |

External sets: hivetrace_pii_bench.

The Russian external datasets were used for error analysis while version 0.1 was developed, so for pii-roundtrip they are not an independent check. Held-out set 5 is.

UK English:

| Threshold | GLiNER Guard Omni, external | pii-roundtrip, same external sets | GLiNER Guard Omni, held-out set 5 | pii-roundtrip, held-out set 5 |
|---|---|---|---|---|
| Structured identifiers ≥ 99% | 96.4% [95.7; 97.1] not met | 100.0% [99.9; 100.0] met | 95.3% [94.8; 95.8] not met | 100.0% [100.0; 100.0] met |
| Names, addresses, organisations ≥ 95% | 98.7% [98.2; 99.1] met | 98.1% [97.6; 98.6] met | 88.9% [88.3; 89.5] not met | 98.9% [98.7; 99.1] met |
| Documents with a leak ≤ 2% | 4.0% [3.4; 4.8] not met | 0.9% [0.6; 1.3] met | 56.7% [53.6; 59.7] not met | 0.7% [0.3; 1.4] met |
| Restoration ≥ 99% (worse of two LLMs) | not measured | not measured | no restore step, not met | 100.0% [99.0; 100.0] met |
| Masked fragments that contain personal data | 89.3% [88.8; 89.9], no threshold | 93.4% [92.8; 93.9], no threshold | 94.8% [94.6; 94.9], no threshold | 99.8% [99.8; 99.9], no threshold |

External sets: nemotron_uk, nemotron_uk_ids.

A threshold is met when the whole 95% confidence interval is on the right side of it, not met when the whole interval is on the wrong side, and undetermined when the interval spans it. Restoration comes from a round trip with qwen3.5:9b and gemma4:12b at temperature 0 on documents of held-out set 5. The last row has no threshold: it shows how much of the masked text is personal data, so that a tool cannot reach high recall by masking everything.

## Desktop app for macOS

For people who do not use the command line: drop in a Word file, a PDF or text, send the cleaned version to any AI tool, drop or paste its answer back and get it with the real values. Formatting is kept where the file allows it, the models are inside the installer, and the app works offline. Download the installer from the [Releases page](https://github.com/beskvladimir-create/pii-roundtrip/releases); details in [desktop/README.md](desktop/README.md).

## Quick start

Requirements: Python 3.12 or later and [uv](https://docs.astral.sh/uv/). pii-roundtrip is installed from source; it depends on pii-guard pinned to a GitHub commit and is not published on PyPI.

```bash
git clone https://github.com/beskvladimir-create/pii-roundtrip.git && cd pii-roundtrip
uv sync --extra all
uv run pii-roundtrip download-models          # once, needs network
```

The extras: `ru` adds pii-guard (Russian NER and name inflection), `gliner` adds GLiNER Guard Omni, `all` adds both, `bench` adds every compared tool. Without extras only the rules run: checksum-validated identifiers, numbers, titled names and the vault.

Command line:

```bash
uv run pii-roundtrip anonymize -l en-GB -i letter.txt -o letter.clean.txt --vault letter.vault
# send letter.clean.txt to an LLM, save its answer to answer.txt
uv run pii-roundtrip restore -i answer.txt -o answer.restored.txt --vault letter.vault
```

The vault password is read from `--password-file`, from `PII_ROUNDTRIP_PASSWORD`, or asked interactively. Output files are written with mode 0600. Use `-l ru` for Russian, `--append` to continue the same conversation, `--force` to overwrite an existing vault, and `--encoding cp1251` for legacy files.

Python:

```python
from pii_roundtrip import anonymize, deanonymize

clean, session = anonymize(text, "en-GB")
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
- **Held-out sets.** Synthetic sets are generated before the engine changes they test and frozen by SHA-256 ([HOLDOUT.en.md](HOLDOUT.en.md)). Each tool runs on a set once, from committed code, and every run is logged. Sets 1 and 2 checked version 0.1. Set 3 checked a candidate of version 0.2; its errors were then analysed, so sets 1 to 3 are development data. Set 4, frozen before that analysis, checked version 0.2. Set 5 checks version 0.3; it was published with its rules and run plan before the first run.
- **Same data for every comparison.** pii-roundtrip is compared with each tool on exactly the datasets that tool is scored on.
- **Precision.** For every tool the report gives the share of masked fragments that contain personal data.
- **What counts as hidden.** A value counts as hidden when all of its meaningful words are masked. A leak is an original value remaining in the cleaned text, with numbers matched across any separators and Russian surnames in all cases.
- **Round trip.** Placeholders issued by the tool and placeholders invented by the LLM are counted separately, and confidence intervals are bootstrapped over answers.

## Limitations

- On short Russian messages of hivetrace the engine masks more non-personal text than pii-guard: 89.2% of its masked fragments contain personal data, against 96.5% for pii-guard. These are errors of the GLiNER component on conversational text, which takes ordinary words and slang for personal data. On documents the engine has the highest precision among the tools that find names.
- The synthetic documents come from this project's own generator. The held-out sets protect against tuning to specific documents, not to the generator's style. pii-roundtrip was developed on documents of this generator, while the other tools never saw them.
- pii-guard and GLiNER Guard, which pii-roundtrip builds on, were released by the authors of the two Russian external datasets.
- UK NHS numbers in the external set were injected into US-style contexts.
- The round trip uses two local LLMs; larger hosted models may alter placeholders differently.
- promptShield, a browser-only tool, was not measured.

## Licence and attribution

Apache License 2.0, see [LICENSE](LICENSE). pii-roundtrip uses pii-guard, GLiNER2 with the model hivetrace/gliner-guard-omni, and pymorphy3; see [NOTICE](NOTICE).

Author: Vladimir Beskorovainyi, Besk Tech ([besk.tech](https://besk.tech)).
