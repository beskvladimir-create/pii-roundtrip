# Held-out sets

[Русская версия](HOLDOUT.md)

Two held-out sets of synthetic documents test the engine on data it did not see during development. Each was generated before the corresponding engine changes, its SHA-256 is recorded below, and it was run once.

The generator in this repository reproduces both sets byte for byte. To check:

```bash
PYTHONPATH=data uv run python -m generator.generate --seed 20261013 --out data/holdout
PYTHONPATH=data uv run python -m generator.generate --seed 20261014 --hard 0.3 --out data/holdout2
shasum -a 256 data/holdout/*.jsonl data/holdout2/*.jsonl
```

`eval/holdout.py` compares the hashes with this file before every run.

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
