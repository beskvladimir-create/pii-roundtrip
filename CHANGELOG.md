# Changelog

[Русская версия](CHANGELOG.ru.md)

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [0.5.4] - 2026-10-27

The engine is unchanged (0.5.3). This release applies a design, QA and content review before the official release.

### Changed

- Desktop app on Windows:
  - "About pii-roundtrip" is in a Help menu;
  - the system title bar is dark, matching the window;
  - the space below the menu bar is the same as on macOS.
- Desktop app: the separators in the footer of the window are the same.
- Documentation: the desktop app includes the models and works offline from the first launch; an installation from source downloads them once.
- Release notes carry the SHA-256 of each installer; the Windows build adds it itself.

## [0.5.3] - 2026-10-26

### Added

- The desktop app for Windows (beta): an installer for the current user, without administrator rights. It is built and checked on a Windows machine on GitHub. The check runs the built program without network access, installs it with the installer, and drives the installed program as a user would: it opens a Word file, cleans it, brings an AI answer back and saves it, with screenshots of each step (`.github/workflows/windows.yml`).
- `--uitest` in the desktop app: the same scripted check, used for both macOS and Windows builds.

### Fixed

- A surname the dictionary also knows as a first name ("Зимина") was stored as the first name when the text had it in an oblique case ("Зиминой Ираидой Павловной" was stored as "Ираида Зимина Павловна").
- Desktop app: a name alone on its line, as in a signature, came back in the form of its first mention in the source ("С уважением, Зиминой Ираидой Павловной"). That form is now kept only if it is the nominative.

## [0.5.2] - 2026-10-26

### Fixed

- Restoring Russian names: in common places the words before a name decide its case. These places are after "Уважаемый", "Кому:" and "ФИО:", at the start of a list item or a line, and in a signature. pii-guard's parse of the sentence chose a wrong case there ("Уважаемый Силиной Г.Э.", "Кому: Ефимову О.Е."). Elsewhere the parse decides as before.

- The macOS app requires macOS 14 (Sonoma) or later, not macOS 12 as stated before. It is built with PySide6 6.9.3 instead of 6.12.
  - The installers of 0.3.0 to 0.5.1 contained PySide6 6.12, whose Qt libraries are built for macOS 26. They most likely did not start on earlier versions of macOS. This could not be checked on an older system here.
  - PyTorch, which the models need, is built for macOS 14, so 14 is the lowest version the app can support. There are no current PyTorch builds for Intel Macs, so an Intel version is not possible without replacing it.

### Checked

- Saved answers of set 7, for reference: Russian name placeholders 99.3% for both models (0.5.1: 98.7% and 99.2%).
- No correct occurrence became a failure.
- The macOS app 0.5.2 is rebuilt with this engine.

## [0.5.1] - 2026-10-25

Fixes the Russian name errors found on held-out set 7. The result of set 7 for version 0.5 is unchanged; by its stopping rule there is no new held-out set for the paper, and set 7 is now development data.

### Fixed

- Restoring Russian names: the engine builds the word forms itself and pii-guard decides only the case. pii-guard took the first dictionary parse of each word, so "Харитонов" came back as "Харитоны" ("1. Харитоны Дмитрий Измаилович"), "Коновалова Анжела Ждановна" as "Коноваловым Анжелом Ждановном".
- Storing Russian names:
  - a first name is put in the nominative from the case of its patronymic ("Тимофей", "Данила" and "Варлаам" are kept; "Фортунату" becomes "Фортунат", "Силы" becomes "Сила", "Милану" with a man's patronymic becomes "Милан");
  - a rare first name inside a name is no longer dropped as a verb form ("Милован");
  - a misspelt patronymic is kept ("Елисевеич");
  - two forms of one first name in a document ("Данил" and "Данила") are one person.

### Checked

- Detection: identical on held-out sets 4 to 6.
- Wrongly stored Russian names on the development data: 125 → 35 (set 5) and 138 → 41 (set 6).
- No more labels shared by two people.
- Saved answers of set 7 scored with 0.5.1, for reference only: Russian name placeholders 98.7% and 99.2% instead of 94.6% and 94.7%.
- Details: `results/engine_0.5.1.json`. The macOS app 0.5.1 is rebuilt with this engine.

## [0.5.0] - 2026-10-24

Version 0.5 is checked on held-out set 7, generated after its changes and published with its rules and run plan before any run (public commit 13c42b8, pushed at 12:01:01 UTC on 23 October 2026). By the stopping rule pre-registered with it, set 7 is the last held-out set for the paper and its result is published as it is. Detection by every tool and the engine's round trip ran once, from committed code; the round trip was interrupted once by a mains power cut and continued by the same command from the saved answers (`results/holdout7_cycle_journal.md`).

### Result on set 7

- Detection, both languages met: structured identifiers 100.0%, names, addresses and organisations 99.9% (Russian) and 99.98% (UK English), documents with a leak 0.3% and 0.2%, strict count 0.8% and 0.2%.
- Restoration, UK English met: all placeholders 99.99% [99.98; 100.0], name placeholders 99.97% [99.9; 100.0].
- Restoration, Russian: all placeholders 98.9% [98.6; 99.1], undetermined; name placeholders (the sixth threshold, new) 94.6% [93.6; 95.6], **not met**.
- Manual check of all 289 failed occurrences (`results/failures_review.holdout7.json`):
  - 199: a correctly stored name inflected wrongly on restoration, mostly a surname in -ов/-ин in the plural ("Харитоны" for "Харитонов", from pii-guard's inflector);
  - 82: a name stored wrongly, mostly the first name ("Тимофя" for "Тимофей");
  - 8: restored correctly, counted as failures by the evaluator.
- Stored names: 30 of 1,027 Russian names are stored wrongly (`results/stored_names.holdout7.json`); no UK name is.

### Changed

- Russian surnames are stored in the nominative by rule. Gender comes from the patronymic, the surname's ending, the context and initials, and when in doubt the name is stored as written.
- A first name the dictionary does not know ("Пров") is inflected through a proxy name of the same declension.
- Detection is unchanged from 0.4.
- The desktop app 0.5.0 is rebuilt with engine 0.5.

### Added

- Round-trip evaluator version 3: a restored name is compared with the generator's annotation as well as with the stored value. It was fixed before set 7.
- The sixth threshold: restoration of name placeholders, at least 99%.
- `results/evaluator_versions.holdout{5,6,7}.json`: every evaluator version on sets 5, 6 and 7.
- `results/failures_review.holdout7.json` and `results/stored_names_review.holdout7.json`: the manual checks of set 7.
- `results/rule_changes.md`: rows for set 7.

### Known issues

- Restoration of Russian names: pii-guard's inflector turns a surname whose stem is also a word or a first name into the plural. It also does this where no change is needed.
- Some first names are stored in a wrong form.
- By the stopping rule these are fixed only in later versions, without a new held-out check for the paper.

## [0.4.1] - 2026-10-23

The engine is unchanged (0.4.0). This release completes the analysis of held-out set 6 after the third round of review; nothing was run again and no model was asked.

### Added

- `bench/eval/stored_names.py` and `results/stored_names.holdout6.json`: every name the engine stored in the round-trip documents of set 6 compared with the generator's annotation, with verdicts by hand for every mismatch (`results/stored_names_review.holdout6.json`). Of 1,097 Russian names 151 are stored wrongly (42 in the plural, 103 in another gender or case, 6 other); no UK name is. Restoration recomputed with their occurrences, and the two inflection errors of the first name "Пров" found by hand, counted as failures, over the occurrences the engine issued (12,720 and 13,481 in Russian): qwen3.5:9b 97.8% over all placeholders and 90.2% over name placeholders, gemma4:12b 98.0% and 90.2%; answers with at least one wrong surname 182 and 180 of 380. Not pre-registered. The same count for set 5 (engine 0.3, verdicts by rule): `results/stored_names.holdout5.json`.
- `bench/eval/evaluator_versions.py`, the script behind `results/evaluator_versions.holdout{5,6}.json`.
- `results/rule_changes.md`: every change to the scoring rules made after data had been seen, with its date and the direction it moved the results.
- The manual check of the 37 evaluator version 1 failures on set 6 (it was committed after the tag v0.4.0).

### Fixed

- REPORT section 1: 0.4 fixes some errors in storing Russian names, not all. Section 11: the stored-name error will be fixed in the next version and can be checked only on a new set. The counts of wrong surnames are stated as plural plus gender or case (up to 263 = 100 + 163 and 261 = 100 + 161 occurrences); the earlier wording in 0.4.0 read as if they were separate.
- `results/strict_leaks.json`: the examples for the UK part of set 6 were empty because only addresses and organisations were collected; every threshold type is collected now. The notes of `results/strict_leaks.json` and `results/cycle_extras.holdout6.json` say which measures were pre-registered for set 6.
- HOLDOUT: dated note that there are six held-out sets. `scripts/reproduce.sh`: sets 5 and 6 and the set 6 round trip. `results/metrics.json`: Presidio version 2.2.364 (was "2.2.364+").



Version 0.4 is checked on held-out set 6, generated after its changes and published with its rules and run plan before any run (public commit 444c4bd, pushed at 07:57:47 UTC on 22 October 2026). Detection by every tool and the engine's round trip ran once, from committed code. On set 6 the engine meets all five thresholds for both languages: structured identifiers 100.0%, names, addresses and organisations 99.98% (Russian) and 99.95% (UK English), documents with a leak 0.1% and 0.6%, the strict count (new, at most 2%) 0.2% and 0.6%, restoration 100.0% with a lower bound of 99.0% for both languages and both LLMs (380 answers per model, no failed occurrence). Full intervals are in REPORT.md and README.md; the course of the run, including a mains power cut and its continuation, is in `results/holdout6_cycle_journal.md`.

**Known issue, found after the run:** the engine stores some Russian surnames in a wrong form: 42 of 1,097 names in the plural ("Абрамов" as "Абрамы", the dictionary reads it as a form of the first name "Абрам") and 103 in another gender or case, mostly when the text has only the surname with initials. The round-trip evaluator compares answers with the stored value and counts such restorations as correct, so the Russian restoration of 100% is overstated: up to 263 (qwen3.5:9b: 100 in the plural and 163 in another gender or case) and 261 (gemma4:12b: 100 and 161) Russian placeholder occurrences carry a wrong surname, 0.8% to 2.1% and 0.7% to 1.9% of all placeholders, and meeting the 99% threshold for Russian names is not established. The error was present in 0.3 too. UK English is not affected. Details: `results/stored_names.holdout6.json`, REPORT section 11. To be fixed in the next version.


### Changed

- Held-out set 5 becomes development data for version 0.4 (22 October 2026): its incompletely masked values and restoration failures were analysed by hand after its single run. Version 0.4 is checked on a new held-out set 6, published before the first run. The external datasets are not used to tune 0.4.
- Engine: an address is masked whole: the number of a building or block cut off after its abbreviation ("д. 486 к. 50"), a note in brackets ("(метеост.)"), a street named with a number ("ш. 9 Января", "алл. Марта 8"), and the UK town between the street and the postcode or before a postcode found alone ("45 Harding Dam, West Mathewhaven B7 9LL").
- Engine: an organisation is masked whole: "Компания Адамас", "Hoff (Домашний интерьер)" (not "(далее Исполнитель)"), "ГКНПЦ им. М.В.Хруничева", "Лобанова и партнеры", hospitals with the town in the name ("General Hospital, Shirleyborough", "University Hospital Stephanietown", "Royal Infirmary of Bath"), firm names with "O'Brien" or "McDonald".
- Engine: when a rule and a model find the same text, the rule's type wins unless one of them is a checksum-validated number (a UK postcode is an address even if GLiNER calls it an ID); a name inside an address or an organisation no longer turns it into a person.
- Engine, stored values of Russian names: a first name the dictionary does not know is kept ("Большакова Милан Андреевича" was stored as "Большаков Андреевич", so "Милан" was lost on restoration); a word the dictionary knows only as a verb form or a function word is not stored as a part of the name ("Выдана Крюковой Марине Никифоровне" was stored as "Крюкова Выдана Никифоровна"); short patronymics such as "Фомич" and "Фокич" are kept; a model span that crosses a line break is split into its lines.
- Engine, restoration: two name placeholders written without a space ("[PERSON_2][PERSON_3]") are both restored; pii-guard's inflection used to lose the surname of the second.
- Round-trip evaluator version 2 (fixed before held-out set 6): surname and first-name case forms that the dictionary does not produce ("Третьякова", "Майи") are added by rule. Held-out set 5 rescored with both versions: `results/evaluator_versions.holdout5.json`.
- Strict document measure: only the types of the thresholds are counted, as described (before, also phone, e-mail and date of birth; no figure of set 5 changes, a few of set 4 and the external datasets do).
- OpenAI privacy-filter is listed as having no organisation type in `results/leak_breakdown*.json`: counting only supported types it leaks in 86.1% [83.8; 88.1] of Russian and 33.5% [30.6; 36.5] of UK documents of set 5.
- Report and README: a bound with no error is rounded down (91.1% for 40 answers, 99.0% for 380; earlier releases showed 91.2%); recall with no miss is shown with the bound 0.025^(1/n) over documents instead of "100.0% [100.0; 100.0]"; no restoration verdict for pii-guard on set 5; the tools are described as run with the settings from their documentation, not tuned; DOI 10.5281/zenodo.23478192 is named as the DOI of all versions.

## [0.3.1] - 2026-10-22

The engine is unchanged. This release fixes the leak metric, corrects the documents of 0.2.2 and 0.3.0 after an external review (dated notes, nothing rewritten), and adds measures that were not pre-registered. No model was queried again; every figure is recomputed from the saved predictions and answers.

### Fixed

- Leak metric: an identifier left visible in a hard format with dots between the groups (`5223.2630.1023.1078`) or with several separators in a row (`45...12...123456`, `123 - 456 - 789 01`) was not counted as a leak, because the rule allowed only single spaces and hyphens between the digits. A leak is now counted if the earlier rule or the new separator rule finds the number (the new rule ignores a number that is part of a longer one), so the fix only adds leaks. Recomputed from the stored predictions for the external datasets and held-out sets 4 and 5 (`python -m bench.eval.rescore_stored`); no tool was run again. Documents with a leak, held-out set 5: pii-guard (Russian) 53.2% → 58.5%, Presidio 86.3% → 87.0% (Russian) and 56.9% → 58.1% (UK English); held-out set 4: pii-guard 53.3% → 58.6%; pii-roundtrip unchanged on every set.
- Report and README, with dated notes in section 10 of the report: the 0.3 restoration change followed the analysis of set 4, not set 5 (set 5 was not used for it); set 4, not set 5, checked release 0.2; five held-out sets, not four; set 5 was generated on 19.10.2026 (20261020 is the seed); the П1 intervals for recall and precision are the cluster bootstrap, not Wilson; the Presidio Mir card recogniser checks the Luhn digit; the engine's round trip uses 190 documents per language, the other configurations 20; pii-guard's restoration verdict on set 5 is conditional (with qwen3.5:9b only 15 of 40 answers contain placeholders); README "Why" and "Restoration" describe set 5 and the 0.3 restoration forms.
- HOLDOUT.md and HOLDOUT.en.md: dated corrections below the unchanged pre-registration (generation date of set 5, five sets, SHA-256 of the project brief at private commit c6477ac).
- The public `uv.lock` was re-created by `uv lock` at every export, so releases 0.2.0 to 0.3.0 listed transformers 5.20.1 and 5.20.2, while the runs on sets 4 and 5 used transformers 5.19.0 and torch 2.14.1 (the same private lock file at the run commits 585c4a8 and 831593c). The export now pins every registry package to the private lock file, so the public lock file has the versions the results were computed with.

### Added

- Strict document measure, not pre-registered (`bench/eval/strict_leaks.py`, `results/strict_leaks.json`): documents in which at least one value of the threshold types is not fully masked, with Wilson intervals, by group of types and by noise, for every tool on sets 4 and 5 and the external datasets. pii-roundtrip on set 5: 3.3% [2.4; 4.6] (Russian) and 13.8% [11.8; 16.1] (UK English), almost entirely addresses and organisations, no identifiers.
- Round-trip measures, not pre-registered (`bench/eval/cycle_extras.py`, `results/cycle_extras.json`): answers with at least one failed occurrence with a Clopper-Pearson interval (pii-roundtrip on set 5: 9 of 380 and 6 of 380 answers in Russian, 0 of 380 in UK English), restoration without values leaked into the input, the overlap of the samples (9 of the 20 competitor documents per language are among the 190 engine documents) and every failed occurrence of pii-roundtrip and pii-guard.
- Manual check of the failures on set 5: of the 8 failed occurrences of pii-roundtrip with Russian gemma4:12b, 4 are real (a noisy document where the uninflected first name was dropped from the stored value) and 4 are evaluator misses on rare patronymics; the 1 and 3 failures of pii-guard on ru-medical-195 are real (a misspelt first name inflected wrongly).
- `results/holdout5_cycle_journal.md`: the course of the round trip on set 5 from logs and file times, including the interruption at the 72nd answer of Russian gemma4:12b (21.10.2026, about 00:01) and its continuation; no answer was requested twice.

> Correction of 22 October 2026 (second round of review): the cause of the evaluator misses given above is wrong. The patronymics are in the dictionary; it does not produce the surname form "Третьякова" of "Третьяков" or the first-name form "Майи" of "Майя". Of the 10 qwen3.5:9b failures 7 are evaluator misses, 1 is a wrong case and 2 are real (two name placeholders without a space); of the 8 gemma4:12b failures 4 are evaluator misses and 4 are real.

## [0.3.0] - 2026-10-22

Version 0.3 is checked on held-out set 5, published with its rules and run plan before any run (public commit 8b8e933). Detection by every tool and the round trips ran once, from committed code. On set 5 the engine meets all four thresholds for both languages: structured identifiers 100.0%, names, addresses and organisations 99.7% (Russian) and 98.9% (UK English), documents with a leak 0.2% and 0.7%, restoration 99.9% (Russian, worse model, 380 answers) and 100.0% with a lower bound of 99.0% (UK English, 380 answers per model). Full intervals are in REPORT.md and README.md.

One interruption: the engine's round trip stopped at answer 72 of Russian gemma4:12b when Ollama closed the connection (RemoteDisconnected); it was continued by the same command from the saved answers, so no answer was requested twice. On a manual check of the 10 failed Russian placeholder occurrences with qwen3.5:9b, the evaluator did not recognise correctly restored names with rare patronymics in another grammatical case (not in the morphology dictionary), and one name was restored in the genitive after "ФИО:". The evaluator's rules were fixed before the run and were not changed.

> Added on 22 October 2026. The finding of release 0.2.2 that the LLMs alter pii-guard's attribute tags more often than plain placeholders is withdrawn. It did not hold on set 5: tags were altered in 0 of 15 and 0 of 40 answers under pii-guard's prompt and in 0 of 26 and 1 of 40 under the generic prompt, plain placeholders in 0 of 80 and 1 of 80. Across the two sets a difference between the formats is not established. What stands is that pii-guard's strict restorer loses an altered tag and lenient restoration recovers it.

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
