# Report: reversible anonymisation of documents for use with external LLMs (RU / UK)

[Русская версия](REPORT.md)

Version 0.4.0, 23 October 2026. Changes by version are in section 8 and in [CHANGELOG.md](CHANGELOG.md). Corrections to earlier releases are listed in section 10.

## 1. Summary

1. **Existing open-source tools do not meet the thresholds in either language.** The best tool for Russian, {BEST_RU}: structured identifiers {=best|ru:ext|struct+} on the external datasets. The best tool for UK English, {BEST_UK}: structured identifiers {=best|uk:ext|struct+}, leaks {=best|uk:ext|leak+}; it has no restore step of its own.
2. **Every existing tool leaks on documents.** On held-out set 6 (1,000 documents per language) a leak remains in {#best|ru:h3|leak} of Russian documents with {BEST_RU} and in {#best|uk:h3|leak} of UK documents with {BEST_UK}. The other tools leak more often (section 6).
3. **pii-roundtrip 0.4, a layer over pii-guard and GLiNER Guard, on held-out set 6: {ANON_PASS_SUMMARY_EN}.** Leaks {RU_LEAK_CI} (Russian) and {UK_LEAK_CI} (UK English). The strict count, which counts any value not fully masked, {RU_STRICT_CI} and {UK_STRICT_CI}. Restoration after the LLM answer {RU_RESTORE_CI} and {UK_RESTORE_CI}: 190 documents per language, 380 answers from each of two LLMs, not one failed occurrence by the pre-registered evaluator. **An important caveat found after the run:** the evaluator compares the answer with the value the engine stored, and some Russian names were stored in a wrong form. Restoration of 100% in Russian is therefore overstated, and meeting the 99% threshold for Russian names is not established (section 11). The error does not occur in UK English.
4. **The high recall does not come from masking more text.** The share of masked fragments that contain personal data on set 6 is {=pii_roundtrip|ru:h3|prec} for Russian and {=pii_roundtrip|uk:h3|prec} for UK English (section 5).
5. **What version 0.4 changed.** Addresses and organisations are masked whole, and the storage and restoration of Russian names are fixed. On the development data the strict count fell several times over with no loss of precision (section 8). Set 6 was generated after these changes and published with the rules before the first run.
6. **Placeholder format.** pii-guard's strict restorer loses an altered placeholder and lenient restoration recovers it. Whether the LLMs alter attribute tags more often, sets 4 and 5 answer differently, so I do not consider a difference between the formats established. On set 5 pii-guard tags were altered in {~pii_guard|ru:holdout5|answers_with_altered} of {~pii_guard|ru:holdout5|answers_with_labels} answers under its own prompt and in {~pii_guard@generic|ru:holdout5|answers_with_altered} of {~pii_guard@generic|ru:holdout5|answers_with_labels} under the generic prompt, plain placeholders in {~pii_guard+placeholders|ru:holdout5|answers_with_altered} of {~pii_guard+placeholders|ru:holdout5|answers_with_labels} and {~pii_guard+placeholders@generic|ru:holdout5|answers_with_altered} of {~pii_guard+placeholders@generic|ru:holdout5|answers_with_labels}.

## 2. Thresholds

| Measure | Threshold |
|---|---|
| Recall for structured identifiers: Russian passport, SNILS, INN, bank account, NHS, NI, card, IBAN | at least 99% |
| Recall for names, addresses, organisations | at least 95% |
| Leaks: share of texts (external datasets) or documents (synthetic) in which at least one original value remains | at most 2% |
| Strict count (from set 6): share of documents with at least one value of the threshold types not fully masked | at most 2% |
| Correct restoration after an LLM answer | at least 99% of placeholders |

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
- **Documents:** synthetic. 200 development documents and six held-out sets. Each held-out set was generated before the engine version it checks, or after its changes but before the first run, and frozen by hashes in `HOLDOUT.en.md`. Sets 1 and 2 checked version 0.1, set 3 a candidate of 0.2, set 4 version 0.2, set 5 version 0.3. The errors on each were analysed after its run, so for version 0.4 sets 1 to 5 are development data. Set 6 (2,000 documents) was generated on 22 October 2026 after the changes of version 0.4 and published with the rules and run plan before the first run (public commit 444c4bd); it checks version 0.4. Each tool ran on it once, from committed code; detection runs are logged in `results/holdout_runs.jsonl`, the round trip in `results/holdout6_cycle_journal.md`.
- **Recall:** a value is hidden when all of its meaningful words are masked. Service words such as "ул.", "д.", "Mr" and initials are not required.
- **Leak:** an original value remains in the cleaned text. A number is matched across any spaces, hyphens, dots and slashes, up to three in a row, a number in words by its spelling. A surname is matched in every case form. A first name or patronymic is matched case-sensitively and counts only if it occurs more often after masking than in the source text outside personal data (the month June is not a leak of the name June).
- **Strict count:** a document counts if at least one value of the threshold types is not fully masked, that is, some meaningful word of it is visible (the same criterion as recall). A leak counts an address or organisation only when the whole string remains; the strict count also counts an address with the postcode masked but the street and town visible.
- **Masking precision:** the share of masked fragments that touch annotated personal data. There is no threshold. The measure shows that high recall does not come from masking everything. Annotation of the external datasets is incomplete, so precision there is understated for every tool alike.
- **Round trip:**
  - a summary and a reply letter for each document; qwen3.5:9b and gemma4:12b in Ollama 0.40.4, temperature 0, seed 0;
  - pii-roundtrip 0.4: 190 documents of set 6 per language, 380 answers per model, so that a run without errors can confirm the 99% threshold;
  - the other configurations were not repeated on set 6: their detection and restorers did not change; their round trip is given from set 5 (20 documents per language, 40 answers per model);
  - placeholders issued by the tool and placeholders invented by the LLM are counted separately; intervals are bootstrapped over answers, with no error the lower bound is 0.025^(1/n) rounded down;
  - restoration evaluator version 2: case forms of surnames and first names that the dictionary does not produce are added by rule (fixed before set 6 was generated, section 11).

## 4. Existing tools

The best tool for each language is chosen on the external datasets without its home dataset.

Russian, {BEST_RU}:

| Threshold | External datasets | Held-out set 6 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|ru:ext|struct+} | {=best|ru:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|ru:ext|names+} | {=best|ru:h3|names+} |
| Leaks ≤ 2% | {=best|ru:ext|leak+} | {=best|ru:h3|leak+} |
| Restoration ≥ 99% (worse model) | not measured | set 5: {~best|ru:holdout5|restore}, no verdict |

UK English, {BEST_UK}:

| Threshold | External datasets | Held-out set 6 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|uk:ext|struct+} | {=best|uk:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|uk:ext|names+} | {=best|uk:h3|names+} |
| Leaks ≤ 2% | {=best|uk:ext|leak+} | {=best|uk:h3|leak+} |
| Restoration ≥ 99% | no restore step, not met | no restore step, not met |

No restoration verdict is given for {BEST_RU}: on set 5 with qwen3.5:9b and pii-guard's prompt only {~pii_guard|ru:holdout5@qwen3.5:9b|answers_with_labels} of {~pii_guard|ru:holdout5@qwen3.5:9b|answers} answers contain placeholders, and with one failure the bootstrap interval is narrower than the zero-error bound of a cell without failures.

The Russian external datasets contain no organisations, so for them the names row covers names and addresses. NHS numbers in the external UK dataset were injected into US-style contexts ("health plan beneficiary number"), which lowers identifier recall for every tool.

## 5. pii-roundtrip

Comparison with the best existing tool on the same data.

Russian:

{TABLE_THRESHOLDS_RU}

UK English:

{TABLE_THRESHOLDS_UK}

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
- The engine's components were released by the authors of both Russian external datasets, and two changes of version 0.1 followed error analysis on these datasets. For the engine the Russian external datasets are therefore not an independent check. The independent check of version 0.4 is held-out set 6.
- The changes of version 0.4 followed analysis of sets 1 to 5 and the development set (section 8). The external datasets were not used for it; their results before and after are given for reference. One caveat: I saw examples of over-masking on hivetrace before writing the general filters of version 0.2. The filters contain no words from those examples, but precision on hivetrace can no longer be taken as fully independent.
- On short Russian messages of hivetrace the engine masks more non-personal text than pii-guard: {#pii_roundtrip|ru:ext-pii_guard|prec} of its masked fragments contain personal data, against {#best|ru:ext|prec} for pii-guard. These are errors of the GLiNER component on conversational text. On documents the engine has the highest precision among the tools that find names.
- The engine was developed on documents of the same generator as held-out set 6. The set protects against tuning to specific documents, not to the generator's style.

## 6. Documents: where the real gap is

Held-out set 6, share of documents with a leak:

{TABLE_HEADLINE}

Share of masked fragments that contain personal data, same set:

{TABLE_PRECISION}

Why the existing tools leak:
- pii-guard and OpenAI privacy-filter have no organisations;
- GLiNER misses repeated mentions: a name is masked in the header but not in the signature;
- most tools do not recognise numbers written in words, with dots or with a typo;
- the others miss a large share of names and addresses.

## 7. Conclusion

- **Existing tools.** The technical gap is confirmed for both languages (appendix of the Russian report, П5).
- **pii-roundtrip 0.4.** Verdicts on the independent held-out set 6: {ANON_PASS_SUMMARY_EN}. Leaks of {RU_LEAK_CI} (RU) and {UK_LEAK_CI} (UK) compare with {=best|ru:h3|leak} for {BEST_RU} and {=best|uk:h3|leak} for {BEST_UK} on the same documents.

## 8. Changes by version

**Version 0.4** (set 6): addresses and organisations are masked whole; a first name the dictionary does not know is kept; a word the dictionary knows only as a verb form or a function word is not stored as part of a name ("Выдана", "Предоставить"); short patronymics ("Фомич") are kept; two name placeholders written without a space are both restored. 0.3 and 0.4 on the development data and the external datasets (for reference; these sets were development data or were not used for tuning):

{TABLE_ENGINE_VERSIONS}

**Version 0.3** (set 5): restoring a placeholder with a lost bracket or with words before the label; it followed an analysis of the round-trip answers of set 4.

**Version 0.2** (set 4): held-out sets ten times larger, comparison on the same data, masking precision for every tool, fixes of the leak metric and the round-trip cache, a reproducible generator. The fixes of version 0.1 found by two independent reviews remain.

## 9. Limitations

- **The LLM detector** was not rerun after the method fixes and is not included.
- **promptShield** was not measured: it runs only in a browser.
- **Synthetic documents** come from this project's own generator. The competing tools have not seen them. The engine was developed on them, so the held-out sets protect only against tuning to specific documents, not to the generator's style.
- **redmadrobot** contains many numbers with an invalid checksum (218 of 223 SNILS) and numbers in words.
- **Nemotron-PII** has annotation noise (for example, "their email" annotated as an e-mail address).
- **Stored Russian names.** After the run on set 6 it was found that the engine stores some Russian surnames in a wrong form; the evaluator counts the restoration of such names as correct although the surname is wrong (section 11). The error was present in version 0.3 too, so the Russian restoration on set 5 is also overstated.
- **Round trip:** the engine on set 6, the other configurations on set 5, two local models. Larger hosted models may alter placeholders differently. The evaluator compares the answer with the value the tool stored; it cannot see an error in the stored value itself, so a separate value fidelity measure was pre-registered for set 6 (section 11).

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

**Strict count by group of types** (`results/strict_leaks.json`). Held-out set 6, Wilson intervals; per group, the share among the documents that contain the group:

{TABLE_STRICT}

**The engine's round trip on set 6: answers with a failure, and restoration without values leaked into the input** (`results/cycle_extras.holdout6.json`). The share of answers with at least one failed occurrence, with a Clopper-Pearson interval (pre-registered as a companion measure):

{TABLE_CYCLE_EXTRAS}

**Value fidelity** (pre-registered): name mentions in the round-trip documents whose stored value lost a word of the source mention: {VALUE_FIDELITY}.

**Stored Russian names (found after the run, not pre-registered)** (`results/stored_names.holdout6.json`). Each name the engine stored was compared with the name in the generator's annotation: {STORED_NAMES}. The other mismatches are not engine errors: a typo in the document's own text, stored as it is, or a text without the surname (first name and patronymic only). The cause of the plural: the dictionary reads the masculine surname "Абрамов" in the nominative as a form of the first name "Абрам" and turns it into "Абрамы". The pre-registered value fidelity measure does not catch it, because "Абрамы" is formally a form of "Абрамов". Restoring such a name returns a wrong surname that the evaluator counts as correct, so the true accuracy of restored Russian names is below 100%, roughly within the range above. The error is fixed in the next version; set 6 can no longer check the fix. The engine makes no such error on UK names.

**Evaluator versions 1 and 2 on set 6** (engine failures, version 1 / version 2): {EVALUATOR_VERSIONS_SET6}. The verdict uses version 2, as pre-registered.

**Manual check of the 37 version 1 failures on set 6** (19 placeholder-in-answer groups, 23 October 2026). Correctly restored and missed by version 1: every "Майя" ("Туровой Майи Артёмовны", "Носовой Майе Робертовне"), the surname "Большаков" ("Большакова Епифана Жановича") and "Щербакове Прове Тимуровиче", "Сорокине Прове Ефремовиче". Real errors that version 2 counted as correct: "Щербаковым Провым Тимуровичем" (should be "Провом") and "Лобанова Прва Игнатьевича", so pii-guard's inflection fails on the rare first name Пров, and "Игнатов Прова Филипповича" (3 occurrences), a consequence of the stored "Игнаты". Four groups could not be isolated automatically. Evaluator version 2 is too lenient for the name "Пров": the dictionary gives it forms the language does not have. This is one more reason to consider the 99% threshold for Russian names not established.

**The other configurations, set 5** (not pre-registered, added on 22 October 2026 after review; pii-roundtrip here is version 0.3):

{TABLE_CYCLE_EXTRAS_5}

**Overlap of the samples on set 5.** The 20 documents per language used for the other configurations and the 190 engine documents are drawn by the same random generator; 9 of the 20 are shared in each language.

**Manual check of the failures on set 5.**
- pii-roundtrip, Russian, gemma4:12b, 8 failed occurrences. 4 are real (ru-hr-022, a noisy document): in "Большакова Милан Андреевича" the first name is not inflected; the engine masked it in full but stored the value as "Большаков Андреевич", so the first name was lost on restoration (fixed in 0.4). The other 4 were restored correctly ("Третьякова Фадея Изотовича", "Третьякова Пимена Валерьяновича", "Афанасьевой Майи Ждановны" in two answers) but the evaluator did not recognise them.
- pii-roundtrip, Russian, qwen3.5:9b, 10 occurrences: 7 were restored correctly but not recognised by the evaluator; 1 name was restored in the genitive after "ФИО:"; 2 are real (ru-letter-145 and ru-letter-129): the LLM wrote two name placeholders without a space (`[PERSON_2][PERSON_3]`), and pii-guard's inflection, which the engine uses to restore Russian names, lost the surname of the second name (fixed in 0.4).
- Why the evaluator missed correct names (correction of 22 October 2026 after the second round of review; release 0.3.1 gave the wrong cause, rare patronymics). The patronymics are in the dictionary. It does not produce the surname form "Третьякова" of "Третьяков" (it reads it as a form of "третьяк") or the form "Майи" of "Майя". Evaluator version 2 adds such forms by rule; it was fixed before set 6 was generated, and set 5 is rescored with both versions for reference (`results/evaluator_versions.holdout5.json`).
- pii-guard, ru-medical-195, 1 occurrence under its own prompt and 3 under the generic prompt (qwen3.5:9b). The source has the misspelt name "Иисдор"; pii-guard stored it in its table as "Иисдоры" and returned "Пахомова Иисдоров Герасимовича". The error is in the stored value, not in the inflection: the evaluator compares the answer with that value, so evaluator version 2 accepts "Иисдоров" as its form.
