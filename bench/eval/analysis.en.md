# Report: reversible anonymisation of documents for use with external LLMs (RU / UK)

[Русская версия](REPORT.md)

Version 0.2, 17 October 2026. Changes since version 0.1 are described in section 8 and in [CHANGELOG.md](CHANGELOG.md).

## 1. Summary

1. **Existing open-source tools do not meet the thresholds in either language.** The best tool for Russian, {BEST_RU}: structured identifiers {=best|ru:ext|struct+} on the external datasets. The best tool for UK English, {BEST_UK}: structured identifiers {=best|uk:ext|struct+}, leaks {=best|uk:ext|leak+}; it has no restore step of its own.
2. **Every existing tool leaks on documents.** On held-out set 4 (1,000 documents per language) a leak remains in {#best|ru:h3|leak} of Russian documents with {BEST_RU} and in {#best|uk:h3|leak} of UK documents with {BEST_UK}. The other tools leak more often (section 6).
3. **pii-roundtrip, a layer over pii-guard and GLiNER Guard, meets {ANON_PASS_SUMMARY_EN} on held-out set 4.** Leaks: {RU_LEAK_CI} for Russian and {UK_LEAK_CI} for UK English.
4. **The high recall does not come from masking more text.** The share of masked fragments that contain personal data on held-out set 4 is {=pii_roundtrip|ru:h3|prec} for Russian and {=pii_roundtrip|uk:h3|prec} for UK English (section 5).
5. **Restoration fails on the placeholder format, not on detection.** The LLM breaks the closing part of pii-guard XML tags, and pii-guard scrubs such tags. Plain placeholders such as `[PERSON_1]` are kept by both LLMs (appendix of the Russian report, П3).

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

- **Tools:** pii-guard, GLiNER Guard Omni, OpenAI privacy-filter, Presidio, Prompt Anonymizer, and a baseline of regular expressions with checksums. Each is configured for its best result according to its documentation; configurations are stored in `results/metrics.json`. LLM Guard is excluded: its repository is archived and it has no Russian.
- **External datasets:**
  - RU: hivetrace/pii-bench and redmadrobot pii_benchmark. Both were released by the authors of tools in the comparison, so a tool is not scored on its authors' dataset.
  - UK: Nemotron-PII. Texts with British features, and texts with injected NHS, NI and IBAN.
- **Same data for every comparison.** pii-roundtrip is scored on exactly the datasets on which the tool it is compared with is scored.
- **Documents:** synthetic. 200 development documents and four held-out sets. Each held-out set was generated before the engine changes it tests and frozen by hashes in `HOLDOUT.en.md`. Sets 1 and 2 (200 documents each) checked version 0.1. Set 3 (2,000 documents) checked a candidate of version 0.2: leaks of {#pii_roundtrip|ru:holdout3_ru|leak} (RU) and {#pii_roundtrip|uk:holdout3_uk|leak} (UK). Its errors were then analysed, so sets 1 to 3 are development data. Set 4 (2,000 documents), frozen before that analysis, checks version 0.2. Each tool ran on it once, from committed code; the runs are logged in `results/holdout_runs.jsonl`.
- **Recall:** a value is hidden when all of its meaningful words are masked. Service words such as "ул.", "д.", "Mr" and initials are not required.
- **Leak:** an original value remains in the cleaned text. A number is matched across any spaces and hyphens, a number in words by its spelling. A surname is matched in every case form. A first name or patronymic is matched case-sensitively and counts only if it occurs more often after masking than in the source text outside personal data (the month June is not a leak of the name June).
- **Masking precision:** the share of masked fragments that touch annotated personal data. There is no threshold. The measure shows that high recall does not come from masking everything. Annotation of the external datasets is incomplete, so precision there is understated for every tool alike.
- **Round trip:**
  - 20 documents per language from held-out set 4, a summary and a reply letter for each;
  - qwen3.5:9b and gemma4:12b at temperature 0;
  - placeholders issued by the tool and placeholders invented by the LLM are counted separately;
  - intervals are bootstrapped over answers.

## 4. Existing tools

The best tool for each language is chosen on the external datasets without its home dataset.

Russian, {BEST_RU}:

| Threshold | External datasets | Held-out set 4 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|ru:ext|struct+} | {=best|ru:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|ru:ext|names+} | {=best|ru:h3|names+} |
| Leaks ≤ 2% | {=best|ru:ext|leak+} | {=best|ru:h3|leak+} |
| Restoration ≥ 99% (worse model) | not measured | {~best|ru:holdout4|restore+} |

UK English, {BEST_UK}:

| Threshold | External datasets | Held-out set 4 |
|---|---|---|
| Structured identifiers ≥ 99% | {=best|uk:ext|struct+} | {=best|uk:h3|struct+} |
| Names, addresses, organisations ≥ 95% | {=best|uk:ext|names+} | {=best|uk:h3|names+} |
| Leaks ≤ 2% | {=best|uk:ext|leak+} | {=best|uk:h3|leak+} |
| Restoration ≥ 99% | no restore step, not met | no restore step, not met |

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
- The engine's components were released by the authors of both Russian external datasets, and two changes of version 0.1 followed error analysis on these datasets. For the engine the Russian external datasets are therefore not an independent check. Held-out set 4 is.
- The changes of version 0.2 followed error analysis on the development set and on held-out sets 1 to 3. The external datasets and set 4 were not used for tuning. One caveat: I saw examples of over-masking on hivetrace before writing general filters (a number without digits, an organisation of lower-case dictionary words, a one-word lower-case "name" the dictionary does not know as a name). The filters contain no words from those examples, but precision on hivetrace can no longer be taken as fully independent.
- On short Russian messages of hivetrace the engine masks more non-personal text than pii-guard: {#pii_roundtrip|ru:ext-pii_guard|prec} of its masked fragments contain personal data, against {#best|ru:ext|prec} for pii-guard. These are errors of the GLiNER component on conversational text, which takes ordinary words and slang for personal data. On documents the engine has the highest precision among the tools that find names.
- The engine was developed on documents of the same generator as held-out set 4. The set protects against tuning to specific documents, not to the generator's style.

## 6. Documents: where the real gap is

Held-out set 4, share of documents with a leak:

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
- **pii-roundtrip.** On the independent held-out set 4 it meets {ANON_PASS_SUMMARY_EN}. Leaks of {RU_LEAK_CI} (RU) and {UK_LEAK_CI} (UK) compare with {=best|ru:h3|leak} for {BEST_RU} and {=best|uk:h3|leak} for {BEST_UK} on the same documents.

## 8. Changes in version 0.2

- **Held-out sets 3 and 4.** Ten times larger than the earlier sets, so that leaks can be judged against the 2% threshold. Set 3 checked a candidate of version 0.2, set 4 checks the release.
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
- **Round trip:** 20 documents per language, two local models. Larger hosted models may alter placeholders differently.
