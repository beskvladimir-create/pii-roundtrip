from eval.cycle import evaluate_answer
from runners.base import Runner, Span
from runners.placeholders import PlaceholderWrapper


class FakeDetector(Runner):
    name = "fake"

    def detect(self, text, lang):
        out = []
        for word, t in (("Smith", "PERSON"), ("943 476 5919", "NHS")):
            i = text.find(word)
            while i != -1:
                out.append(Span(t, i, i + len(word)))
                i = text.find(word, i + 1)
        return out


def test_placeholders_consistent_and_tolerant():
    w = PlaceholderWrapper(FakeDetector())
    anon, mapping = w.anonymize("Mr Smith, NHS 943 476 5919. Smith agreed.", "uk")
    assert anon == "Mr [PERSON_1], NHS [NHS_1]. [PERSON_1] agreed."
    assert w.deanonymize("Dear Mr person_1, your NHS number is [NHS_1].", mapping) == (
        "Dear Mr Smith, your NHS number is 943 476 5919."
    )


def test_evaluate_answer_counts():
    mapping = {"[PERSON_1]": "Smith", "[NHS_1]": "943 476 5919"}
    answer = "Dear [PERSON_1], about NHS_1 and [PERSON_7]."
    restored = "Dear Smith, about 943 476 5919 and [PERSON_7]."
    ev = evaluate_answer("placeholders", mapping, answer, restored, "uk")
    assert ev["labels_in_answer"] == 2 and ev["invented"] == 1  # [PERSON_7] выдумана нейросетью
    assert ev["exact"] == 1 and ev["altered"] == 1 and ev["altered_recoverable"] == 1
    assert ev["residual_after_restore"] == 0 and ev["values_lost"] == 0


def test_pii_guard_broken_tag_counts_as_own_label():
    mapping = {'<PII type="INN" id="4" />': "7707083893"}
    answer = 'ИНН <PII type="INN" id="4" », и ещё <PII type="INN" id="9" />'
    restored = "ИНН ****, и ещё ****"
    ev = evaluate_answer("pii_guard", mapping, answer, restored, "ru")
    assert ev["labels_in_answer"] == 1 and ev["invented"] == 1 and ev["values_lost"] == 1
