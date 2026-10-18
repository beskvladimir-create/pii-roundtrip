# Held-out sets

[Русская версия](HOLDOUT.md)

Four held-out sets of synthetic documents test the engine on data it did not see during development. Each was generated before the corresponding engine changes, its SHA-256 is recorded below, and it was run once.

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
