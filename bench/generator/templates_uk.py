"""British English document templates: contract, certificate, letter, HR document, discharge summary."""

from __future__ import annotations

import datetime as dt

from bench.generator.persons import OrgUK, PersonUK, World
from bench.generator.render import Doc


def date_uk(d: dt.date, long: bool = False) -> str:
    return f"{d.day} {d.strftime('%B %Y')}" if long else d.strftime("%d/%m/%Y")


def _doc_date(w: World) -> dt.date:
    return dt.date(2025, 1, 1) + dt.timedelta(days=w.rng.randint(0, 600))


def name(d: Doc, p: PersonUK, form: str = "full") -> Doc:
    return d.e("PERSON", p.name(form), canonical=p.name("full"), pid=p.pid)


def person_block(d: Doc, p: PersonUK, full: bool = True) -> Doc:
    name(d, p).t(", born ").e("DATE_OF_BIRTH", date_uk(p.dob), pid=p.pid)
    d.t(", NI number ").e("NINO", p.nino, pid=p.pid).t(", NHS number ").e("NHS", p.nhs, pid=p.pid)
    d.t(", of ").e("ADDRESS", p.address, pid=p.pid)
    if full:
        d.t(", tel. ").e("PHONE", p.phone, pid=p.pid).t(", email ").e("EMAIL", p.email, pid=p.pid)
        d.t(", bank account IBAN ").e("IBAN", p.iban, pid=p.pid).t(", card ").e("CARD", p.card, pid=p.pid)
    return d.t(".\n")


def org_block(d: Doc, o: OrgUK) -> Doc:
    d.e("ORG", o.name).t(f" (company number {o.company_no}), registered office ").e("ADDRESS", o.address)
    return d.t(", tel. ").e("PHONE", o.phone).t(".\n")


def schedule(d: Doc, w: World, title: str, k: int) -> list[PersonUK]:
    people = [w.person_uk() for _ in range(k)]
    d.t(f"\n{title}\n")
    for i, p in enumerate(people, 1):
        d.t(f"{i}. ")
        person_block(d, p)
    return people


QUASI_UK = (
    "the only farrier practising on the Isle of",
    "a former captain of the county women's cricket team in",
    "the sole Gaelic-speaking pharmacist in",
    "the longest-serving lifeboat coxswain in",
)
QUASI_PLACES = ("Coll", "Tiree", "Lerwick", "Stornoway", "Barra", "Unst")

DIAGNOSES_UK = (
    "Pompe disease (late-onset), confirmed by enzyme assay",
    "hypermobile Ehlers-Danlos syndrome",
    "acromegaly, post transsphenoidal surgery",
    "generalised myasthenia gravis",
)


def quasi(d: Doc, w: World, p: PersonUK) -> None:
    d.t("Note: the applicant is ")
    d.e("QUASI", f"{w.rng.choice(QUASI_UK)} {w.rng.choice(QUASI_PLACES)}", quasi=True, pid=p.pid).t(".\n")


def contract(w: World, d: Doc) -> None:
    r = w.rng
    a, b = w.person_uk(), w.person_uk()
    agent = w.org_uk()
    when = _doc_date(w)
    kind = r.choice(
        (
            "ASSURED SHORTHOLD TENANCY AGREEMENT",
            "AGREEMENT FOR THE SALE OF A MOTOR VEHICLE",
            "CONSULTANCY SERVICES AGREEMENT",
        )
    )
    price = r.randint(5, 900) * 100
    d.t(f"{kind}\n\nThis agreement is dated {date_uk(when, long=True)} and is made between:\n\n")
    d.t("(1) ")
    name(d, a, "titled_full").t(" of ").e("ADDRESS", a.address, pid=a.pid).t(' ("Party A"); and\n')
    d.t("(2) ")
    name(d, b, "titled_full").t(" of ").e("ADDRESS", b.address, pid=b.pid).t(' ("Party B").\n\n')
    d.t(f"1. The consideration is £{price:,}, payable to Party A's account ")
    d.e("IBAN", a.iban, pid=a.pid).t(" or by card ending in the details held on file (card ").e(
        "CARD", a.card, pid=a.pid
    ).t(").\n")
    d.t("2. Payments are administered by ")
    org_block(d, agent)
    d.t("3. Notices shall be sent to ").e("EMAIL", b.email, pid=b.pid).t(" or by post to Party B's address above.\n")
    d.t("4. ")
    name(d, b, "titled").t(" confirms that ")
    name(d, a, "initial").t(" has disclosed all known defects.\n\n")
    d.t("Identification of the parties\n")
    d.t("Party A: ")
    person_block(d, a)
    d.t("Party B: ")
    person_block(d, b)
    schedule(d, w, "Schedule 2. Witnesses", r.randint(1, 2))
    d.t("\nSigned: ____________ ")
    name(d, a).t("    ____________ ")
    name(d, b).t("\n")


def certificate(w: World, d: Doc) -> None:
    r = w.rng
    p, hr = w.person_uk(), w.person_uk()
    org = w.org_uk()
    when = _doc_date(w)
    since = when - dt.timedelta(days=r.randint(200, 4000))
    role = r.choice(("Senior Software Engineer", "Payroll Officer", "Staff Nurse", "Paralegal", "Warehouse Supervisor"))
    d.t("TO WHOM IT MAY CONCERN\n\nConfirmation of Employment\n\n")
    d.t("We confirm that ")
    name(d, p, "titled_full").t(", date of birth ").e("DATE_OF_BIRTH", date_uk(p.dob), pid=p.pid)
    d.t(", National Insurance number ").e("NINO", p.nino, pid=p.pid)
    d.t(", has been employed by ").e("ORG", org.name).t(f" as {role} since {date_uk(since, long=True)}.\n")
    d.t(f"Gross annual salary: £{r.randint(22, 95) * 1000:,}. Salary is paid monthly into account ")
    d.e("IBAN", p.iban, pid=p.pid).t(".\n")
    d.t("The employee's registered address is ").e("ADDRESS", p.address, pid=p.pid).t(".\n")
    if r.random() < 0.4:
        quasi(d, w, p)
    schedule(d, w, "Dependants recorded for benefits purposes", r.randint(2, 3))
    d.t("\nYours faithfully,\n")
    name(d, hr).t("\nHR Manager, ").e("ORG", org.name).t(", tel. ").e("PHONE", org.phone).t("\n")


def letter(w: World, d: Doc) -> None:
    r = w.rng
    sender, recipient = w.person_uk(), w.person_uk()
    org_from, org_to = w.org_uk(), w.org_uk()
    when = _doc_date(w)
    d.e("ORG", org_from.name).t("\n").e("ADDRESS", org_from.address).t("\n\n")
    d.t(f"{date_uk(when, long=True)}\n\n")
    name(d, recipient, "titled_full").t("\n").e("ORG", org_to.name).t("\n").e("ADDRESS", org_to.address).t("\n\n")
    d.t("Dear ")
    name(d, recipient, "titled").t(",\n\n")
    d.t(f"Re: site access for our engineers, ref. {r.randint(1000, 99999)}\n\n")
    d.t("Further to our call, please arrange site passes for ")
    staff = [w.person_uk() for _ in range(2)]
    name(d, staff[0]).t(" and ")
    name(d, staff[1]).t(". Their details are set out below.\n")
    for p in staff:
        person_block(d, p, full=r.random() < 0.5)
    d.t("Our point of contact is ")
    name(d, sender).t(", on ").e("PHONE", sender.phone, pid=sender.pid).t(" or ").e(
        "EMAIL", sender.email, pid=sender.pid
    ).t(".\n")
    d.t("Please settle invoice ").t(str(r.randint(100, 9999))).t(" to the account below:\n")
    org_block(d, org_from)
    schedule(d, w, "Appendix: accompanying persons", r.randint(1, 2))
    d.t("\nYours sincerely,\n\n")
    name(d, sender, "initial").t("\n")


def hr_doc(w: World, d: Doc) -> None:
    r = w.rng
    org = w.org_uk()
    emp, mgr = w.person_uk(), w.person_uk()
    when = _doc_date(w)
    kind = r.choice(("offer", "grievance", "leave"))
    d.e("ORG", org.name).t("\n\n")
    if kind == "offer":
        d.t("OFFER OF EMPLOYMENT\n\nDear ")
        name(d, emp, "first").t(",\n\nWe are pleased to offer you the position of ")
        d.t(
            f"{r.choice(('Data Analyst', 'Receptionist', 'HGV Driver', 'Accounts Assistant'))}, starting on {date_uk(when, long=True)}"
        )
        d.t(f", at a salary of £{r.randint(21, 70) * 1000:,} per annum.\n")
    elif kind == "grievance":
        d.t("GRIEVANCE HEARING OUTCOME\n\n")
        name(d, emp, "formal").t(f" raised a formal grievance on {date_uk(when)} concerning ")
        name(d, mgr, "titled").t(". The hearing was chaired by ")
        name(d, w.person_uk()).t(".\n")
    else:
        d.t("ANNUAL LEAVE REQUEST\n\n")
        name(d, emp).t(f" requests {r.choice((5, 10, 15))} days of annual leave from {date_uk(when)}.\n")
    d.t("Employee details for payroll: ")
    person_block(d, emp)
    if r.random() < 0.4:
        quasi(d, w, emp)
    schedule(d, w, "Distribution list", r.randint(2, 3))
    d.t("\nSigned ____________ ")
    name(d, mgr, "initial").t(", Line Manager\n")


def medical(w: World, d: Doc) -> None:
    r = w.rng
    p, gp, nok = w.person_uk(), w.person_uk(), w.person_uk()
    trust = r.choice(("Royal Infirmary of ", "University Hospital ", "General Hospital, ")) + w.uk.city()
    adm = _doc_date(w)
    dis = adm + dt.timedelta(days=r.randint(2, 20))
    d.e("ORG", trust).t("\n\nDISCHARGE SUMMARY\n\n")
    d.t("Patient: ")
    name(d, p, "formal").t("\nDOB: ").e("DATE_OF_BIRTH", date_uk(p.dob), pid=p.pid)
    d.t("\nNHS No: ").e("NHS", p.nhs, pid=p.pid).t("\nAddress: ").e("ADDRESS", p.address, pid=p.pid).t("\n")
    d.t(f"Admitted: {date_uk(adm)}    Discharged: {date_uk(dis)}\n\n")
    if r.random() < 0.5:
        d.t("Primary diagnosis: ").e("QUASI", r.choice(DIAGNOSES_UK), quasi=True, pid=p.pid).t(".\n")
    else:
        d.t(
            f"Primary diagnosis: {r.choice(('community-acquired pneumonia', 'cellulitis of the left leg', 'acute cholecystitis'))}.\n"
        )
    d.t("Follow-up with GP ")
    name(d, gp, "titled").t(" in two weeks. Next of kin: ")
    name(d, nok).t(", tel. ").e("PHONE", nok.phone, pid=nok.pid).t(".\n")
    d.t("Private prescription charges paid by card ").e("CARD", p.card, pid=p.pid)
    d.t("; NI number for the exemption claim ").e("NINO", p.nino, pid=p.pid).t(".\n")
    if r.random() < 0.4:
        quasi(d, w, p)
    schedule(d, w, "Persons authorised to receive information", r.randint(1, 2))
    d.t("\nDischarging clinician: ")
    name(d, w.person_uk(), "titled").t("\n")


DOC_TYPES = {
    "contract": contract,
    "certificate": certificate,
    "letter": letter,
    "hr": hr_doc,
    "medical": medical,
}
