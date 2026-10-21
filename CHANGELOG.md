# Changelog

[Русская версия](CHANGELOG.ru.md)

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-10-22

Version 0.3 is checked on held-out set 5, published with its rules and run plan before any run (public commit 8b8e933). Detection by every tool and the round trips ran once, from committed code. On set 5 the engine meets all four thresholds for both languages: structured identifiers 100.0%, names, addresses and organisations 99.7% (Russian) and 98.9% (UK English), documents with a leak 0.2% and 0.7%, restoration 99.9% (Russian, worse model, 380 answers) and 100.0% with a lower bound of 99.0% (UK English, 380 answers per model). Full intervals are in REPORT.md and README.md.

One interruption: the engine's round trip stopped at answer 72 of Russian gemma4:12b when Ollama closed the connection (RemoteDisconnected); it was continued by the same command from the saved answers, so no answer was requested twice. On a manual check of the 10 failed Russian placeholder occurrences with qwen3.5:9b, the evaluator did not recognise correctly restored names with rare patronymics in another grammatical case (not in the morphology dictionary), and one name was restored in the genitive after "ФИО:". The evaluator's rules were fixed before the run and were not changed.


### Changed

- Engine restoration accepts a placeholder with a lost bracket (`ORG_1]`, `[ORG_1`) and with words the model put before the label inside the brackets (`[Company: ORG_1]`; the words are kept). Every form is matched by one pattern, `PLACEHOLDER_ANY`, so each occurrence is restored once. Tested on synthetic examples, not on the answers of held-out set 4.
- The restoration threshold is again judged on the share of restored placeholder occurrences, with a bootstrap interval over answers; with no error the lower bound over answers is 0.025^(1/n). The per-answer rule of 0.2.2 is withdrawn; on held-out set 4 the UK restoration of 0.2 is 99.6% [99.2; 99.9], met, and the Russian one 100.0% [91.2; 100.0], undetermined.

### Added

- Held-out set 5, its hashes, the threshold rules and the run plan (HOLDOUT.md), published before any run on it. The engine's round trip on set 5 uses 380 answers per model and language, so that a run without errors can meet the 99% threshold.
- `results/cycle_metrics.holdout5.json`, `results/leak_breakdown.holdout5.json`; the cluster bootstrap includes set 5.
- macOS app 0.3.1: the engine 0.3 inside, so answers with a lost bracket around a placeholder are restored in the app too.

## [0.2.2] - 2026-10-19

The engine is unchanged. Only the evaluation of the round trip and the way the report states verdicts changed; all figures were recomputed from saved predictions and answers, without new model queries.

### Fixed

- Round-trip evaluator: labels a model rewrote in square brackets (`[PII type="…" id="…"]` for pii-guard, `[Name_2]` for Prompt Anonymizer) were not recognised, so such answers counted as answers without labels. They now count as issued labels that the model altered. This adds 43 pii-guard and 29 Prompt Anonymizer occurrences in two answers, all lost by the tools' restorers.
- The finding on the label format is restated: the LLMs altered pii-guard's attribute tags more often than plain placeholders, and pii-guard's strict restorer turned the alterations into losses, including intact neighbouring tags it swallowed. The earlier wording, that the format and the prompt play no role, is withdrawn.

### Changed

- Intervals for recall and masking precision in the report and README come from the document-level cluster bootstrap (`results/cluster_ci.json`) instead of Wilson intervals over values. A verdict that changes with the bootstrap seed (0 to 5) is reported as undetermined, borderline.
- The restoration threshold is judged on answers (answers restored without an error, Wilson interval), not on placeholder occurrences. With 40 of 40 clean answers the interval starts at 91.2%, so a perfect restoration is undetermined against 99%.
- The engine's results on hivetrace/pii-bench and redmadrobot pii_benchmark, the home datasets of its components, are shown for reference, without a verdict.
- The summary lists the verdict for each threshold instead of a count such as "4 of 4".

### Added

- `results/cycle_metrics.holdout4.json`: answers and documents with altered labels, and failed occurrences split into altered labels and intact neighbours lost with them.

## [0.2.1] - 2026-10-19

The engine is unchanged; its detection and leak figures on held-out set 4 stand. The restoration figures were recomputed with a corrected metric (below).

### Changed

- Restoration metric: each placeholder occurrence issued by a tool is scored once. It fails if it is still in the text after restoration, if its value is missing from the restored text, or if the tool's restorer scrubbed it. Before, an occurrence left in the text was also counted as a lost value, so it counted twice. All held-out set 4 answers were rescored from the saved answers (`python -m bench.eval.cycle --data holdout4 --rescore`); no model was queried again.
- The pooled bootstrap over the UK external datasets treats the 28 source texts shared by the two Nemotron subsets as one cluster each.
- Held-out set 3 is described as development data in the 0.2.0 notes: its errors were analysed after it had checked a 0.2 candidate.

### Added

- Controls for the round trip on held-out set 4: pii-guard tags with the generic system prompt, plain placeholders with the generic prompt (Russian and UK), and pii-guard answers restored by label type and number (lenient parsing, written after the failures had been found). The evaluator of this version missed labels rewritten in square brackets; 0.2.2 corrects it and restates the finding.
- `bench/eval/leak_breakdown.py` and `results/leak_breakdown.json`: document-level leaks on held-out set 4 for clean and noisy documents, with and without hard-format identifiers, by entity type, and over the types each tool supports.
- Published data: held-out sets 1 to 4, the LLM answers of the held-out set 4 round trip, every tool's saved predictions, `results/cluster_ci.json` and the Ollama and model versions (`results/ollama_versions.txt`).

### Added (desktop)

- Desktop app for macOS (desktop 0.3.0) in `desktop/`: drop in a Word file, a PDF or text, send the cleaned version to any AI tool, and get its answer back with the real values. It works offline with the models inside the installer, keeps the formatting of Word files and the layout of PDFs where the returned file allows it, and stores the link between labels and values encrypted with a key in the macOS Keychain. The installer is attached to the release; see desktop/README.md.

### Fixed

- CLI: a missing input or password file and a run without a terminal to ask for the password now give a message instead of a Python traceback.

## [0.2.0] - 2026-10-18

### Changed (may need action)

- British English is now `en-GB`. `uk` is the ISO 639-1 code for Ukrainian, so it is accepted only as a deprecated alias with a `DeprecationWarning` and will be removed. Sessions saved with `uk` load as `en-GB`.
- Installation is split into extras. `pip install pii-roundtrip` installs the core (checksum rules, placeholders, vault, restoration) without torch or models. Use `pii-roundtrip[ru]` for pii-guard (Russian NER and name inflection), `[gliner]` for GLiNER Guard, `[all]` for both, `[bench]` for the benchmark.
- Sessions carry a format version. A session of an unknown version raises `SessionError` instead of being misread.
- Errors are typed: `PiiRoundtripError` and its subclasses `UnsupportedLanguageError`, `SessionError`, `ModelsNotAvailableError`, `InflectionError`, `VaultError`.

### Added

- `--password-file` for the CLI. Output files are written with mode 0600 and never through a symbolic link.
- `Engine(strict_inflection=False)` restores names in the nominative case instead of failing when inflection fails.
- Held-out sets 3 and 4 (1,000 documents per language each). Set 3 was frozen before any 0.2 change and checked a 0.2 candidate; its errors were then analysed and it became development data. Set 4 was frozen before that analysis and checks the release; see HOLDOUT.en.md.
- A log of held-out runs: a tool runs on a held-out set once, from committed code; a repeat needs a stated reason, which stays in the log.
- CI: ruff, mypy and the tests on Python 3.12 and 3.13.

### Fixed

Detection (found on the development data: the synthetic set and held-out sets 1 and 2, which became development data for 0.2, and held-out set 3, whose errors were analysed after it had checked a 0.2 candidate; external datasets and held-out set 4 were not used for tuning):

- An organisation name repeated without its legal form ("ГКУ «Восход» ... представитель Восход") stayed visible for 12 of 19 Russian legal forms; every form is now handled, and a form matches only as a whole word.
- Names next to initials are masked even with a typo in the surname ("А.О. Нкионовой", "V. Rcie"); "SURNAME, Firstname" records are masked whole.
- Addresses are masked with the house, building, flat, postcode and region next to them; a UK house number and street before a recognised town are included.
- The addressee organisation in a Russian business letter, the place of work in a certificate ("работает в ... в должности"), a sole proprietor's trade name ("ИП «...»") and a partners' firm on a UK letterhead are masked.
- Labels are no longer masked as personal data: "РФ" after "Гражданин" spread over the whole document as part of a name; "Сторона 1", "Party A", "ОГРН", "IBAN", bank codes (БИК) and Companies House numbers are left visible. On the development data the share of masked fragments that contain personal data rose from 88% to 98.5% for Russian and from 97% to 99.9% for UK English, with no loss of recall.
- UK letters: the organisation under the addressee, names after "chaired by", "point of contact is", "site passes for", list entries "Name Surname, born", and names with the first two letters swapped by a typo are masked. Russian: the organisation on the line of "Генеральному директору" and at the head of an order.
- Model spans that cannot be what their type says are dropped: a number without digits, an organisation of lower-case dictionary words, a one-word lower-case "name" that is not a name.
- A model span that ended past the end of the text, or included a trailing newline, is trimmed to the text.

Benchmark:

- Leak detection: a first name or patronymic that also occurs in the text as an ordinary word outside personal data (the month in "8 June 2025" for "June Gibbons") is a leak only if it occurs more often after masking. Surnames are still checked strictly in every case form. This applies to every tool.
- Masking precision is reported for every tool: the share of masked fragments that touch personal data, with a 95% interval, and the same share by characters.
- The round trip cache keys LLM answers by a hash of the prompt, so a changed anonymisation is sent to the model again instead of reusing an answer to the old text.
- Models are loaded from the local cache without changing process environment variables (`HF_HUB_OFFLINE` and others are no longer set).
- A failed `anonymize` call leaves the session unchanged.
- The synthetic generator no longer depends on the day it runs. Faker takes some values (the year in an e-mail address) from the range up to "today"; the generator now fixes that date (`--now`). Regenerating held-out set 2 on another day had differed from the frozen file in one e-mail address; the frozen files and their hashes are unchanged.

### Internal

- The engine talks to pii-guard and GLiNER only through adapters in `pii_roundtrip/adapters`.
- The benchmark is a package (`bench`) and needs no `PYTHONPATH`. Checksum validators exist once, in `pii_roundtrip.checksums`.
- A golden test compares anonymisation and restoration with version 0.1.0 output; refactoring changed none of 280 outputs.

## [0.1.0] - 2026-10-14

First public release: the engine, the benchmark of existing tools on Russian and UK English documents, the report and a draft preprint.

[0.3.0]: https://github.com/beskvladimir-create/pii-roundtrip/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/beskvladimir-create/pii-roundtrip/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/beskvladimir-create/pii-roundtrip/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/beskvladimir-create/pii-roundtrip/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/beskvladimir-create/pii-roundtrip/releases/tag/v0.1.0
