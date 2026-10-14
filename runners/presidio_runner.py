"""Presidio (data-privacy-stack/presidio), лучшая конфигурация по документации.

RU: spaCy ru_core_news_lg + собственные распознаватели паспорта, СНИЛС, ИНН,
расчётного счёта (Presidio не содержит русских распознавателей), встроенные
email, карта, IBAN, телефон с языком ru.
UK: spaCy en_core_web_lg + встроенные UK_NHS, UK_NINO, IBAN, карта, email,
телефон с supported_regions=["GB"] (обход ошибки с регионом "UK").
Порог уверенности низкий: полнота важнее точности.
"""

from __future__ import annotations

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    DateRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
    UkDrivingLicenceRecognizer,
    UkNinoRecognizer,
    UkPassportRecognizer,
    UkPostcodeRecognizer,
)

from generator import ids
from runners.base import Runner, Span, resolve_overlaps

SCORE_THRESHOLD = 0.3

TYPE_MAP = {
    "PERSON": "PERSON",
    "LOCATION": "ADDRESS",
    "ORGANIZATION": "ORG",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CARD",
    "IBAN_CODE": "IBAN",
    "UK_NHS": "NHS",
    "UK_NINO": "NINO",
    "UK_POSTCODE": "ADDRESS",
    "DATE_TIME": "DATE",
}

NLP_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "ru", "model_name": "ru_core_news_lg"},
        {"lang_code": "en", "model_name": "en_core_web_lg"},
    ],
    "ner_model_configuration": {
        "model_to_presidio_entity_mapping": {
            "PER": "PERSON",
            "PERSON": "PERSON",
            "LOC": "LOCATION",
            "GPE": "LOCATION",
            "FAC": "LOCATION",
            "ORG": "ORGANIZATION",
            "DATE": "DATE_TIME",
        },
        "low_confidence_score_multiplier": 0.4,
        "low_score_entity_names": [],
        "labels_to_ignore": [],
    },
}


class _ValidatedRecognizer(PatternRecognizer):
    def __init__(self, entity, patterns, context, validator):
        super().__init__(supported_entity=entity, patterns=patterns, context=context, supported_language="ru")
        self._validator = validator

    def validate_result(self, pattern_text: str):
        return self._validator(pattern_text) if self._validator else None


def ru_recognizers() -> list:
    return [
        _ValidatedRecognizer(
            "PASSPORT_RU",
            [Pattern("passport", r"(?<!\d)\d{2} ?\d{2}(?: ?№)? ?\d{6}(?!\d)", 0.4)],
            ["паспорт", "серия", "номер", "выдан"],
            None,
        ),
        _ValidatedRecognizer(
            "SNILS",
            [Pattern("snils", r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{2}(?!\d)", 0.4)],
            ["снилс", "страховой"],
            ids.is_valid_snils,
        ),
        _ValidatedRecognizer(
            "INN",
            [Pattern("inn", r"(?<!\d)(?:\d{12}|\d{10})(?!\d)", 0.3)],
            ["инн", "налогоплательщика"],
            ids.is_valid_inn,
        ),
        _ValidatedRecognizer(
            "BANK_ACCOUNT_RU",
            [Pattern("rs", r"(?<!\d)(?:4\d{19}|4\d{4}(?: \d{5}){3})(?!\d)", 0.4)],
            ["р/с", "счёт", "счет", "расчетный", "расчётный"],
            None,
        ),
        _ValidatedRecognizer(
            "CREDIT_CARD",
            [Pattern("mir", r"(?<!\d)220[0-4][- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)", 0.4)],
            ["карта", "карты", "картой", "карту"],
            ids.is_valid_card,
        ),
        DateRecognizer(supported_language="ru", context=["рождения", "г.р.", "дата"]),
        EmailRecognizer(supported_language="ru"),
        CreditCardRecognizer(supported_language="ru", context=["карта", "карты", "картой", "карту"]),
        IbanRecognizer(supported_language="ru"),
        PhoneRecognizer(supported_language="ru", supported_regions=["RU"], context=["тел", "телефон", "моб"]),
    ]


class PresidioRunner(Runner):
    name = "presidio"

    def __init__(self):
        nlp = NlpEngineProvider(nlp_configuration=NLP_CONFIG).create_engine()
        registry = RecognizerRegistry(supported_languages=["en", "ru"])
        registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)
        # телефон: регион GB вместо ошибочного "UK"
        registry.remove_recognizer("PhoneRecognizer")
        registry.add_recognizer(PhoneRecognizer(supported_language="en", supported_regions=["GB"]))
        # UK распознаватели, которые не входят в набор по умолчанию
        for cls in (UkNinoRecognizer, UkPostcodeRecognizer, UkPassportRecognizer, UkDrivingLicenceRecognizer):
            loaded = {type(r) for r in registry.recognizers}
            if cls not in loaded:
                registry.add_recognizer(cls())
        registry.add_recognizer(SpacyRecognizer(supported_language="ru", supported_entities=["PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME"]))
        for r in ru_recognizers():
            registry.add_recognizer(r)
        self.engine = AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en", "ru"])

    def config(self) -> dict:
        import presidio_analyzer

        return {
            "version": getattr(presidio_analyzer, "__version__", "2.2.364+"),
            "score_threshold": SCORE_THRESHOLD,
            "nlp": NLP_CONFIG,
            "ru_custom": ["PASSPORT_RU", "SNILS (checksum)", "INN (checksum)", "BANK_ACCOUNT_RU", "CARD Mir 2200-2204 (Luhn)", "DATE"],
            "uk_added": ["UK_NINO", "UK_POSTCODE", "UK_PASSPORT", "UK_DRIVING_LICENCE"],
            "uk_phone_regions": ["GB"],
        }

    def detect(self, text: str, lang: str) -> list[Span]:
        language = "ru" if lang == "ru" else "en"
        res = self.engine.analyze(text=text, language=language, score_threshold=SCORE_THRESHOLD)
        spans = [Span(TYPE_MAP.get(r.entity_type, r.entity_type), r.start, r.end) for r in res]
        return resolve_overlaps(spans)
