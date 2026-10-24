"""README and REPORT are generated from results/: hand edits of the numbers are caught here."""

import re

import pytest

from bench import ROOT
from bench.eval import report


@pytest.mark.skipif(not (ROOT / "results/metrics.json").exists(), reason="no benchmark results")
def test_committed_documents_match_the_generator():
    for name, text in report.render().items():
        assert (ROOT / name).read_text(encoding="utf-8") == text, f"{name} differs: run python -m bench.eval.report"
        assert not re.search(r"\{[A-Z_]{4,}\}", text), f"{name} has an unfilled placeholder"


def _res(struct, names, leaks, docs, prec=(90, 100)):
    def g(k, n):
        return {"n": n, "recall": k / n, "ci": None}

    return {
        "structured": g(*struct),
        "names": g(*names),
        "leak_rate": leaks / docs,
        "docs": docs,
        "per_type": {},
        "masked_fragments_ok": prec[0],
        "masked_fragments": prec[1],
    }


FAKE = {
    "pii_guard": {
        "hivetrace_pii_bench": _res((95, 100), (99, 100), 1, 100),
        "redmadrobot_pii_benchmark": _res((100, 100), (100, 100), 0, 100),  # home set: must be excluded
        "holdout7_ru": _res((900, 1000), (990, 1000), 300, 1000),
    },
    "pii_roundtrip": {
        "hivetrace_pii_bench": _res((100, 100), (100, 100), 0, 100),
        "redmadrobot_pii_benchmark": _res((50, 100), (50, 100), 50, 100),
        "holdout7_ru": _res((1000, 1000), (999, 1000), 5, 1000),
    },
}


def test_status_rule_is_the_same_for_every_threshold():
    assert report.status("struct", 0.995, (0.991, 0.998)) == "met"
    assert report.status("struct", 0.98, (0.97, 0.989)) == "not met"
    assert report.status("struct", 0.99, (0.985, 0.995)) == "undetermined"
    assert report.status("leak", 0.01, (0.005, 0.019)) == "met"
    assert report.status("leak", 0.05, (0.03, 0.07)) == "not met"
    assert report.status("leak", 0.02, (0.01, 0.03)) == "undetermined"


def test_engine_is_scored_on_the_competitor_sets():
    s = report.stats(FAKE, "pii_roundtrip", report.ext_sets("ru", "pii_guard"))
    assert s["sets"] == ["hivetrace_pii_bench"] and s["struct"][0] == 1.0
    table = report.threshold_table(FAKE, {}, "ru", "en")
    assert "pii-guard, external" in table and "pii-roundtrip, same external sets" in table
    assert "External sets: hivetrace_pii_bench." in table


def test_references_in_text_are_filled_from_results():
    text = "Leaks: {=pii_guard|ru:h3|leak+}; engine {#pii_roundtrip|ru:h3|leak}; best {BEST_RU}."
    out = report.fill(text, FAKE, {}, "en")
    assert out == "Leaks: 30.0% [27.2; 32.9] not met; engine 0.5%; best pii-guard."
    with pytest.raises(KeyError):
        report.fill("{=presidio|ru:h3|leak}", FAKE, {}, "en")
