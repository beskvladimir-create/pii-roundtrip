# Contributing

[Русская версия](CONTRIBUTING.ru.md)

Issues and pull requests are welcome. Please write in Russian or English.

## Setup

```bash
uv sync                    # the core and the dev tools
uv sync --extra all        # with the models (pii-guard, GLiNER)
uv run pii-roundtrip download-models
```

## Checks

The same checks run in CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q              # without models
uv run pytest -q -m models    # with the models in the local cache
```

## Rules for changes

- **Behaviour changes need a test.** A fix to detection or restoration comes with a test that fails before the fix.
- **Refactoring must not change output.** `uv run python -m scripts.golden save golden.json` before and `uv run python -m scripts.golden check golden.json` after the change; the check must show no differences.
- **Held-out sets are not for development.** Do not tune on `data/holdout*`. A held-out run is made once per version with `python -m bench.eval.holdout`; see HOLDOUT.md.
- **Numbers in README and REPORT are generated.** Edit the templates in `docs/` and `bench/eval/analysis*.md`, then run `python -m bench.eval.report`; do not edit the numbers by hand.
- **No personal data in issues.** Reproduce a problem with invented names and valid test identifiers (for example `python -m bench.generator.generate`).
