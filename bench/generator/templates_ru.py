"""Russian document templates: contract, certificate, letter, HR document, discharge summary."""

from __future__ import annotations

import datetime as dt

from bench.generator.persons import OrgRU, PersonRU, World
from bench.generator.render import Doc

MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def date_ru(d: dt.date, long: bool | None = None) -> str:
    if long:
        return f"«{d.day:02d}» {MONTHS[d.month - 1]} {d.year} г."
    return d.strftime("%d.%m.%Y")


def _doc_date(w: World) -> dt.date:
    return dt.date(2025, 1, 1) + dt.timedelta(days=w.rng.randint(0, 600))


# ---------- fragments ----------


def name(d: Doc, p: PersonRU, case: str = "nomn", form: str = "full") -> Doc:
    return d.e("PERSON", p.fio(case, form), canonical=p.fio("nomn", "full"), pid=p.pid)


def passport(d: Doc, p: PersonRU) -> Doc:
    d.t("паспорт гражданина РФ серия и номер ").e("PASSPORT_RU", p.passport, pid=p.pid)
    return d.t(f", выдан {date_ru(p.passport_issued)}")


def person_block(d: Doc, p: PersonRU, w: World, full: bool = True) -> Doc:
    """Line with an individual's details in an appendix or in the parties section."""
    name(d, p).t(", дата рождения ").e("DATE_OF_BIRTH", date_ru(p.dob), pid=p.pid).t(", ")
    passport(d, p).t(", СНИЛС ").e("SNILS", p.snils, pid=p.pid).t(", ИНН ").e("INN", p.inn, pid=p.pid)
    d.t(", адрес регистрации: ").e("ADDRESS", p.address, pid=p.pid)
    if full:
        d.t(", тел. ").e("PHONE", p.phone, pid=p.pid).t(", эл. почта ").e("EMAIL", p.email, pid=p.pid)
        d.t(", р/с ").e("BANK_ACCOUNT_RU", p.rs, pid=p.pid).t(f" в банке с БИК {p.bik}")
        d.t(", карта ").e("CARD", p.card, pid=p.pid)
    return d.t(".\n")


def org_block(d: Doc, o: OrgRU) -> Doc:
    d.e("ORG", o.name).t(", ИНН ").e("INN", o.inn).t(f", ОГРН {o.ogrn}, адрес: ").e("ADDRESS", o.address)
    d.t(", тел. ").e("PHONE", o.phone).t(", р/с ").e("BANK_ACCOUNT_RU", o.rs).t(f", БИК {o.bik}.\n")
    return d


def annex(d: Doc, w: World, title: str, k: int) -> list[PersonRU]:
    people = [w.person_ru() for _ in range(k)]
    d.t(f"\n{title}\n")
    for i, p in enumerate(people, 1):
        d.t(f"{i}. ")
        person_block(d, p, w)
    return people


QUASI_RU = (
    ("единственный ветеринарный врач в посёлке", ("Сосновка", "Верхние Луки", "Красный Бор", "Ильинское")),
    ("бывший главный тренер городской сборной по биатлону в городе", ("Кандалакша", "Белорецк", "Кудымкар")),
    ("победитель регионального конкурса «Учитель года» в", ("Ишиме", "Сарапуле", "Котласе")),
    ("единственная женщина-капитан речного буксира в порту", ("Самара", "Пермь", "Сызрань")),
)

DIAGNOSES_RU = (
    "болезнь Помпе (редкое наследственное заболевание)",
    "синдром Элерса–Данлоса, гипермобильный тип",
    "акромегалия, состояние после транссфеноидальной аденомэктомии",
    "миастения гравис, генерализованная форма",
)


def quasi(d: Doc, w: World, p: PersonRU) -> None:
    role, places = w.rng.choice(QUASI_RU)
    place = w.rng.choice(places)
    d.t("Примечание: ")
    d.t("заявитель — " if p.gender == "masc" else "заявительница — ")
    d.e("QUASI", f"{role} {place}", quasi=True, pid=p.pid).t(".\n")


# ---------- documents ----------


def contract(w: World, d: Doc) -> None:
    r = w.rng
    city = w.ru.city_name()
    when = _doc_date(w)
    seller, buyer = w.person_ru(), w.person_ru()
    org = w.org_ru()
    kind = r.choice(("купли-продажи транспортного средства", "аренды жилого помещения", "возмездного оказания услуг"))
    price = r.randint(30, 3000) * 1000
    d.t(f"ДОГОВОР {kind.upper()} № {r.randint(1, 999)}/{when.year % 100}\n\n")
    d.t(f"г. {city}\t\t\t\t{date_ru(when, long=True)}\n\n")
    d.t("Гражданин РФ " if seller.gender == "masc" else "Гражданка РФ ")
    name(d, seller).t(", ")
    passport(d, seller)
    d.t(", именуем" + ("ый" if seller.gender == "masc" else "ая") + " в дальнейшем «Сторона 1», с одной стороны, и ")
    name(d, buyer).t(", ")
    passport(d, buyer)
    d.t(", именуем" + ("ый" if buyer.gender == "masc" else "ая") + " в дальнейшем «Сторона 2», с другой стороны, ")
    d.t("заключили настоящий договор о нижеследующем.\n\n")
    d.t(f"1. Предмет договора определён в приложении № 1. Цена составляет {price:,} руб.".replace(",", " "))
    d.t(" Оплата производится на счёт Стороны 1 ")
    d.e("BANK_ACCOUNT_RU", seller.rs, pid=seller.pid).t(f" (БИК {seller.bik}) либо переводом на карту ")
    d.e("CARD", seller.card, pid=seller.pid).t(".\n")
    d.t("2. Расчёты сопровождает агент ").e("ORG", org.name).t(", ИНН ").e("INN", org.inn).t(".\n")
    d.t("3. Претензии направляются по адресу ")
    d.e("ADDRESS", buyer.address, pid=buyer.pid).t(" или на электронную почту ").e(
        "EMAIL", buyer.email, pid=buyer.pid
    ).t(".\n")
    d.t("4. Стороны подтверждают, что ")
    name(d, buyer, "nomn", "short").t(" ознакомлен" + ("" if buyer.gender == "masc" else "а") + " с условиями, а у ")
    name(d, seller, "gent", "short").t(" отсутствуют обременения.\n\n")
    d.t("Реквизиты и подписи сторон\n")
    d.t("Сторона 1: ")
    person_block(d, seller, w)
    d.t("Сторона 2: ")
    person_block(d, buyer, w)
    annex(d, w, "Приложение № 2. Лица, присутствовавшие при подписании", r.randint(1, 2))
    d.t("\nПодписи: ____________ ")
    name(d, seller, "nomn", "short_pre").t("   ____________ ")
    name(d, buyer, "nomn", "short_pre").t("\n")


def certificate(w: World, d: Doc) -> None:
    r = w.rng
    p, boss, org = w.person_ru(), w.person_ru(), w.org_ru()
    when = _doc_date(w)
    hired = when - dt.timedelta(days=r.randint(200, 4000))
    pos = r.choice(("ведущий инженер", "бухгалтер", "менеджер по продажам", "юрисконсульт", "врач-терапевт"))
    salary = r.randint(40, 300) * 1000
    d.t(f"СПРАВКА № {r.randint(10, 999)}\nот {date_ru(when)}\n\n")
    d.t("Выдана ")
    name(d, p, "datv").t(", ").e("DATE_OF_BIRTH", date_ru(p.dob) + " г.р.", pid=p.pid)
    d.t(", СНИЛС ").e("SNILS", p.snils, pid=p.pid).t(", ИНН ").e("INN", p.inn, pid=p.pid)
    d.t(", в том, что " + ("он" if p.gender == "masc" else "она"))
    d.t(" действительно работает в ").e("ORG", org.name).t(
        f" в должности «{pos}» с {date_ru(hired)} по настоящее время.\n"
    )
    d.t(f"Среднемесячная заработная плата за последние 6 месяцев составляет {salary:,} руб.".replace(",", " "))
    d.t(" Заработная плата перечисляется на счёт ").e("BANK_ACCOUNT_RU", p.rs, pid=p.pid)
    d.t(", карта ").e("CARD", p.card, pid=p.pid).t(".\n")
    d.t("Справка выдана для предъявления по месту требования. Адрес работника: ")
    d.e("ADDRESS", p.address, pid=p.pid).t(".\n")
    if r.random() < 0.4:
        quasi(d, w, p)
    annex(d, w, "Сведения о членах семьи работника (для расчёта вычетов)", r.randint(2, 3))
    d.t("\nГенеральный директор ____________ ")
    name(d, boss, "nomn", "short").t("\nИсп. ")
    name(d, w.person_ru(), "nomn", "short_space").t(", тел. ")
    d.e("PHONE", org.phone).t("\n")


def letter(w: World, d: Doc) -> None:
    r = w.rng
    sender, recipient = w.person_ru(), w.person_ru()
    org_from, org_to = w.org_ru(), w.org_ru()
    when = _doc_date(w)
    d.e("ORG", org_from.name).t("\n").e("ADDRESS", org_from.address).t("\nИНН ").e("INN", org_from.inn).t("\n\n")
    d.t(f"Исх. № {r.randint(100, 9999)} от {date_ru(when)}\n\n")
    d.t("Генеральному директору\n").e("ORG", org_to.name, canonical=org_to.name).t("\n")
    name(d, recipient, "datv", "short_pre").t("\n\n")
    d.t("Уважаем" + ("ый " if recipient.gender == "masc" else "ая "))
    name(d, recipient, "nomn", "first_middle").t("!\n\n")
    d.t("Направляем сведения о сотрудниках, командируемых на ваш объект. ")
    d.t("Ответственным назначен" + ("" if sender.gender == "masc" else "а") + " ")
    name(d, sender, "nomn", "full").t(", тел. ").e("PHONE", sender.phone, pid=sender.pid)
    d.t(", e-mail ").e("EMAIL", sender.email, pid=sender.pid).t(".\n")
    d.t("Просим оформить пропуска на имя ")
    names = [w.person_ru() for _ in range(2)]
    name(d, names[0], "gent").t(" и ")
    name(d, names[1], "gent").t(". Данные для оформления приведены ниже.\n")
    for p in names:
        person_block(d, p, w, full=r.random() < 0.5)
    d.t("Оплату счёта № ").t(str(r.randint(1, 500))).t(" просим произвести по реквизитам: ")
    org_block(d, org_from)
    d.t("Вопросы по оплате можно адресовать ")
    name(d, sender, "datv", "short").t(".\n")
    annex(d, w, "Приложение. Список сопровождающих лиц", r.randint(1, 2))
    d.t("\nС уважением,\n")
    name(d, w.person_ru(), "nomn", "short_pre").t("\n")


def hr_order(w: World, d: Doc) -> None:
    r = w.rng
    org = w.org_ru()
    when = _doc_date(w)
    emp, boss = w.person_ru(), w.person_ru()
    kind = r.choice(("hire", "vacation", "application"))
    if kind == "application":
        d.t("Генеральному директору ").e("ORG", org.name).t("\n")
        name(d, boss, "datv", "short_pre").t("\nот ")
        name(d, emp, "gent").t("\n\nЗАЯВЛЕНИЕ\n\n")
        d.t(
            f"Прошу предоставить мне ежегодный оплачиваемый отпуск с {date_ru(when)} продолжительностью {r.choice((14, 21, 28))} календарных дней. "
        )
        d.t("Отпускные прошу перечислить на карту ").e("CARD", emp.card, pid=emp.pid).t(".\n")
        d.t("Мои данные: ")
        person_block(d, emp, w)
    else:
        d.e("ORG", org.name).t("\n\nПРИКАЗ № ").t(f"{r.randint(1, 400)}-к от {date_ru(when)}\n")
        if kind == "hire":
            d.t("О приёме на работу\n\nПринять на работу ")
            name(d, emp, "accs").t(
                f" на должность «{r.choice(('кладовщик', 'программист', 'кассир', 'водитель'))}» с {date_ru(when)}"
            )
            d.t(f" с окладом {r.randint(35, 250) * 1000} руб.\n")
        else:
            d.t("О предоставлении отпуска\n\nПредоставить ")
            name(d, emp, "datv").t(f" ежегодный отпуск с {date_ru(when)}.\n")
        d.t("Основание: ").t("личное заявление ")
        name(d, emp, "gent", "short").t(", трудовой договор.\n")
        d.t("Сведения о работнике: ")
        person_block(d, emp, w)
        if r.random() < 0.4:
            quasi(d, w, emp)
    annex(d, w, "Лист ознакомления", r.randint(2, 3))
    d.t("\nРуководитель ____________ ")
    name(d, boss, "nomn", "short").t("\nС приказом ознакомлен(а) ____________ ")
    name(d, emp, "nomn", "short").t("\n")


def medical(w: World, d: Doc) -> None:
    r = w.rng
    p, doc_, rel = w.person_ru(), w.person_ru(), w.person_ru()
    clinic = r.choice(("ГБУЗ «Городская клиническая больница № ", "ГАУЗ «Областная больница № "))
    clinic = clinic + str(r.randint(1, 80)) + "»"
    adm = _doc_date(w)
    dis = adm + dt.timedelta(days=r.randint(3, 25))
    d.e("ORG", clinic).t("\n\nВЫПИСНОЙ ЭПИКРИЗ\nиз медицинской карты стационарного больного № ")
    d.t(f"{r.randint(1000, 99999)}\n\n")
    d.t("Пациент: " if p.gender == "masc" else "Пациентка: ")
    name(d, p).t(", ").e("DATE_OF_BIRTH", date_ru(p.dob), pid=p.pid).t(" г.р.\n")
    d.t("Адрес: ").e("ADDRESS", p.address, pid=p.pid).t("\nСНИЛС: ").e("SNILS", p.snils, pid=p.pid).t("\n")
    d.t("Документ: ")
    passport(d, p)
    d.t(f"\nНаходил{'ся' if p.gender == 'masc' else 'ась'} на лечении с {date_ru(adm)} по {date_ru(dis)}.\n")
    if r.random() < 0.5:
        d.t("Диагноз основной: ").e("QUASI", r.choice(DIAGNOSES_RU), quasi=True, pid=p.pid).t(".\n")
    else:
        d.t(
            f"Диагноз основной: {r.choice(('внебольничная пневмония', 'гипертоническая болезнь II стадии', 'острый холецистит'))}.\n"
        )
    d.t("Проведено лечение в полном объёме. Состояние при выписке удовлетворительное.\n")
    d.t("Рекомендовано наблюдение у терапевта по месту жительства. ")
    d.t("Контактное лицо: ")
    name(d, rel).t(", тел. ").e("PHONE", rel.phone, pid=rel.pid).t(".\n")
    d.t("Платные услуги оплачены картой ").e("CARD", p.card, pid=p.pid).t(", ИНН плательщика ").e(
        "INN", p.inn, pid=p.pid
    ).t(".\n")
    if r.random() < 0.4:
        quasi(d, w, p)
    annex(d, w, "Сведения о законных представителях и лицах, допущенных к информации", r.randint(1, 2))
    d.t("\nЛечащий врач ____________ ")
    name(d, doc_, "nomn", "short").t("\nЗав. отделением ____________ ")
    name(d, w.person_ru(), "nomn", "short").t("\n")


DOC_TYPES = {
    "contract": contract,
    "certificate": certificate,
    "letter": letter,
    "hr": hr_order,
    "medical": medical,
}
