"""Сборка REPORT.md из results/metrics.json и results/cycle_metrics.json.

python -m eval.report
Вердикт по порогам из REPORT.md: для каждого языка берётся лучший инструмент
на внешних наборах без его «домашнего» набора; порог не пройден, если верхняя
граница 95% интервала ниже порога, «не определено», если интервал накрывает порог.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from eval.external import HOME_TOOL
from eval.metrics import STRUCTURED as STRUCT_TYPES
from eval.metrics import THRESHOLDS

RESULTS = Path("results")

EXTERNAL = {
    "ru": ["hivetrace_pii_bench", "redmadrobot_pii_benchmark"],
    "uk": ["nemotron_uk", "nemotron_uk_ids"],
}
SYNTH = {"ru": "synthetic_ru", "uk": "synthetic_uk"}
LANG_NAME = {"ru": "русский", "uk": "британский английский"}
TOOL_NAME = {
    "regex_baseline": "Регулярки с контрольными суммами",
    "presidio": "Presidio",
    "pii_guard": "pii-guard",
    "gliner_guard": "GLiNER Guard",
    "privacy_filter": "OpenAI privacy-filter",
    "prompt_anonymizer": "Prompt Anonymizer",
    "pii_roundtrip": "pii_roundtrip",
}
COMPETITORS = [t for t in TOOL_NAME if t != "pii_roundtrip"]
CYCLE_NAME = {
    "pii_guard": "pii-guard (свои теги)",
    "pii_guard+placeholders": "pii-guard + метки [TYPE_n]",
    "prompt_anonymizer": "Prompt Anonymizer (свои метки)",
    "gliner_guard+placeholders": "GLiNER Guard + метки [TYPE_n]",
    "pii_roundtrip": "pii_roundtrip",
}
NATIVE_RESTORE = {"pii_guard", "prompt_anonymizer", "pii_roundtrip"}


def pct(x) -> str:
    return "нет" if x is None else f"{100 * x:.1f}%".replace(".", ",")


def ci(c) -> str:
    return "" if not c else f" [{100 * c[0]:.1f}; {100 * c[1]:.1f}]".replace(".", ",")


def status_recall(rate, c, thr) -> str:
    if rate is None:
        return "нет данных"
    if c[1] < thr:
        return "не пройден"
    if c[0] >= thr:
        return "пройден"
    return "не определено" if rate < thr else "пройден (на грани)"


def status_leak(rate, c, thr) -> str:
    if rate is None:
        return "нет данных"
    if c[0] > thr:
        return "не пройден"
    if c[1] <= thr:
        return "пройден"
    return "не определено" if rate > thr else "пройден (на грани)"


def pooled(m: dict, tool: str, lang: str, include_home: bool = False) -> dict | None:
    """Сумма по внешним наборам языка без домашнего набора инструмента."""
    from eval.metrics import wilson

    sets = [ds for ds in EXTERNAL[lang] if include_home or HOME_TOOL.get(ds) != tool]
    sets = [ds for ds in sets if ds in m.get(tool, {}) or f"{ds}@300" in m.get(tool, {})]
    if not sets:
        return None
    acc = {"structured": [0, 0], "names": [0, 0], "leak": [0, 0], "structured_no_nhs": [0, 0]}
    for ds in sets:
        r = m[tool].get(ds) or m[tool].get(f"{ds}@300")
        for g in ("structured", "names"):
            if r[g]["n"]:
                acc[g][0] += round(r[g]["recall"] * r[g]["n"])
                acc[g][1] += r[g]["n"]
        for t, v in r["per_type"].items():
            if t in STRUCT_TYPES[lang] and t != "NHS" and v["n"]:
                acc["structured_no_nhs"][0] += round(v["recall_masked"] * v["n"])
                acc["structured_no_nhs"][1] += v["n"]
        acc["leak"][0] += round(r["leak_rate"] * r["docs"])
        acc["leak"][1] += r["docs"]
    out = {"sets": sets}
    for g, (k, n) in acc.items():
        out[g] = (k / n if n else None, wilson(k, n) if n else None, n)
    return out


def best_tool(m: dict, lang: str) -> str:
    """Лучший из существующих инструментов (наш движок не участвует в выборе)."""

    def score(t):
        p = pooled(m, t, lang)
        if not p or p["names"][0] is None:
            return -1
        leak = p["leak"][0] if p["leak"][0] is not None else 1
        return (p["structured"][0] or 0) + (p["names"][0] or 0) - leak

    return max((t for t in COMPETITORS if t in m), key=score)


def restore_rows(cyc: dict, t: str, lang: str) -> list[tuple]:
    """Восстановление: собственным механизмом инструмента, если он есть, и отдельно
    с общей обвязкой меток (это уже не возможность инструмента)."""
    rows = []

    def worst(key):
        best = None
        for lm, agg in cyc.get(key, {}).items():
            if lm.startswith(lang) and agg.get("restore_rate") is not None:
                if best is None or agg["restore_rate"] < best["restore_rate"]:
                    best = agg
        return best

    if t in NATIVE_RESTORE:
        a = worst(t)
        if a:
            rr = (a["restore_rate"], a["restore_ci"], a["labels_in_answer"])
            rows.append(("Восстановление ≥ 99% меток, своим механизмом, худшая из моделей", rr, status_recall(rr[0], rr[1], THRESHOLDS["restore"])))
    else:
        rows.append(("Восстановление ≥ 99% меток, своим механизмом", (None, None, 0), "не пройден: собственного восстановления нет"))
    a = worst(f"{t}+placeholders")
    if a:
        rr = (a["restore_rate"], a["restore_ci"], a["labels_in_answer"])
        rows.append(("Справочно: восстановление с общей обвязкой меток [TYPE_n]", rr, "справочно, в вердикт не входит"))
    return rows


def build() -> str:
    m = json.loads((RESULTS / "metrics.json").read_text())
    cyc_path = RESULTS / "cycle_metrics.json"
    cyc = json.loads(cyc_path.read_text()) if cyc_path.exists() else {}
    L: list[str] = []
    L.append("Воспроизведение: `scripts/reproduce.sh`. Конфигурации запусков: `results/metrics.json` (`_config`).\n")

    L.append("### П1. Сводная таблица распознавания\n")
    L.append("Полнота в режиме «скрыто целиком» (masked), 95% интервал Уилсона. Номера: паспорт, СНИЛС, ИНН, счёт, карта (RU); NHS, NI, карта, IBAN (UK). Утечки: доля документов, где после очистки осталось исходное значение.\n")
    for lang in ("ru", "uk"):
        L.append(f"#### {LANG_NAME[lang].capitalize()}\n")
        L.append("| Инструмент | Набор | Номера | Имена, адреса, организации | Утечки |")
        L.append("|---|---|---|---|---|")
        for tool in TOOL_NAME:
            for ds in EXTERNAL[lang] + [SYNTH[lang]]:
                r = m.get(tool, {}).get(ds) or m.get(tool, {}).get(f"{ds}@300")
                if not r:
                    continue
                home = " (домашний)" if HOME_TOOL.get(ds) == tool else ""
                name = ds + ("@300" if f"{ds}@300" in m.get(tool, {}) and ds not in m.get(tool, {}) else "")
                st, nm = r["structured"], r["names"]
                L.append(
                    f"| {TOOL_NAME[tool]} | {name}{home} | {pct(st['recall'])}{ci(st['ci'])} n={st['n']} | "
                    f"{pct(nm['recall'])}{ci(nm['ci'])} n={nm['n']} | {pct(r['leak_rate'])} |"
                )
        L.append("")

    L.append("### П2. Пороги: лучшие существующие инструменты (внешние наборы без домашнего)\n")
    verdict_gap = {}
    for lang in ("ru", "uk"):
        t = best_tool(m, lang)
        p = pooled(m, t, lang)
        L.append(f"#### {LANG_NAME[lang].capitalize()}: лучший инструмент {TOOL_NAME[t]}\n")
        L.append(f"Наборы: {', '.join(p['sets'])}.\n")
        L.append("| Порог | Значение | Итог |")
        L.append("|---|---|---|")
        names_label = "Имена, адреса ≥ 95% (организаций во внешних RU наборах нет)" if lang == "ru" else "Имена, адреса, организации ≥ 95%"
        rows = [
            ("Номера ≥ 99%", p["structured"], status_recall(p["structured"][0], p["structured"][1], THRESHOLDS["structured"])),
            (names_label, p["names"], status_recall(p["names"][0], p["names"][1], THRESHOLDS["names"])),
            ("Утечки ≤ 2%", p["leak"], status_leak(p["leak"][0], p["leak"][1], THRESHOLDS["leak"])),
        ]
        if lang == "uk":
            sn = p["structured_no_nhs"]
            rows.insert(1, ("Справочно: номера без NHS (NHS подставлены в американский контекст)", sn, "справочно, в вердикт не входит"))
        rows += restore_rows(cyc, t, lang)
        for name, (rate, c, n), st in rows:
            L.append(f"| {name} | {pct(rate)}{ci(c)} n={n} | {st} |")
        L.append("")
        verdict_gap[lang] = [name for name, _, st in rows if st.startswith("не пройден")]

    L.append("### П2а. Наш движок pii-roundtrip по тем же порогам\n")
    L.append("Компоненты движка (pii-guard и GLiNER Guard) выпущены авторами обоих русских внешних наборов, поэтому для RU оба набора для него частично домашние; показаны все внешние наборы.\n")
    for lang in ("ru", "uk"):
        p = pooled(m, "pii_roundtrip", lang, include_home=True)
        if not p:
            continue
        L.append(f"#### {LANG_NAME[lang].capitalize()}\n")
        L.append(f"Наборы: {', '.join(p['sets'])}.\n")
        L.append("| Порог | Значение | Итог |")
        L.append("|---|---|---|")
        rows = [
            ("Номера ≥ 99%", p["structured"], status_recall(p["structured"][0], p["structured"][1], THRESHOLDS["structured"])),
            ("Имена, адреса, организации ≥ 95%", p["names"], status_recall(p["names"][0], p["names"][1], THRESHOLDS["names"])),
            ("Утечки ≤ 2%", p["leak"], status_leak(p["leak"][0], p["leak"][1], THRESHOLDS["leak"])),
        ] + restore_rows(cyc, "pii_roundtrip", lang)
        for name, (rate, c, n), st in rows:
            L.append(f"| {name} | {pct(rate)}{ci(c)} n={n} | {st} |")
        L.append("")

    L.append("### П2б. Отложенные наборы (однократные прогоны, хеши в HOLDOUT.md)\n")
    L.append("Набор 1 прогнан на предыдущей версии движка (до доработки номеров), набор 2 на текущей.\n")
    L.append("| Инструмент | Набор | Номера | Имена, адреса, организации | Утечки |")
    L.append("|---|---|---|---|---|")
    for tool in TOOL_NAME:
        for ds in ("holdout_ru", "holdout_uk", "holdout2_ru", "holdout2_uk"):
            r = m.get(tool, {}).get(ds)
            if r:
                st, nm = r["structured"], r["names"]
                from eval.metrics import wilson as _w

                lk = round(r["leak_rate"] * r["docs"])
                L.append(
                    f"| {TOOL_NAME[tool]} | {'набор 1' if ds.startswith('holdout_') else 'набор 2'}, {ds[-2:].upper()} | {pct(st['recall'])}{ci(st['ci'])} | {pct(nm['recall'])}{ci(nm['ci'])} | "
                    f"{pct(r['leak_rate'])}{ci(_w(lk, r['docs']))} |"
                )
    L.append("")

    L.append("### П3. Полный цикл (очистка → нейросеть → восстановление)\n")
    if cyc:
        L.append("Интервалы бутстрепом по ответам. «Свои метки»: выданные инструментом (дословно и искажённые нейросетью). «Выдумано»: метки, которых инструмент не выдавал; в долю восстановления не входят.\n")
        L.append("| Инструмент | Язык / модель | Свои метки в ответах | Дословно | Искажено | Выдумано нейросетью | Восстановлено | Потеряно значений | Документов с утечкой на входе |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for tool, by in cyc.items():
            for lm, a in by.items():
                L.append(
                    f"| {CYCLE_NAME.get(tool, tool)} | {lm} | {a['labels_in_answer']} | {pct(a['exact_share'])} | {a['altered']} | {a.get('invented', 0)} | "
                    f"{pct(a['restore_rate'])}{ci(a['restore_ci'])} | {a['values_lost']} | {a['docs_with_input_leak']} из {a['answers'] // 2} |"
                )
        L.append("")
    else:
        L.append("Полный цикл ещё не прогнан.\n")

    L.append("### П4. Показательные ошибки (до 10 на инструмент)\n")
    L.append("Пропущенные значения: сначала внешние наборы (без домашнего), затем синтетика.\n")
    for tool in TOOL_NAME:
        if tool not in m:
            continue
        seen, per_lang = set(), {"ru": [], "uk": []}
        for lang in ("ru", "uk"):
            for ds in [d for d in EXTERNAL[lang] + [SYNTH[lang]] if HOME_TOOL.get(d) != tool]:
                r = m[tool].get(ds) or m[tool].get(f"{ds}@300")
                if not r:
                    continue
                # по одному примеру на тип за набор: показать разные виды ошибок
                for t, v in r["per_type"].items():
                    for _, value in v["misses"]:
                        if (t, value) not in seen:
                            seen.add((t, value))
                            per_lang[lang].append(f"`{t}` в {ds}: «{value[:80]}»")
                            break
        ex = []
        for i in range(10):
            for lang in ("ru", "uk"):
                if i < len(per_lang[lang]) and len(ex) < 10:
                    ex.append(per_lang[lang][i])
        if ex:
            L.append(f"**{TOOL_NAME[tool]}**\n")
            L.extend(f"{i}. {e}" for i, e in enumerate(ex, 1))
            L.append("")

    L.append("### П5. Вердикт по порогам для существующих инструментов\n")
    gaps = {k: v for k, v in verdict_gap.items() if v}
    if gaps:
        L.append("**Технический разрыв есть.** Не пройдены пороги:\n")
        for lang, names in gaps.items():
            L.append(f"- {LANG_NAME[lang]}: {'; '.join(names)}")
    else:
        L.append("**Технического разрыва нет:** лучшие инструменты проходят все пороги.")
    L.append("")
    return "\n".join(L)


def _fmt(x: float | None, lang: str) -> str:
    if x is None:
        return "n/a"
    v = f"{100 * x:.1f}%"
    return v.replace(".", ",") if lang == "ru" else v


def _status(st: str, lang: str) -> str:
    if lang == "ru":
        return st
    return {"пройден": "met", "не пройден": "not met", "не определено": "undetermined", "пройден (на грани)": "met (borderline)"}.get(st, st)


def engine_values(m: dict, cyc: dict) -> dict:
    """Итоговые цифры движка для подстановки в README и анализ."""
    vals: dict = {}
    for lang, key in (("ru", "RU"), ("uk", "UK")):
        p = pooled(m, "pii_roundtrip", lang, include_home=True)
        worst = None
        for lm, a in cyc.get("pii_roundtrip", {}).items():
            if lm.startswith(lang) and a.get("restore_rate") is not None and (worst is None or a["restore_rate"] < worst["restore_rate"]):
                worst = a
        rows = {
            "STRUCT": (p["structured"][0], p["structured"][1], status_recall(p["structured"][0], p["structured"][1], THRESHOLDS["structured"])),
            "NAMES": (p["names"][0], p["names"][1], status_recall(p["names"][0], p["names"][1], THRESHOLDS["names"])),
            "LEAK": (p["leak"][0], p["leak"][1], status_leak(p["leak"][0], p["leak"][1], THRESHOLDS["leak"])),
        }
        if worst:
            rows["RESTORE"] = (worst["restore_rate"], tuple(worst["restore_ci"]), status_recall(worst["restore_rate"], worst["restore_ci"], THRESHOLDS["restore"]))
        vals[key] = rows
    return vals


def fill(text: str, vals: dict, lang: str) -> str:
    met_ru, met_en = [], []
    names_ru = {"STRUCT": "номера", "NAMES": "имена и адреса", "LEAK": "утечки", "RESTORE": "восстановление"}
    names_en = {"STRUCT": "identifiers", "NAMES": "names and addresses", "LEAK": "leaks", "RESTORE": "restoration"}
    for key, rows in vals.items():
        for metric, (rate, c, st) in rows.items():
            ci_txt = f" [{_fmt(c[0], lang)[:-1]}; {_fmt(c[1], lang)[:-1]}]" if c else ""
            text = text.replace(f"{{{key}_{metric}}}", _fmt(rate, lang))
            text = text.replace(f"{{{key}_{metric}_CI}}", f"{_fmt(rate, lang)}{ci_txt} {_status(st, lang)}")
        ok_ru = [names_ru[k] for k, (_, _, st) in rows.items() if st.startswith("пройден")]
        ok_en = [names_en[k] for k, (_, _, st) in rows.items() if st.startswith("пройден")]
        lang_ru = "по русскому" if key == "RU" else "по британскому английскому"
        lang_en = "for Russian" if key == "RU" else "for UK English"
        met_ru.append(f"{len(ok_ru)} порога из {len(rows)} {lang_ru} ({', '.join(ok_ru)})")
        met_en.append(f"{len(ok_en)} of {len(rows)} thresholds {lang_en} ({', '.join(ok_en)})")
    text = text.replace("{ANON_PASS_SUMMARY}", " и ".join(met_ru))
    text = text.replace("{ANON_PASS_SUMMARY_EN}", " and ".join(met_en))
    return text


def main() -> None:
    m = json.loads((RESULTS / "metrics.json").read_text())
    cyc_path = RESULTS / "cycle_metrics.json"
    cyc = json.loads(cyc_path.read_text()) if cyc_path.exists() else {}
    vals = engine_values(m, cyc)
    head = fill(Path("eval/analysis.md").read_text(encoding="utf-8"), vals, "ru")
    Path("REPORT.md").write_text(head + "\n\n---\n\n## Приложение: полные таблицы\n\n" + build(), encoding="utf-8")
    Path("REPORT.en.md").write_text(fill(Path("eval/analysis.en.md").read_text(encoding="utf-8"), vals, "en"), encoding="utf-8")
    Path("README.md").write_text(fill(Path("docs/README.tpl.md").read_text(encoding="utf-8"), vals, "en"), encoding="utf-8")
    Path("README.ru.md").write_text(fill(Path("docs/README.ru.tpl.md").read_text(encoding="utf-8"), vals, "ru"), encoding="utf-8")
    left = [f for f in ("REPORT.md", "REPORT.en.md", "README.md", "README.ru.md") if re.search(r"\{[A-Z_]{4,}\}", Path(f).read_text())]
    print("REPORT.md, REPORT.en.md, README.md, README.ru.md" + (f"; не заполнено: {left}" if left else ""))


if __name__ == "__main__":
    main()
