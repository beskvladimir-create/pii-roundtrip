"""Тесты движка на правилах (без загрузки моделей)."""

import pytest

from pii_roundtrip import vault
from pii_roundtrip.core import Engine, Session
from pii_roundtrip.detect import Models


@pytest.fixture(scope="module")
def eng():
    return Engine(Models(use_pii_guard=False, use_gliner=False))


def test_structured_and_consistent_labels(eng):
    t = "Карта 5536913745678900, повторно 5536 9137 4567 8900. СНИЛС 112-233-445 95."
    a, s = eng.anonymize(t, "ru")
    assert "5536" not in a and "112-233" not in a
    assert a.count("[CARD_1]") == 2 and "[CARD_2]" not in a
    assert s.mapping["[SNILS_1]"] == "112-233-445 95"


def test_uk_titled_names_firm_dob_and_restore(eng):
    t = "Dear Miss Rachael Rowe,\nWright, Middleton and Francis act for Mr Tom Hale, born 12/03/1980. NHS 943 476 5919."
    a, s = eng.anonymize(t, "uk")
    for v in ("Rachael", "Rowe", "Middleton", "Hale", "12/03/1980", "943 476 5919"):
        assert v not in a, v
    answer = "Dear [person_1], we confirm NHS [NHS_1] and [ ORG_1 ]. Regards, [DATE_OF_BIRTH_1]"
    r = eng.deanonymize(answer, s)
    assert "Rachael Rowe" in r and "943 476 5919" in r and "Wright, Middleton and Francis" in r


def test_russian_surname_forms_propagate(eng):
    # имя найдено один раз правилом ИП, остальные упоминания и падежи скрываются распространением
    t = "ИП Кузнецов Андрей. Договор с Кузнецовым подписан. Подпись: Кузнецова нет."
    a, _ = eng.anonymize(t, "ru")
    assert "Кузнецов" not in a


def test_session_roundtrip_through_vault(eng, tmp_path):
    a, s = eng.anonymize("Mr John Smith, NI AB 12 34 56 C", "uk")
    p = tmp_path / "doc.vault"
    vault.save(p, s, "secret-pass")
    s2 = vault.load(p, "secret-pass")
    assert s2.mapping == s.mapping
    assert eng.deanonymize("Hello [PERSON_1], NI [NINO_1].", s2) == "Hello John Smith, NI AB 12 34 56 C."
    with pytest.raises(Exception):
        vault.load(p, "wrong")


def test_unknown_labels_left_untouched(eng):
    s = Session("uk", {"[PERSON_1]": "John Smith"})
    assert eng.deanonymize("[PERSON_1] met [PERSON_9].", s) == "John Smith met [PERSON_9]."


# ---------- регрессии ----------


def test_two_parties_never_share_a_label(eng):
    a, s = eng.anonymize("Арендодатель ИП Кузнецов Андрей Петрович, арендатор ИП Сидорова Ольга Ивановна.", "ru")
    assert "[PERSON_1]" in a and "[PERSON_2]" in a
    a, s = eng.anonymize("Mr John Smith is the claimant. Mrs Mary Smith is his ex-wife. Mr J. Smith signed.", "uk")
    assert s.mapping["[PERSON_1]"] == "John Smith" and s.mapping["[PERSON_2]"] == "Mary Smith"
    assert a.count("[PERSON_1]") == 2  # «Mr J. Smith» совместим только с John


def test_female_surname_and_gender():
    from pii_roundtrip.names import parse

    n = parse("Ждановой Елизаветы Макаровны", "ru")
    assert n.display == "Жданова Елизавета Макаровна" and n.gender == "female"
    assert parse("ИВАНОВ ПЁТР СЕРГЕЕВИЧ", "ru").display == "Иванов Пётр Сергеевич"


def test_propagation_variants(eng):
    a, _ = eng.anonymize("BETWEEN: JOHN SMITH and Mr John Smith; Mr O'Brien met O’Brien.", "uk")
    assert "JOHN" not in a and "Brien" not in a
    a, _ = eng.anonymize("ИП Римский-Корсаков Николай. Подпись: Римским-Корсаковым Н.А. и Пётр, Петр.", "ru")
    assert "Корсаков" not in a and "Н.А." not in a


def test_common_words_not_overmasked(eng):
    a, _ = eng.anonymize("Mrs May Brown was admitted on 3 May 2024. Will the court agree?", "uk")
    assert "3 May 2024" in a and "Will the court" in a and "Brown" not in a


def test_label_like_text_is_not_replaced(eng):
    a, s = eng.anonymize("Form field PERSON_1 must be completed by Mr John Hale.", "uk")
    assert "PERSON_1 must" in a
    r = eng.deanonymize("Field PERSON_1 is for [PERSON_2]; variable person_2 stays.", s)
    assert r == "Field PERSON_1 is for John Hale; variable person_2 stays."


def test_session_follow_up_reuses_known_names(eng):
    a, s = eng.anonymize("Mr John Smith called.", "uk")
    a2, s = eng.anonymize("Follow-up: Smith rang again.", "uk", s)
    assert "Smith" not in a2 and "[PERSON_1]" in a2


def test_session_language_is_checked(eng):
    _, s = eng.anonymize("Mr John Smith", "uk")
    with pytest.raises(ValueError):
        eng.anonymize("Иванов", "ru", s)


def test_uk_initials_and_more_rules(eng):
    t = "Dr A Patel saw Mr J. Smith. D.O.B.: 12/03/1980. Born on 3rd March 1980. Sort code: 12-34-56, account number 12345678."
    a, _ = eng.anonymize(t, "uk")
    for v in ("Patel", "Smith", "12/03/1980", "3rd March 1980", "12-34-56", "12345678"):
        assert v not in a, v


def test_ru_more_rules(eng):
    t = "Паспорт серии 45 10 номер 123456, ДР 01.02.1980, тел. 79991234567, ООО Ромашка, telegram @ivanov_petr."
    a, _ = eng.anonymize(t, "ru")
    for v in ("123456", "01.02.1980", "79991234567", "Ромашка", "ivanov_petr"):
        assert v not in a, v


def test_checksum_typo_masked_with_context(eng):
    a, _ = eng.anonymize("Номер карты 5536 9137 4567 8901, СНИЛС 112-233-445 96.", "ru")
    assert "5536" not in a and "112-233" not in a


def test_vault_safety(eng, tmp_path):
    _, s = eng.anonymize("Mr John Smith", "uk")
    p = tmp_path / "v.vault"
    vault.save(p, s, "pw")
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    with pytest.raises(vault.VaultError):
        vault.save(p, s, "pw")  # без явного разрешения не перезаписывает
    with pytest.raises(vault.VaultError):
        vault.save(tmp_path / "x.vault", s, "")  # пустой пароль
    link = tmp_path / "link.vault"
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    link.symlink_to(victim)
    with pytest.raises(vault.VaultError):
        vault.save(link, s, "pw", overwrite=True)
    assert victim.read_text() == "keep"
    with pytest.raises(vault.VaultError, match="Wrong password"):
        vault.load(p, "wrong")
    p.write_bytes(p.read_bytes()[:20])
    with pytest.raises(vault.VaultError, match="damaged"):
        vault.load(p, "pw")


def test_cli_roundtrip(tmp_path, monkeypatch):
    from pii_roundtrip import cli
    from pii_roundtrip.detect import Models

    monkeypatch.setenv("PII_ROUNDTRIP_PASSWORD", "pw")
    monkeypatch.setattr(Models, "__init__", _rules_only_init)
    doc, clean, ans, out, v = (tmp_path / n for n in ("d.txt", "c.txt", "a.txt", "o.txt", "d.vault"))
    doc.write_text("Иванов Пётр Сергеевич, СНИЛС 112-233-445 95", encoding="cp1251")
    cli.main(["anonymize", "-l", "ru", "-i", str(doc), "-o", str(clean), "--vault", str(v), "--encoding", "cp1251"])
    assert "112-233" not in clean.read_text(encoding="utf-8")
    ans.write_text("СНИЛС [SNILS_1] подтверждён.", encoding="utf-8")
    cli.main(["restore", "-i", str(ans), "-o", str(out), "--vault", str(v)])
    assert out.read_text(encoding="utf-8") == "СНИЛС 112-233-445 95 подтверждён."
    assert oct(out.stat().st_mode & 0o777) == "0o600"


def _rules_only_init(self, **_):
    import threading

    self.use_pii_guard, self.use_gliner, self.offline = False, False, True
    self._pg = self._gl = None
    self._lock = threading.Lock()


def test_house_number_kept_with_street():
    from pii_roundtrip.detect import Span, _clean, merge

    text = "адрес офиса Воронеж, Плехановская 34"
    spans = [Span("ADDRESS", 12, 19, "pii_guard"), Span("ADDRESS", 21, 33, "pii_guard"), Span("ADDRESS", 34, 36, "pii_guard")]
    out = merge(_clean(text, spans, False), text)
    assert [(s.type, text[s.start : s.end]) for s in out] == [("ADDRESS", "Воронеж, Плехановская 34")]


def test_restore_label_with_llm_prefix(eng):
    s = Session("uk", {"[ORG_1]": "Acme Ltd", "[PERSON_2]": "John Smith"})
    assert eng.deanonymize("[ORG_NAME_ORG_1] and [PERSON_NAME_PERSON_2]", s) == "Acme Ltd and John Smith"


def test_hard_number_formats(eng):
    t = (
        "СНИЛС 112.233.445.96, карта 4276-1111-2222-3333, ИНН 771122233344, "
        "телефон семь девять один шесть один два три четыре пять шесть семь. "
    )
    a, _ = eng.anonymize(t, "ru")
    for v in ("112.233", "4276", "771122233344", "девять один шесть"):
        assert v not in a, v
    u = "IBAN GB82.WEST.1234.5698.7654.33, NI AB.12.34.56.C, NHS nine four three four seven six five nine one nine."
    a, _ = eng.anonymize(u, "uk")
    for v in ("GB82", "AB.12", "four three four"):
        assert v not in a, v


def test_amounts_and_dates_not_masked(eng):
    a, _ = eng.anonymize("Сумма 1 500 000 руб., дата 17.10.2025, договор № 762/26.", "ru")
    assert "1 500 000" in a and "17.10.2025" in a and "762/26" in a
