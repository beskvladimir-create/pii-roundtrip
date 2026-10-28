# English translation of the remaining Russian comments

The files below are part of the version hash of the benchmark: `bench/eval/run.py` (`code_version`) hashes their exact bytes and stores the hash with every released prediction (field `v` in `results/<tool>/*.jsonl`). Changing even a comment in them would mark all released predictions as stale and force the tools to be re-run, including on held-out sets that by the project's rules are run only once. Their Russian comments and docstrings are therefore left unchanged in the code, and their English translation is given here, by file and line.

## `bench/runners/base.py`

Line 1:

```text
"""Единый интерфейс инструментов.
```
English:

```text
"""Common interface for the tools.
```

Line 3:

```text
Каждый раннер умеет detect(); обратимые инструменты дополнительно реализуют
anonymize() и deanonymize() своими средствами. Для инструментов, которые только
распознают, полный цикл идёт через общую подстановку меток (bench/runners/placeholders.py),
это фиксируется в отчёте.
```
English:

```text
Every runner implements detect(); reversible tools additionally implement
anonymize() and deanonymize() with their own means. For tools that only
detect, the full cycle goes through the shared placeholder substitution
(bench/runners/placeholders.py), and this is recorded in the report.
```

Line 13:

```text
# Единая схема типов (совпадает с генератором и bench/eval/external.py).
```
English:

```text
# Single type schema (matches the generator and bench/eval/external.py).
```

Line 48:

```text
        """Конфигурация запуска для отчёта."""
```
English:

```text
        """Run configuration for the report."""
```

Line 62:

```text
    """Для каждой позиции src (включая len(src)) ближайшая позиция в dst.
```
English:

```text
    """For each position in src (including len(src)), the nearest position in dst.
```

Line 64:

```text
    Нужна инструментам, которые возвращают спаны по нормализованному тексту.
```
English:

```text
    Needed for tools that return spans over normalised text.
```

Line 73:

```text
            else:  # пропорционально внутри изменённого участка
```
English:

```text
            else:  # proportionally within the changed segment
```

Line 92:

```text
    """Объединяет пересекающиеся спаны (тип берётся у более длинного), чтобы ничего
    не потерять при маскировке. Если передан текст, спан, обрывающийся посреди
    слова, расширяется до границ слова: одинаково для всех инструментов."""
```
English:

```text
    """Merges overlapping spans (the type is taken from the longer one) so that nothing
    is lost during masking. If text is given, a span that ends in the middle of a
    word is extended to the word boundaries, identically for all tools."""
```

## `bench/runners/chunking.py`

Line 1:

```text
"""Нарезка длинных документов для моделей с ограниченным окном."""
```
English:

```text
"""Splitting of long documents for models with a limited context window."""
```

Line 7:

```text
    """Окна до size символов с перекрытием, границы по переводу строки или пробелу."""
```
English:

```text
    """Overlapping windows of up to size characters, split at a newline or a space."""
```

## `bench/runners/gliner_guard_runner.py`

Line 1:

```text
"""hivetrace/gliner-guard-omni (GLiNER2, multilingual deberta v3): полная PII таксономия
из карточки модели (32 метки), порог 0.4 как в примере карточки. Длинные документы
режутся на окна с перекрытием."""
```
English:

```text
"""hivetrace/gliner-guard-omni (GLiNER2, multilingual deberta v3): the full PII taxonomy
from the model card (32 labels), threshold 0.4 as in the model card example. Long documents
are split into overlapping windows."""
```

## `bench/runners/llm_detector.py`

Line 1:

```text
"""Локальная нейросеть как детектор (Ollama, температура 0, без режима размышлений).
```
English:

```text
"""A local neural model as a detector (Ollama, temperature 0, no thinking mode).
```

Line 3:

```text
Модель возвращает JSON со списком найденных значений и типов; значения ищутся
в тексте (все вхождения). Длинные документы режутся на окна.
```
English:

```text
The model returns JSON with a list of the values and types it found; the values are
searched for in the text (all occurrences). Long documents are split into windows.
```

## `bench/runners/pii_guard_runner.py`

Line 1:

```text
"""redmadrobot pii-guard: правила с контрольными суммами + ruBERT, обратимый режим
pseudonymize с восстановлением в нужном падеже. Только русский.
```
English:

```text
"""redmadrobot pii-guard: checksum rules + ruBERT, reversible pseudonymize mode
with restoration in the required grammatical case. Russian only.
```

Line 4:

```text
Спаны pii-guard указывают на нормализованный текст; они переносятся на исходный
выравниванием строк (runners.base.map_spans).
```
English:

```text
pii-guard spans point into the normalised text; they are carried over to the original
by string alignment (runners.base.map_spans).
```

Line 38:

```text
        # настройки передаются явно, без переменных окружения; модель из локального кеша
```
English:

```text
        # settings are passed explicitly, not via environment variables; model from local cache
```

## `bench/runners/pii_roundtrip_runner.py`

Line 1:

```text
"""Движок pii-roundtrip через тот же интерфейс, что и остальные инструменты."""
```
English:

```text
"""The pii-roundtrip engine through the same interface as the other tools."""
```

Line 9:

```text
    """В данных бенчмарка британский английский помечен как "uk"; библиотека ждёт "en-GB"."""
```
English:

```text
    """In the benchmark data British English is tagged "uk"; the library expects "en-GB"."""
```

## `bench/runners/presidio_runner.py`

Line 1:

```text
"""Presidio (data-privacy-stack/presidio), лучшая конфигурация по документации.

RU: spaCy ru_core_news_lg + собственные распознаватели паспорта, СНИЛС, ИНН,
расчётного счёта (Presidio не содержит русских распознавателей), встроенные
email, карта, IBAN, телефон с языком ru.
UK: spaCy en_core_web_lg + встроенные UK_NHS, UK_NINO, IBAN, карта, email,
телефон с supported_regions=["GB"] (обход ошибки с регионом "UK").
Порог уверенности низкий: полнота важнее точности.
```
English:

```text
"""Presidio (data-privacy-stack/presidio), the best configuration per the documentation.

RU: spaCy ru_core_news_lg + custom recognizers for passport, SNILS, INN and
settlement account (Presidio has no Russian recognizers), built-in
email, card, IBAN, phone with language ru.
UK: spaCy en_core_web_lg + built-in UK_NHS, UK_NINO, IBAN, card, email,
phone with supported_regions=["GB"] (works around the bug with region "UK").
The confidence threshold is low: recall matters more than precision.
```

Line 128:

```text
        # телефон: регион GB вместо ошибочного "UK"
```
English:

```text
        # phone: region GB instead of the erroneous "UK"
```

Line 131:

```text
        # UK распознаватели, которые не входят в набор по умолчанию
```
English:

```text
        # UK recognizers that are not in the default set
```

## `bench/runners/privacy_filter_runner.py`

Line 1:

```text
"""openai/privacy-filter через официальный пакет opf: декодирование Витерби,
контекст до 128 тыс. токенов (без нарезки). 8 категорий, типа «организация» нет."""
```
English:

```text
"""openai/privacy-filter via the official opf package: Viterbi decoding,
context up to 128k tokens (no chunking). 8 categories, no "organisation" type."""
```

## `bench/runners/prompt_anonymizer_runner.py`

Line 1:

```text
"""Prompt Anonymizer (akazah, Python 0.3.3): Presidio + spaCy, обратимые метки вида
<Name_1>. Русского нет, только UK. Лучшая документированная конфигурация:
model_size="lg", все типы по умолчанию плюс опциональный IBAN_CODE. Британских
номеров (NHS, NI) и организаций в нём нет."""
```
English:

```text
"""Prompt Anonymizer (akazah, Python 0.3.3): Presidio + spaCy, reversible placeholders of
the form <Name_1>. No Russian, UK only. Best documented configuration:
model_size="lg", all default types plus the optional IBAN_CODE. It has no British
identifiers (NHS, NI) and no organisations."""
```

## `bench/runners/regex_baseline.py`

Line 1:

```text
"""Базовая линия: регулярные выражения с проверкой контрольных сумм, без моделей."""
```
English:

```text
"""Baseline: regular expressions with checksum validation, no models."""
```

Line 10:

```text
D = r"(?<![\d])"  # слева не цифра
E = r"(?![\d])"  # справа не цифра
```
English:

```text
D = r"(?<![\d])"  # not a digit on the left
E = r"(?![\d])"  # not a digit on the right
```

Line 63:

```text
                    # 10 цифр бывают и ИНН, и паспортом; решает контекст слева
```
English:

```text
                    # 10 digits can be either an INN or a passport; the left context decides
```

## `bench/eval/run.py`

Line 1:

```text
"""Запуск инструментов на наборах и подсчёт метрик распознавания и утечек.

python -m bench.eval.run --tools regex_baseline,presidio --datasets all
Предсказания кешируются в results/<tool>/<dataset>.jsonl.
"""
```
English:

```text
"""Running the tools on the datasets and computing detection and leak metrics.

python -m bench.eval.run --tools regex_baseline,presidio --datasets all
Predictions are cached in results/<tool>/<dataset>.jsonl.
"""
```

Line 49:

```text
"""Загружает модель, только если предсказаний нет в кеше."""
```
English:

```text
"""Loads the model only if the predictions are not in the cache."""
```

Line 74:

```text
# Код, от которого зависят предсказания каждого инструмента: при его изменении кеш сбрасывается.
```
English:

```text
# Code that each tool's predictions depend on: when it changes, the cache is reset.
```

Line 101:

```text
"""Одинаково для всех: объединение пересечений и расширение до границ слова."""
```
English:

```text
"""The same for every tool: merging overlapping spans and extending them to word boundaries."""
```

Line 118:

```text
# продолжение с места остановки
```
English:

```text
# resume from where it stopped
```

Line 128:

```text
f"  {name} / {ds}: {len(docs)} текстов за {time.time() - t0:.0f} с"  (console message)
```
English:

```text
f"  {name} / {ds}: {len(docs)} texts in {time.time() - t0:.0f} s"
```

Line 156:

```text
help="случайная выборка N текстов из внешних наборов (seed 0)"  (option --sample)
```
English:

```text
help="random sample of N texts from the external datasets (seed 0)"
```

Line 182:

```text
номера … имена/адреса/орг … утечки  (column labels of the console summary)
```
English:

```text
numbers … names/addresses/organisations … leaks
```

Line 185:

```text
# слияние с тем, что успели записать параллельные запуски
```
English:

```text
# merge with what parallel runs have managed to write
```

## Notes written into `results/metrics.json`

These strings in the hashed runner files are copied into the `_config` entries of `results/metrics.json`.

Line 52 of `bench/runners/pii_guard_runner.py`:

```text
"note": "нет типа ORG; спаны перенесены с normalized_text на исходный текст"
```
English:

```text
"note": "no ORG type; spans carried over from normalized_text to the source text"
```

Line 35 of `bench/runners/privacy_filter_runner.py`:

```text
"note": "нет типа ORG; account_number засчитывается для IBAN, карт, счетов в режиме masked"
```
English:

```text
"note": "no ORG type; account_number counts for IBAN, cards and accounts in masked mode"
```

Line 32 of `bench/runners/pii_roundtrip_runner.py`:

```text
"labels": "[TYPE_n], согласованные по документу"
```
English:

```text
"labels": "[TYPE_n], consistent within a document"
```

Line 33 of `bench/runners/pii_roundtrip_runner.py`:

```text
"note": "компоненты pii-guard и GLiNER Guard выпущены авторами обоих русских внешних наборов"
```
English:

```text
"note": "the pii-guard and GLiNER Guard components were released by the authors of both Russian external datasets"
```

## Other Russian label in released results

`restore_ci_method` in `results/cycle_metrics.*.json` (written by `bench/eval/cycle.py`): "bootstrap по ответам, 2000 повторов" means "bootstrap over answers, 2,000 resamples". It is kept unchanged in the code so that regenerated results stay identical to the released ones.
