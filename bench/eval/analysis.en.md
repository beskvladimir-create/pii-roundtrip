# Report: reversible anonymisation of documents for use with external LLMs (RU / UK)

[Русская версия](REPORT.md)

Version 0.3.1, 22 October 2026. Changes since version 0.1 are described in section 8 and in [CHANGELOG.md](CHANGELOG.md). Corrections to releases 0.2.2 and 0.3.0 are listed in section 10.

## 1. Summary

1. **Existing open-source tools do not meet the thresholds in either language.** The best tool for Russian, {BEST_RU}: structured identifiers {=best|ru:ext|struct+} on the external datasets. The best tool for UK English, {BEST_UK}: structured identifiers {=best|uk:ext|struct+}, leaks {=best|uk:ext|leak+}; it has no restore step of its own.
2. **Every existing tool leaks on documents.** On held-out set 5 (1,000 documents per language) a leak remains in {#best|ru:h3|leak} of Russian documents with {BEST_RU} and in {#best|uk:h3|leak} of UK documents with {BEST_UK}. The other tools leak more often (section 6).
3. **pii-roundtrip, a layer over pii-guard and GLiNER Guard, on held-out set 5: {ANON_PASS_SUMMARY_EN}.** Leaks: {RU_LEAK_CI} for Russian and {UK_LEAK_CI} for UK English.
4. **The high recall does not come from masking more text.** The share of masked fragments that contain personal data on held-out set 5 is {=pii_roundtrip|ru:h3|prec} for Russian and {=pii_roundtrip|uk:h3|prec} for UK English (section 5).
5. **pii-guard's strict restorer loses an altered label and lenient restoration recovers it; whether the LLMs alter attribute tags more often, the two sets answer differently.** On held-out set 5 alterations were rare in both formats: pii-guard tags were altered in {~pii_guard|ru:holdout5|answers_with_altered} of {~pii_guard|ru:holdout5|answers_with_labels} answers under its own prompt and in {~pii_guard@generic|ru:holdout5|answers_with_altered} of {~pii_guard@generic|ru:holdout5|answers_with_labels} under the generic prompt; plain `[TYPE_n]` placeholders over the same detection in {~pii_guard+placeholders|ru:holdout5|answers_with_altered} of {~pii_guard+placeholders|ru:holdout5|answers_with_labels} and {~pii_guard+placeholders@generic|ru:holdout5|answers_with_altered} of {~pii_guard+placeholders@generic|ru:holdout5|answers_with_labels}. On held-out set 4 (version 0.2.2) the tags were altered more often: 3 of 53 and 6 of 74 answers against 1 of 80 and 0 of 80 for plain placeholders, so I do not consider a difference between the formats established. What holds on both sets: pii-guard's strict restorer does not recognise an altered tag and scrubs it; on set 5 under the generic prompt {~pii_guard@generic|ru:holdout5|failed_altered} altered occurrences failed and {~pii_guard@generic|ru:holdout5|failed_intact} more without an alteration, under its own prompt {~pii_guard|ru:holdout5|failed_altered} altered and {~pii_guard|ru:holdout5|failed_intact} without an alteration. Lenient parsing by the label's type and number, written after such failures were found on set 4, restores the same answers in full. Engine 0.3 also restores altered labels: on the UK part of set 5 there were {~pii_roundtrip|uk:holdout5|altered} of them across both LLMs, with {~pii_roundtrip|uk:holdout5|occurrences_failed} failures. Sample: 190 documents per language for pii-roundtrip and 20 for the other configurations, two tasks, two LLMs (appendix of the Russian report, П3).

## 2. Thresholds

| Measure | Threshold |
|---|---|
| Recall for structured identifiers: Russian passport, SNILS, INN, bank account, NHS, NI, card, IBAN | at least 99% |
| Recall for names, addresses, organisations | at least 95% |
| Leaks: share of texts (external datasets) or documents (synthetic) in which at least one original value remains | at most 2% |
| Correct restoration after an LLM answer | at least 99% of placeholders |

One rule for every tool and threshold:
- **met:** the whole 95% confidence interval is on the right side of the threshold;
- **not met:** the whole interval is on the wrong side;
- **undetermined:** the interval spans the threshold.

## 3. Method

- **Tools:** pii-guard, GLiNER Guard Omni, OpenAI privacy-filter, Presidio, Prompt Anonymizer, and a baseline of regular expressions with checksums. Each is configured for its best result according to its documentation; configurations are stored in `results/metrics.json`. Presidio has no Russian recognisers, so recognisers for the passport, SNILS, INN, bank account and Mir card were added by us; the SNILS, INN and Mir card recognisers check the checksum (Luhn for the card), the passport and account recognisers do not. LLM Guard is excluded: its repository is archived and it has no Russian.
- **External datasets:**
  - RU: hivetrace/pii-bench and redmadrobot pii_benchmark. Both were released by the authors of tools in the comparison, so a tool is not scored on its authors' dataset.
  - UK: Nemotron-PII. Texts with British features, and texts with injected NHS, NI and IBAN.
- **Same data for every comparison.** pii-roundtrip is scored on exactly the datasets on which the tool it is compared with is scored.
- **Documents:** synthetic. 200 development documents and five held-out sets. Each held-out set was generated before the engine changes it tests and frozen by hashes in `HOLDOUT.en.md`. Sets 1 and 2 (200 documents each) checked version 0.1. Set 3 (2,000 documents) checked a candidate of version 0.2: leaks of {#pii_roundtrip|ru:holdout3_ru|leak} (RU) and {#pii_roundtrip|uk:holdout3_uk|leak} (UK). Its errors were then analysed, so sets 1 to 3 are development data. Set 4 (2,000 documents), frozen before that analysis, checked version 0.2. Set 5 (2,000 documents) was generated on 19 October 2026 after the changes of version 0.3 and published with the rules before the first run; it checks version 0.3. On sets 4 and 5 each tool ran once, from committed code; the detection runs are logged in `results/holdout_runs.jsonl`, the course of the round trip on set 5 in `results/holdout5_cycle_journal.md`.
- **Recall:** a value is hidden when all of its meaningful words are masked. Service words such as "ул.", "д.", "Mr" and initials are not required.
- **Leak:** an original value remains in the cleaned text. A number is matched across any spaces, hyphens, dots and slashes, up to three in a row (dots and several separators are counted from version 0.3.1), a number in words by its spelling. A surname is matched in every case form. A first name or patronymic is matched case-sensitively and counts only if it occurs more often after masking than in the source text outside personal data (the month June is not a leak of the name June).
- **Masking precision:** the share of masked fragments that touch annotated personal data. There is no threshold. The measure shows that high recall does not come from masking everything. Annotation of the external datasets is incomplete, so precision there is understated for every tool alike.
- **Round trip:**
  - documents of held-out set 5, a summary and a reply letter for each: 190 documents per language for pii-roundtrip (380 answers per model, so that a run without errors can confirm the 99% threshold) and 20 documents per language for the other configurations (40 answers);
  - qwen3.5:9b and gemma4:12b at temperature 0;
  - placeholders issued by the tool and placeholders invented by the LLM are counted separately;
  - intervals are bootstrapped over answers.

## 4. Existing tools

The best tool for each language is chosen on the external datasets without its home dataset.

Russian, {BEST_RU}:

| Threshold | External datasets | Held-out set 5 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|ru:ext|struct+} | {=best|ru:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|ru:ext|names+} | {=best|ru:h3|names+} |
| Leaks ≤ 2% | {=best|ru:ext|leak+} | {=best|ru:h3|leak+} |
| Restoration ≥ 99% (worse model) | not measured | {~best|ru:holdout5|restore+} |

UK English, {BEST_UK}:

| Threshold | External datasets | Held-out set 5 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|uk:ext|struct+} | {=best|uk:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|uk:ext|names+} | {=best|uk:h3|names+} |
| Leaks ≤ 2% | {=best|uk:ext|leak+} | {=best|uk:h3|leak+} |
| Restoration ≥ 99% | no restore step, not met | no restore step, not met |

The restoration verdict for {BEST_RU} on set 5 is conditional. With qwen3.5:9b and pii-guard's prompt only {~pii_guard|ru:holdout5@qwen3.5:9b|answers_with_labels} of {~pii_guard|ru:holdout5@qwen3.5:9b|answers} answers contain placeholders: in the others the LLM repeated no placeholder, so there was nothing to restore. The threshold is checked on those answers, not on all 40 (correction of 22 October 2026).

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
- organisations, sole proprietors, the addressee organisation of a business letter;
- names with titles and initials, including a typo in the surname;
- an address together with its house, building, postcode and region;
- consistent placeholders across a document and a conversation: one person always gets one placeholder, different people are never merged;
- every found name propagated to all its mentions: Russian case forms, ё/е, capitals, double-barrelled surnames;
- labels ("Сторона 1", "Party A", "ОГРН", "IBAN"), bank codes and Companies House numbers are left visible;
- restoration tolerant to changes made by the LLM, with morphology for Russian names;
- an encrypted vault and offline operation.

Caveats:
- The engine's components were released by the authors of both Russian external datasets, and two changes of version 0.1 followed error analysis on these datasets. For the engine the Russian external datasets are therefore not an independent check. Held-out sets 4 and 5 are.
- The changes of version 0.2 followed error analysis on the development set and on held-out sets 1 to 3. The external datasets and sets 4 and 5 were not used for tuning detection. The change of version 0.3 (restoring a placeholder with a lost bracket or with words before the label) followed an analysis of the round-trip answers of set 4 and was tested on synthetic examples; it does not change detection. Set 4 was used for it, set 5 was not: set 5 was generated after this change and published with the rules before the first run. One caveat: I saw examples of over-masking on hivetrace before writing general filters (a number without digits, an organisation of lower-case dictionary words, a one-word lower-case "name" the dictionary does not know as a name). The filters contain no words from those examples, but precision on hivetrace can no longer be taken as fully independent.
- On short Russian messages of hivetrace the engine masks more non-personal text than pii-guard: {#pii_roundtrip|ru:ext-pii_guard|prec} of its masked fragments contain personal data, against {#best|ru:ext|prec} for pii-guard. These are errors of the GLiNER component on conversational text, which takes ordinary words and slang for personal data. On documents the engine has the highest precision among the tools that find names.
- The engine was developed on documents of the same generator as held-out set 5. The set protects against tuning to specific documents, not to the generator's style.

## 6. Documents: where the real gap is

Held-out set 5, share of documents with a leak:

{TABLE_HEADLINE}

Share of masked fragments that contain personal data, same set:

{TABLE_PRECISION}

Why the existing tools leak:
- pii-guard has no organisations;
- GLiNER misses repeated mentions: a name is masked in the header but not in the signature;
- most tools do not recognise numbers written in words, with dots or with a typo;
- the others miss a large share of names and addresses.

## 7. Conclusion

- **Existing tools.** The technical gap is confirmed for both languages (appendix of the Russian report, П5).
- **pii-roundtrip.** Verdicts on the independent held-out set 5: {ANON_PASS_SUMMARY_EN}. Leaks of {RU_LEAK_CI} (RU) and {UK_LEAK_CI} (UK) compare with {=best|ru:h3|leak} for {BEST_RU} and {=best|uk:h3|leak} for {BEST_UK} on the same documents.

## 8. Changes in version 0.2

- **Held-out sets 3 and 4.** Ten times larger than the earlier sets, so that leaks can be judged against the 2% threshold. Set 3 checked a candidate of version 0.2, set 4 checked the release. Set 5, of the same size, checks version 0.3; it was published in the public repository before the first run.
- **Comparison on the same data.** In version 0.1 a competitor was scored without its home dataset, while the engine was scored on all external datasets. Now both are scored on the same datasets.
- **Masking precision** is reported for every tool.
- **Leak metric fixed.** A name that is also an ordinary word of the text (June in a date) is no longer a leak if that word occurred in the text outside personal data. The rule is the same for every tool.
- **Round trip cache fixed.** An LLM answer is keyed by a hash of the prompt; after a change in anonymisation the answer is requested again.
- **The generator is reproducible on any day.** Details are in `HOLDOUT.en.md`.
- The fixes of version 0.1 found by two independent reviews remain: GLiNER's UK leaks had been understated by the leak detector; the finding "pii-guard fails restoration in RU" did not hold once the interval was computed over answers; "regular expressions find 100% of NHS numbers" was excluded as circular.

## 9. Limitations

- **The LLM detector** was not rerun after the method fixes and is not included.
- **promptShield** was not measured: it runs only in a browser.
- **Synthetic documents** come from this project's own generator. The competing tools have not seen them. The engine was developed on them, so the held-out sets protect only against tuning to specific documents, not to the generator's style.
- **redmadrobot** contains many numbers with an invalid checksum (218 of 223 SNILS) and numbers in words.
- **Nemotron-PII** has annotation noise (for example, "their email" annotated as an e-mail address).
- **Round trip:** 190 documents per language for pii-roundtrip and 20 for the other configurations, two local models. Larger hosted models may alter placeholders differently.

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

## 11. Additional measures after review (not pre-registered)

These measures were added on 22 October 2026 in response to the review. They were not among the rules fixed before the run, so no verdict is given on them. All are computed from the saved predictions and answers, without new LLM queries.

**Strict share of documents with a leak** (`results/strict_leaks.json`, `bench/eval/strict_leaks.py`). A document counts if at least one value of the threshold types is not fully masked: some meaningful word of it stayed visible. The pre-registered measure counts an address or an organisation only when the whole string remains; this one also counts, for example, an address with the postcode masked but the street, house and town visible. Held-out set 5, Wilson intervals; per group, the share among the documents that contain the group:

{TABLE_STRICT}

For pii-roundtrip such documents come almost entirely from addresses and organisations; there are no identifiers among them. The results file has the same figures for set 4 and the external datasets, a split by noise, and 20 examples from the UK part of set 5.

**Round trip: answers with a failure, and restoration without values leaked into the input** (`results/cycle_extras.json`, `bench/eval/cycle_extras.py`). The share of answers with at least one failed occurrence, with a Clopper-Pearson interval; restoration without the occurrences whose value was already in the cleaned text (the LLM could copy it rather than have it restored). Held-out set 5:

{TABLE_CYCLE_EXTRAS}

**Overlap of the samples.** The 20 documents per language used for the other configurations and the 190 engine documents are drawn by the same random generator; 9 of the 20 are shared in each language. The round-trip comparison of the engine with the other tools is therefore on partly different documents.

**Manual check of the failures on set 5.**
- pii-roundtrip, Russian, gemma4:12b, 8 failed occurrences. 4 are real (ru-hr-022, a noisy document): in "Большакова Милан Андреевича" the first name is not inflected; the engine masked it in full but stored the value as "Большаков Андреевич", so the first name was lost on restoration. The other 4 were restored correctly ("Третьякова Фадея Изотовича", "Третьякова Пимена Валерьяновича", "Афанасьевой Майи Ждановны") but the evaluator did not recognise them: for rare patronymics the morphology dictionary produces wrong forms. In one answer the nominative would be expected after a dash; the genitive was restored.
- pii-roundtrip, Russian, qwen3.5:9b, 10 occurrences (checked for release 0.3.0): the evaluator did not recognise correctly restored names with rare patronymics; one name was restored in the genitive after "ФИО:".
- pii-guard, ru-medical-195, 1 occurrence under its own prompt and 3 under the generic prompt (qwen3.5:9b). All are real: the source has the misspelt name "Иисдор", pii-guard stored it as "Иисдоры" and returned "Пахомова Иисдоров Герасимовича".

