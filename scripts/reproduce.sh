#!/usr/bin/env bash
# Reproduces the whole benchmark with one command.
# Requirements: Python 3.12, uv, Ollama with the models qwen3.5:9b and gemma4:12b
# (ollama pull qwen3.5:9b && ollama pull gemma4:12b), about 20 GB of free disk.
# The full run takes several hours on a laptop.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --extra bench
uv run pytest -q

# synthetic documents for development and the two held-out sets (hashes in HOLDOUT.md)
PYTHONPATH=data uv run python -m generator.generate
PYTHONPATH=data uv run python -m generator.generate --seed 20261013 --out data/holdout
PYTHONPATH=data uv run python -m generator.generate --seed 20261014 --hard 0.3 --out data/holdout2

# external datasets
uv run python -m eval.external

TOOLS=regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip
uv run python -m eval.run --tools "$TOOLS"
uv run python -m eval.holdout --tools "$TOOLS"
uv run python -m eval.holdout --set2 --tools "$TOOLS"
uv run python -m eval.cycle --per-type 4
uv run python -m eval.report
