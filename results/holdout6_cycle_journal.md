# Held-out set 6: run journal

[Русская версия ниже](#журнал-прогона-на-наборе-6)

Kept during the run (HOLDOUT.en.md, set 6, plan step 5). Times are local (+04:00) and come from the logs `~/anonapp_h6_detect.log` and `~/anonapp_h6_cycle.log`, the run script `~/anonapp_h6_run.sh` (each attempt is stamped with its start, end, exit code and commit) and the answer files.

## Before the run

- Set 6 generated on 22.10.2026 at 11:21:36 (file times), regeneration checked to give the same hashes.
- Engine 0.4.0, private commit 2e33854; pre-registration committed in 328a821; public pre-registration commit 444c4bd pushed at 11:57:47 (07:57:47 UTC); the push recorded in HOLDOUT in private commit 21ebb9d. The trees of `pii_roundtrip` (6be0f189…) and `bench` (8e81c328…) are the same in 2e33854, 328a821, 21ebb9d and the public 444c4bd.
- Ollama 0.40.4 (Homebrew `ollama serve`, started 11:12:24 with default settings, `OLLAMA_NUM_PARALLEL` 1), no model loaded before the start. The Ollama.app server (version 0.32.5) is not running.

## Course of the run

| Time | Event |
|---|---|
| 22.10 11:58:33 | Detection by all seven tools started from commit 21ebb9d (`bench.eval.holdout --set 6`). |
| 22.10 11:58:36 | Engine round trip, attempt 1, started from commit 21ebb9d (`bench.eval.cycle --data holdout6 --tools pii_roundtrip --per-type 38`). The hashes of `data/holdout6` matched HOLDOUT.md. |
| 22.10 18:23:00 | Mains power cut; the Mac on battery (46%). Detection paused (SIGSTOP of its process, pid 74958, to be continued with SIGCONT; the process keeps its state, nothing is rerun). The round trip continues; a battery guard (`~/anonapp_h6_battery_guard.sh`) stops it cleanly at 10% so that it can be continued by the same command. Answers at that moment: Russian qwen3.5:9b 255 of 380. |
| 22.10 19:14:06–19:14:36 | Battery at 10%: the guard stopped the run script; its interrupt reached the `uv` wrapper but not the Python process, which was then stopped by hand (SIGTERM) at 19:14:36, between two answers. The answer file is intact: 317 lines, each a complete answer (Russian qwen3.5:9b, 317 of 380). Detection stays paused. |
| 22.10 19:26 | Mains power back (battery 8%, charging). Detection continued at 19:26:17 (SIGCONT, the same process). Round trip, attempt 2, started at 19:26:18 by the same command from commit 21ebb9d; the hashes matched again. The 317 saved answers are reused by their cache key; the model is asked from the 318th answer of Russian qwen3.5:9b. Attempt 1 has no end line in the log because its script was stopped by the guard. |
| 22.10 22:21:52 | Detection by all seven tools finished; seven entries in `results/holdout_runs.jsonl` with commit 21ebb9d. The pause from 18:23:00 to 19:26:17 did not restart any tool. |
| 23.10 12:24:26 | Round trip, attempt 2, finished with exit code 0: 380 answers for each of Russian and UK English with qwen3.5:9b and gemma4:12b. No other interruption. |

---

# Журнал прогона на наборе 6

Ведётся в ходе прогона (HOLDOUT.md, набор 6, пункт 5 плана). Время местное (+04:00), источники: логи `~/anonapp_h6_detect.log` и `~/anonapp_h6_cycle.log`, скрипт прогона `~/anonapp_h6_run.sh` (у каждой попытки записаны начало, конец, код выхода и коммит) и файлы ответов.

## До прогона

- Набор 6 сгенерирован 22.10.2026 в 11:21:36 (время файлов), повторная генерация даёт те же хеши.
- Движок 0.4.0, закрытый коммит 2e33854; предрегистрация в коммите 328a821; открытый коммит предрегистрации 444c4bd отправлен в 11:57:47 (07:57:47 UTC); отправка записана в HOLDOUT в закрытом коммите 21ebb9d. Деревья `pii_roundtrip` (6be0f189…) и `bench` (8e81c328…) одинаковы в 2e33854, 328a821, 21ebb9d и открытом 444c4bd.
- Ollama 0.40.4 (`ollama serve` из Homebrew, запущен в 11:12:24 с настройками по умолчанию, `OLLAMA_NUM_PARALLEL` 1), до начала ни одна модель не загружена. Сервер приложения Ollama.app (версия 0.32.5) не запущен.

## Ход прогона

| Время | Событие |
|---|---|
| 22.10 11:58:33 | Распознавание всеми семью инструментами запущено с коммита 21ebb9d (`bench.eval.holdout --set 6`). |
| 22.10 11:58:36 | Полный цикл движка, попытка 1, запущен с коммита 21ebb9d (`bench.eval.cycle --data holdout6 --tools pii_roundtrip --per-type 38`). Хеши `data/holdout6` совпали с HOLDOUT.md. |
| 22.10 18:23:00 | Отключили электричество, Mac работает от батареи (46%). Распознавание поставлено на паузу (SIGSTOP процесса, pid 74958, продолжение через SIGCONT; процесс сохраняет состояние, ничего не перезапускается). Полный цикл продолжается; страж батареи (`~/anonapp_h6_battery_guard.sh`) аккуратно остановит его при 10%, чтобы продолжить той же командой. Ответов к этому моменту: русский qwen3.5:9b, 255 из 380. |
| 22.10 19:14:06–19:14:36 | Батарея 10%: страж остановил скрипт прогона; его прерывание дошло до обёртки `uv`, но не до процесса Python, который затем остановлен вручную (SIGTERM) в 19:14:36, между двумя ответами. Файл ответов цел: 317 строк, каждая полный ответ (русский qwen3.5:9b, 317 из 380). Распознавание остаётся на паузе. |
| 22.10 19:26 | Электричество вернулось (батарея 8%, заряжается). Распознавание продолжено в 19:26:17 (SIGCONT, тот же процесс). Полный цикл, попытка 2, запущен в 19:26:18 той же командой с коммита 21ebb9d; хеши снова совпали. 317 сохранённых ответов берутся по ключу кеша; нейросеть спрашивается с 318-го ответа русского qwen3.5:9b. У попытки 1 нет строки окончания в логе, потому что её скрипт остановил страж. |
| 22.10 22:21:52 | Распознавание всеми семью инструментами завершено; семь записей в `results/holdout_runs.jsonl` с коммитом 21ebb9d. Пауза с 18:23:00 до 19:26:17 ни один инструмент не перезапускала. |
| 23.10 12:24:26 | Полный цикл, попытка 2, завершён с кодом 0: по 380 ответов для русского и британского английского с qwen3.5:9b и gemma4:12b. Других остановок не было. |
