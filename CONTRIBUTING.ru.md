# Участие в разработке

[English version](CONTRIBUTING.md)

Задачи и запросы на слияние принимаются на русском и английском.

## Установка

```bash
uv sync                    # ядро и инструменты разработки
uv sync --extra all        # с моделями (pii-guard, GLiNER)
uv run pii-roundtrip download-models
```

## Проверки

Те же проверки запускаются в CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q              # без моделей
uv run pytest -q -m models    # с моделями в локальном кеше
```

## Правила изменений

- **Изменение поведения сопровождается тестом.** Исправление распознавания или восстановления приходит с тестом, который до исправления падает.
- **Переработка кода не меняет выход.** `uv run python -m scripts.golden save golden.json` до изменения и `uv run python -m scripts.golden check golden.json` после; проверка не должна показать расхождений.
- **Отложенные наборы не используются для разработки.** На `data/holdout*` ничего не подбирается. Прогон на отложенном наборе делается один раз на версию командой `python -m bench.eval.holdout`; см. HOLDOUT.md.
- **Числа в README и REPORT генерируются.** Правятся шаблоны в `docs/` и `bench/eval/analysis*.md`, затем запускается `python -m bench.eval.report`; числа вручную не меняются.
- **Никаких персональных данных в задачах.** Проблему воспроизводят на выдуманных именах и корректных тестовых номерах (например, `python -m bench.generator.generate`).
