"""Interface texts in Russian and English. The language follows the system locale."""

from __future__ import annotations

import locale
import sys

TEXTS = {
    "ru": {
        "app": "pii-roundtrip",
        "drop_title": "Перетащите документ",
        "drop_release": "Отпустите, чтобы очистить",
        "drop_sub": "Документ очистим, а ответ нейросети с метками вернём в исходный вид.\nWord, PDF или текст. Или вставьте ⌘V",
        "choose_file": "Выбрать файл",
        "recent": "НЕДАВНИЕ",
        "maker": "© {year} {maker} · версия {version}",
        "maker_short": "© {year} {maker}",
        "terms_link": "Условия",
        "contact": "Связаться",
        "terms_title": "Условия использования",
        "terms_body": [
            "pii-roundtrip выпускает индивидуальный предприниматель Бескоровайный Владимир Андреевич (Besk Tech, besk.tech). Программа бесплатна и распространяется с открытым кодом по лицензии Apache 2.0. Эти условия дополняют лицензию и не ограничивают права, которые она вам даёт.",
            "Программа работает только на этом компьютере и сама ничего не отправляет в интернет. Besk Tech не получает, не хранит и не обрабатывает ваши документы и данные. Если вы работаете с чужими персональными данными, их оператором остаётесь вы или ваша организация.",
            "Программа находит и заменяет личные данные автоматически и может пропустить часть из них. В нашей опубликованной проверке хотя бы одно значение осталось в 0,2% российских и 0,9% британских тестовых документов. Косвенные сведения (диагноз, должность, обстоятельства дела) метки не скрывают. Проверьте текст сами перед отправкой.",
            "Решение передать текст в нейросеть или кому-либо ещё принимаете вы. Текст с метками обычно остаётся персональными данными. Убедитесь, что у вас есть законное основание, что условия выбранного сервиса это допускают и что вы соблюдаете правила передачи данных за рубеж: в России статью 12 Федерального закона № 152-ФЗ, в Великобритании правила UK GDPR. Для медицинских сведений, врачебной, адвокатской и иной тайны правила строже.",
            "Программа не проверяет, верен ли ответ нейросети. Проверьте восстановленный текст, прежде чем на него полагаться.",
            "Таблица соответствий меток и данных хранится на этом Mac в зашифрованном виде, ключ находится в Связке ключей macOS. Её защита зависит от защиты вашей учётной записи. Если удалить хранилище или ключ, исходные значения восстановить будет нельзя.",
            "Программа предоставляется «как есть», без гарантий, в том числе того, что она подойдёт для вашей задачи или будет работать без ошибок. Besk Tech не отвечает за убытки от использования программы. Это не ограничивает ответственность за умышленное нарушение, обман, причинение вреда жизни или здоровью и не лишает вас прав потребителя, которые по закону нельзя ограничить.",
            "Если вы живёте в России, применяется право Российской Федерации, если в Великобритании, право Англии и Уэльса, в остальных случаях право Российской Федерации. Обязательные правила о защите потребителей страны, где вы живёте, применяются в любом случае, и вы вправе обратиться в суд по месту жительства.",
            "Новая версия программы может содержать новые условия: программа покажет их при первом запуске. Вопросы направляйте на admin@besk.tech.",
        ],
        "accept": "Принимаю",
        "quit": "Выйти",
        "close": "Закрыть",
        "about": "О программе pii-roundtrip",
        "about_body": "Обезличивание документов перед отправкой в нейросеть. Работает на этом компьютере, без интернета.",
        "license": "Открытый код, лицензия Apache 2.0",
        "notices": "Лицензии компонентов",
        "trust": "Программа ничего не отправляет в сеть.",
        "working": "Ищу личные данные…",
        "preparing": "Подготовка моделей, около минуты",
        "loading_models": "Загружаю модели распознавания в память этого Mac, около минуты. Документ можно перетащить уже сейчас.",
        "models_ready": "Модели готовы. Перетащите документ.",
        "copy": "Скопировать",
        "copied": "Скопировано",
        "save_docx": "Сохранить…",
        "f_docx": "Word, с оформлением исходного файла",
        "f_docx_plain": "Word",
        "f_pdf": "PDF, упрощённая вёрстка",
        "f_pdf_layout": "PDF, с вёрсткой исходного файла",
        "f_txt": "Текст",
        "unplaced": "Страницы этого PDF перерисованы картинкой после очистки, и места меток на них не определить. Ответ сохранён с простой вёрсткой, все значения восстановлены. Чтобы сохранить оформление, попросите нейросеть вернуть результат в Word или новым PDF с текстом.",
        "unsafe": "В частях файла, которые программа не может очистить, остались данные. Сохранено без исходного оформления.",
        "masked": "Скрыто {n}: {summary}",
        "restored_n": "Возвращено значений: {n}",
        "paste_answer": "Когда нейросеть ответит, скопируйте её ответ и нажмите",
        "paste_btn": "Вставить ответ  ⌘V",
        "next_send": "Отправьте файл в нейросеть. Когда она ответит, скопируйте ответ и нажмите",
        "saved": "Сохранено: {name}",
        "reveal": "Показать в Finder",
        "paste_next": "Следующее сообщение в этот диалог: скопируйте и нажмите",
        "added": "Добавлено в диалог «{title}».",
        "as_new": "Как новый документ",
        "unknown": "Меток {labels} нет в этом документе, они оставлены как есть.",
        "request": "Запрос",
        "answer": "Ответ",
        "which": "К какому документу этот ответ?",
        "which_body": "Метки из этого ответа подходят к нескольким документам. Выберите тот, который вы очищали и отправляли в нейросеть: настоящие данные вернутся из него.",
        "match": "совпало меток {n} из {m}",
        "restore": "Восстановить",
        "cancel": "Отмена",
        "lang_ru": "Русский",
        "lang_en": "Британский английский",
        "err_scan_title": "В этом PDF нет текста",
        "err_scan_body": "Похоже, это скан. Откройте файл с текстовым слоем или вставьте текст.",
        "err_format_title": "Этот формат не поддерживается",
        "err_format_body": "Подойдут Word, PDF и текст.",
        "err_other_title": "Не удалось открыть файл",
        "choose_other": "Выбрать другой файл",
        "nothing": "Личные данные не найдены. Прочитайте текст перед отправкой.",
        "rules_only": "Модели недоступны: имена без обращения могут быть пропущены.",
        "today": "сегодня",
        "yesterday": "вчера",
        "delete": "Удалить",
        "delete_all": "Удалить все",
        "delete_one_title": "Удалить «{title}»?",
        "delete_all_title": "Удалить все документы ({n})?",
        "delete_body": "Будут стёрты сохранённые тексты и связь меток с настоящими данными. После этого ответ нейросети к этим документам восстановить не получится. Исходные файлы на диске не затрагиваются.",
        "menu_file": "Файл",
        "menu_new": "Загрузить документ",
        "menu_open": "Открыть…",
        "menu_recent": "Открыть недавние",
        "menu_copy_all": "Скопировать всё",
        "migrate": "Введите прежний пароль хранилища один раз. Дальше программа будет обходиться без него.",
        "migrate_title": "Переход на ключ в Связке ключей",
        "wrong": "Неверный пароль",
        "types": {
            "PERSON": "имена",
            "ORG": "организации",
            "ADDRESS": "адреса",
            "PHONE": "телефоны",
            "EMAIL": "почта",
            "DATE_OF_BIRTH": "даты рождения",
        },
        "numbers": "номера",
        "constellations": {
            "ursa": "Большая Медведица",
            "lock": "Созвездие Замка",
            "label": "Созвездие Метки",
            "besk": "Besk Tech · 2026",
        },
    },
    "en": {
        "app": "pii-roundtrip",
        "drop_title": "Drop a document",
        "drop_release": "Release to clean",
        "drop_sub": "We clean a document and bring an AI answer with labels back to the original.\nWord, PDF or text. Or paste ⌘V",
        "choose_file": "Choose file",
        "recent": "RECENT",
        "maker": "© {year} {maker} · version {version}",
        "maker_short": "© {year} {maker}",
        "terms_link": "Terms",
        "contact": "Contact",
        "terms_title": "Terms of use",
        "terms_body": [
            "pii-roundtrip is made by Vladimir Beskorovainyi, trading as Besk Tech (besk.tech). It is free, open-source software under the Apache License 2.0. These terms add to the licence and do not limit the rights it gives you.",
            "The app runs only on this computer and sends nothing to the internet. Besk Tech does not receive, store or process your documents or data. If you handle other people's personal data, you or your organisation remain the controller of that data.",
            "The app finds and replaces personal data automatically and may miss some. In our published test, at least one original value remained in 0.2% of Russian and 0.9% of UK test documents. Labels do not hide indirect details such as a diagnosis, a job title or the facts of a case. Check the text yourself before you send it.",
            "You decide whether to share the text with an AI service or anyone else. Text with labels usually remains personal data. Make sure you have a lawful basis, that the service's terms allow it, and that you follow the UK GDPR rules on sending personal data outside the United Kingdom. Stricter rules apply to health data and to confidential, legally privileged or other protected information.",
            "The app does not check whether the AI's answer is correct. Check the restored text before you rely on it.",
            "The table linking labels to real values is stored encrypted on this Mac, with its key in the macOS Keychain. Its protection depends on the security of your Mac user account. If the vault or the key is deleted, the original values cannot be restored.",
            'The app is provided "as is", without warranties, including that it will suit your purpose or work without errors. Besk Tech is not liable for losses arising from use of the app. Nothing in these terms limits liability for fraud, deliberate breach, or death or personal injury caused by negligence, or affects your statutory rights as a consumer.',
            "These terms are governed by the law of England and Wales. Mandatory consumer protection rules of the country where you live apply in any case, and you may bring a claim in the courts where you live, including in Scotland or Northern Ireland.",
            "A new version of the app may come with new terms, which it will show at first launch. Questions: admin@besk.tech.",
        ],
        "accept": "I accept",
        "quit": "Quit",
        "close": "Close",
        "about": "About pii-roundtrip",
        "about_body": "Removes personal data from documents before they go to an AI tool. Runs on this computer, offline.",
        "license": "Open source, Apache License 2.0",
        "notices": "Third-party licences",
        "trust": "The app sends nothing over the network.",
        "working": "Looking for personal data…",
        "preparing": "Preparing the models, about a minute",
        "loading_models": "Loading the recognition models into this Mac\u2019s memory, about a minute. You can drop a document now.",
        "models_ready": "Models ready. Drop a document.",
        "copy": "Copy",
        "copied": "Copied",
        "save_docx": "Save…",
        "f_docx": "Word, with the original formatting",
        "f_docx_plain": "Word",
        "f_pdf": "PDF, simple layout",
        "f_pdf_layout": "PDF, with the original layout",
        "f_txt": "Text",
        "unplaced": "The pages of this PDF were redrawn as pictures after cleaning, so where the labels are cannot be told. The answer was saved with a simple layout, with every value restored. To keep the formatting, ask the AI to return the result as a Word file or a new PDF with text.",
        "unsafe": "Some parts of the file the app cannot clean still contain data. Saved without the original formatting.",
        "masked": "Masked {n}: {summary}",
        "restored_n": "{n} values restored",
        "paste_answer": "When the AI answers, copy its answer and press",
        "paste_btn": "Paste answer  ⌘V",
        "next_send": "Send the file to the AI. When it answers, copy the answer and press",
        "saved": "Saved: {name}",
        "reveal": "Show in Finder",
        "paste_next": "Next message in this conversation: copy it and press",
        "added": "Added to the “{title}” conversation.",
        "as_new": "As a new document",
        "unknown": "{labels} are not in this document and were left as they are.",
        "request": "Request",
        "answer": "Answer",
        "which": "Which document is this answer for?",
        "which_body": "The labels in this answer fit several documents. Choose the one you cleaned and sent to the AI: the real values come back from it.",
        "match": "{n} of {m} labels match",
        "restore": "Restore",
        "cancel": "Cancel",
        "lang_ru": "Russian",
        "lang_en": "UK English",
        "err_scan_title": "This PDF has no text",
        "err_scan_body": "It looks like a scan. Open a file with a text layer or paste the text.",
        "err_format_title": "This format is not supported",
        "err_format_body": "Use Word, PDF or text.",
        "err_other_title": "The file could not be opened",
        "choose_other": "Choose another file",
        "nothing": "No personal data found. Read the text before sending it.",
        "rules_only": "Models unavailable: names without a title may be missed.",
        "today": "today",
        "yesterday": "yesterday",
        "delete": "Delete",
        "delete_all": "Delete all",
        "delete_one_title": "Delete \u201c{title}\u201d?",
        "delete_all_title": "Delete all documents ({n})?",
        "delete_body": "The saved texts and the link between labels and real values will be erased. After that, AI answers to these documents can no longer be restored. Your original files on disk are not affected.",
        "menu_file": "File",
        "menu_new": "Load a document",
        "menu_open": "Open…",
        "menu_recent": "Open Recent",
        "menu_copy_all": "Copy all",
        "migrate": "Enter your previous vault password once. After that the app will not need it.",
        "migrate_title": "Moving to a Keychain key",
        "wrong": "Wrong password",
        "types": {
            "PERSON": "names",
            "ORG": "organisations",
            "ADDRESS": "addresses",
            "PHONE": "phones",
            "EMAIL": "emails",
            "DATE_OF_BIRTH": "dates of birth",
        },
        "numbers": "numbers",
        "constellations": {
            "ursa": "Ursa Major",
            "lock": "The Padlock",
            "label": "The Label",
            "besk": "Besk Tech · 2026",
        },
    },
}


def ui_language() -> str:
    loc = (locale.getlocale()[0] or "").lower()
    return "ru" if loc.startswith("ru") else "en"


def detect_language(text: str) -> str:
    """ru if Cyrillic letters dominate, otherwise en-GB."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c in "ёЁ")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    return "ru" if cyr >= lat else "en-GB"


def mixed(text: str) -> bool:
    """True if the minority script makes up more than 15% of the letters."""
    cyr = sum(1 for c in text if "а" <= c.lower() <= "я" or c in "ёЁ")
    lat = sum(1 for c in text if "a" <= c.lower() <= "z")
    total = cyr + lat
    return bool(total) and min(cyr, lat) / total > 0.15


def summary(mapping: dict[str, str], t: dict) -> str:
    """'имена 2 · номера 4' from the session mapping."""
    counts: dict[str, int] = {}
    for label in mapping:
        kind = label.strip("[]").rsplit("_", 1)[0]
        name = t["types"].get(kind, t["numbers"])
        counts[name] = counts.get(name, 0) + 1
    return " · ".join(f"{k} {v}" for k, v in counts.items())


# On Windows the same texts, without the Mac words: the key is in Windows Credential Manager.
if sys.platform == "win32":
    _WINDOWS = {
        "ru": [
            ("⌘V", "Ctrl+V"),
            ("на этом Mac", "на этом компьютере"),
            ("в Связке ключей macOS", "в диспетчере учётных данных Windows"),
            ("в память этого Mac", "в память этого компьютера"),
            ("в Finder", "в Проводнике"),
            ("в Связке ключей", "в диспетчере учётных данных"),
        ],
        "en": [
            ("⌘V", "Ctrl+V"),
            ("on this Mac", "on this computer"),
            ("in the macOS Keychain", "in Windows Credential Manager"),
            ("your Mac user account", "your Windows user account"),
            ("this Mac\u2019s memory", "this computer\u2019s memory"),
            ("in Finder", "in File Explorer"),
            ("a Keychain key", "a Credential Manager key"),
        ],
    }

    def _for_windows(value, pairs):
        if isinstance(value, str):
            for a, b in pairs:
                value = value.replace(a, b)
            return value
        if isinstance(value, list):
            return [_for_windows(v, pairs) for v in value]
        if isinstance(value, tuple):
            return tuple(_for_windows(v, pairs) for v in value)
        if isinstance(value, dict):
            return {k: _for_windows(v, pairs) for k, v in value.items()}
        return value

    for _lang, _pairs in _WINDOWS.items():
        if _lang in TEXTS:
            TEXTS[_lang] = _for_windows(TEXTS[_lang], _pairs)
