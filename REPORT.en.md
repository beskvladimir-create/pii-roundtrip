# Report: reversible anonymisation of documents for use with external LLMs (RU / UK)

[Русская версия](REPORT.md)

Version 0.5.4, 27 October 2026. Changes by version are in section 8 and in [CHANGELOG.md](CHANGELOG.md). Corrections to earlier releases are listed in section 10.

## 1. Summary

1. **Existing open-source tools do not meet the thresholds in either language.** The best tool for Russian, pii-guard: structured identifiers 97.7% [96.1; 99.0] undetermined, borderline on the external datasets. The best tool for UK English, GLiNER Guard Omni: structured identifiers 96.4% [95.7; 97.1] not met, leaks 4.0% [3.4; 4.8] not met; it has no restore step of its own.
2. **Every existing tool leaks on documents.** On held-out set 7 (1,000 documents per language) a leak remains in 60.8% of Russian documents with pii-guard and in 58.3% of UK documents with GLiNER Guard Omni. The other tools leak more often (section 6).
3. **pii-roundtrip 0.5, a layer over pii-guard and GLiNER Guard, on held-out set 7: Russian: met: identifiers, names and addresses, leaks, strict leaks; undetermined: restoration; not met: restoration of name placeholders; UK English: met: identifiers, names and addresses, leaks, restoration, restoration of name placeholders, strict leaks.** Leaks 0.3% [0.1; 0.9] met (Russian) and 0.2% [0.1; 0.7] met (UK English). The strict count, which counts any value not fully masked, 0.8% [0.4; 1.6] met and 0.2% [0.1; 0.7] met. Restoration after the LLM answer, all placeholders: 98.9% [98.6; 99.1] undetermined and 99.99% [99.98; 100.0] met; name placeholders only (the sixth threshold, new for set 7): 94.6% [93.6; 95.6] not met and 99.97% [99.9; 100.0] met. 190 documents per language, 380 answers from each of two LLMs, evaluator version 3, which compares a restored name with the generator's annotation as well as with the stored value. **In Russian the restoration of names fails the threshold.** A manual check of every failure (section 11) finds three groups: 199 occurrences with a correctly stored name inflected wrongly on restoration, mostly a surname in -ов/-ин turned into the plural ("Харитоны Дмитрий Измаилович"); 82 occurrences of names stored in a wrong form, mostly the first name ("Тимофя" for "Тимофей"); 8 occurrences restored correctly but counted as failures by the evaluator. Set 7 is the last held-out set for this paper (stopping rule in HOLDOUT.en.md), and these verdicts stand. Version 0.5.1 fixes the restoration and storage errors after the run; on the saved answers of set 7, no longer a held-out check, its Russian name placeholders are restored in 98.7% and 99.2% of cases (section 8).
4. **The high recall does not come from masking more text.** The share of masked fragments that contain personal data on set 7 is 98.4% [98.3; 98.5] for Russian and 99.8% [99.8; 99.9] for UK English (section 5).
5. **What version 0.5 changed.** Russian surnames are stored in the nominative by rule; the gender comes from the patronymic, the surname's ending, the context and initials; when in doubt the name is stored as written; a first name the dictionary does not know ("Пров") is inflected through a proxy name of the same declension. On the development data the share of wrongly stored Russian names fell from about 9% to 0.3% on set 5 and was 0.1% on set 6; detection measures did not change. What it did not change: the restoration step still inflects a surname such as "Харитонов" into the plural; the storage check of the development data could not see this, because the saved answers of a set can be scored only with the engine version that produced them. Set 7 was generated after these changes and published with the rules before the first run.
6. **Placeholder format.** pii-guard's strict restorer loses an altered placeholder and lenient restoration recovers it. Whether the LLMs alter attribute tags more often, sets 4 and 5 answer differently, so I do not consider a difference between the formats established. On set 5 pii-guard tags were altered in 0 of 55 answers under its own prompt and in 1 of 66 under the generic prompt, plain placeholders in 0 of 80 and 1 of 80.

## 2. Thresholds

| Measure | Threshold |
|---|---|
| Recall for structured identifiers: Russian passport, SNILS, INN, bank account, NHS, NI, card, IBAN | at least 99% |
| Recall for names, addresses, organisations | at least 95% |
| Leaks: share of texts (external datasets) or documents (synthetic) in which at least one original value remains | at most 2% |
| Strict count (from set 6): share of documents with at least one value of the threshold types not fully masked | at most 2% |
| Correct restoration after an LLM answer | at least 99% of placeholders |
| Correct restoration of name placeholders `[PERSON_n]` (from set 7) | at least 99% |

One rule for every tool and threshold:
- **met:** the whole 95% confidence interval is on the right side of the threshold;
- **not met:** the whole interval is on the wrong side;
- **undetermined:** the interval spans the threshold.

## 3. Method

- **Tools:** pii-guard, GLiNER Guard Omni, OpenAI privacy-filter, Presidio, Prompt Anonymizer, and a baseline of regular expressions with checksums. Each runs with the settings from its documentation (model, types, confidence threshold); no threshold was tuned on our data. Configurations are stored in `results/metrics.json`. Presidio has no Russian recognisers, so recognisers for the passport, SNILS, INN, bank account and Mir card were added by us; the SNILS, INN and Mir card recognisers check the checksum (Luhn for the card), the passport and account recognisers do not. OpenAI privacy-filter has no organisation type. LLM Guard is excluded: its repository is archived and it has no Russian.
- **External datasets:**
  - RU: hivetrace/pii-bench and redmadrobot pii_benchmark. Both were released by the authors of tools in the comparison, so a tool is not scored on its authors' dataset.
  - UK: Nemotron-PII. Texts with British features, and texts with injected NHS, NI and IBAN.
- **Same data for every comparison.** pii-roundtrip is scored on exactly the datasets on which the tool it is compared with is scored.
- **Documents:** synthetic. 200 development documents and seven held-out sets. Each held-out set was generated before the engine version it checks, or after its changes but before the first run, and frozen by hashes in `HOLDOUT.en.md`. Sets 1 and 2 checked version 0.1, set 3 a candidate of 0.2, set 4 version 0.2, set 5 version 0.3. Set 6 checked version 0.4. The errors on each set were analysed after its run, so for version 0.5 sets 1 to 6 are development data. Set 7 (2,000 documents) was generated on 23 October 2026 after the changes of version 0.5 and published with the rules and run plan before the first run (public commit 13c42b8, pushed at 12:01:01 UTC, the first run at 16:03 +04); it checks version 0.5 and is the last held-out set for this paper. Each tool ran on it once, from committed code; detection runs are logged in `results/holdout_runs.jsonl`, the round trip in `results/holdout7_cycle_journal.md` (one interruption: mains power was lost, the run was continued by the same command from the saved answers, no answer was asked twice).
- **Recall:** a value is hidden when all of its meaningful words are masked. Service words such as "ул.", "д.", "Mr" and initials are not required.
- **Leak:** an original value remains in the cleaned text. A number is matched across any spaces, hyphens, dots and slashes, up to three in a row, a number in words by its spelling. A surname is matched in every case form. A first name or patronymic is matched case-sensitively and counts only if it occurs more often after masking than in the source text outside personal data (the month June is not a leak of the name June).
- **Strict count:** a document counts if at least one value of the threshold types is not fully masked, that is, some meaningful word of it is visible (the same criterion as recall). A leak counts an address or organisation only when the whole string remains; the strict count also counts an address with the postcode masked but the street and town visible.
- **Masking precision:** the share of masked fragments that touch annotated personal data. There is no threshold. The measure shows that high recall does not come from masking everything. Annotation of the external datasets is incomplete, so precision there is understated for every tool alike.
- **Round trip:**
  - a summary and a reply letter for each document; qwen3.5:9b and gemma4:12b in Ollama 0.40.4, temperature 0, seed 0;
  - pii-roundtrip 0.5: 190 documents of set 7 per language, 380 answers per model, so that a run without errors can confirm the 99% threshold;
  - the other configurations were not repeated on sets 6 and 7: their detection and restorers did not change; their round trip is given from set 5 (20 documents per language, 40 answers per model);
  - placeholders issued by the tool and placeholders invented by the LLM are counted separately; intervals are bootstrapped over answers, with no error the lower bound is 0.025^(1/n) rounded down;
  - restoration evaluator version 3 (fixed before set 7 was generated): a restored name must match the value the tool stored and the name in the generator's annotation; every word of the annotated name that the document has must appear in a correct case form (surnames in -ов/-ев/-ин/-ын and masculine first names ending in a consonant by rule, other words by the dictionary) or exactly as the document wrote it. A gender error where the masculine and feminine forms coincide ("Копылову") is not visible to it.

## 4. Existing tools

The best tool for each language is chosen on the external datasets without its home dataset.

Russian, pii-guard:

| Threshold | External datasets | Held-out set 7 |
|---|---|---|
| Structured identifiers ≥ 99% | 97.7% [96.1; 99.0] undetermined, borderline | 92.4% [91.7; 93.1] not met |
| Names, addresses, organisations ≥ 95% | 99.5% [98.7; 100.0] met | 73.4% [72.8; 74.0] not met |
| Leaks ≤ 2% | 0.7% [0.4; 1.2] met | 60.8% [57.7; 63.8] not met |
| Restoration ≥ 99% (worse model) | not measured | set 5: 99.8% [99.4; 100.0], no verdict |

UK English, GLiNER Guard Omni:

| Threshold | External datasets | Held-out set 7 |
|---|---|---|
| Structured identifiers ≥ 99% | 96.4% [95.7; 97.1] not met | 95.4% [94.9; 95.8] not met |
| Names, addresses, organisations ≥ 95% | 98.7% [98.2; 99.1] met | 88.9% [88.4; 89.5] not met |
| Leaks ≤ 2% | 4.0% [3.4; 4.8] not met | 58.3% [55.2; 61.3] not met |
| Restoration ≥ 99% | no restore step, not met | no restore step, not met |

No restoration verdict is given for pii-guard: on set 5 with qwen3.5:9b and pii-guard's prompt only 15 of 40 answers contain placeholders, and with one failure the bootstrap interval is narrower than the zero-error bound of a cell without failures.

The Russian external datasets contain no organisations, so for them the names row covers names and addresses. NHS numbers in the external UK dataset were injected into US-style contexts ("health plan beneficiary number"), which lowers identifier recall for every tool.

## 5. pii-roundtrip

Comparison with the best existing tool on the same data.

Russian:

| Threshold | pii-guard, external | pii-roundtrip, same external sets | pii-guard, held-out set 7 | pii-roundtrip, held-out set 7 |
|---|---|---|---|---|
| Structured identifiers ≥ 99% | 97.7% [96.1; 99.0] undetermined, borderline | 100.0% [99.1; 100.0], for reference | 92.4% [91.7; 93.1] not met | 100.0% [99.6; 100.0] met |
| Names, addresses, organisations ≥ 95% | 99.5% [98.7; 100.0] met | 100.0% [98.9; 100.0], for reference | 73.4% [72.8; 74.0] not met | 99.9% [99.9; 99.98] met |
| Documents with a leak ≤ 2% | 0.7% [0.4; 1.2] met | 0.0% [0.0; 0.2], for reference | 60.8% [57.7; 63.8] not met | 0.3% [0.1; 0.9] met |
| Documents with a value not fully masked ≤ 2% (strict, new) | 0.7% [0.4; 1.2], for reference | 0.0% [0.0; 0.2], for reference | 99.9% [99.4; 99.98] not met | 0.8% [0.4; 1.6] met |
| Restoration ≥ 99% (worse of two LLMs) | not measured | not measured | 99.8% [99.4; 100.0], set 5, no verdict (see below) | 98.9% [98.6; 99.1] undetermined |
| Restoration of name placeholders ≥ 99% (worse of two LLMs, new) | not measured | not measured | not measured | 94.6% [93.6; 95.6] not met |
| Masked fragments that contain personal data | 96.5% [95.5; 97.5], no threshold | 89.2% [87.7; 90.6], no threshold | 87.6% [87.5; 87.7], no threshold | 98.4% [98.3; 98.5], no threshold |

External sets: hivetrace_pii_bench.

UK English:

| Threshold | GLiNER Guard Omni, external | pii-roundtrip, same external sets | GLiNER Guard Omni, held-out set 7 | pii-roundtrip, held-out set 7 |
|---|---|---|---|---|
| Structured identifiers ≥ 99% | 96.4% [95.7; 97.1] not met | 99.97% [99.9; 100.0] met | 95.4% [94.9; 95.8] not met | 100.0% [99.6; 100.0] met |
| Names, addresses, organisations ≥ 95% | 98.7% [98.2; 99.1] met | 98.3% [97.9; 98.8] met | 88.9% [88.4; 89.5] not met | 99.98% [99.96; 100.0] met |
| Documents with a leak ≤ 2% | 4.0% [3.4; 4.8] not met | 0.9% [0.6; 1.3] met | 58.3% [55.2; 61.3] not met | 0.2% [0.1; 0.7] met |
| Documents with a value not fully masked ≤ 2% (strict, new) | 4.9% [4.2; 5.7], for reference | 2.1% [1.7; 2.7], for reference | 83.5% [81.1; 85.7] not met | 0.2% [0.1; 0.7] met |
| Restoration ≥ 99% (worse of two LLMs) | not measured | not measured | no restore step, not met | 99.99% [99.98; 100.0] met |
| Restoration of name placeholders ≥ 99% (worse of two LLMs, new) | not measured | not measured | not measured | 99.97% [99.9; 100.0] met |
| Masked fragments that contain personal data | 89.3% [88.8; 89.9], no threshold | 93.5% [92.9; 94.0], no threshold | 94.8% [94.7; 95.0], no threshold | 99.8% [99.8; 99.9], no threshold |

External sets: nemotron_uk, nemotron_uk_ids.

What the engine adds to its components:
- rules with checksums;
- long numbers with any separators, and numbers in words;
- organisations, sole proprietors, the addressee organisation of a business letter, an organisation masked whole with the word "Компания", a name in brackets, "им." and the town in a hospital's name;
- names with titles and initials, including a typo in the surname;
- the whole address: street, house, building, block, postcode, region, and the UK town between the street and the postcode;
- consistent placeholders across a document and a conversation: one person always gets one placeholder, different people are never merged;
- every found name propagated to all its mentions: Russian case forms, ё/е, capitals, double-barrelled surnames;
- labels ("Сторона 1", "Party A", "ОГРН", "IBAN"), bank codes and Companies House numbers are left visible;
- restoration tolerant to changes made by the LLM, with morphology for Russian names;
- an encrypted vault and offline operation.

Caveats:
- The engine's components were released by the authors of both Russian external datasets, and two changes of version 0.1 followed error analysis on these datasets. For the engine the Russian external datasets are therefore not an independent check. The independent check of version 0.5 is held-out set 7.
- The changes of version 0.5 followed analysis of sets 1 to 6 and the development set (section 8). The external datasets were not used for it; their results before and after are given for reference. One caveat: I saw examples of over-masking on hivetrace before writing the general filters of version 0.2. The filters contain no words from those examples, but precision on hivetrace can no longer be taken as fully independent.
- On short Russian messages of hivetrace the engine masks more non-personal text than pii-guard: 89.2% of its masked fragments contain personal data, against 96.5% for pii-guard. These are errors of the GLiNER component on conversational text. On documents the engine has the highest precision among the tools that find names.
- The engine was developed on documents of the same generator as held-out set 7. The set protects against tuning to specific documents, not to the generator's style.

## 6. Documents: where the real gap is

Held-out set 7, share of documents with a leak:

| Tool | Russian | UK English |
|---|---|---|
| **pii-roundtrip** | **0.3% [0.1; 0.9]** | **0.2% [0.1; 0.7]** |
| pii-guard | 60.8% [57.7; 63.8] | n/a |
| GLiNER Guard Omni | 99.6% [99.0; 99.8] | 58.3% [55.2; 61.3] |
| Presidio | 87.1% [84.9; 89.0] | 61.1% [58.0; 64.1] |
| OpenAI privacy-filter | 97.0% [95.7; 97.9] | 81.1% [78.6; 83.4] |
| Prompt Anonymizer | n/a | 100.0% [99.6; 100.0] |
| Regular expressions with checksums | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] |

Share of masked fragments that contain personal data, same set:

| Tool | Russian | UK English |
|---|---|---|
| pii-roundtrip | 98.4% [98.3; 98.5] | 99.8% [99.8; 99.9] |
| pii-guard | 87.6% [87.5; 87.7] | n/a |
| GLiNER Guard Omni | 77.0% [76.7; 77.2] | 94.8% [94.7; 95.0] |
| Presidio | 76.1% [75.8; 76.3] | 79.0% [78.8; 79.3] |
| OpenAI privacy-filter | 81.2% [81.1; 81.4] | 92.9% [92.7; 93.1] |
| Prompt Anonymizer | n/a | 99.0% [98.9; 99.1] |
| Regular expressions with checksums | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] |

Why the existing tools leak:
- pii-guard and OpenAI privacy-filter have no organisations;
- GLiNER misses repeated mentions: a name is masked in the header but not in the signature;
- most tools do not recognise numbers written in words, with dots or with a typo;
- the others miss a large share of names and addresses.

## 7. Conclusion

- **Existing tools.** The technical gap is confirmed for both languages (appendix of the Russian report, П5).
- **pii-roundtrip 0.5.** Verdicts on the independent held-out set 7: Russian: met: identifiers, names and addresses, leaks, strict leaks; undetermined: restoration; not met: restoration of name placeholders; UK English: met: identifiers, names and addresses, leaks, restoration, restoration of name placeholders, strict leaks. Leaks of 0.3% [0.1; 0.9] met (RU) and 0.2% [0.1; 0.7] met (UK) compare with 60.8% [57.7; 63.8] for pii-guard and 58.3% [55.2; 61.3] for GLiNER Guard Omni on the same documents. Restoration of Russian names remains below 99%: the error that 0.5 fixed in storage reappears in the restoration step (section 11).

## 8. Changes by version

**Version 0.5.3** (26 October 2026): a surname the dictionary also knows as a first name ("Зимина") is no longer stored as the first name; in the desktop app a name alone on its line comes back in the nominative; the desktop app for Windows (beta), built and checked by a scripted run of the installed program on a Windows machine. Detection is unchanged; wrongly stored Russian names on the development data 33 (set 5) and 36 (set 6).

**Version 0.5.2** (26 October 2026): in common places the words before a name decide its case on restoration (after "Уважаемый", "Кому:", "ФИО:", at the start of a list item or a line, in a signature); elsewhere pii-guard's parse of the sentence decides, as before. On the saved answers of set 7 (for reference) Russian name placeholders are restored in 99.3% (qwen3.5:9b) and 99.3% (gemma4:12b) of cases; the remaining failures are mostly correct names the evaluator does not recognise. Details: `results/engine_0.5.1.json`.

**Version 0.5.1** (25 October 2026, after set 7): the engine builds the word forms of a Russian name itself when it restores the answer (pii-guard still decides the case from the syntax): surnames in -ов/-ев/-ин/-ын by rule, first names and patronymics in the singular of the name's gender, by rule when the dictionary does not know them. A first name is put in the nominative from the case of its patronymic ("Тимофей" stays, "Фортунату" becomes "Фортунат", "Силы" becomes "Сила"); a rare first name inside a name is no longer dropped as a verb form ("Милован"); a misspelt patronymic is kept. Detection is unchanged (identical scores on sets 4 to 6). Russian names stored wrongly on the development data (rule plus first names and patronymics): 125 → 35 of about 5,350 on set 5, 138 → 41 on set 6; no two people share a placeholder more often than before, and a person split into two placeholders became rarer (284 → 266 on set 5). The saved answers of set 7 scored with 0.5.1 (for reference only, set 7 was seen before 0.5.1 was written): Russian name placeholders 98.7% (qwen3.5:9b) and 99.2% (gemma4:12b) instead of 94.6% and 94.7%; most of the remaining failures are correct names the evaluator does not recognise ("Софии", "Милованом") and a case chosen wrongly by pii-guard's syntax ("Уважаемый Силиной Г.Э."). Details: `results/engine_0.5.1.json`.

**Version 0.5** (set 7): Russian surnames stored in the nominative by rule, gender from the patronymic, the surname's ending, the context and initials, a name stored as written when in doubt, rare first names inflected through a proxy name; the earlier evaluators are kept and evaluator version 3 added. Detection is unchanged from 0.4.

**Version 0.4** (set 6): addresses and organisations are masked whole; a first name the dictionary does not know is kept; a word the dictionary knows only as a verb form or a function word is not stored as part of a name ("Выдана", "Предоставить"); short patronymics ("Фомич") are kept; two name placeholders written without a space are both restored. 0.3 and 0.4 on the development data and the external datasets (for reference; these sets were development data or were not used for tuning):

| Set | Strict 0.3 → 0.4 | Leaks 0.3 → 0.4 | Names, addresses, organisations 0.3 → 0.4 | Precision 0.3 → 0.4 |
|---|---|---|---|---|
| holdout5_ru | 33 → 3 of 1000 | 0.20% → 0.20% | 99.73% → 99.97% | 98.46% → 98.45% |
| holdout5_uk | 138 → 5 of 1000 | 0.70% → 0.50% | 98.88% → 99.96% | 99.84% → 99.84% |
| holdout4_ru | 25 → 5 of 1000 | 0.20% → 0.20% | 99.79% → 99.95% | 98.50% → 98.49% |
| holdout4_uk | 155 → 9 of 1000 | 0.90% → 0.90% | 98.72% → 99.93% | 99.85% → 99.85% |
| hivetrace_pii_bench | 0.0% → 0.0% | 0.0% → 0.0% | 100.0% → 100.0% | 89.2% → 89.2% |
| redmadrobot_pii_benchmark | 1.3% → 1.3% | 1.1% → 1.1% | 98.3% → 98.3% | 76.5% → 76.4% |
| nemotron_uk | 5.7% → 4.5% | 0.7% → 0.7% | 96.4% → 97.1% | 92.9% → 93.0% |
| nemotron_uk_ids | 1.4% → 1.3% | 0.9% → 0.9% | 98.9% → 98.9% | 93.5% → 93.6% |

**Version 0.3** (set 5): restoring a placeholder with a lost bracket or with words before the label; it followed an analysis of the round-trip answers of set 4.

**Version 0.2** (set 4): held-out sets ten times larger, comparison on the same data, masking precision for every tool, fixes of the leak metric and the round-trip cache, a reproducible generator. The fixes of version 0.1 found by two independent reviews remain.

## 9. Limitations

- **The LLM detector** was not rerun after the method fixes and is not included.
- **promptShield** was not measured: it runs only in a browser.
- **Synthetic documents** come from this project's own generator. The competing tools have not seen them. The engine was developed on them, so the held-out sets protect only against tuning to specific documents, not to the generator's style.
- **redmadrobot** contains many numbers with an invalid checksum (218 of 223 SNILS) and numbers in words.
- **Nemotron-PII** has annotation noise (for example, "their email" annotated as an e-mail address).
- **Russian names.** On set 7, 30 of 1,027 Russian names in the round-trip documents are stored wrongly, mostly the first name, and many correctly stored surnames are restored in the plural (section 11). On sets 5 and 6 the stored surnames themselves were wrong, so the Russian restoration published for those sets is overstated (release 0.4.1).
- **Round trip:** the engine on set 7, the other configurations on set 5, two local models. Larger hosted models may alter placeholders differently. Evaluator version 3 requires a typo of the source to be restored exactly as written: an inflected misspelt word ("Лдюмилой") counts as a failure.

## 10. Corrections to releases 0.2.2 and 0.3.0 (22 October 2026)

The corrections follow an external review. The release texts in the CHANGELOG and the pre-registration in HOLDOUT.en.md are not rewritten: dated notes are added to them.

- **The 0.3 change and set 5.** The 0.3.0 report said the restoration change of 0.3 followed an analysis of the answers of set 5. That is wrong: it followed an analysis of the answers of set 4; set 5 was generated after it and was not used for it (section 5).
- **Section 8** said set 5 checked the 0.2 release. Set 4 did. There are five held-out sets, not four (section 3).
- **Date of set 5.** The set was generated on 19 October 2026, not 20 October; 20261020 is the generator's seed (correction in HOLDOUT.en.md).
- **Intervals in П1** were labelled as Wilson intervals. For recall and precision they are the document-level cluster bootstrap; only the share of documents with a leak has a Wilson interval.
- **Presidio.** The list of added recognisers omitted the Mir card; its recogniser checks the Luhn digit. The passport and account recognisers have no check (section 3).
- **The round trip in section 9** was described as 20 documents per language. For pii-roundtrip it is 190 documents (380 answers per model), for the other configurations 20.
- **pii-guard's restoration on set 5** was shown as met without a caveat. With qwen3.5:9b only part of its answers contain placeholders; the verdict is conditional (section 4).
- **Placeholder format.** The finding of release 0.2.2 that the LLMs alter pii-guard's tags more often is withdrawn: it did not hold on set 5 (section 1, CHANGELOG 0.3.0).
- **The leak metric** did not count a number with dots or with several separators in a row. Fixed in 0.3.1: leaks of pii-guard, Presidio, GLiNER Guard and others went up, those of pii-roundtrip did not change (CHANGELOG 0.3.1).
- **Library versions.** The public `uv.lock` of releases 0.2.0 to 0.3.0 was re-created at export and listed transformers 5.20.1 and 5.20.2. The runs on sets 4 and 5 used one environment: transformers 5.19.0, torch 2.14.1 (the private lock file, identical at the run commits 585c4a8 and 831593c). From 0.3.1 the public lock file is pinned to the versions of that environment.

Second round of review (23 October 2026):
- **The cause of the evaluator misses** on set 5 was given wrongly (rare patronymics). The patronymics are in the dictionary; it does not produce "Третьякова" from "Третьяков" or "Майи" from "Майя" (section 11).
- **The strict count** counted every annotated type while it is described as a count over the threshold types; aligned with the description, the figures of set 5 did not change.
- **OpenAI privacy-filter** was not marked as having no organisations; counting only its supported types it leaks in 86.1% of Russian and 33.5% of UK documents of set 5 (`results/leak_breakdown.holdout5.json`).
- **Bounds with no error** are rounded down (91.1% for 40 answers, 99.0% for 380); recall with no miss is shown with the same kind of bound over documents.
- **The method** described the tools as configured "for their best result"; they run with the settings from their documentation, with no threshold tuned.

## 11. Additional measures

**Strict count by group of types** (`results/strict_leaks.json`). Held-out set 7, Wilson intervals; per group, the share among the documents that contain the group:

| Tool | Set | All documents | Identifiers | Names | Addresses | Organisations |
|---|---|---|---|---|---|---|
| pii-roundtrip | holdout7_ru | 0.8% [0.4; 1.6] | 0.0% [0.0; 0.4] | 0.0% [0.0; 0.4] | 0.2% [0.1; 0.7] | 0.6% [0.3; 1.3] |
| pii-roundtrip | holdout7_uk | 0.2% [0.1; 0.7] | 0.0% [0.0; 0.4] | 0.2% [0.1; 0.7] | 0.0% [0.0; 0.4] | 0.0% [0.0; 0.4] |
| pii-guard | holdout7_ru | 99.9% [99.4; 99.98] | 38.4% [35.4; 41.5] | 0.2% [0.1; 0.7] | 90.4% [88.4; 92.1] | 98.4% [97.4; 99.0] |
| GLiNER Guard Omni | holdout7_ru | 99.9% [99.4; 99.98] | 99.6% [99.0; 99.8] | 64.8% [61.8; 67.7] | 63.2% [60.2; 66.1] | 23.9% [21.4; 26.6] |
| GLiNER Guard Omni | holdout7_uk | 83.5% [81.1; 85.7] | 33.6% [30.7; 36.6] | 31.9% [29.1; 34.9] | 56.0% [52.9; 59.0] | 24.6% [22.0; 27.4] |
| Presidio | holdout7_ru | 100.0% [99.6; 100.0] | 39.7% [36.7; 42.8] | 70.7% [67.8; 73.4] | 100.0% [99.6; 100.0] | 9.3% [7.7; 11.3] |
| Presidio | holdout7_uk | 100.0% [99.6; 100.0] | 38.1% [35.1; 41.2] | 32.7% [29.9; 35.7] | 100.0% [99.6; 100.0] | 42.3% [39.3; 45.4] |
| OpenAI privacy-filter | holdout7_ru | 99.6% [99.0; 99.8] | 34.7% [31.8; 37.7] | 76.3% [73.6; 78.8] | 57.7% [54.6; 60.7] | 80.0% [77.4; 82.4] |
| OpenAI privacy-filter | holdout7_uk | 96.8% [95.5; 97.7] | 41.9% [38.9; 45.0] | 8.4% [6.8; 10.3] | 39.3% [36.3; 42.4] | 85.0% [82.7; 87.1] |
| Prompt Anonymizer | holdout7_uk | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] | 40.3% [37.3; 43.4] | 100.0% [99.6; 100.0] | 90.3% [88.3; 92.0] |
| Regular expressions with checksums | holdout7_ru | 100.0% [99.6; 100.0] | 39.8% [36.8; 42.9] | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] |
| Regular expressions with checksums | holdout7_uk | 100.0% [99.6; 100.0] | 40.0% [37.0; 43.1] | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] | 100.0% [99.6; 100.0] |

**The engine's round trip on set 7: answers with a failure, and restoration without values leaked into the input** (`results/cycle_extras.holdout7.json`). The share of answers with at least one failed occurrence, with a Clopper-Pearson interval (pre-registered as a companion measure):

| Configuration | Language, model | Answers with a failure | Restoration without values leaked into the input |
|---|---|---|---|
| pii_roundtrip | ru/gemma4:12b | 100/380, 26.3% [22.0; 31.0] | 99.0% (13900/14045) |
| pii_roundtrip | ru/qwen3.5:9b | 99/380, 26.1% [21.7; 30.8] | 98.9% (12404/12547) |
| pii_roundtrip | uk/gemma4:12b | 1/380, 0.3% [0.0; 1.5] | 99.99% (13875/13876) |
| pii_roundtrip | uk/qwen3.5:9b | 0/380, 0.0% [0.0; 1.0] | 100.0% (12232/12232) |

**Stored names** (pre-registered as a companion measure for set 7; `results/stored_names.holdout7.json`, `bench/eval/stored_names.py`, every mismatch with the annotation checked by hand in `results/stored_names_review.holdout7.json`; the rule compares surnames, so first names and patronymics were compared separately): of 1027 Russian names in the round-trip documents 30 were stored wrongly (every mismatch with the annotation checked by hand), nearly all in the first name or patronymic: "Тимофя" and "Фадя" for "Тимофей" and "Фадей", "Данил" and "Гаврил" for "Данила" and "Гаврила", a first name left in an oblique case ("Фортунату"), a rare first name or a misspelt patronymic dropped. Restoration with this taken into account: qwen3.5:9b: over all issued placeholders 98.6% [98.4; 98.9], over name placeholders only 93.5% [92.4; 94.6], answers with at least one wrongly stored name 50 of 380 [9.9; 17.0]; gemma4:12b: over all issued placeholders 98.7% [98.5; 99.0], over name placeholders only 93.6% [92.5; 94.7], answers with at least one wrongly stored name 48 of 380 [9.5; 16.4]. UK English: no stored name is wrong.

**Evaluator versions on set 7** (engine failures, versions 1 / 2 / 3; `results/evaluator_versions.holdout7.json`): ru/qwen3.5:9b: 27 / 7 / 143; ru/gemma4:12b: 24 / 10 / 145; uk/qwen3.5:9b: 0 / 0 / 0; uk/gemma4:12b: 0 / 0 / 1. The verdict uses version 3, as pre-registered. Versions 1 and 2 accept a surname in the plural as a dictionary form of the stored surname, which is why they show far fewer failures.

**Manual check of every failure on set 7** (`results/failures_review.holdout7.json`; 289 failed occurrences in 91 pairs of document and label, 288 of them Russian):
- **Restoration (199 occurrences, 67 pairs).** The name was stored correctly and inflected wrongly when the answer was restored. Mostly a surname in -ов/-ев/-ин whose stem is also a word or a first name came back in the plural ("Харитонов" as "Харитоны", "Максимов" as "Максимы", "Орехов" as "Орехи", "Ильин" as "Ильины"), also in the nominative where nothing needs to change ("1. Харитоны Дмитрий Измаилович"). The engine passes the stored name to pii-guard's inflector, and the inflector reads the surname as a form of the noun or first name. In 11 occurrences (5 pairs) the first name "София" went through the proxy name "Олимпия" and was not carried back ("Громов Олимпий Степановна"). Other cases: a wrong case or gender ("Коноваловым Анжелом Ждановном").
- **Stored value (82 occurrences, 17 pairs).** The name was stored in a wrong form: a first name in -ей as "Тимофя" or "Фадя", a rare first name lost ("Жуков Венедиктович" for "Жуков Милован Венедиктович"), a misspelt patronymic lost, a misspelt name left in an oblique case.
- **Evaluator (8 occurrences, 7 pairs).** The restored text is correct: a typo of the source restored exactly as written or in the right case ("Лдюмилой", "Валетниновича"), and in UK English "Kate Matthews", which the evaluator matched with another person of the document. The pre-registered figures are not changed by this check.

Why this was not found before set 7: in 0.4 the same surnames were already stored in the plural, and the fix of 0.5 was checked on stored names; a set's saved answers can be scored only with the engine version that produced them, so the restoration of 0.5 had no answers to be scored on before set 7. The unit tests check storage and the proxy names, not the restoration of such surnames.

**Sets 5 and 6 with every evaluator version** (for reference; `results/evaluator_versions.holdout5.json`, `results/evaluator_versions.holdout6.json`): with version 3 the Russian name placeholders were restored correctly in about 89% of cases on set 5 (engine 0.3) and about 94% to 95% on set 6 (engine 0.4).

**Set 6, stored names (release 0.4.1, not pre-registered)**: of 1097 Russian names in the round-trip documents 151 were stored wrongly (checked by hand): 42 in the plural ("Абрамов" as "Абрамы"), 103 in another gender or case, 6 other (surname or initials dropped, order changed). Restoration with this taken into account: qwen3.5:9b: over all issued placeholders 97.8% [97.6; 98.1], over name placeholders only 90.2% [88.9; 91.5], answers with at least one wrong surname 182 of 380 [42.8; 53.0]; gemma4:12b: over all issued placeholders 98.0% [97.7; 98.2], over name placeholders only 90.2% [88.9; 91.4], answers with at least one wrong surname 180 of 380 [42.3; 52.5].

**The other configurations, set 5** (not pre-registered, added on 22 October 2026 after review; pii-roundtrip here is version 0.3):

| Configuration | Language, model | Answers with a failure | Restoration without values leaked into the input |
|---|---|---|---|
| gliner_guard+placeholders | uk/gemma4:12b | 2/40, 5.0% [0.6; 16.9] | 99.8% (1920/1923) |
| gliner_guard+placeholders | uk/qwen3.5:9b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1644/1644) |
| gliner_guard+placeholders@generic | uk/gemma4:12b | 1/40, 2.5% [0.1; 13.2] | 99.9% (1898/1900) |
| gliner_guard+placeholders@generic | uk/qwen3.5:9b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1595/1595) |
| pii_guard | ru/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1564/1564) |
| pii_guard | ru/qwen3.5:9b | 1/15, 6.7% [0.2; 31.9] | 99.8% (541/542) |
| pii_guard+placeholders | ru/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (2168/2168) |
| pii_guard+placeholders | ru/qwen3.5:9b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1961/1961) |
| pii_guard+placeholders@generic | ru/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (2297/2297) |
| pii_guard+placeholders@generic | ru/qwen3.5:9b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1956/1956) |
| pii_guard@generic | ru/gemma4:12b | 1/40, 2.5% [0.1; 13.2] | 98.3% (1674/1703) |
| pii_guard@generic | ru/qwen3.5:9b | 2/26, 7.7% [0.9; 25.1] | 99.7% (1057/1060) |
| pii_guard@generic~tolerant | ru/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1703/1703) |
| pii_guard@generic~tolerant | ru/qwen3.5:9b | 0/26, 0.0% [0.0; 13.2] | 100.0% (1060/1060) |
| pii_guard~tolerant | ru/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1564/1564) |
| pii_guard~tolerant | ru/qwen3.5:9b | 0/15, 0.0% [0.0; 21.8] | 100.0% (542/542) |
| pii_roundtrip | ru/gemma4:12b | 6/380, 1.6% [0.6; 3.4] | 99.9% (13714/13722) |
| pii_roundtrip | ru/qwen3.5:9b | 9/380, 2.4% [1.1; 4.4] | 99.9% (12264/12274) |
| pii_roundtrip | uk/gemma4:12b | 0/380, 0.0% [0.0; 1.0] | 100.0% (13857/13857) |
| pii_roundtrip | uk/qwen3.5:9b | 0/380, 0.0% [0.0; 1.0] | 100.0% (11963/11963) |
| prompt_anonymizer | uk/gemma4:12b | 0/40, 0.0% [0.0; 8.8] | 100.0% (1115/1115) |
| prompt_anonymizer | uk/qwen3.5:9b | 0/40, 0.0% [0.0; 8.8] | 100.0% (911/911) |

**Overlap of the samples on set 5.** The 20 documents per language used for the other configurations and the 190 engine documents are drawn by the same random generator; 9 of the 20 are shared in each language.

The manual checks of sets 5 and 6 are in release 0.4.1 (`results/stored_names_review.holdout6.json`, REPORT of 0.4.1).
