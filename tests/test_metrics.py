from bench.eval import metrics


def test_wilson():
    lo, hi = metrics.wilson(100, 100)
    assert lo > 0.96 and hi > 0.9999
    lo, hi = metrics.wilson(98, 100)
    assert lo < 0.99 < hi  # 98 из 100 не отличить от 99%


def doc(text, ents, lang="ru"):
    return {"id": "t", "lang": lang, "text": text, "entities": ents}


def ent(text, value, etype, canonical=None):
    s = text.index(value)
    e = {"type": etype, "start": s, "end": s + len(value), "value": value}
    if canonical:
        e["canonical"] = canonical
    return e


def test_masked_any_type_and_loose_edges():
    text = "СНИЛС 112-233-445 95 выдан"
    g = ent(text, "112-233-445 95", "SNILS")
    acc = metrics.new_acc()
    # предсказан другим типом и разбит на две части: значение всё равно скрыто
    preds = [
        {"type": "INN", "start": g["start"], "end": g["start"] + 11},
        {"type": "PHONE", "start": g["start"] + 12, "end": g["end"]},
    ]
    metrics.score_doc(doc(text, [g]), preds, acc)
    assert acc["SNILS"]["masked"] == 1 and acc["SNILS"]["partial"] == 0


def test_service_words_and_initials_not_required():
    text = "Адрес: г. Тула, ул. Ленина, д. 5. Подпись: Иванов И.И."
    a = ent(text, "г. Тула, ул. Ленина, д. 5", "ADDRESS")
    p = ent(text, "Иванов И.И.", "PERSON")
    preds = [
        {"type": "ADDRESS", "start": text.index("Тула"), "end": text.index("Тула") + 4},
        {"type": "ADDRESS", "start": text.index("Ленина"), "end": text.index("Ленина") + 6},
        {"type": "ADDRESS", "start": text.index("5."), "end": text.index("5.") + 1},
        {"type": "PERSON", "start": text.index("Иванов"), "end": text.index("Иванов") + 6},
    ]
    acc = metrics.new_acc()
    metrics.score_doc(doc(text, [a, p]), preds, acc)
    assert acc["ADDRESS"]["masked"] == 1 and acc["PERSON"]["masked"] == 1
    # а без номера дома адрес не скрыт
    acc = metrics.new_acc()
    metrics.score_doc(doc(text, [a]), preds[:2], acc)
    assert acc["ADDRESS"]["masked"] == 0


def test_leak_number_with_other_separators():
    text = "СНИЛС 112-233-445 95, повторно 11223344595."
    g = ent(text, "112-233-445 95", "SNILS", canonical="11223344595")
    d = doc(text, [g])
    masked = metrics.mask_text(text, [{"type": "SNILS", "start": g["start"], "end": g["end"]}])
    assert metrics.leaked_values(d, masked) == ["112-233-445 95"]


def test_leak_surname_in_other_case():
    text = "Договор с Ивановым Петром Сергеевичем. Подпись: Иванова П.С."
    g = ent(text, "Ивановым Петром Сергеевичем", "PERSON", canonical="Иванов Пётр Сергеевич")
    d = doc(text, [g])
    masked = metrics.mask_text(text, [{"type": "PERSON", "start": g["start"], "end": g["end"]}])
    assert metrics.leaked_values(d, masked)  # «Иванова» осталась в подписи


def test_no_leak_when_masked():
    text = "Договор с Ивановым Петром Сергеевичем."
    g = ent(text, "Ивановым Петром Сергеевичем", "PERSON", canonical="Иванов Пётр Сергеевич")
    masked = metrics.mask_text(text, [{"type": "PERSON", "start": g["start"], "end": g["end"]}])
    assert metrics.leaked_values(doc(text, [g]), masked) == []


def test_leak_number_after_latin_word():
    for text, value, canon, t in [
        ("NHS number 943 476 5919 issued", "943 476 5919", "9434765919", "NHS"),
        ("IBAN GB82 WEST 1234 5698 7654 32 ok", "GB82 WEST 1234 5698 7654 32", "GB82WEST12345698765432", "IBAN"),
        ("NI number AB 12 34 56 C here", "AB 12 34 56 C", "AB123456C", "NINO"),
    ]:
        d = doc(text, [ent(text, value, t, canonical=canon)], lang="uk")
        assert metrics.leaked_values(d, text) == [value], text


def test_number_not_glued_to_neighbours():
    text = "ref 12 9434765919 0"
    d = doc(text, [ent(text, "9434765919", "NHS", canonical="9434765919")], lang="uk")
    masked = text.replace("9434765919", "[PII]")
    assert metrics.leaked_values(d, masked) == []


def test_person_leak_is_case_sensitive():
    text = "Will Smith said they will come."
    g = ent(text, "Will Smith", "PERSON")
    masked = metrics.mask_text(text, [{"type": "PERSON", "start": 0, "end": 10}])
    assert metrics.leaked_values(doc(text, [g], lang="uk"), masked) == []


def test_mask_text_uses_union_of_overlaps():
    text = "John Smith of 12 Baker Street"
    masked = metrics.mask_text(
        text, [{"type": "PERSON", "start": 0, "end": 10}, {"type": "ADDRESS", "start": 5, "end": 29}]
    )
    assert "John" not in masked and "Baker" not in masked


def test_leak_number_in_words():
    text = "СНИЛС один два три - четыре пять шесть"
    g = ent(text, "один два три - четыре пять шесть", "SNILS", canonical="123456")
    assert metrics.leaked_values(doc(text, [g]), text)


def test_masking_precision_counts_fragments_and_characters():
    text = "Иванов пришёл в понедельник."
    g = ent(text, "Иванов", "PERSON")
    acc = metrics.new_acc()
    preds = [
        {"type": "PERSON", "start": 0, "end": 6},
        {"type": "DATE", "start": text.index("понедельник"), "end": len(text) - 1},
    ]
    metrics.score_doc(doc(text, [g]), preds, acc)
    s = metrics.summarize(acc, 0, 1, "ru")
    assert s["precision_any"] == 0.5
    assert s["precision_chars"] == 6 / (6 + len("понедельник"))
    assert s["per_type"].keys() == {"PERSON", "DATE"}


def test_name_that_is_also_an_ordinary_word_in_the_text_is_not_a_leak():
    text = "Dated 8 June 2025. Passes for June Gibbons."
    g = ent(text, "June Gibbons", "PERSON")
    masked = metrics.mask_text(text, [{"type": "PERSON", "start": g["start"], "end": g["end"]}])
    assert metrics.leaked_values(doc(text, [g], lang="uk"), masked) == []
    # but the first name left next to the masked surname is still a leak
    masked = metrics.mask_text(text, [{"type": "PERSON", "start": g["start"] + 5, "end": g["end"]}])
    assert metrics.leaked_values(doc(text, [g], lang="uk"), masked) == ["June Gibbons"]


def test_number_written_with_dots_counts_as_a_leak():
    from bench.eval import metrics

    doc = {
        "lang": "ru",
        "text": "Карта 5223.2630.1023.1078 клиента.",
        "entities": [
            {"type": "CARD", "start": 6, "end": 25, "value": "5223.2630.1023.1078", "canonical": "5223263010231078"}
        ],
    }
    assert metrics.leaked_values(doc, doc["text"]) == ["5223.2630.1023.1078"]
    assert metrics.leaked_values(doc, "Карта [CARD_1] клиента.") == []
    # a longer number that only contains the digits is not this number
    assert metrics.leaked_values(doc, "Код 95223.2630.1023.10789.") == []


def test_number_with_an_ellipsis_still_counts_as_a_leak():
    from bench.eval import metrics

    doc = {
        "lang": "ru",
        "text": "Паспорт 45...12...123456.",
        "entities": [
            {"type": "PASSPORT_RU", "start": 8, "end": 24, "value": "45...12...123456", "canonical": "45...12...123456"}
        ],
    }
    assert metrics.leaked_values(doc, doc["text"]) == ["45...12...123456"]


def test_number_inside_a_longer_number_is_not_a_leak():
    from bench.eval import metrics

    doc = {
        "lang": "ru",
        "text": "Паспорт 123456.",
        "entities": [{"type": "PASSPORT_RU", "start": 8, "end": 14, "value": "123456", "canonical": "123456"}],
    }
    assert metrics.leaked_values(doc, "Паспорт [PASSPORT_RU_1], СНИЛС 123 - 456 - 789 01.") == []
    assert metrics.leaked_values(doc, "Паспорт 123 - 456.") == ["123456"]
