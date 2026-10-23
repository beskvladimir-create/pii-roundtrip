# Held-out sets

[Русская версия](HOLDOUT.md)

Four held-out sets of synthetic documents test the engine on data it did not see during development. Each was generated before the corresponding engine changes, its SHA-256 is recorded below, and it was run once.

> Correction of 22 October 2026: there are five sets, not four. The fifth was added on 19 October 2026 (section "Set 5"); the sentence above dates from version 0.2.

> Correction of 23 October 2026: with set 6 there are six held-out sets (section "Set 6"); set 7 will be the last one for the paper.

The generator in this repository reproduces every set byte for byte. Faker draws some values (the year in an e-mail address) from the range up to "today", so the generator fixes that date: 13 October 2026 by default, and for set 3 it is given in the command (`--now 2026-10-16`). Before 16 October 2026 the date was not fixed, and regenerating set 2 on another day differed from the file in one e-mail address out of 100 documents; the set file and its hash did not change. To check:

```bash
uv run python -m bench.generator.generate --seed 20261013 --out data/holdout
uv run python -m bench.generator.generate --seed 20261014 --hard 0.3 --out data/holdout2
shasum -a 256 data/holdout*/*.jsonl
```

`bench/eval/holdout.py` compares the hashes with this file before every run, runs only from committed code, and records every run (tool, set, commit, time) in `results/holdout_runs.jsonl`. It refuses to run the same tool on the same set again unless a reason is given; the reason stays in the log. The log starts with set 3; sets 1 and 2 were run before it existed.

## Set 1

Generated on 13 October 2026, before engine development began. It was run on the engine version that preceded the identifier changes.

| File | SHA-256 |
|---|---|
| data/holdout/ru.jsonl | `b8e0523fbaf6dca966e72343549c9c9b2158310ed6f6e041ff84d86f0a94a9ec` |
| data/holdout/uk.jsonl | `10191aa5d7e90f1684d559c471eae595638c79ec514dd54fc4abf64c10668ec6` |

## Set 2

Generated on 13 October 2026, after the first run and before the identifier changes to the engine. Some identifiers in it are written in words, with dots, or with a typo in one digit. Misses of such identifiers were found on the external redmadrobot dataset, so the changes are tested on this new set rather than on that external one.

| File | SHA-256 |
|---|---|
| data/holdout2/ru.jsonl | `0058325f5eb69c60cb7a59552a97a5c9b0de7afbd860a8c13f34ca69c427dcde` |
| data/holdout2/uk.jsonl | `2829848ade96292c0e786d76eca1ee99fe720be25b3821e1406584f744329a81` |


## Set 3 (for version 0.2)

Generated on 16 October 2026, before any change of engine version 0.2. Ten times larger than the earlier sets: 1,000 documents per language, so that leaks can be judged against the 2% threshold. Run once on 17 October 2026 for every tool, with the engine at commit 5ac97ef (a version 0.2 candidate, not released): leaks of 0.5% (RU) and 3.7% (UK). The engine's errors on set 3 were then analysed, and the set became development data, like sets 1 and 2. The results of that run are kept in the log `results/holdout_runs.jsonl`.

```bash
uv run python -m bench.generator.generate --seed 20261016 --per-type 200 --hard 0.3 --now 2026-10-16 --out data/holdout3
```

| File | SHA-256 |
|---|---|
| data/holdout3/ru.jsonl | `5d82c771a92b328c9a1cad11ccbe3f1358ac932e25ab64732f245e133cb0d94e` |
| data/holdout3/uk.jsonl | `5ebebc056f200c66f384d6289b113b7827be0316a047bd9e39bc3e9a0107b7f3` |

## Set 4 (independent check of version 0.2)

Generated on 17 October 2026, before any engine change after the set 3 run and before its errors were analysed. Same size and parameters as set 3. Each tool runs on it once.

```bash
uv run python -m bench.generator.generate --seed 20261018 --per-type 200 --hard 0.3 --now 2026-10-17 --out data/holdout4
```

| File | SHA-256 |
|---|---|
| data/holdout4/ru.jsonl | `fc04a1453c17523d689f8d909e0299aeb9e0d3f7c73c9502358429f06c55ace5` |
| data/holdout4/uk.jsonl | `ce915b6d8a624cab8f0273dc6a5f6b28ded56c2181fdd1c77de30f738a46056b` |

## Set 5 (independent check of version 0.3)

Generated on 20.10.2026 after the engine changes of 0.3 (tolerance of a lost bracket around a placeholder and of words before the label inside the brackets; tested on synthetic examples, not on the answers of set 4). Same size and parameters as sets 3 and 4, a new seed. This section, the set files and the code it checks were published in the open repository before any tool was run on set 5.

```bash
uv run python -m bench.generator.generate --seed 20261020 --per-type 200 --hard 0.3 --now 2026-10-19 --out data/holdout5
```

| File | SHA-256 |
|---|---|
| data/holdout5/ru.jsonl | `41377122673a94428d27197890ec4e52426ba435585625fdc3e43b5d7de5068c` |
| data/holdout5/uk.jsonl | `9aea6e7a253c83442df8f3506882df48294006b0610f948ec38689eeee99fac2` |

### Rules fixed before the run

- Thresholds as before: structured identifiers at least 99%, names, addresses and organisations at least 95%, documents with a leak at most 2%, restoration at least 99% (worse of the two LLMs).
- Intervals of recall and masking precision: document-level cluster bootstrap (`bench/eval/cluster_ci.py`, 2,000 resamples, seed 0); a verdict that changes across seeds 0 to 5 is reported as undetermined, borderline. Share of documents with a leak: Wilson interval.
- Restoration: the share of placeholder occurrences issued by the tool that are restored correctly (each occurrence is scored once, `bench/eval/cycle.py`); interval by bootstrap over answers (2,000 resamples, seed 0). With no error, the lower bound over answers is 0.025^(1/n), n being the number of answers with placeholders. The threshold is met when the lower bound is at least 99%.
- A verdict is "met" when the whole 95% interval is on the right side of the threshold, "not met" when it is wholly on the wrong side, and "undetermined" otherwise.

### Run plan (each step once, from committed code)

1. Detection by every tool: `uv run python -m bench.eval.holdout --set 5 --tools regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip`.
2. Round trip of the engine: `uv run python -m bench.eval.cycle --data holdout5 --tools pii_roundtrip --per-type 38`: 38 documents of each of the 5 types, 2 tasks each, i.e. 380 answers per model and language; with no error the lower bound is 0.025^(1/380) = 99.03%.
3. Round trip of the other configurations in the previous volume, 40 answers per model and language: `uv run python -m bench.eval.cycle --data holdout5 --per-type 4 --tools pii_guard,pii_guard@generic,pii_guard+placeholders,pii_guard+placeholders@generic,prompt_anonymizer,gliner_guard+placeholders,gliner_guard+placeholders@generic`.
4. LLMs: qwen3.5:9b and gemma4:12b in Ollama, temperature 0, seed 0; versions in `results/ollama_versions.txt`.
5. A rerun is allowed only with a stated reason recorded in `results/holdout_runs.jsonl`.

### Corrections of 22 October 2026 (after the run; the text above is unchanged)

- Set 5 was generated on 19.10.2026, not on 20.10.2026: the files `data/holdout5/*.jsonl` were created on 19.10.2026 at 21:47 +04 by the command above with `--now 2026-10-19`, and the public pre-registration commit 8b8e933 was made on 19.10.2026 at 21:49 +04 (pushed to GitHub at 2026-10-19T17:49:23Z). The number 20261020 in the command is the generator's seed, not a date.
- The thresholds behind the verdicts were set in the project's original brief before development began. The brief is not published; its SHA-256 at the private commit c6477ac of 12.10.2026 is `a0e5bc6602334b9e79da1836c04608e6dd50b023e7dbd3055abbad43e5612f29`, so the date of the thresholds can be checked if the file is published.
- The course of the round trip on set 5, including one interruption and its continuation with the same commands, is recorded in `results/holdout5_cycle_journal.md`. The round-trip commands do not write to `results/holdout_runs.jsonl`, so the continuation is recorded there, not in that log.

### Set 5 becomes development data (22 October 2026)

Set 5 was run once and checked version 0.3 (results above and in releases 0.3.0 and 0.3.1). Its incompletely masked values and restoration failures were then analysed by hand (report, section 11). For version 0.4 set 5 is therefore development data, like sets 1 to 4. Version 0.4 is checked on a new set 6, generated and published before the first run. The external datasets are not used to tune version 0.4: their results before and after are only reported.

## Set 6 (independent check of version 0.4)

Generated on 22 October 2026 at 11:21 +04 after the engine changes of 0.4 (whole addresses and organisations, keeping a first name the dictionary does not know, keeping a non-name word out of the stored value, short patronymics, two name placeholders without a space; developed on sets 1 to 5 and the development set). The generator is unchanged since commit 22d154d (16 October 2026); same size and parameters as sets 3 to 5, a new seed. Regenerating with this command gives the same hashes (checked). This section, the set files and the code it checks were published in the open repository before any tool was run on set 6.

```bash
uv run python -m bench.generator.generate --seed 20261022 --per-type 200 --hard 0.3 --now 2026-10-22 --out data/holdout6
```

| File | SHA-256 |
|---|---|
| data/holdout6/ru.jsonl | `8ab98e467b87a7ba47f963a864d4eec51687947bae7fedad49c356271c3063be` |
| data/holdout6/uk.jsonl | `4990b7e0137e805e74157d8080d95e88792910418d70002689208e7278cb9e54` |

Code under test: engine 0.4.0, private commit 2e33854. Git tree hashes by which the code can be matched in any repository (`git rev-parse <commit>:pii_roundtrip` and `:bench`): `pii_roundtrip` 6be0f1891ce5759a402130bb637d861fa4f46745, `bench` 8e81c328ef661ca8b14e5618f923e2f7ff7a1a9f. The run uses the commit that records this section; these trees are the same in it. The public pre-registration commit and the time it was pushed to GitHub are added below after the push.

### Rules fixed before the run

- Thresholds as before: structured identifiers at least 99%, names, addresses and organisations at least 95%, documents with a leak at most 2%, restoration at least 99% (the worse of two LLMs).
- A fifth measure, new: the strict share of documents with a leak at most 2%. A document counts if at least one value of the threshold types (structured identifiers, names, addresses, organisations) is not fully masked: some meaningful word of it is visible (`bench/eval/strict_leaks.py`, the same criterion as recall). Wilson interval.
- The leak metric as in 0.3.1 (numbers with dots and several separators). Intervals for recall and precision: document-level cluster bootstrap (`bench/eval/cluster_ci.py`, 2,000 resamples, seed 0); a verdict that changes with seeds 0 to 5 is recorded as undetermined, borderline. With no miss the lower bound is 0.025^(1/n) over documents with values. The shares of documents with a leak, ordinary and strict: Wilson intervals.
- Restoration: the share of issued placeholder occurrences restored correctly, with a bootstrap interval over answers (2,000 resamples, seed 0); with no error the lower bound is 0.025^(1/n), n the number of answers with placeholders (99.03% for 380 answers). Bounds with no error are rounded down.
- Restoration evaluator version 2 (`bench/eval/cycle.py`, `EVALUATOR = 2`), fixed on 22 October 2026 before this set was generated: besides the dictionary, the case endings of surnames in -ов/-ев/-ин/-ын and -ова/-ева/-ина/-ына and of first names in -а/-я/-ия are added to the forms of a value's words, and every dictionary parse is used, not the first three. Reason: on set 5 correctly restored "Третьякова" and "Майи" were not recognised. Set 5 is rescored with both versions (`results/evaluator_versions.holdout5.json`): 10 and 8 engine failures with version 1, 2 and 0 with version 2. Restoration on set 6 is reported with version 2 (for the verdict) and version 1 (for reference). A limitation of both: the evaluator compares the answer with the value the tool stored and cannot see an error in the stored value itself.
- Companion measures without a threshold: the share of answers with at least one failed occurrence (Clopper-Pearson interval), and value fidelity: the share of name mentions in the round-trip documents whose stored value lost a word of the source mention (`bench/eval/cycle_extras.py`, `value_fidelity`).
- A threshold is met when the whole 95% interval is on the right side of it, not met when it is wholly on the wrong side, otherwise undetermined.

### Run plan (each step once, from committed code)

1. Detection by every tool, so that the comparison is on the same documents: `uv run python -m bench.eval.holdout --set 6 --tools regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip`.
2. The engine's round trip: `uv run python -m bench.eval.cycle --data holdout6 --tools pii_roundtrip --per-type 38`. 38 documents of each of 5 types, 2 tasks each: 380 answers per model and language.
3. The round trip of the other configurations is not repeated on set 6: their detection and restorers did not change, and their round trips are on sets 4 and 5.
4. LLMs: qwen3.5:9b and gemma4:12b, temperature 0, seed 0, `num_ctx` 16384; Ollama server 0.40.4 (Homebrew) with default settings, one request at a time. Concurrent requests (`OLLAMA_NUM_PARALLEL=2`) were tested on synthetic documents on 22 October 2026: for qwen3.5 the server still runs them one by one ("architecture does not currently support parallel requests"), for gemma4 one answer of six changed, with no speed-up. Concurrent requests are therefore not used. No other task uses the server during the run (on set 5 another session caused the interruption, see `results/holdout5_cycle_journal.md`).
5. The round-trip journal is kept during the run: `results/holdout6_cycle_journal.md` (start, interruptions, continuations, commit). A continuation after an interruption uses only the same command and the saved answers.
6. A detection rerun is allowed only with a stated reason recorded in `results/holdout_runs.jsonl`.

> Added after the push, before the first run: the public pre-registration commit 444c4bd was pushed to GitHub on 22 October 2026 at 07:57:47 UTC (11:57:47 +04). Its `pii_roundtrip` and `bench` trees are the ones given above.

## Set 7 (independent check of version 0.5, the last one for the paper)

Generated on 23 October 2026 at 15:24 +04 after the engine changes of 0.5 (storing and restoring Russian names; developed on sets 1 to 6 and the development set; set 6 became development data after the analysis of stored names in release 0.4.1). The generator is unchanged since commit 22d154d (16 October 2026); same size and parameters as sets 3 to 6, a new seed. Regenerating with this command gives the same hashes (checked). This section, the set files and the code it checks were published in the open repository before any tool was run on set 7.

```bash
uv run python -m bench.generator.generate --seed 20261023 --per-type 200 --hard 0.3 --now 2026-10-23 --out data/holdout7
```

| File | SHA-256 |
|---|---|
| data/holdout7/ru.jsonl | `f2df8c64f730ad0f893662c6fad201797adb6b55bda8604c20345b30a56dc330` |
| data/holdout7/uk.jsonl | `3e85284b32f1d1f683171b8537d97e794eab15ce44f8cfdd84bb950b34697281` |

Code under test: engine 0.5.0, private commit 5159948. Git tree hashes (`git rev-parse <commit>:pii_roundtrip` and `:bench`): `pii_roundtrip` e58cbfd6a621c87e6a422ae11335b147aa91fd82, `bench` 269e4e02655081737515bf9cbf15a5e25f4e72a9. The run uses the commit that records this section; these trees are the same in it. The public pre-registration commit and the push time are added below after the push.

### Stopping rule

Set 7 is the last held-out set for this paper. Its result is published whatever it is. Until the paper is published there will be no further cycle of "development, then a check on a new set"; errors found after the run are described and fixed only in later versions, without a new set for this paper.

### Rules fixed before the run

- The five thresholds as before: structured identifiers at least 99%, names, addresses and organisations at least 95%, documents with a leak at most 2%, the strict count (any value of the threshold types not fully masked) at most 2%, restoration at least 99% of placeholders (the worse of two LLMs).
- A sixth threshold, new: restoration of name placeholders `[PERSON_n]` only, at least 99% (the worse of two LLMs), with the same interval as restoration.
- Intervals, the leak metric and the verdict rule as for set 6: cluster bootstrap for recall and precision with the borderline rule over seeds 0 to 5; Wilson for shares of documents; restoration over issued occurrences with a bootstrap over answers (2,000 resamples, seed 0), with no error the lower bound 0.025^(1/n), rounded down.
- Restoration evaluator version 3 (`bench/eval/cycle.py`, `EVALUATOR = 3`): a restored name must match both the value the tool stored and the name in the generator's annotation. Every word of the annotated name that the document has must be found in the restored text in a correct form: a surname in -ов/-ев/-ин/-ын and a man's first name ending in a consonant by the declension rule, other words by the dictionary (singular), or exactly as the document wrote it (a typo of the text is not an error). Only the words of the mention closest to the stored value are required (a placeholder for "N. Johnston" or "Lucy" does not require the full name). A known limitation: a gender error where the masculine and feminine forms coincide ("Копылову") is not visible to it; stored names are therefore also checked against the annotation and by hand (below). Checked on sets 5 and 6 for reference (`results/evaluator_versions.holdout5.json`, `results/evaluator_versions.holdout6.json`).
- Companion measures without a threshold: the share of answers with at least one failed occurrence (Clopper-Pearson); stored names compared with the annotation (`bench/eval/stored_names.py`), every mismatch checked by hand; restoration with occurrences of wrongly stored names counted as failures.

### Run plan (each step once, from committed code)

1. Detection by every tool: `uv run python -m bench.eval.holdout --set 7 --tools regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip`.
2. The engine's round trip: `uv run python -m bench.eval.cycle --data holdout7 --tools pii_roundtrip --per-type 38` (380 answers per model and language).
3. The round trip of the other configurations is not repeated: their detection and restorers did not change, and their round trips are on sets 4 and 5.
4. LLMs: qwen3.5:9b and gemma4:12b, Ollama 0.40.4 (Homebrew) with default settings, one request at a time, temperature 0, seed 0, `num_ctx` 16384. No other task uses the server; the Mac is on mains power.
5. The run journal is kept during the run: `results/holdout7_cycle_journal.md`. A continuation after an interruption uses only the same command and the saved answers.
6. After the run: `bench/eval/stored_names.py holdout7`, a manual check of every failure and every stored-name mismatch.

