# Held-out set 7: run journal

[Русская версия ниже](#журнал-прогона-на-наборе-7)

Kept during the run (HOLDOUT.en.md, set 7, plan step 4). Times are local (+04:00) and come from the logs `~/anonapp_h7_detect.log` and `~/anonapp_h7_cycle.log`, the run script `~/anonapp_h7_run.sh` (each attempt is stamped with its start, end, exit code and commit) and the answer files.

## Before the run

- Set 7 generated on 23.10.2026 at 15:24 (file times); the hashes of `data/holdout7` checked again before the start and match HOLDOUT.md.
- Engine 0.5.0, code under test in private commit 5159948; pre-registration committed in 6703b92; public pre-registration commit 13c42b8 pushed at 16:01:01 (12:01:01 UTC); the push recorded in HOLDOUT in private commit 19c6478. The trees of `pii_roundtrip` (e58cbfd6…) and `bench` (269e4e02…) are the same in 5159948, 19c6478 and the public 13c42b8.
- Ollama 0.40.4 (Homebrew `ollama serve`, started 22.10 11:12:24 with default settings, `OLLAMA_NUM_PARALLEL` 1), no model loaded before the start. The Ollama.app server (version 0.32.5) is not running. The Mac on mains power, sleep prevented (`caffeinate`).

## Course of the run

| Time | Event |
|---|---|
| 23.10 16:03:02 | Detection by all seven tools started from commit 19c6478 (`bench.eval.holdout --set 7`). |
| 23.10 16:03:04 | Engine round trip, attempt 1, started from commit 19c6478 (`bench.eval.cycle --data holdout7 --tools pii_roundtrip --per-type 38`). The hashes of `data/holdout7` matched HOLDOUT.md. A battery guard (`~/anonapp_h7_battery_guard.sh`) stops it cleanly at 10% if mains power is lost. |
| 24.10 04:57:24 | Detection by all seven tools finished; seven entries in `results/holdout_runs.jsonl` with commit 19c6478. No interruption. |
| 24.10 15:38:03 | Mains power lost (pmset log); the Mac on battery (100%). The round trip continues. Answers at that moment: Russian complete (380 and 380), UK qwen3.5:9b complete (380), UK gemma4:12b in progress. |
| 24.10 18:21:27 | Battery at 10%: the guard stopped the run script and sent SIGTERM to the round trip between two answers. The answer file is intact: 248 lines, each a complete answer (UK gemma4:12b, 248 of 380). Attempt 1 has no end line in the log because its script was stopped by the guard. To be continued by the same command when mains power is back; saved answers are reused by their cache key. |
| 24.10 18:37:28 | Mains power back at 18:37:16 (battery 3%, charging). Round trip, attempt 2, started by the same command from commit 19c6478 (`~/anonapp_h7_run.sh 2`, started automatically when mains power returned); the hashes matched again. The 248 saved answers are reused by their cache key; the model is asked from the 249th answer of UK gemma4:12b. The battery guard restarted. |
| 24.10 20:52:11 | Round trip, attempt 2, finished with exit code 0: 380 answers for each of Russian and UK English with qwen3.5:9b and gemma4:12b. No other interruption. |

---

# Журнал прогона на наборе 7

Ведётся в ходе прогона (HOLDOUT.md, набор 7, пункт 4 плана). Время местное (+04:00), источники: логи `~/anonapp_h7_detect.log` и `~/anonapp_h7_cycle.log`, скрипт прогона `~/anonapp_h7_run.sh` (у каждой попытки записаны начало, конец, код выхода и коммит) и файлы ответов.

## До прогона

- Набор 7 сгенерирован 23.10.2026 в 15:24 (время файлов); хеши `data/holdout7` перед началом проверены ещё раз и совпадают с HOLDOUT.md.
- Движок 0.5.0, код под проверкой в закрытом коммите 5159948; предрегистрация в коммите 6703b92; открытый коммит предрегистрации 13c42b8 отправлен в 16:01:01 (12:01:01 UTC); отправка записана в HOLDOUT в закрытом коммите 19c6478. Деревья `pii_roundtrip` (e58cbfd6…) и `bench` (269e4e02…) одинаковы в 5159948, 19c6478 и открытом 13c42b8.
- Ollama 0.40.4 (`ollama serve` из Homebrew, запущен 22.10 в 11:12:24 с настройками по умолчанию, `OLLAMA_NUM_PARALLEL` 1), до начала ни одна модель не загружена. Сервер приложения Ollama.app (версия 0.32.5) не запущен. Mac от сети, сон запрещён (`caffeinate`).

## Ход прогона

| Время | Событие |
|---|---|
| 23.10 16:03:02 | Обнаружение всеми семью инструментами запущено с коммита 19c6478 (`bench.eval.holdout --set 7`). |
| 23.10 16:03:04 | Полный цикл движка, попытка 1, запущен с коммита 19c6478 (`bench.eval.cycle --data holdout7 --tools pii_roundtrip --per-type 38`). Хеши `data/holdout7` совпали с HOLDOUT.md. Страж батареи (`~/anonapp_h7_battery_guard.sh`) аккуратно останавливает его при 10%, если пропадёт сеть. |
| 24.10 04:57:24 | Обнаружение всеми семью инструментами закончено; семь записей в `results/holdout_runs.jsonl` с коммитом 19c6478. Перерывов не было. |
| 24.10 15:38:03 | Пропало питание от сети (журнал pmset); Mac на батарее (100%). Полный цикл продолжается. Ответов на этот момент: русский готов (380 и 380), британский qwen3.5:9b готов (380), британский gemma4:12b идёт. |
| 24.10 18:21:27 | Батарея 10%: страж остановил скрипт прогона и отправил SIGTERM полному циклу между двумя ответами. Файл ответов цел: 248 строк, каждая полный ответ (британский gemma4:12b, 248 из 380). У попытки 1 нет строки конца в логе, потому что её скрипт остановил страж. Продолжение той же командой после возвращения сети; сохранённые ответы берутся по ключу кеша. |
| 24.10 18:37:28 | Сеть вернулась в 18:37:16 (батарея 3%, заряжается). Полный цикл, попытка 2, запущен той же командой с коммита 19c6478 (`~/anonapp_h7_run.sh 2`, запуск автоматически при появлении сети); хеши снова совпали. 248 сохранённых ответов берутся по ключу кеша; модель спрашивается с 249-го ответа британского gemma4:12b. Страж батареи перезапущен. |
| 24.10 20:52:11 | Полный цикл, попытка 2, закончен с кодом 0: по 380 ответов для русского и британского английского с qwen3.5:9b и gemma4:12b. Других перерывов не было. |
