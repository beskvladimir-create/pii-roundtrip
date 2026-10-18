"""Word lists used by detection, entity resolution and restoration.

All language data that is not a regular expression lives here, so that the lists
are defined once and are easy to review.
"""

from __future__ import annotations

# Titles before a name. They are not part of the name and are not identifying.
TITLES = frozenset(
    {"mr", "mrs", "ms", "miss", "dr", "sir", "lady", "prof", "professor", "господин", "госпожа", "г-н", "г-жа"}
)
FEMALE_TITLES = frozenset({"mrs", "ms", "miss", "lady", "госпожа", "г-жа", "гражданка"})
MALE_TITLES = frozenset({"mr", "sir", "господин", "г-н", "гражданин"})

# Role words and form words that often stand next to a name but are not part of it.
ROLES = frozenset(
    {
        # Russian
        "ип",
        "гражданин",
        "гражданка",
        "истец",
        "истица",
        "ответчик",
        "ответчица",
        "заявитель",
        "заявительница",
        "арендатор",
        "арендодатель",
        "продавец",
        "покупатель",
        "заказчик",
        "исполнитель",
        "работник",
        "работодатель",
        "пациент",
        "пациентка",
        "свидетель",
        "представитель",
        "доверитель",
        "поверенный",
        "директор",
        "врач",
        "исп",
        "уважаемый",
        "уважаемая",
        "сторона",
        # English
        "claimant",
        "defendant",
        "respondent",
        "applicant",
        "appellant",
        "witness",
        "patient",
        "tenant",
        "landlord",
        "employee",
        "employer",
        "buyer",
        "seller",
        "party",
        "dear",
        "signed",
        # function words that can be captured together with a name
        "the",
        "and",
        "of",
    }
)

# Well-known names that are not personal data: countries and public bodies.
ALLOW = frozenset(
    {
        # labels of parties and fields that detectors take for names
        "сторона 1",
        "сторона 2",
        "party a",
        "party b",
        "огрн",
        "снилс",
        "инн",
        "кпп",
        "бик",
        "с бик",
        "серия",
        "адрес",
        "iban",
        "bank",
        "bank account",
        "registered office",
        "рф",
        "россия",
        "российская федерация",
        "ссср",
        "nhs",
        "hmrc",
        "uk",
        "united kingdom",
        "england",
        "scotland",
        "wales",
        "gb",
        "great britain",
        "dvla",
        "nhs england",
    }
)

# First names that are not searched for across the document because they coincide with
# months or common words ("May", "Will", "Вера"). Surnames are always searched for.
NOT_PROPAGATED = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "will",
        "bill",
        "mark",
        "grace",
        "hope",
        "faith",
        "rose",
        "joy",
        "dawn",
        "summer",
        "pat",
        "sue",
        "frank",
        "rich",
        "art",
        "dean",
        "ray",
        "вера",
        "надежда",
        "любовь",
        "роза",
        "лев",
        "мир",
        "слава",
    }
)

# Russian legal forms of organisations.
LEGAL_FORMS_RU = (
    "ООО",
    "ОАО",
    "ЗАО",
    "ПАО",
    "АО",
    "НАО",
    "НКО",
    "АНО",
    "ТОО",
    "ФГУП",
    "ГУП",
    "МУП",
    "ГБУЗ",
    "ГАУЗ",
    "ГБУ",
    "ГКУ",
    "ФГБУ",
    "МБУ",
    "МАУ",
)
# Regular expression for any of the legal forms: the longest first (ГБУЗ before ГБУ),
# as a whole word (АО must not match the start of "Аорта").
LEGAL_FORM_RU_RE = r"(?<![\w-])(?:" + "|".join(sorted(LEGAL_FORMS_RU, key=len, reverse=True)) + r")(?![\w-])"
