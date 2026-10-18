#!/usr/bin/env bash
# Reproduces the whole benchmark with one command.
# Requirements: Python 3.12, uv, Ollama with the models qwen3.5:9b and gemma4:12b
# (ollama pull qwen3.5:9b && ollama pull gemma4:12b), about 20 GB of free disk.
# The full run takes several hours on a laptop.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --extra bench
uv run pytest -q

# synthetic documents for development and the four held-out sets (hashes in HOLDOUT.md)
uv run python -m bench.generator.generate
uv run python -m bench.generator.generate --seed 20261013 --out data/holdout
uv run python -m bench.generator.generate --seed 20261014 --hard 0.3 --out data/holdout2
uv run python -m bench.generator.generate --seed 20261016 --per-type 200 --hard 0.3 --now 2026-10-16 --out data/holdout3
uv run python -m bench.generator.generate --seed 20261018 --per-type 200 --hard 0.3 --now 2026-10-17 --out data/holdout4

# external datasets
uv run python -m bench.eval.external

TOOLS=regex_baseline,presidio,pii_guard,gliner_guard,privacy_filter,prompt_anonymizer,pii_roundtrip
uv run python -m bench.eval.run --tools "$TOOLS"
# held-out set 4 checks version 0.2 (sets 1 to 3 are development data, see HOLDOUT.md)
uv run python -m bench.eval.holdout --set 4 --tools "$TOOLS" --rerun-reason "independent reproduction"
uv run python -m bench.eval.cycle --per-type 4 --data holdout4 --tools pii_guard,pii_guard+placeholders,pii_roundtrip
uv run python -m bench.eval.report
