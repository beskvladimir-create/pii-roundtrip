# Report: reversible anonymisation of documents for use with external LLMs (RU / UK)

Date: 13 October 2026. During the work, the engine code and the evaluation code went through two independent reviews. The errors found were fixed, and all figures were obtained after the fixes. Section 8 lists what changed compared with an interim version of this report. The complete tables in Russian are in [REPORT.md](REPORT.md).

## 1. Summary

1. **Existing open-source tools do not meet the thresholds for either language.**
   - The best tool for Russian, pii-guard, reaches 97.7% on structured identifiers against a 99% threshold.
   - The best tool for UK English, GLiNER Guard, reaches 96.4% on identifiers, with leaks in 4.0% of texts against a 2% threshold. It has no restore step of its own.
2. **All existing tools leak in documents.** On the short texts of the external datasets the best of them are almost clean. On synthetic contracts, certificates, letters, HR documents and discharge summaries, 54–100% of Russian and 57–100% of UK documents leak.
3. **pii-roundtrip is built as a layer on top of pii-guard and GLiNER Guard.** On the external datasets it meets 3 of 4 thresholds for Russian (names and addresses, leaks, restoration; undetermined: identifiers) and 4 of 4 thresholds for UK English (identifiers, names and addresses, leaks, restoration). On the held-out set with hard-to-read identifiers, 1% of Russian and 4% of UK documents leak; with 100 documents per language, neither rate is determined against the 2% threshold.
4. **Restoration fails on the placeholder format, not on detection.** qwen3.5:9b breaks the closing of pii-guard's XML tags, and pii-guard then scrubs them. Both LLMs keep plain placeholders such as `[PERSON_1]` intact 99–100% of the time.

## 2. Thresholds

| Measure | Threshold |
|---|---|
| Recall on structured identifiers: Russian passport, SNILS, INN, bank account, NHS, NI, bank card, IBAN | at least 99% |
| Recall on names, addresses, organisations | at least 95% |
| Leaks: share of texts (external datasets) or documents (synthetic) in which at least one original value remains in the cleaned text | at most 2% |
| Correct restoration after an LLM answer | at least 99% of placeholders |

- **Not met:** the upper bound of the 95% confidence interval is below the threshold.
- **Undetermined:** the interval spans the threshold.

## 3. Method

- **Tools:** pii-guard, GLiNER Guard Omni, OpenAI privacy-filter, Presidio, Prompt Anonymizer, and a baseline of regular expressions with checksums. Each is configured for its best result according to its own documentation; configurations are recorded in `results/metrics.json`. LLM Guard was excluded: its repository is archived and it has no Russian support.
- **External datasets, used for the verdict:**
  - Russian: hivetrace/pii-bench and redmadrobot pii_benchmark. Both were released by the authors of tools in the benchmark, so for the verdict no tool is evaluated on its own authors' dataset.
  - UK English: Nemotron-PII. Texts with UK markers, plus texts with injected NHS, NI and IBAN values.
- **Documents:** synthetic.
  - 200 documents for development.
  - Two held-out sets of 200 documents. Each was generated before the corresponding engine changes and frozen by hash in `HOLDOUT.md`.
  - The second held-out set contains identifiers written in words, with dots and with typos.
- **Recall:** a value counts as hidden when all of its meaningful words are masked. Service words ("ул.", "д.", "серия", "Mr") and initials are not required.
- **Leak:** an original value remains in the cleaned text.
  - Numbers are matched across any spaces and hyphens, and numbers written in words by their written form.
  - Russian surnames are matched in all grammatical cases.
  - Names are matched case-sensitively.
- **Round trip:**
  - 20 documents per language, with a summary and a reply letter for each;
  - qwen3.5:9b and gemma4:12b at temperature 0;
  - placeholders issued by the tool and placeholders invented by the LLM are counted separately;
  - intervals are bootstrapped over answers.

## 4. Existing tools

| Threshold | RU: pii-guard (hivetrace) | UK: GLiNER Guard (Nemotron) |
|---|---|---|
| Identifiers ≥ 99% | 97.7% [95.7; 98.7] **not met** | 96.4% [95.7; 97.0] **not met** |
| Names, addresses, organisations ≥ 95% | 99.5% met (the Russian external sets contain no organisations) | 98.7% met |
| Leaks ≤ 2% | 0.7% met | 4.0% [3.4; 4.8] **not met** |
| Restoration ≥ 99% (worse model) | 92.0% [79.1; 99.7] undetermined | **not met**: no restore step |

For reference:
- **UK without NHS.** Excluding NHS, GLiNER Guard reaches 98.5% on UK identifiers. The NHS numbers were injected into US-style contexts ("health plan beneficiary number"), which understates GLiNER's result.
- **Plain placeholders.** With `[TYPE_n]` placeholders, restoration is 99.9–100% for both tools.

## 5. pii-roundtrip

| Threshold | RU, external | UK, external | RU, held-out 2 | UK, held-out 2 |
|---|---|---|---|---|
| Identifiers ≥ 99% | 99.1% [98.5; 99.5] undetermined | 100.0% [99.8; 100.0] met | 100% | 100% |
| Names, addresses, organisations ≥ 95% | 98.6% [98.1; 99.0] met | 98.1% [97.7; 98.4] met | 98.8% | 96.6% |
| Leaks ≤ 2% | 0.5% [0.4; 0.8] met | 0.9% [0.6; 1.3] met | 1% [0.2; 5.4] undetermined | 4% [1.6; 9.8] undetermined |
| Restoration ≥ 99% (worse model) | 99.9% [99.7; 100.0] met | 99.6% [99.2; 99.9] met | not measured | not measured |

What the engine adds on top of its components:
- checksum rules;
- long numbers with any separators, and numbers written in words;
- organisations and sole proprietors;
- names with titles and initials;
- consistent placeholders across a document and a conversation: one person always gets one placeholder, and different people are never merged;
- propagation of a found name to every mention, covering grammatical cases, ё/е, capitals and hyphenated surnames;
- restoration that tolerates changes made by the LLM, with case inflection for Russian names;
- an encrypted vault and offline operation.

Caveats:
- **Shared authorship.** The engine's components were released by the authors of both Russian external datasets, so for Russian these datasets are partly "home" sets for it.
- **Changes made after looking at external errors.** Two changes followed an analysis of misses on the Russian external sets: the house number (hivetrace), and numbers in words and with typos (redmadrobot). The results on those datasets are therefore not an independent test. Held-out set 2, generated before these changes, is the independent test.
- **Held-out set 1** was run on the previous version of the engine, before the identifier changes. The leaks then were 1% (RU) and 3% (UK).
- **Small held-out sets.** Each holds 100 documents per language. At this size neither leak rate (1% and 4%) is determined against the 2% threshold: the intervals [0.2; 5.4] and [1.6; 9.8] span it. The held-out sets are too small for a verdict on leaks.
- **Round trip.** Restoration was measured on the development documents, not on the held-out sets.

## 6. Documents: where the real gap is

Held-out set 2, share of documents with a leak:

| Tool | Russian | UK English |
|---|---|---|
| pii-roundtrip | 1% | 4% |
| pii-guard | 54% | n/a |
| GLiNER Guard | 100% | 57% |
| Presidio | 78% | 60% |
| OpenAI privacy-filter | 92% | 86% |
| Prompt Anonymizer | n/a | 100% |

Why they leak:
- pii-guard has no organisation type;
- GLiNER misses repeated mentions: a name masked in the header stays in the signature;
- most tools do not recognise identifiers written in words, with dots or with a typo;
- the rest miss a large share of names and addresses.

## 7. Conclusion

- **Existing tools:** the technical gap is confirmed for both languages.
- **pii-roundtrip:** it closes most of the gap on documents: leaks in 1% and 4% of documents against 54–100% for existing tools. Its results against the thresholds on the external datasets are in section 5. The open questions are Russian identifiers (undetermined) and leaks in documents, which need a held-out set larger than 100 documents for a verdict.

## 8. Corrections made during the work

- **Not confirmed:** "pii-guard fails restoration in Russian (95.9%)". 19 of the 24 errors came from one answer, and placeholders within an answer are not independent. The interval over answers is [79.1; 99.7], so the result is undetermined.
- **Understated:** "GLiNER leaks in 2.5% of UK texts". The leak detector missed numbers that follow an English word. The corrected value is 4.0%.
- **Circular:** "regular expressions find 100% of NHS numbers". The numbers and the expressions came from the same generator.

## 9. Limitations

- **LLM detector.** It was not rerun after the method fixes and is not included.
- **promptShield** was not measured: it runs only in a browser.
- **Synthetic documents** come from this project's own generator. The competing tools have not seen them. The engine was developed on them, so the held-out sets protect only against tuning to specific documents, not to the generator's style.
- **redmadrobot** contains many identifiers with an invalid checksum (218 of 223 SNILS numbers) and numbers written in words.
- **Nemotron-PII** has annotation noise; for example, "their email" is labelled as an email address.
- **Round trip:** 20 documents per language and two models. With pii-guard's system prompt, qwen often avoids personal data in summaries, so pii-guard's restoration was tested mainly on reply letters.
