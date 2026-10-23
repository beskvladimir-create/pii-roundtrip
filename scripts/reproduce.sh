#!/usr/bin/env bash
# Reproduces the whole benchmark with one command.
# Requirements: Python 3.12, uv, Ollama with the models qwen3.5:9b and gemma4:12b
# (ollama pull qwen3.5:9b && ollama pull gemma4:12b), about 20 GB of free disk.
# The full run takes several hours on a laptop.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --extra bench
uv run pytest -q

# synthetic documents for development and the six held-out sets (hashes in HOLDOUT.md; the files of
# every set are also in the repository, so regenerating them is only a check)
uv run python -m bench.generator.generate
uv run python -m bench.generator.generate --seed 20261013 --out data/holdout
uv run python -m bench.generator.generate --seed 20261014 --hard 0.3 --out data/holdout2
uv run python -m bench.generator.generate --seed 20261016 --per-type 200 --hard 0.3 --now 2026-10-16 --out data/holdout3
uv run python -m bench.generator.generate --seed 20261018 --per-type 200 --hard 0.3 --now 2026-10-17 --out data/holdout4
uv run python -m bench.generator.generate --seed 20261020 --per-type 200 --hard 0.3 --now 2026-10-19 --out data/holdout5
uv run python -m bench.generator.generate --seed 20261022 --per-type 200 --hard 0.3 --now 2026-10-22 --out data/holdout6
shasum -a 256 data/holdout*/*.jsonl  # compare with HOLDOUT.md

# external datasets
uv run python -m bench.eval.external

TOOLS=regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip
uv run python -m bench.eval.run --tools "$TOOLS"
# held-out set 6 checks version 0.4 (sets 1 to 5 are development data, see HOLDOUT.md); the
# round trip needs Ollama with qwen3.5:9b and gemma4:12b and takes about a day
uv run python -m bench.eval.holdout --set 6 --tools "$TOOLS" --rerun-reason "independent reproduction"
uv run python -m bench.eval.cycle --per-type 38 --data holdout6 --tools pii_roundtrip
uv run python -m bench.eval.report
