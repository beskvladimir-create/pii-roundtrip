# Held-out set 5: round-trip run journal

[Русская версия ниже](#журнал-полного-цикла-на-наборе-5)

Written on 22.10.2026, after the run, from the files only: the run logs, the creation and modification times of the answer files, `results/holdout_runs.jsonl` and the git history. Times are local (+04:00). Nothing here is from memory.

## Code and environment

- Code: private commit 831593c (19.10.2026 21:48). The next commit, 10fb55b, came after the run (22.10.2026 00:55), so all answers were requested with 831593c checked out. Its public counterpart is the pre-registration commit 8b8e933 (19.10.2026 21:49).
- Data: `data/holdout5/ru.jsonl` and `uk.jsonl`, created 19.10.2026 21:47. Every command checked their SHA-256 against HOLDOUT.md before starting ("Хеши data/holdout5 совпадают с HOLDOUT.md" in each log).
- Python environment: the private `uv.lock` (SHA-256 starts with 7ca62d385d72), transformers 5.19.0, torch 2.14.1. This lock file is the same at 585c4a8 (the set 4 runs) and at 831593c (the set 5 runs).
- Models: Ollama 0.40.4, qwen3.5:9b (digest 56671c2a…) and gemma4:12b (digest 6114515d…), temperature 0, seed 0 (`results/ollama_versions.txt`, recorded 19.10.2026).

## Timeline

| Time | Event | Source |
|---|---|---|
| 20.10 12:33 | Both commands of the plan started in one shell: first the engine (`--tools pii_roundtrip --per-type 38`), then the other configurations (`--per-type 4 …`), output to `~/anonapp_h5_cycle.log`. Detection on set 5 started at the same time, in a separate process. | session transcript; creation of `pii_roundtrip/ru_qwen3.5_9b.jsonl` at 12:33:47 |
| 20.10 22:28 | Engine, RU, qwen3.5:9b: 380 answers. RU gemma4:12b begins. | modification of `ru_qwen3.5_9b.jsonl` 22:28:35, creation of `ru_gemma4_12b.jsonl` 22:28:36 |
| 20.10 23:24 | Detection on set 5 finished for all seven tools; entries written to `results/holdout_runs.jsonl` with commit 831593c. | `holdout_runs.jsonl` (19:24:12 UTC), `~/anonapp_h5_detect.log` |
| 21.10 00:01 | Last answer saved for engine RU gemma4:12b: the 71st. The request for the 72nd ended with `http.client.RemoteDisconnected` (Ollama closed the connection); the engine command exited with code 1. | `ru_gemma4_12b.jsonl` had 71 lines, last modified 00:01 (checked 21.10 06:11); `engine cycle exit=1` in the log |
| 21.10 00:03 | The second command of the plan (other configurations) started as scheduled. | creation of `pii_guard/ru_qwen3.5_9b.jsonl` 00:03:13 |
| 21.10 06:11 | Resume script `~/anonapp_h5_resume.sh` written: it waits for the running command, then repeats both commands of the plan unchanged. Saved answers are reused by their cache key (document, task, hash of the prompt); a model is asked only for answers not yet saved. | file time of the script |
| 21.10 09:41 | Other configurations finished: 14 files of 40 answers. | last modification 09:41:21, `competitors cycle exit=0` |
| 21.10 09:41 | Resume: the command for the other configurations found every answer saved and asked nothing; the engine command reused RU qwen (380) and the first 71 RU gemma answers and continued from the 72nd. | `ok: --per-type 4 …` in `~/anonapp_h5_resume.log` |
| 21.10 14:31 | Engine RU gemma4:12b: 380 answers. | modification 14:31:17 |
| 21.10 19:23 | Engine UK qwen3.5:9b: 380 answers. | creation 14:31:20, modification 19:23:44 |
| 22.10 00:27 | Engine UK gemma4:12b: 380 answers. Script finished. | modification 00:27:43, `all done Thu Oct 22 00:27:52` |
| 22.10 00:55 | Results committed (private 10fb55b), published as v0.3.0. | git history |

## Answer counts

| Configuration | Answers per model and language | Duplicate keys |
|---|---|---|
| pii_roundtrip (RU, UK) | 380 (190 documents × 2 tasks) | 0 |
| each of the 7 other configurations | 40 (20 documents × 2 tasks) | 0 |

Each answer file has exactly one line per (document, task, prompt hash): no answer was requested twice, and none is missing.

> Clarification of 22 October 2026: each answer was requested from a model once. On the resumption the command for the other configurations was started a second time, found every answer saved and made no new request.

> Addition of 22 October 2026: the cause of the interruption is established from the session logs of this machine. Another Claude Code session, working on a different project (nl2sql-onprem-bench) on the same Ollama server, ran `ollama stop gemma4:12b` at 23:58:06 on 20.10, `pkill -f 'ollama serve'` at 00:03:00 on 21.10 and then started `ollama serve` again (the same Homebrew binary, 0.40.4); from 23:57 it also sent its own requests to other models on that server. The kill closed the connection during the 72nd answer. Answers up to the 71st of Russian gemma4:12b were therefore produced while the other session was using the server; at temperature 0 and seed 0 this is not expected to change an answer, but it was not checked by asking again.

## Deviations from the plan in HOLDOUT.md

- One interruption (above). The resumed commands were the same as in the plan; no code, data or model changed between the interruption and the resumption.
- Rule 5 of the plan names `results/holdout_runs.jsonl` for any repeated run. That log records detection runs only; the round-trip commands do not write to it. The resumption is therefore recorded here and in the CHANGELOG, not in that log.
- A note about the interruption was appended to `~/anonapp_h5_cycle.log` at 06:11 but does not survive: the still running command opened the log with `>` and overwrote it. This journal replaces that note.

---

# Журнал полного цикла на наборе 5

Составлен 22.10.2026 после прогона только по файлам: логам прогона, временам создания и изменения файлов ответов, `results/holdout_runs.jsonl` и истории git. Время местное (+04:00). По памяти здесь ничего не написано.

## Код и окружение

- Код: закрытый коммит 831593c (19.10.2026 21:48). Следующий коммит 10fb55b сделан после прогона (22.10.2026 00:55), поэтому все ответы запрошены на 831593c. Ему соответствует открытый коммит предрегистрации 8b8e933 (19.10.2026 21:49).
- Данные: `data/holdout5/ru.jsonl` и `uk.jsonl`, созданы 19.10.2026 в 21:47. Каждая команда перед запуском сверяла их SHA-256 с HOLDOUT.md (строка «Хеши data/holdout5 совпадают с HOLDOUT.md» в каждом логе).
- Окружение Python: закрытый `uv.lock` (SHA-256 начинается с 7ca62d385d72), transformers 5.19.0, torch 2.14.1. Этот lock-файл одинаков на 585c4a8 (прогоны набора 4) и на 831593c (прогоны набора 5).
- Нейросети: Ollama 0.40.4, qwen3.5:9b (digest 56671c2a…) и gemma4:12b (digest 6114515d…), температура 0, зерно 0 (`results/ollama_versions.txt`, записан 19.10.2026).

## Ход прогона

| Время | Событие | Источник |
|---|---|---|
| 20.10 12:33 | Обе команды плана запущены в одной оболочке: сначала движок (`--tools pii_roundtrip --per-type 38`), затем остальные конфигурации (`--per-type 4 …`), вывод в `~/anonapp_h5_cycle.log`. В то же время отдельным процессом запущено распознавание на наборе 5. | запись сессии; создание `pii_roundtrip/ru_qwen3.5_9b.jsonl` в 12:33:47 |
| 20.10 22:28 | Движок, RU, qwen3.5:9b: 380 ответов. Начат RU gemma4:12b. | изменение `ru_qwen3.5_9b.jsonl` 22:28:35, создание `ru_gemma4_12b.jsonl` 22:28:36 |
| 20.10 23:24 | Распознавание на наборе 5 завершено для всех семи инструментов, записи в `results/holdout_runs.jsonl` с коммитом 831593c. | `holdout_runs.jsonl` (19:24:12 UTC), `~/anonapp_h5_detect.log` |
| 21.10 00:01 | Последний сохранённый ответ движка RU gemma4:12b: 71-й. Запрос 72-го завершился ошибкой `http.client.RemoteDisconnected` (Ollama закрыл соединение), команда движка вышла с кодом 1. | в `ru_gemma4_12b.jsonl` 71 строка, последнее изменение 00:01 (проверено 21.10 в 06:11); `engine cycle exit=1` в логе |
| 21.10 00:03 | По плану запустилась вторая команда (остальные конфигурации). | создание `pii_guard/ru_qwen3.5_9b.jsonl` 00:03:13 |
| 21.10 06:11 | Записан скрипт продолжения `~/anonapp_h5_resume.sh`: ждёт завершения идущей команды и повторяет обе команды плана без изменений. Сохранённые ответы берутся по ключу кеша (документ, задание, хеш запроса); нейросеть спрашивается только о несохранённых. | время файла скрипта |
| 21.10 09:41 | Остальные конфигурации завершены: 14 файлов по 40 ответов. | последнее изменение 09:41:21, `competitors cycle exit=0` |
| 21.10 09:41 | Продолжение: команда остальных конфигураций нашла все ответы сохранёнными и ничего не запрашивала; команда движка взяла сохранённые RU qwen (380) и первые 71 ответ RU gemma и продолжила с 72-го. | `ok: --per-type 4 …` в `~/anonapp_h5_resume.log` |
| 21.10 14:31 | Движок RU gemma4:12b: 380 ответов. | изменение 14:31:17 |
| 21.10 19:23 | Движок UK qwen3.5:9b: 380 ответов. | создание 14:31:20, изменение 19:23:44 |
| 22.10 00:27 | Движок UK gemma4:12b: 380 ответов. Скрипт завершён. | изменение 00:27:43, `all done Thu Oct 22 00:27:52` |
| 22.10 00:55 | Результаты закоммичены (закрытый 10fb55b), опубликованы как v0.3.0. | история git |

## Число ответов

| Конфигурация | Ответов на модель и язык | Повторных ключей |
|---|---|---|
| pii_roundtrip (RU, UK) | 380 (190 документов × 2 задания) | 0 |
| каждая из 7 остальных конфигураций | 40 (20 документов × 2 задания) | 0 |

В каждом файле ответов ровно одна строка на (документ, задание, хеш запроса): ни один ответ не запрошен дважды и ни один не пропущен.

> Уточнение от 22.10.2026: каждый ответ запрошен у нейросети один раз. При продолжении команда остальных конфигураций была запущена второй раз, нашла все ответы сохранёнными и новых запросов не делала.

> Дополнение от 22.10.2026: причина остановки установлена по журналам сессий на этом компьютере. Другая сессия Claude Code, работавшая над другим проектом (nl2sql-onprem-bench) на том же сервере Ollama, выполнила `ollama stop gemma4:12b` в 23:58:06 20.10, `pkill -f 'ollama serve'` в 00:03:00 21.10 и затем снова запустила `ollama serve` (тот же бинарник из Homebrew, 0.40.4); с 23:57 она также отправляла этому серверу свои запросы к другим моделям. Остановка процесса оборвала соединение во время 72-го ответа. Ответы русского gemma4:12b до 71-го получены, пока сервером пользовалась другая сессия; при температуре 0 и зерне 0 это не должно менять ответ, но повторным запросом это не проверялось.

## Отступления от плана в HOLDOUT.md

- Одна остановка (выше). Продолжение шло теми же командами плана; код, данные и нейросети между остановкой и продолжением не менялись.
- Пункт 5 плана называет `results/holdout_runs.jsonl` для любого повторного запуска. Этот журнал записывает только прогоны распознавания, команды полного цикла в него не пишут. Поэтому продолжение записано здесь и в CHANGELOG, а не в нём.
- Пометка об остановке, дописанная в `~/anonapp_h5_cycle.log` в 06:11, не сохранилась: ещё работавшая команда открыла лог через `>` и перезаписала его. Этот журнал заменяет ту пометку.
