# Data codebook (English)

This codebook describes the data and result files released with pii-roundtrip and the benchmark reported in the paper "Reversible pseudonymisation of documents sent to external LLMs: an open bilingual benchmark and an engine". Field names are in English, and code comments, documentation and console messages are in English except as noted below. Russian appears in the data and result files only where it is the object of study or a verbatim record of it, as explained for each file.

## Why some data are in Russian

The benchmark measures how well tools detect, mask and restore personal data in Russian and in UK English documents. The Russian documents, the Russian answers of the language models and the Russian names quoted in the reviews are therefore the data under test: translating them would remove exactly the properties being measured (Cyrillic script, case inflection of names, Russian identifier formats). The Russian content of the held-out sets (`data/holdout*`), of the round-trip answers (`results/cycle`) and of the files derived from them (`stored_names*`, `cycle_extras*`, the review files) is synthetic: names, identifiers, addresses and organisations were produced by the project's generator and do not refer to real people. The exception is `results/metrics.json`, which quotes missed values from the external datasets (see section 4).

Every Russian-language document file of the project (README.ru.md, REPORT.md, HOLDOUT.md, CHANGELOG.ru.md, CONTRIBUTING.ru.md, SECURITY.ru.md, bench/eval/analysis.md, desktop/README.ru.md, docs/README.ru.tpl.md) has an English counterpart (README.md, REPORT.en.md, HOLDOUT.en.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, bench/eval/analysis.en.md, desktop/README.md, docs/README.tpl.md). The run journals and results/rule_changes.md contain an English version first and a Russian version below it.

## 1. Synthetic documents: `data/holdout*/{ru,uk}.jsonl`

Held-out sets 1 to 7 (`data/holdout` is set 1, `data/holdout2` to `data/holdout7` are sets 2 to 7). One JSON object per line, one synthetic document per object. `ru.jsonl` holds Russian documents, `uk.jsonl` UK English documents. The file `SEED` in each folder (all sets except set 3) holds the generator seed; the full generation command of each set is in HOLDOUT.en.md.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Document identifier: language, document type and number, e.g. `ru-contract-000`. |
| `lang` | string | `ru` (Russian) or `uk` (UK English). |
| `doc_type` | string | `contract`, `letter`, `hr` (HR file), `medical` (hospital discharge summary) or `certificate` (employment certificate). |
| `noisy` | boolean | `true` if the document contains generated noise, such as doubled spaces and typos in names; in sets 2 to 7, noisy documents also contain hard number formats (numbers written in words, with dots, or with a digit typo). Set 1 was generated without hard formats. |
| `text` | string | Full text of the document, in the language given by `lang`. |
| `entities` | list | Gold annotation: every occurrence of personal data in `text` (see below). |

Fields of each entity:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | Entity label (see the label list). |
| `start`, `end` | integer | Character offsets of the occurrence in `text` (end exclusive). |
| `value` | string | The occurrence exactly as it appears in the text (in Russian documents, a Russian word form). |
| `canonical` | string | Normalised value: for names, the nominative form "Surname First-name Patronymic" (Russian) or "First-name Surname" (UK); for the checksum identifiers (PASSPORT_RU, SNILS, INN, BANK_ACCOUNT_RU, CARD, NHS), digits only; for NINO and IBAN, upper case with whitespace removed; for other types, the value as written. |
| `person_id` | string | Identifier of the synthetic person the value belongs to, so that all mentions of one person can be linked (absent for values not tied to a person). |
| `quasi` | boolean | Present and `true` for quasi-identifiers (see `QUASI`). |

Entity labels:

| Label | Meaning |
|---|---|
| `PERSON` | Name of a person, in any grammatical case, with or without title and initials. |
| `ORG` | Name of an organisation. |
| `ADDRESS` | Postal address. |
| `PHONE` | Telephone number. |
| `EMAIL` | E-mail address. |
| `DATE_OF_BIRTH` | Date of birth. |
| `PASSPORT_RU` | Russian internal passport, series and number. |
| `SNILS` | Russian individual insurance account number (pension insurance). |
| `INN` | Russian taxpayer identification number. |
| `BANK_ACCOUNT_RU` | Russian bank account number. |
| `CARD` | Payment card number. |
| `NHS` | UK NHS number. |
| `NINO` | UK National Insurance number. |
| `IBAN` | International bank account number (UK). |
| `QUASI` | Quasi-identifier: a description that identifies a person without a name or number, e.g. "the only veterinary doctor in the village of …". |

## 2. Predictions of each tool: `results/<tool>/<dataset>.jsonl`

One folder per tool (`pii_roundtrip`, `pii_guard`, `gliner_guard`, `presidio`, `privacy_filter`, `prompt_anonymizer`, `regex_baseline`; `pii_roundtrip_0.3` holds the predictions of engine version 0.3 on the four external datasets) and one file per dataset (`holdout*_ru`, `holdout*_uk`, `hivetrace_pii_bench`, `redmadrobot_pii_benchmark`, `nemotron_uk`, `nemotron_uk_ids`, `synthetic_*`). The files contain no text from the documents, only character offsets.

| Field | Meaning |
|---|---|
| `id` | Document identifier (as in the dataset). |
| `h` | First 12 hex digits of the SHA-256 of the document text, to check that predictions match the text. |
| `v` | First 12 hex digits of a SHA-256 over the exact bytes of `bench/runners/base.py`, `bench/eval/run.py`, `uv.lock` and the tool's own files (`CODE_DEPS` in `bench/eval/run.py`; for pii_roundtrip, the whole engine). |
| `pred` | Predicted spans: `type` (label), `start`, `end` (character offsets into the document text). |

## 3. Round trip with local language models: `results/cycle/<set>/<tool>/<lang>_<model>.jsonl`

For a sample of documents of each held-out set (a fixed number per document type: 40 answers per tool, model and language on set 4 and for the other tools on set 5; 380 answers, from 190 documents with two tasks, for pii-roundtrip on sets 5 to 7), the masked text was sent to a local language model (`qwen3.5:9b` or `gemma4:12b`; in file names ":" is replaced by "_") with two tasks, and the answer was stored. The answers to Russian documents are in Russian, because the model was asked in Russian. They contain each tool's own placeholders: `[PERSON_1]` for pii-roundtrip and the `+placeholders` runs, `<PII …/>` tags for pii-guard, `<Name_1>` for Prompt Anonymizer. A suffix `@generic` in the folder name marks runs with the generic system prompt instead of the tool's own.

| Field | Meaning |
|---|---|
| `id` | Document identifier. |
| `task` | `summary` (short summary of the document) or `reply` (formal reply letter). The exact instructions, in Russian for Russian documents and in English for UK documents, are in `TASKS` in `bench/eval/cycle.py`. |
| `q` | First 16 hex digits of the SHA-256 of the system prompt, the instruction and the masked text sent to the model. |
| `answer` | The model's answer to the masked document, before restoration. |

## 4. Summary results: `results/*.json`

| File | Content |
|---|---|
| `metrics.json` | Recall, precision, leak counts and other metrics per tool, dataset and label. `per_type.<label>.misses` and `leak_examples` quote missed values verbatim, including short excerpts from the external datasets (kept under their licences, see NOTICE). The `_config` entries carry notes on each tool, some in Russian; their translation is in docs/CODE_COMMENTS_EN.md. |
| `cluster_ci.json` | Confidence intervals (bootstrap over documents) for recall and precision. |
| `leak_breakdown*.json`, `strict_leaks.json` | Documents with a leak, by label; the strict count of values not fully masked. |
| `cycle_metrics.*.json`, `cycle_extras*.json` | Restoration results of the round trip per tool, language and model, for all placeholders and for name placeholders only; `restore_ci_method` "bootstrap по ответам, 2000 повторов" means "bootstrap over answers, 2,000 resamples". `cycle_extras` lists individual failed occurrences, quoting Russian values verbatim where the document is Russian. |
| `evaluator_versions.*.json` | The same saved round-trip answers scored under each version of the evaluator (see `results/rule_changes.md`). |
| `stored_names.*.json` | For every name the engine masked, the stored value compared with the generator's annotation; Russian names are quoted verbatim. |
| `stored_names_review.*.json` | Manual review of stored names: an object keyed `"<document id> [PERSON_n]"` with the verdict `"right"` or `"wrong"` (defined in `_note`). Set 6 also has English `"<key> note"` entries, `_inflection_errors` (model, id, task, label, occurrences, note; notes partly in Russian) and `_groups_checked`; set 7 has `_notes`, a remark per key in Russian, because the remarks discuss Russian word forms. |
| `failures_review.holdout7.json` | Manual review of every failed occurrence in the engine's round trip on set 7: `items` with `id`, `label`, `stored`, `group`, `note` and `occurrences` per model. `group` gives the verdict in English: `stored_wrong` (the name was stored in a wrong form), `restore_inflection` (stored correctly, put back in a wrong grammatical case), `evaluator_false_failure` (counted as a failure by the evaluator but restored correctly); definitions are in `_note`. The free-text `note` is in Russian, because it discusses Russian word forms. |
| `engine_*.json` | Results of engine versions on development and external data. |
| `holdout_runs.jsonl` | Log of every run on a held-out set: set, tool, commit and time; `rescore: true` marks a recomputation of metrics from stored predictions. |

## 5. Code

Comments, docstrings, console messages and option help in the code are in English, with two exceptions. First, Russian appears in the code where it is data: Russian document templates (`bench/generator/templates_ru.py`), word lists and name forms used by the engine, the Russian instructions sent to the language models for Russian documents (`TASKS` in `bench/eval/cycle.py`), the Russian text of REPORT.md built by `bench/eval/report.py`, the Russian user interface of the desktop application, and Russian test inputs; comments that quote such data keep the Russian words verbatim. Second, the comments of the files that enter the version hash of the released predictions (`bench/eval/run.py`, `bench/runners/base.py` and the tool runners) are left unchanged, including three console messages of `bench/eval/run.py` and the tool notes copied into `results/metrics.json`, because changing a byte of them would invalidate the released predictions; their English translation is in [docs/CODE_COMMENTS_EN.md](docs/CODE_COMMENTS_EN.md).

## 6. External datasets

The external datasets (hivetrace/pii-bench and redmadrobot-rnd/pii_benchmark in Russian, nvidia/Nemotron-PII in English) are not redistributed; they are downloaded at pinned revisions by `bench/eval/external.py`, which also documents how their labels are mapped to the labels above.
