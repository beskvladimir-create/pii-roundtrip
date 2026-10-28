"""Tests of the rule-based engine (no models loaded)."""

import pytest

from pii_roundtrip import vault
from pii_roundtrip.core import Engine, Session
from pii_roundtrip.detect import Models
from pii_roundtrip.errors import VaultError


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
    a, s = eng.anonymize(t, "en-GB")
    for v in ("Rachael", "Rowe", "Middleton", "Hale", "12/03/1980", "943 476 5919"):
        assert v not in a, v
    answer = "Dear [person_1], we confirm NHS [NHS_1] and [ ORG_1 ]. Regards, [DATE_OF_BIRTH_1]"
    r = eng.deanonymize(answer, s)
    assert "Rachael Rowe" in r and "943 476 5919" in r and "Wright, Middleton and Francis" in r


def test_russian_surname_forms_propagate(eng):
    # the name is found once by the sole proprietor (ИП) rule; the other mentions and case forms
    # are hidden by propagation
    t = "ИП Кузнецов Андрей. Договор с Кузнецовым подписан. Подпись: Кузнецова нет."
    a, _ = eng.anonymize(t, "ru")
    assert "Кузнецов" not in a


def test_session_roundtrip_through_vault(eng, tmp_path):
    a, s = eng.anonymize("Mr John Smith, NI AB 12 34 56 C", "en-GB")
    p = tmp_path / "doc.vault"
    vault.save(p, s, "secret-pass")
    s2 = vault.load(p, "secret-pass")
    assert s2.mapping == s.mapping
    assert eng.deanonymize("Hello [PERSON_1], NI [NINO_1].", s2) == "Hello John Smith, NI AB 12 34 56 C."
    with pytest.raises(VaultError):
        vault.load(p, "wrong")


def test_unknown_labels_left_untouched(eng):
    s = Session("en-GB", {"[PERSON_1]": "John Smith"})
    assert eng.deanonymize("[PERSON_1] met [PERSON_9].", s) == "John Smith met [PERSON_9]."


# ---------- regressions ----------


def test_two_parties_never_share_a_label(eng):
    a, s = eng.anonymize("Арендодатель ИП Кузнецов Андрей Петрович, арендатор ИП Сидорова Ольга Ивановна.", "ru")
    assert "[PERSON_1]" in a and "[PERSON_2]" in a
    a, s = eng.anonymize("Mr John Smith is the claimant. Mrs Mary Smith is his ex-wife. Mr J. Smith signed.", "en-GB")
    assert s.mapping["[PERSON_1]"] == "John Smith" and s.mapping["[PERSON_2]"] == "Mary Smith"
    assert a.count("[PERSON_1]") == 2  # "Mr J. Smith" is compatible only with John


def test_female_surname_and_gender():
    from pii_roundtrip.names import parse

    n = parse("Ждановой Елизаветы Макаровны", "ru")
    assert n.display == "Жданова Елизавета Макаровна" and n.gender == "female"
    assert parse("ИВАНОВ ПЁТР СЕРГЕЕВИЧ", "ru").display == "Иванов Пётр Сергеевич"


def test_first_name_unknown_to_the_dictionary_is_kept():
    """ru-hr-022 of held-out set 5: «Милан» is not a known first name and was dropped from the
    stored value, so it was lost on restoration."""
    from pii_roundtrip.names import parse

    assert parse("Большакова Милан Андреевича", "ru").display == "Большаков Милан Андреевич"
    assert parse("Милан Большаков", "ru").display == "Большаков Милан"
    # held-out set 5 (found by the value fidelity check): a verb form taken into the name span
    assert parse("Выдана Крюковой Марине Никифоровне", "ru").display == "Крюкова Марина Никифоровна"
    assert parse("Лихачёва Карла Фомича", "ru").display == "Лихачёв Карл Фомич"
    assert parse("Ермакова Клавдия Фокича", "ru").display == "Ермаков Клавдий Фокич"


def test_propagation_variants(eng):
    a, _ = eng.anonymize("BETWEEN: JOHN SMITH and Mr John Smith; Mr O'Brien met O’Brien.", "en-GB")
    assert "JOHN" not in a and "Brien" not in a
    a, _ = eng.anonymize("ИП Римский-Корсаков Николай. Подпись: Римским-Корсаковым Н.А. и Пётр, Петр.", "ru")
    assert "Корсаков" not in a and "Н.А." not in a


def test_common_words_not_overmasked(eng):
    a, _ = eng.anonymize("Mrs May Brown was admitted on 3 May 2024. Will the court agree?", "en-GB")
    assert "3 May 2024" in a and "Will the court" in a and "Brown" not in a


def test_label_like_text_is_not_replaced(eng):
    a, s = eng.anonymize("Form field PERSON_1 must be completed by Mr John Hale.", "en-GB")
    assert "PERSON_1 must" in a
    r = eng.deanonymize("Field PERSON_1 is for [PERSON_2]; variable person_2 stays.", s)
    assert r == "Field PERSON_1 is for John Hale; variable person_2 stays."


def test_session_follow_up_reuses_known_names(eng):
    a, s = eng.anonymize("Mr John Smith called.", "en-GB")
    a2, s = eng.anonymize("Follow-up: Smith rang again.", "en-GB", s)
    assert "Smith" not in a2 and "[PERSON_1]" in a2


def test_session_language_is_checked(eng):
    _, s = eng.anonymize("Mr John Smith", "en-GB")
    with pytest.raises(ValueError):
        eng.anonymize("Иванов", "ru", s)


def test_uk_initials_and_more_rules(eng):
    t = "Dr A Patel saw Mr J. Smith. D.O.B.: 12/03/1980. Born on 3rd March 1980. Sort code: 12-34-56, account number 12345678."
    a, _ = eng.anonymize(t, "en-GB")
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
    _, s = eng.anonymize("Mr John Smith", "en-GB")
    p = tmp_path / "v.vault"
    vault.save(p, s, "pw")
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    with pytest.raises(vault.VaultError):
        vault.save(p, s, "pw")  # does not overwrite without explicit permission
    with pytest.raises(vault.VaultError):
        vault.save(tmp_path / "x.vault", s, "")  # empty password
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

    self.use_pii_guard, self.use_gliner, self.offline, self.device = False, False, True, None
    self._detectors = None
    self._lock = threading.Lock()


def test_house_number_kept_with_street():
    from pii_roundtrip.detect import Span, merge
    from pii_roundtrip.detect import clean as _clean

    text = "адрес офиса Воронеж, Плехановская 34"
    spans = [
        Span("ADDRESS", 12, 19, "pii_guard"),
        Span("ADDRESS", 21, 33, "pii_guard"),
        Span("ADDRESS", 34, 36, "pii_guard"),
    ]
    out = merge(_clean(text, spans, False), text)
    assert [(s.type, text[s.start : s.end]) for s in out] == [("ADDRESS", "Воронеж, Плехановская 34")]


def test_restore_label_with_llm_prefix(eng):
    s = Session("en-GB", {"[ORG_1]": "Acme Ltd", "[PERSON_2]": "John Smith"})
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
    a, _ = eng.anonymize(u, "en-GB")
    for v in ("GB82", "AB.12", "four three four"):
        assert v not in a, v


def test_amounts_and_dates_not_masked(eng):
    a, _ = eng.anonymize("Сумма 1 500 000 руб., дата 17.10.2025, договор № 762/26.", "ru")
    assert "1 500 000" in a and "17.10.2025" in a and "762/26" in a


@pytest.mark.parametrize("form", ["ООО", "ГКУ", "МБУ", "ФГБУ", "АНО", "ТОО", "МАУ"])
def test_org_name_repeated_without_legal_form_is_masked(eng, form):
    a, s = eng.anonymize(f"Договор с {form} «Восход». Представитель Восход подписал акт.", "ru")
    assert "Восход" not in a, a
    assert a.count("[ORG_1]") == 2 and "[ORG_2]" not in a


def test_legal_form_prefix_needs_a_word_boundary(eng):
    # "АО" must not be cut from the start of a name such as "Аорта"
    a, s = eng.anonymize("Договор с ООО «Аорта-Мед». Поставщик Аорта-Мед.", "ru")
    assert "Аорта" not in a, a
    assert s.mapping["[ORG_1]"] == "ООО «Аорта-Мед»"


@pytest.mark.parametrize(
    "text,lang,value",
    [
        ("Генеральному директору РАО «Субботин»\nА.О. Нкионовой\nот Егорова", "ru", "Нкионовой"),
        ("Подпись: Петров И.И.", "ru", "Петров"),
        ("Signed ____________ V. Rcie, Line Manager", "en-GB", "Rcie"),
        ("Miss Edwards confirms that L. Talyor has disclosed all known defects.", "en-GB", "Talyor"),
        ("Patient: LAWRENCE, Maureen\nDOB: 06/02/1986", "en-GB", "Maureen"),
        ("Johnston and Sons\n\nHWOARTH, Lee raised a formal grievance.", "en-GB", "HWOARTH"),
        ("Adams-O'Brien\n\nANNUAL LEAVE REQUEST\n\nEmily Stephens requests leave.", "en-GB", "Adams"),
        ("Генеральному директору\nЗагорский трубный завод\nГ.Ф. Игнатову", "ru", "Загорский"),
        ("в том, что он действительно работает в Группа О'кей в должности «бухгалтер»", "ru", "О'кей"),
    ],
)
def test_context_rules_mask_names_and_orgs(eng, text, lang, value):
    a, _ = eng.anonymize(text, lang)
    assert value not in a, a


@pytest.mark.parametrize(
    "text",
    [
        "See Appendix A. The terms apply.",
        "Plan B. Please call.",
        "NOTE, Please read carefully.",
        "Option C. Total due.",
    ],
)
def test_context_rules_do_not_mask_ordinary_words(eng, text):
    a, s = eng.anonymize(text, "en-GB")
    assert a == text, a


def test_spans_from_a_detector_are_kept_inside_the_text():
    from pii_roundtrip.detect import Span

    class Overshooting:
        name, languages = "fake", frozenset({"ru"})

        def detect(self, text, lang):
            return [
                Span("PERSON", len(text) - 8, len(text) + 1, "fake"),
                Span("PERSON", len(text) + 2, len(text) + 5, "fake"),
            ]

    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [Overshooting()]
    text = "Подпись: Д.В. Медвеедв\n"
    a, s = Engine(models).anonymize(text, "ru")
    assert all(0 <= sp.start < sp.end <= len(text) for sp in Engine(models).spans(text, "ru"))
    assert "Медвеедв" not in a and a.endswith("\n")


@pytest.mark.parametrize(
    "text,lang,rest",
    [
        ("Адрес: г. Тула (Тульск.), ул. Ленина, д. 5/7 к. 9, 300041. Далее", "ru", ["Тульск", "5/7", "300041"]),
        ("Address: 4 Conor Motorway, Julialand BH3 3WX.", "en-GB", ["Conor", "BH3"]),
        ("Поставщик: ИП «Фомина, Елисеев и Савин».", "ru", ["ИП", "Фомина"]),
    ],
)
def test_address_and_trade_name_are_masked_whole(eng, text, lang, rest, monkeypatch):
    from pii_roundtrip.detect import Span

    class Town:
        name, languages = "fake", frozenset({"ru", "en-GB"})

        def detect(self, text, lang):
            out = []
            for word in ("г. Тула", "ул. Ленина", "Julialand"):
                i = text.find(word)
                if i >= 0:
                    out.append(Span("ADDRESS", i, i + len(word), "fake"))
            return out

    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [Town()]
    a, _ = Engine(models).anonymize(text, lang)
    for w in rest:
        assert w not in a, a


def test_abbreviation_before_a_name_is_not_propagated():
    from pii_roundtrip.detect import Span

    t = "Гражданин РФ Трофимов Нестор Андреевич, паспорт гражданина РФ, далее Сторона 1."

    class Name:
        name, languages = "fake", frozenset({"ru"})

        def detect(self, text, lang):
            i = text.find("Нестор")
            return [Span("PERSON", i, i + len("Нестор Андреевич"), "fake")]

    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [Name()]
    a, s = Engine(models).anonymize(t, "ru")
    assert a.count("РФ") == 2, a
    assert "Трофимов" not in a


def test_labels_and_registry_numbers_are_not_masked(eng):
    a, _ = eng.anonymize("р/с 40817810099910004312 в ПАО Сбербанк, БИК 044525225, к/с 30101810400000000225.", "ru")
    assert "044525225" in a and "40817810099910004312" not in a, a
    a, _ = eng.anonymize("Acme Widgets Ltd (company number 06323239), registered office 1 High St.", "en-GB")
    assert "06323239" in a, a
    a, _ = eng.anonymize("Passport number 123456789 issued in 2019.", "en-GB")
    assert "123456789" not in a, a


@pytest.mark.parametrize(
    "text,lang,value",
    [
        ("4. Mrs Walsh confirms that T. uLcas has disclosed all known defects.", "en-GB", "uLcas"),
        ("4. Mrs aHll confirms that A. Martin has disclosed all known defects.", "en-GB", "aHll"),
        ("The hearing was chaired by Leon Ford.\nEmployee details", "en-GB", "Ford"),
        ("Our point of contact is Glen Bailey, on +44 20 7946 0099.", "en-GB", "Bailey"),
        ("please arrange site passes for Glen Wright and Owen Cook. Their details", "en-GB", "Cook"),
        ("2. Marytn Taylor, born 09/01/1972, NI number", "en-GB", "Marytn"),
        ("5 July 2026\n\nMiss Syliva Moore\nPrice LLC\n574 Carter Underpass, New John", "en-GB", "Price"),
        ("6 August 2026\n\nMr Ross Harvey\nThomas and Sons\n72 Brown Manor", "en-GB", "Thomas"),
        ("27 August 2025\n\nMr Stewart Edwards\nNash-King\n4 Denise Glen", "en-GB", "Nash"),
        ("Генеральному директору Ямал СПГ\nФ.Т. Кошелеву\nот Цветкова", "ru", "Ямал"),
        ("СК Согласие\n\nПРИКАЗ № 359-к от 03.04.2026", "ru", "Согласие"),
    ],
)
def test_names_and_orgs_in_document_structure_are_masked(eng, text, lang, value):
    a, _ = eng.anonymize(text, lang)
    assert value not in a, a


def test_implausible_model_spans_are_dropped():
    from pii_roundtrip.detect import Span

    class Noisy:
        name, languages = "fake", frozenset({"ru"})

        def detect(self, text, lang):
            out = []
            for word, t in (
                ("паспорт", "ID"),
                ("CVC", "ID"),
                ("налоговой", "ORG"),
                ("плз", "PERSON"),
                ("валера", "PERSON"),
            ):
                i = text.find(word)
                out.append(Span(t, i, i + len(word), "fake"))
            return out

    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [Noisy()]
    t = "паспорт и CVC отправил в налоговой, плз проверь, валера"
    a, _ = Engine(models).anonymize(t, "ru")
    assert a == "паспорт и CVC отправил в налоговой, плз проверь, [PERSON_1]", a


def test_cli_errors_are_messages_not_tracebacks(tmp_path, monkeypatch):
    import io

    from pii_roundtrip import cli

    monkeypatch.setenv("PII_ROUNDTRIP_PASSWORD", "x")
    with pytest.raises(SystemExit, match="Cannot read"):
        cli.main(["anonymize", "-l", "ru", "-i", str(tmp_path / "nope.txt"), "--vault", str(tmp_path / "v")])
    monkeypatch.delenv("PII_ROUNDTRIP_PASSWORD")
    doc = tmp_path / "doc.txt"
    doc.write_text("Иванов Пётр Сергеевич", encoding="utf-8")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("getpass.getpass", lambda *_a, **_k: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(SystemExit, match="No password"):
        cli.main(["anonymize", "-l", "ru", "-i", str(doc), "--vault", str(tmp_path / "v")])


def test_restore_label_with_a_lost_bracket(eng):
    # synthetic examples: a model drops one bracket of a placeholder
    s = Session("en-GB", {"[ORG_1]": "Acme Ltd", "[PERSON_2]": "John Smith"})
    assert eng.deanonymize("Signed for ORG_1] by [PERSON_2.", s) == "Signed for Acme Ltd by John Smith."
    assert eng.deanonymize("[ORG_1 and PERSON_2] agreed", s) == "Acme Ltd and John Smith agreed"


def test_restore_label_with_words_before_it_in_the_brackets(eng):
    s = Session("en-GB", {"[ORG_1]": "Acme Ltd", "[PERSON_2]": "John Smith"})
    assert eng.deanonymize("Party: [Company: ORG_1], [name PERSON_2]", s) == "Party: Company: Acme Ltd, name John Smith"
    assert eng.deanonymize("[Org Name ORG_1]", s) == "Org Name Acme Ltd"


def test_lenient_forms_leave_other_text_alone(eng):
    s = Session("en-GB", {"[ORG_1]": "Acme Ltd"})
    s.reserved.add("ORG_2")
    text = "See [note 1], item ORG_2], [ORG_9 and ref_1]."
    assert eng.deanonymize(text, s) == text


def test_restore_ru_label_with_a_lost_bracket(eng):
    s = Session("ru", {"[ORG_1]": "ООО «Восход»", "[INN_1]": "7707083893"})
    assert eng.deanonymize("Договор с ORG_1], ИНН [INN_1.", s) == "Договор с ООО «Восход», ИНН 7707083893."


def test_restore_ru_two_names_without_a_space(eng):
    """ru-letter-145 and ru-letter-129 of held-out set 5: a model wrote two name placeholders
    without a space, and the surname of the second name was lost on restoration."""
    from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

    if not PiiGuardInflector.available():
        pytest.skip("pii-guard is not installed")
    s = Session("ru", {"[PERSON_2]": "Гущин Олег Петрович", "[PERSON_3]": "Рыбаков Аверкий"})
    s.genders = {"[PERSON_2]": "male", "[PERSON_3]": "male"}
    out = eng.deanonymize("Письмо руководителя организации [PERSON_2][PERSON_3] получено.", s)
    assert "Рыбаков" in out and "Гущин" in out, out


class _Fake:
    """A detector that returns the given fragments with the given types."""

    name, languages = "fake", frozenset({"ru", "en-GB"})

    def __init__(self, parts):
        self.parts = parts

    def detect(self, text, lang):
        from pii_roundtrip.detect import Span

        out = []
        for etype, word in self.parts:
            i = text.find(word)
            if i >= 0:
                out.append(Span(etype, i, i + len(word), "fake"))
        return out


@pytest.mark.parametrize(
    "text,lang,parts,rest",
    [
        # held-out set 5: the parts of an address and an organisation left visible by 0.3
        (
            "Адрес: с. Березники, пер. Комарова, д. 221 стр. 698, 721980.",
            "ru",
            [("ADDRESS", "Березники, пер. Комарова, д. 221 стр")],
            ["698", "721980"],
        ),
        (
            "Адрес: п. Соликамск, ш. Луначарского, д. 486 к. 50, 247671.",
            "ru",
            [("ADDRESS", "Соликамск, ш. Луначарского, д. 486 к.")],
            [" 50", "247671"],
        ),
        (
            "Адрес: д. Быково (метеост.), ш. Монтажников, д. 345 к. 52, 319324.",
            "ru",
            [("ADDRESS", "д. Быково"), ("ADDRESS", "ш. Монтажников, д. 345 к. 52, 319324")],
            ["метеост", "Монтажников"],
        ),
        (
            "Адрес: г. Карабулак, ш. 9 мая, д. 6/4 к. 75, 689383.",
            "ru",
            [("ADDRESS", "Карабулак")],
            ["мая", "6/4", "689383"],
        ),
        (
            "Адрес: г. Приозерск, алл. Марта 8, д. 327 стр. 468, 061293.",
            "ru",
            [("ADDRESS", "Приозерск, алл. Марта")],
            ["Марта", " 8,", "468"],
        ),
        ("Поставщик: Компания Адамас, тел. не указан.", "ru", [("ORG", "Адамас")], ["Компания", "Адамас"]),
        ("Покупатель: Hoff (Домашний интерьер), Москва.", "ru", [("ORG", "Hoff")], ["Домашний"]),
        ("Работодатель: ГКНПЦ им. М.В.Хруничева.", "ru", [("ORG", "ГКНПЦ")], ["им.", "Хруничева"]),
        ("Юрист: Лобанова и партнеры.", "ru", [("PERSON", "Лобанова")], ["партнеры"]),
        ("Address: 45 Harding Dam, West Mathewhaven B7 9LL.", "en-GB", [], ["Harding", "Mathewhaven", "B7"]),
        (
            "Address: 840 Carter Road, Lake Georgia W5G 3NE.",
            "en-GB",
            [("ADDRESS", "840 Carter Road"), ("ADDRESS", "W5G 3NE")],
            ["Lake Georgia"],
        ),
        ("Admitted to General Hospital, Shirleyborough on 3 May.", "en-GB", [], ["Shirleyborough", "General"]),
        ("Seen at University Hospital Stephanietown.", "en-GB", [], ["Stephanietown"]),
        ("Solicitors: Chadwick, O'Brien and Stokes.", "en-GB", [], ["Chadwick", "Brien", "Stokes"]),
    ],
)
def test_addresses_and_orgs_masked_whole(text, lang, parts, rest):
    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [_Fake(parts)]
    a, _ = Engine(models).anonymize(text, lang)
    for w in rest:
        assert w not in a, a


@pytest.mark.parametrize(
    "text,lang,kept",
    [
        ("ООО «Ромашка» (далее Исполнитель) обязуется", "ru", "(далее Исполнитель)"),
        ("Hospital Number: 12345", "en-GB", "Hospital Number"),
        ("Адрес: г. Тула, ул. Ленина, д. 5. Срок 9 мая.", "ru", "Срок 9 мая"),
    ],
)
def test_address_and_org_extensions_stop_in_time(text, lang, kept):
    models = Models(use_pii_guard=False, use_gliner=False)
    models._detectors = [_Fake([("ADDRESS", "г. Тула"), ("ORG", "ООО «Ромашка»")])]
    a, _ = Engine(models).anonymize(text, lang)
    assert kept in a, a


@pytest.mark.parametrize(
    "value,left,display",
    [
        # held-out set 6, names stored wrongly by 0.4 (results/stored_names_review.holdout6.json)
        ("Абрамов Болеслав", "", "Абрамов Болеслав"),  # not "Абрамы"
        ("Игнатов Пров Филиппович", "", "Игнатов Пров Филиппович"),
        ("Кириллов Давыд Гурьевич", "", "Кириллов Давыд Гурьевич"),  # not read as a first name
        ("Копыловой А.В.", "", "Копылова А.В."),  # "-ой" decides the gender
        ("Т.Т. Исаевой", "", "Исаева Т.Т."),
        ("Субботина П.Х.", "в лице ", "Субботин П.Х."),  # genitive after "в лице"
        ("Кононова Л.Г.", "Основание: личное заявление ", "Кононов Л.Г."),
        ("Кононова Л.Г.", "Руководитель ____________ ", "Кононова Л.Г."),  # signature: nominative
        ("Субботина П.Х.", "Стороны подтверждают, что ", "Субботина П.Х."),  # undecided: as written
        ("Полякову А.А.", "ООО «Ромашка»\n", "Поляков А.А."),  # dative in a letter's address
        ("Полякову А.А.", "Приказываю принять ", "Полякова А.А."),  # accusative after a verb
        ("Зимину Софии Эдуардовне", "Выдана ", "Зимина София Эдуардовна"),
        ("Ситниковой Натальи Константиновны", "", "Ситникова Наталья Константиновна"),
        ("Ситникова Нинель Павловна", "", "Ситникова Нинель Павловна"),  # not dropped as an adjective
        ("Лидии Петровой", "", "Петрова Лидия"),
        ("Сидоровой Анне", "", "Сидорова Анна"),
        ("Горбачеав А.В.", "", "Горбачеав А.В."),  # a typo of the text kept, initials kept
        # held-out set 7, names stored wrongly by 0.5 (results/stored_names_review.holdout7.json)
        ("Зиновьев Тимофей Ильич", "", "Зиновьев Тимофей Ильич"),  # not "Тимофя"
        ("Воронцов Фадей Дорофеевич", "", "Воронцов Фадей Дорофеевич"),
        ("Селиверстов Данила Трифонович", "", "Селиверстов Данила Трифонович"),  # not "Данил"
        ("Белоусову Фортунату Венедиктовичу", "", "Белоусов Фортунат Венедиктович"),
        ("Никитину Милану Артёмовичу", "", "Никитин Милан Артёмович"),  # a man, from the patronymic
        ("Лихачёвой Алины Владимировны", "", "Лихачёва Алина Владимировна"),
        ("Сафонова Силы Филимоновича", "", "Сафонов Сила Филимонович"),
        ("Жуков Милован Венедиктович", "", "Жуков Милован Венедиктович"),  # not dropped as a verb form
        ("Сафонов Варлаам Валерьянович", "", "Сафонов Варлаам Валерьянович"),
        ("Михеев Милен Адрианович", "", "Михеев Милен Адрианович"),
        ("Сазонов Сидор Елисевеич", "", "Сазонов Сидор Елисевеич"),  # a misspelt patronymic kept
        ("Ивановой Анне Сергеевне", "", "Иванова Анна Сергеевна"),
        ("Сидоровым Ильёй Петровичем", "", "Сидоров Илья Петрович"),
    ],
)
def test_russian_names_stored_in_the_right_form(value, left, display):
    from pii_roundtrip.names import parse

    assert parse(value, "ru", left).display == display


def test_restore_ru_rare_first_name_through_a_proxy(eng):
    """Held-out set 6: pii-guard inflected the first name «Пров» as «Провым» and «Прва»."""
    from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

    if not PiiGuardInflector.available():
        pytest.skip("pii-guard is not installed")
    s = Session("ru", {"[PERSON_1]": "Щербаков Пров Тимурович", "[PERSON_2]": "Иванов Пётр Сергеевич"})
    s.genders = {"[PERSON_1]": "male", "[PERSON_2]": "male"}
    out = eng.deanonymize("Документы для [PERSON_1] и [PERSON_2] готовы. Мы говорили о [PERSON_1].", s)
    assert "Щербакова Прова Тимуровича" in out and "Иванова Петра Сергеевича" in out, out
    assert "Щербакове Прове Тимуровиче" in out and "Прва" not in out and "Провым" not in out, out


@pytest.mark.parametrize(
    "value,case,expected",
    [
        # held-out set 7: pii-guard put these surnames in the plural ("Харитоны", "Максимы", "Ильины")
        ("Харитонов Дмитрий Измаилович", "nomn", "Харитонов Дмитрий Измаилович"),
        ("Харитонов Дмитрий Измаилович", "ablt", "Харитоновым Дмитрием Измаиловичем"),
        ("Максимов Юрий Тимурович", "datv", "Максимову Юрию Тимуровичу"),
        ("Ильин Ю.М.", "ablt", "Ильиным Ю.М."),
        ("Зимина Ираида Павловна", "gent", "Зиминой Ираиды Павловны"),
        ("Коновалова Анжела Ждановна", "ablt", "Коноваловой Анжелой Ждановной"),  # not "Коноваловым Анжелом"
        ("Громова София Степановна", "gent", "Громовой Софии Степановны"),
        ("Щербаков Пров Тимурович", "ablt", "Щербаковым Провом Тимуровичем"),
        ("Иванов Пётр Сергеевич", "gent", "Иванова Петра Сергеевича"),
        ("Ефимов Николай Ильич", "ablt", "Ефимовым Николаем Ильичом"),
        ("Пестова Наина Львовна", "gent", "Пестовой Наины Львовны"),
        ("Сафонов Сила Филимонович", "datv", "Сафонову Силе Филимоновичу"),
        ("Шевчук Тарас Богданович", "gent", "Шевчука Тараса Богдановича"),
        ("Римский-Корсаков Николай Андреевич", "datv", "Римскому-Корсакову Николаю Андреевичу"),
        ("Ирина", "ablt", "Ириной"),
    ],
)
def test_russian_name_inflected_in_the_singular(value, case, expected):
    from pii_roundtrip.names import inflect_name_tokens

    assert inflect_name_tokens(value.split(), case) == expected


def test_restore_ru_surname_not_in_the_plural(eng):
    """Held-out set 7: "1. Харитоны Дмитрий Измаилович" in the nominative, "Федотами Ф.Ю."."""
    from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

    if not PiiGuardInflector.available():
        pytest.skip("pii-guard is not installed")
    s = Session("ru", {"[PERSON_1]": "Харитонов Дмитрий Измаилович", "[PERSON_2]": "Федотов Ф.Ю."})
    s.genders = {"[PERSON_1]": "male", "[PERSON_2]": "male"}
    out = eng.deanonymize("Данные:\n1. [PERSON_1] (дата рождения 01.01.1990)\nПодписан директором [PERSON_2].", s)
    assert "1. Харитонов Дмитрий Измаилович" in out and "директором Федотовым Ф.Ю." in out, out


@pytest.mark.parametrize(
    "answer,expected",
    [
        # held-out set 7: pii-guard's parse put these names in the wrong case
        ("Уважаемый [PERSON_1],", "Уважаемый Силина Г.Э.,"),
        ("Кому: [PERSON_1]\nОт: ООО", "Кому: Силиной Г.Э.\nОт: ООО"),
        ("*   **ФИО:** [PERSON_1]\n", "*   **ФИО:** Силина Г.Э.\n"),
        ("2. [PERSON_1] (дата рождения", "2. Силина Г.Э. (дата рождения"),
        ("С уважением,\n[PERSON_1]", "С уважением,\nСилина Г.Э."),
        ("Приказ подписан директором [PERSON_1].", "Приказ подписан директором Силиной Г.Э."),  # the syntax decides
    ],
)
def test_restore_ru_case_from_the_words_before_the_name(eng, answer, expected):
    from pii_roundtrip.adapters.pii_guard import PiiGuardInflector

    if not PiiGuardInflector.available():
        pytest.skip("pii-guard is not installed")
    s = Session("ru", {"[PERSON_1]": "Силина Г.Э."})
    s.genders = {"[PERSON_1]": "female"}
    assert eng.deanonymize(answer, s) == expected
