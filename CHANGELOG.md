# Changelog

[Русская версия](CHANGELOG.ru.md)

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

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

Detection (found on the development data: the synthetic set and held-out sets 1 and 2, which became development data for 0.2; external datasets and held-out set 3 were not used for tuning):

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

First public release: the engine, the benchmark of existing tools on Russian and UK English documents, the report and the preprint.

[0.2.0]: https://github.com/beskvladimir-create/pii-roundtrip/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/beskvladimir-create/pii-roundtrip/releases/tag/v0.1.0
