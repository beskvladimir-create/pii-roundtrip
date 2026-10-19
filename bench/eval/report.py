"""Сборка REPORT и README из results/.

python -m bench.eval.report

Все числа в документах берутся из results/metrics.json и results/cycle_metrics*.json;
шаблоны (docs/*.tpl.md, bench/eval/analysis*.md) содержат только подстановки:

  {=tool|lang:sets|metric}  значение с 95% интервалом; metric: struct, names, leak, prec;
                            «+» в конце добавляет итог по порогу: {=pii_guard|ru:h3|leak+}
  {#tool|lang:sets|metric}  только значение, без интервала
  {%tool|lang:sets|metric}  голое число для атрибутов HTML: 53.3
  metric clean / docs       число документов без утечки и всего: {#pii_roundtrip|ru:h3|clean} из {#pii_roundtrip|ru:h3|docs}
  {~tool|lang:data|restore} восстановление в полном цикле, худшая из двух моделей
                            (data: synthetic или holdout4); «+» добавляет итог;
                            data@model берёт одну модель: {~pii_guard|ru:holdout4@qwen3.5:9b|altered};
                            вместо restore можно взять счётчик (altered, invented, labels_in_answer)
  tool: имя инструмента или best (лучший существующий для языка ссылки)
  sets: h3 (отложенный набор 4), ext (внешние наборы без домашнего набора инструмента),
        ext-<tool> (внешние наборы без домашнего набора другого инструмента),
        или имена наборов через запятую
  {BEST_RU}, {BEST_UK}      лучший существующий инструмент на внешних наборах
  {TABLE_HEADLINE}, {TABLE_PRECISION}, {TABLE_THRESHOLDS_RU}, {TABLE_THRESHOLDS_UK}
  {RU_STRUCT_CI} ... {UK_RESTORE_CI}, {ANON_PASS_SUMMARY}: итог движка на наборе 3

Правило итога одно для всех: «не пройден», если весь 95% интервал по неверную сторону
порога; «пройден», если весь по верную; иначе «не определено».
"""

from __future__ import annotations

import json
import re

from bench import ROOT
from bench.eval.external import HOME_TOOL
from bench.eval.metrics import THRESHOLDS, wilson

RESULTS = ROOT / "results"
ENGINE = "pii_roundtrip"

EXTERNAL = {
    "ru": ["hivetrace_pii_bench", "redmadrobot_pii_benchmark"],
    "uk": ["nemotron_uk", "nemotron_uk_ids"],
}
DOWNLOAD_MAC = "https://github.com/beskvladimir-create/pii-roundtrip/releases/latest/download/pii-roundtrip-mac.dmg"
HOLDOUT = {"ru": "holdout4_ru", "uk": "holdout4_uk"}  # the independent held-out set of this version
SYNTH = {"ru": "synthetic_ru", "uk": "synthetic_uk"}
TOOLS = [
    "pii_roundtrip",
    "pii_guard",
    "gliner_guard",
    "presidio",
    "privacy_filter",
    "prompt_anonymizer",
    "regex_baseline",
]
TOOL_NAME = {
    "en": {
        "pii_roundtrip": "pii-roundtrip",
        "pii_guard": "pii-guard",
        "gliner_guard": "GLiNER Guard Omni",
        "presidio": "Presidio",
        "privacy_filter": "OpenAI privacy-filter",
        "prompt_anonymizer": "Prompt Anonymizer",
        "regex_baseline": "Regular expressions with checksums",
    },
    "ru": {
        "pii_roundtrip": "pii-roundtrip",
        "pii_guard": "pii-guard",
        "gliner_guard": "GLiNER Guard Omni",
        "presidio": "Presidio",
        "privacy_filter": "OpenAI privacy-filter",
        "prompt_anonymizer": "Prompt Anonymizer",
        "regex_baseline": "Регулярные выражения с контрольными суммами",
    },
}
TOOL_NAME["tex"] = TOOL_NAME["en"]
COMPETITORS = [t for t in TOOLS if t != ENGINE]
# инструменты с собственным восстановлением; остальные только распознают
NATIVE_RESTORE = {"pii_guard", "prompt_anonymizer", "pii_roundtrip"}
CYCLE_NAME = {
    "pii_guard": "pii-guard (свои теги)",
    "pii_guard+placeholders": "pii-guard + метки [TYPE_n]",
    "prompt_anonymizer": "Prompt Anonymizer (свои метки)",
    "gliner_guard+placeholders": "GLiNER Guard + метки [TYPE_n]",
    "pii_roundtrip": "pii-roundtrip",
    # контроль формата и промпта: те же ответы с терпимым разбором и прогоны с общим промптом
    "pii_guard~tolerant": "pii-guard (свои теги, терпимый разбор)",
    "pii_guard@generic": "pii-guard (свои теги, общий промпт)",
    "pii_guard@generic~tolerant": "pii-guard (свои теги, общий промпт, терпимый разбор)",
    "pii_guard+placeholders@generic": "pii-guard + метки [TYPE_n], общий промпт",
    "gliner_guard+placeholders@generic": "GLiNER Guard + метки [TYPE_n], общий промпт",
}
STATUS = {
    "en": {
        "met": "met",
        "not met": "not met",
        "undetermined": "undetermined",
        "borderline": "undetermined, borderline",
    },
    "ru": {
        "met": "пройден",
        "not met": "не пройден",
        "undetermined": "не определено",
        "borderline": "не определено, на границе",
    },
}
WORDS = {
    "en": {
        "na": "n/a",
        "not_measured": "not measured",
        "no_restore": "no restore step, not met",
        "reference": "for reference",
        "no_threshold": "no threshold",
    },
    "ru": {
        "na": "нет",
        "not_measured": "не измерялось",
        "no_restore": "восстановления нет, не пройден",
        "reference": "справочно",
        "no_threshold": "без порога",
    },
}


# LaTeX: English wording, "%" escaped
STATUS["tex"] = STATUS["en"]
WORDS["tex"] = WORDS["en"]


# ---------- числа ----------


def pct(x: float | None, lang: str) -> str:
    if x is None:
        return WORDS[lang]["na"]
    v = f"{100 * x:.1f}%"
    if lang == "tex":
        return v.replace("%", "\\%")
    return v.replace(".", ",") if lang == "ru" else v


def interval(c, lang: str) -> str:
    if not c:
        return ""
    lo, hi = (f"{100 * c[0]:.1f}", f"{100 * c[1]:.1f}")
    if lang == "ru":
        lo, hi = lo.replace(".", ","), hi.replace(".", ",")
    return f" [{lo}; {hi}]"


def status_recall(rate, c, thr) -> str:
    if rate is None:
        return ""
    if c[1] < thr:
        return "not met"
    if c[0] >= thr:
        return "met"
    return "undetermined"


def status_leak(rate, c, thr) -> str:
    if rate is None:
        return ""
    if c[0] > thr:
        return "not met"
    if c[1] <= thr:
        return "met"
    return "undetermined"


def status(metric: str, rate, c) -> str:
    if metric == "leak":
        return status_leak(rate, c, THRESHOLDS["leak"])
    key = {"struct": "structured", "names": "names", "restore": "restore"}.get(metric)
    return status_recall(rate, c, THRESHOLDS[key]) if key else ""


def _result(m: dict, tool: str, ds: str) -> dict | None:
    return m.get(tool, {}).get(ds) or m.get(tool, {}).get(f"{ds}@300")


# Intervals of recall and masking precision come from the document-level cluster bootstrap
# (results/cluster_ci.json): values inside one document are not independent, so Wilson
# intervals over values are too narrow. Document-level leak rates keep Wilson intervals.
CLUSTER_METRIC = {"struct": "structured", "names": "names", "prec": "precision_fragments"}
# the home datasets of the engine's components (pii-guard and GLiNER Guard): reference only
ENGINE_HOME = {"hivetrace_pii_bench", "redmadrobot_pii_benchmark"}


def _cluster() -> dict:
    p = RESULTS / "cluster_ci.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _cluster_key(sets: list[str]) -> str:
    return "nemotron_uk+ids" if sets == ["nemotron_uk", "nemotron_uk_ids"] else "+".join(sets)


def stats(m: dict, tool: str, sets: list[str]) -> dict | None:
    """Сумма по наборам: полнота номеров и имён, доля документов с утечкой, точность маскирования."""
    rows = [r for r in (_result(m, tool, ds) for ds in sets) if r]
    if not rows:
        return None
    acc = {"struct": [0, 0], "names": [0, 0], "leak": [0, 0], "prec": [0, 0]}
    for r in rows:
        for key, g in (("struct", "structured"), ("names", "names")):
            if r[g]["n"]:
                acc[key][0] += round(r[g]["recall"] * r[g]["n"])
                acc[key][1] += r[g]["n"]
        acc["leak"][0] += round(r["leak_rate"] * r["docs"])
        acc["leak"][1] += r["docs"]
        if r.get("masked_fragments"):
            acc["prec"][0] += r["masked_fragments_ok"]
            acc["prec"][1] += r["masked_fragments"]
    out: dict = {"sets": [ds for ds in sets if _result(m, tool, ds)]}
    cl = _cluster().get(tool, {}).get(_cluster_key(out["sets"]), {})
    for key, (k, n) in acc.items():
        boot = cl.get(CLUSTER_METRIC.get(key, ""))
        if boot and boot[0] == k and boot[1] == n:
            out[key] = (k / n, (boot[3], boot[4]), n)
            out[key + "_seeds"] = cl.get(CLUSTER_METRIC[key] + "_seeds")
        else:
            out[key] = (k / n if n else None, wilson(k, n) if n else None, n)
    return out


def ext_sets(lang: str, tool: str) -> list[str]:
    """Внешние наборы языка без домашнего набора инструмента."""
    return [ds for ds in EXTERNAL[lang] if HOME_TOOL.get(ds) != tool]


def resolve_sets(spec: str, tool: str) -> tuple[str, list[str]]:
    lang, sets = spec.split(":", 1)
    if sets == "h3":
        return lang, [HOLDOUT[lang]]
    if sets == "ext":
        return lang, ext_sets(lang, tool)
    if sets.startswith("ext-"):
        return lang, ext_sets(lang, sets[4:])
    return lang, sets.split(",")


def best_tool(m: dict, lang: str) -> str:
    """Лучший из существующих инструментов на внешних наборах без домашнего (движок не участвует)."""

    def score(t: str) -> float:
        p = stats(m, t, ext_sets(lang, t))
        if not p or p["names"][0] is None:
            return -1
        leak = p["leak"][0] if p["leak"][0] is not None else 1
        return (p["struct"][0] or 0) + (p["names"][0] or 0) - leak

    return max((t for t in COMPETITORS if t in m), key=score)


def load_cycles() -> dict[str, dict]:
    out = {}
    # version 0.2 measures the round trip on the held-out set only; cycle_metrics.json holds version 0.1 runs
    for data, name in (("holdout4", "cycle_metrics.holdout4.json"),):
        p = RESULTS / name
        out[data] = json.loads(p.read_text()) if p.exists() else {}
    return out


def restore(cyc: dict, tool: str, lang: str) -> tuple | None:
    """Восстановление собственным механизмом инструмента, худшая из моделей: (доля вхождений,
    интервал бутстрепом по ответам, вхождений, ответов без ошибок, ответов с метками)."""
    worst = None
    for lm, a in cyc.get(tool, {}).items():
        usable = lm.startswith(lang) and a.get("restore_rate") is not None
        if usable and (worst is None or a["restore_rate"] < worst["restore_rate"]):
            worst = a
    if not worst:
        return None
    n = worst["answers_with_labels"]
    return (
        worst["restore_rate"],
        tuple(worst["restore_ci"]),
        worst["labels_in_answer"],
        n - worst["answers_with_failure"],
        n,
    )


def restore_interval(r: tuple) -> tuple[float, float]:
    """The interval of the restored share: bootstrap over answers. With no failed placeholder the
    bootstrap collapses to a point, so the lower bound is the one-sided 97.5% bound over answers,
    0.025^(1/n): with 40 answers it is 91.2%, and about 370 answers are needed to reach 99%."""
    rate, c, _, _, n = r
    if rate == 1.0 and n:
        return (0.025 ** (1 / n), 1.0)
    return c


def restore_status(r: tuple) -> str:
    """Restored share of the placeholders the tool issued, threshold 99%, judged on the interval above."""
    return status_recall(r[0], restore_interval(r), THRESHOLDS["restore"])


def restore_cell(r: tuple, lang: str, with_status: bool = True) -> str:
    st = restore_status(r) if with_status else ""
    return f"{pct(r[0], lang)}{interval(restore_interval(r), lang)}" + (f" {STATUS[lang][st]}" if st else "")


def cell(rate, c, metric: str, lang: str, with_status: bool = True) -> str:
    if rate is None:
        return WORDS[lang]["na"]
    st = status(metric, rate, c) if with_status else ""
    return f"{pct(rate, lang)}{interval(c, lang)}" + (f" {STATUS[lang][st]}" if st else "")


def status_of(s: dict, metric: str) -> str:
    """The verdict; "borderline" when it changes with the bootstrap seed (seeds 0 to 5)."""
    rate, c, _ = s[metric]
    st = status(metric, rate, c)
    seeds = s.get(metric + "_seeds")
    if seeds and len({status(metric, rate, tuple(b)) for b in seeds}) > 1:
        return "borderline"
    return st


def cell_of(s: dict, metric: str, lang: str, with_status: bool = True) -> str:
    rate, c, _ = s[metric]
    if rate is None:
        return WORDS[lang]["na"]
    st = status_of(s, metric) if with_status else ""
    return f"{pct(rate, lang)}{interval(c, lang)}" + (f" {STATUS[lang][st]}" if st else "")


# ---------- подстановки в тексте ----------

_REF = re.compile(r"\{([=#~%])([a-z_+@~]+)\|([a-z]{2}:[\w,.:@\-]+)\|([a-z_]+)(\+?)\}")


def _ref(m: dict, cycles: dict, match: re.Match, lang: str) -> str:
    kind, tool, spec, metric, plus = match.groups()
    if tool == "best":  # the best existing tool for the language of the reference
        tool = best_tool(m, spec.split(":", 1)[0])
    if kind == "~":
        lang_d, data = spec.split(":", 1)
        data, _, model = data.partition("@")
        by = cycles.get(data, {}).get(tool, {})
        if model:
            a = by.get(f"{lang_d}/{model}")
            if not a:
                raise KeyError(f"нет полного цикла для {match.group(0)}")
            if metric == "restore":
                n = a["answers_with_labels"]
                r = (a["restore_rate"], tuple(a["restore_ci"]), a["labels_in_answer"], n - a["answers_with_failure"], n)
                return restore_cell(r, lang, bool(plus))
            return str(a[metric])
        if metric != "restore":  # a count summed over both models
            rows = [a for lm, a in by.items() if lm.startswith(lang_d)]
            if not rows:
                raise KeyError(f"нет полного цикла для {match.group(0)}")
            if isinstance(rows[0][metric], list):  # document ids: the number of distinct documents
                return str(len({d for a in rows for d in a[metric]}))
            return str(sum(a[metric] for a in rows))
        r = restore(cycles.get(data, {}), tool, lang_d)
        if not r:
            raise KeyError(f"нет полного цикла для {match.group(0)}")
        return restore_cell(r, lang, bool(plus))
    _, sets = resolve_sets(spec, tool)
    s = stats(m, tool, sets)
    if metric in ("clean", "docs") and s:  # whole documents: without any leak, and in total
        rate, _, n = s["leak"]
        value = n - round(rate * n) if metric == "clean" else n
        return f"{value:,}".replace(",", "\u00a0" if lang == "ru" else ",")
    if not s or s[metric][0] is None:
        raise KeyError(f"нет результатов для {match.group(0)}")
    rate, c, _ = s[metric]
    if kind == "#":
        return pct(rate, lang)
    if kind == "%":  # a bare number for HTML attributes: "53.3"
        return f"{100 * rate:.1f}"
    return cell_of(s, metric, lang, bool(plus))


def headline_table(m: dict, lang: str) -> str:
    """Доля документов с утечкой на отложенном наборе 4 для всех инструментов."""
    head = "| Tool | Russian | UK English |" if lang == "en" else "| Инструмент | Русский | Британский английский |"
    rows = [head, "|---|---|---|"]
    for t in TOOLS:
        cells = []
        for lg in ("ru", "uk"):
            s = stats(m, t, [HOLDOUT[lg]])
            cells.append(cell_of(s, "leak", lang, False) if s else WORDS[lang]["na"])
        name = TOOL_NAME[lang][t]
        if t == ENGINE:
            name, cells = f"**{name}**", [f"**{c}**" for c in cells]
        rows.append(f"| {name} | {cells[0]} | {cells[1]} |")
    return "\n".join(rows)


def precision_table(m: dict, lang: str) -> str:
    """Доля скрытых фрагментов, задевающих персональные данные, на отложенном наборе 4."""
    head = "| Tool | Russian | UK English |" if lang == "en" else "| Инструмент | Русский | Британский английский |"
    rows = [head, "|---|---|---|"]
    for t in TOOLS:
        cells = []
        for lg in ("ru", "uk"):
            s = stats(m, t, [HOLDOUT[lg]])
            cells.append(cell_of(s, "prec", lang, False) if s and s["prec"][0] is not None else WORDS[lang]["na"])
        rows.append(f"| {TOOL_NAME[lang][t]} | {cells[0]} | {cells[1]} |")
    return "\n".join(rows)


def threshold_table(m: dict, cycles: dict, lang_data: str, lang: str) -> str:
    """Лучший существующий инструмент и движок на одних и тех же данных: внешние наборы без
    домашнего набора этого инструмента и отложенный набор 4."""
    x = best_tool(m, lang_data)
    ext = ext_sets(lang_data, x)
    h3 = [HOLDOUT[lang_data]]
    cols = [(x, ext), (ENGINE, ext), (x, h3), (ENGINE, h3)]
    n = TOOL_NAME[lang]
    if lang == "en":
        heads = [
            f"{n[x]}, external",
            f"{n[ENGINE]}, same external sets",
            f"{n[x]}, held-out set 4",
            f"{n[ENGINE]}, held-out set 4",
        ]
        labels = {
            "struct": "Structured identifiers ≥ 99%",
            "names": "Names, addresses, organisations ≥ 95%",
            "leak": "Documents with a leak ≤ 2%",
            "restore": "Restoration ≥ 99% (worse of two LLMs)",
            "prec": "Masked fragments that contain personal data",
        }
        first = "Threshold"
    else:
        heads = [
            f"{n[x]}, внешние",
            f"{n[ENGINE]}, те же внешние наборы",
            f"{n[x]}, отложенный набор 4",
            f"{n[ENGINE]}, отложенный набор 4",
        ]
        labels = {
            "struct": "Номера ≥ 99%",
            "names": "Имена, адреса, организации ≥ 95%",
            "leak": "Документы с утечкой ≤ 2%",
            "restore": "Восстановление ≥ 99% (худшая из двух нейросетей)",
            "prec": "Скрытые фрагменты, содержащие персональные данные",
        }
        first = "Порог"
    rows = [f"| {first} | " + " | ".join(heads) + " |", "|---" * (len(heads) + 1) + "|"]
    for metric in ("struct", "names", "leak", "restore", "prec"):
        cells = []
        for tool, sets in cols:
            if metric == "restore":
                if sets is not h3:
                    cells.append(WORDS[lang]["not_measured"])
                elif tool not in NATIVE_RESTORE:
                    cells.append(WORDS[lang]["no_restore"])
                else:
                    r = restore(cycles.get("holdout4", {}), tool, lang_data)
                    cells.append(restore_cell(r, lang) if r else WORDS[lang]["na"])
                continue
            s = stats(m, tool, sets)
            if not s or s[metric][0] is None:
                cells.append(WORDS[lang]["na"])
            elif metric == "prec":
                cells.append(f"{cell_of(s, 'prec', lang, False)}, {WORDS[lang]['no_threshold']}")
            elif tool == ENGINE and set(sets) & ENGINE_HOME:
                # home datasets of the engine's components: shown for reference, no verdict
                cells.append(f"{cell_of(s, metric, lang, False)}, {WORDS[lang]['reference']}")
            else:
                cells.append(cell_of(s, metric, lang))
        rows.append(f"| {labels[metric]} | " + " | ".join(cells) + " |")
    sets_line = ", ".join(ext)
    rows.append("")
    rows.append(("External sets: " if lang == "en" else "Внешние наборы: ") + sets_line + ".")
    return "\n".join(rows)


def engine_values(m: dict, cycles: dict) -> dict:
    """Итог движка на отложенном наборе 4 (независимая проверка) для подстановок {RU_STRUCT_CI} и др."""
    vals: dict = {}
    for lg, key in (("ru", "RU"), ("uk", "UK")):
        s = stats(m, ENGINE, [HOLDOUT[lg]])
        if not s:
            continue
        rows = {k.upper(): (s[k][0], s[k][1], status_of(s, k)) for k in ("struct", "names", "leak")}
        r = restore(cycles.get("holdout4", {}), ENGINE, lg)
        if r:
            rows["RESTORE"] = (r[0], restore_interval(r), restore_status(r))
        vals[key] = rows
    return vals


VERDICT_GROUPS = {"met": ("met",), "undetermined": ("undetermined", "borderline"), "not met": ("not met",)}


def fill(text: str, m: dict, cycles: dict, lang: str) -> str:
    vals = engine_values(m, cycles)
    names = {
        "ru": {"STRUCT": "номера", "NAMES": "имена и адреса", "LEAK": "утечки", "RESTORE": "восстановление"},
        "en": {"STRUCT": "identifiers", "NAMES": "names and addresses", "LEAK": "leaks", "RESTORE": "restoration"},
    }["ru" if lang == "ru" else "en"]
    summary = []
    for key, rows in vals.items():
        for metric, (rate, c, st) in rows.items():
            text = text.replace(f"{{{key}_{metric}}}", pct(rate, lang))
            text = text.replace(
                f"{{{key}_{metric}_CI}}", f"{pct(rate, lang)}{interval(c, lang)} {STATUS[lang].get(st, '')}".rstrip()
            )
        groups = {g: [names[k] for k, (_, _, st) in rows.items() if st in sts] for g, sts in VERDICT_GROUPS.items()}
        words = {"ru": ("пройдены", "не определены", "не пройдены"), "en": ("met", "undetermined", "not met")}
        w = dict(zip(VERDICT_GROUPS, words["ru" if lang == "ru" else "en"], strict=True))
        parts = "; ".join(f"{w[g]}: {', '.join(v)}" for g, v in groups.items() if v)
        if lang == "ru":
            where = "русский" if key == "RU" else "британский английский"
        else:
            where = "Russian" if key == "RU" else "UK English"
        summary.append(f"{where}: {parts}")
    joined = "; ".join(summary)
    text = text.replace("{ANON_PASS_SUMMARY_EN}", joined).replace("{ANON_PASS_SUMMARY}", joined)
    text = text.replace("{DOWNLOAD_MAC}", DOWNLOAD_MAC)
    text = text.replace("{BEST_RU}", TOOL_NAME[lang][best_tool(m, "ru")])
    text = text.replace("{BEST_UK}", TOOL_NAME[lang][best_tool(m, "uk")])
    text = text.replace("{TABLE_HEADLINE}", headline_table(m, lang))
    text = text.replace("{TABLE_PRECISION}", precision_table(m, lang))
    text = text.replace("{TABLE_THRESHOLDS_RU}", threshold_table(m, cycles, "ru", lang))
    text = text.replace("{TABLE_THRESHOLDS_UK}", threshold_table(m, cycles, "uk", lang))
    return _REF.sub(lambda mt: _ref(m, cycles, mt, lang), text)


# ---------- приложение с полными таблицами ----------


def build(m: dict, cycles: dict) -> str:
    L: list[str] = []
    L.append("Воспроизведение: `scripts/reproduce.sh`. Конфигурации запусков: `results/metrics.json` (`_config`).\n")

    L.append("### П1. Сводная таблица распознавания\n")
    L.append(
        "Полнота в режиме «скрыто целиком» (masked), 95% интервал Уилсона. Номера: паспорт, СНИЛС, ИНН, счёт, карта (RU); "
        "NHS, NI, карта, IBAN (UK). Утечки: доля документов, где после очистки осталось исходное значение. Точность: доля "
        "скрытых фрагментов, задевающих размеченные персональные данные. Отложенные наборы 1 и 2 с версии 0.2 служат для "
        "разработки и здесь не показаны; их однократные прогоны версии 0.1 приведены в выпуске 0.1.0.\n"
    )
    for lang in ("ru", "uk"):
        L.append(f"#### {'Русский' if lang == 'ru' else 'Британский английский'}\n")
        L.append("| Инструмент | Набор | Номера | Имена, адреса, организации | Утечки | Точность |")
        L.append("|---|---|---|---|---|---|")
        for tool in TOOLS:
            for ds in [HOLDOUT[lang], *EXTERNAL[lang], SYNTH[lang]]:
                s = stats(m, tool, [ds])
                if not s:
                    continue
                home = " (домашний)" if HOME_TOOL.get(ds) == tool else ""
                c = [
                    cell_of(s, k, "ru", False) + (f" n={s[k][2]}" if k != "prec" else "")
                    for k in ("struct", "names", "leak", "prec")
                ]
                L.append(f"| {TOOL_NAME['ru'][tool]} | {ds}{home} | " + " | ".join(c) + " |")
        L.append("")

    L.append("### П2. Пороги: лучший существующий инструмент и pii-roundtrip на одних и тех же данных\n")
    L.append(
        "Лучший инструмент выбирается по внешним наборам без его домашнего набора. Движок считается на тех же наборах и на "
        "отложенном наборе 4, которого не видел ни один инструмент. Русские внешние наборы использовались для разбора ошибок "
        "при разработке движка версии 0.1, поэтому для движка они не являются независимой проверкой.\n"
    )
    verdict_gap = {}
    for lang in ("ru", "uk"):
        L.append(f"#### {'Русский' if lang == 'ru' else 'Британский английский'}\n")
        L.append(threshold_table(m, cycles, lang, "ru"))
        L.append("")
        x = best_tool(m, lang)
        gaps = []
        for metric in ("struct", "names", "leak"):
            for sets, where in ((ext_sets(lang, x), "внешние"), ([HOLDOUT[lang]], "набор 4")):
                s = stats(m, x, sets)
                if s and s[metric][0] is not None and status_of(s, metric) == "not met":
                    gaps.append(f"{metric} ({where})")
        if x not in NATIVE_RESTORE:
            gaps.append("восстановление (нет своего)")
        else:
            r = restore(cycles.get("holdout4", {}), x, lang)
            if r and status("restore", r[0], r[1]) == "not met":
                gaps.append("восстановление")
        verdict_gap[lang] = (x, gaps)

    L.append("### П3. Полный цикл (очистка, ответ нейросети, восстановление)\n")
    for data, title in (("holdout4", "Отложенный набор 4"),):
        cyc = cycles.get(data, {})
        L.append(f"#### {title}\n")
        if not cyc:
            L.append("Не прогнан.\n")
            continue
        L.append(
            "Интервалы бутстрепом по ответам. «Свои метки»: выданные инструментом (дословно и искажённые нейросетью). "
            "«Выдумано»: метки, которых инструмент не выдавал; в долю восстановления не входят.\n"
        )
        L.append(
            "| Инструмент | Язык / модель | Свои метки в ответах | Дословно | Искажено | Выдумано нейросетью | Восстановлено | Потеряно значений | Документов с утечкой на входе |"
        )
        L.append("|---|---|---|---|---|---|---|---|---|")
        for tool, by in cyc.items():
            for lm, a in by.items():
                L.append(
                    f"| {CYCLE_NAME.get(tool, tool)} | {lm} | {a['labels_in_answer']} | {pct(a['exact_share'], 'ru')} | {a['altered']} | "
                    f"{a.get('invented', 0)} | {pct(a['restore_rate'], 'ru')}{interval(a['restore_ci'], 'ru')} | {a['values_lost']} | "
                    f"{a['docs_with_input_leak']} из {a['answers'] // 2} |"
                )
        L.append("")

    L.append("### П4. Показательные пропуски (до 10 на инструмент)\n")
    L.append("Сначала отложенный набор 4, затем внешние наборы без домашнего.\n")
    for tool in TOOLS:
        if tool not in m:
            continue
        seen, per_lang = set(), {"ru": [], "uk": []}
        for lang in ("ru", "uk"):
            for ds in [HOLDOUT[lang], *ext_sets(lang, tool)]:
                r = _result(m, tool, ds)
                if not r:
                    continue
                for t, v in r["per_type"].items():  # по одному примеру на тип за набор
                    for _, value in v["misses"]:
                        if (t, value) not in seen:
                            seen.add((t, value))
                            per_lang[lang].append(f"`{t}` в {ds}: «{value[:80]}»")
                            break
        ex = [per_lang[lg][i] for i in range(10) for lg in ("ru", "uk") if i < len(per_lang[lg])][:10]
        if ex:
            L.append(f"**{TOOL_NAME['ru'][tool]}**\n")
            L.extend(f"{i}. {e}" for i, e in enumerate(ex, 1))
            L.append("")

    L.append("### П5. Вердикт по порогам для существующих инструментов\n")
    named = {"struct": "номера", "names": "имена, адреса, организации", "leak": "утечки"}
    if any(g for _, g in verdict_gap.values()):
        L.append("**Технический разрыв есть.** Лучшие существующие инструменты не проходят пороги:\n")
        for lang, (x, gaps) in verdict_gap.items():
            if gaps:
                pretty = [re.sub(r"^(\w+)", lambda mt: named.get(mt.group(1), mt.group(1)), g) for g in gaps]
                L.append(
                    f"- {'русский' if lang == 'ru' else 'британский английский'}, {TOOL_NAME['ru'][x]}: {'; '.join(pretty)}"
                )
    else:
        L.append("**Технического разрыва нет:** лучшие инструменты проходят все пороги.")
    L.append("")
    return "\n".join(L)


def render() -> dict[str, str]:
    """The generated documents: file name -> text. Every number in them comes from results/."""
    m = json.loads((RESULTS / "metrics.json").read_text())
    cycles = load_cycles()

    def tpl(path: str, lang: str) -> str:
        return fill((ROOT / path).read_text(encoding="utf-8"), m, cycles, lang)

    docs = {
        "REPORT.md": tpl("bench/eval/analysis.md", "ru")
        + "\n\n---\n\n## Приложение: полные таблицы\n\n"
        + build(m, cycles),
        "REPORT.en.md": tpl("bench/eval/analysis.en.md", "en"),
        "README.md": tpl("docs/README.tpl.md", "en"),
        "README.ru.md": tpl("docs/README.ru.tpl.md", "ru"),
    }
    # the preprint and the article, when their templates are present (they are not in the public export)
    for out, src, lang in (
        ("outreach/arxiv/main.tex", "outreach/arxiv/main.tpl.tex", "tex"),
        ("outreach/arxiv/paper.ru.md", "outreach/arxiv/paper.ru.tpl.md", "ru"),
        ("outreach/habr/article.ru.md", "outreach/habr/article.ru.tpl.md", "ru"),
        ("outreach/linkedin/post-v0.2.en.md", "outreach/linkedin/post-v0.2.en.tpl.md", "en"),
        ("outreach/linkedin/post-v0.2.ru.md", "outreach/linkedin/post-v0.2.ru.tpl.md", "ru"),
        ("site/index.html", "site/index.tpl.html", "ru"),
        ("site/uk/index.html", "site/uk/index.tpl.html", "en"),
    ):
        if (ROOT / src).exists():
            docs[out] = tpl(src, lang)
    return docs


def main() -> None:
    docs = render()
    for name, text in docs.items():
        (ROOT / name).write_text(text, encoding="utf-8")
    left = [name for name, text in docs.items() if re.search(r"\{[A-Z_]{4,}\}|\{[=#~%][a-z_]+\|", text)]
    print(", ".join(docs) + (f"; не заполнено: {left}" if left else ""))


if __name__ == "__main__":
    main()
