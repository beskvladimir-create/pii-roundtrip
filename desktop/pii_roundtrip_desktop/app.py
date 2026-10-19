"""The window: drop a document (or paste ⌘V) and it is cleaned; paste the AI's answer and the
real values come back. One card, one gesture; the paste is routed by its content.

Everything runs on this computer. The mapping between placeholders and real values stays in
an encrypted vault whose key lives in the macOS Keychain.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QTextBrowser,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pii_roundtrip_desktop import MAKER, VERSION, YEAR, documents, i18n, keys, theme
from pii_roundtrip_desktop.engine import AppEngine
from pii_roundtrip_desktop.store import DEFAULT_DIR, Store
from pii_roundtrip_desktop.widgets import (
    PLACEHOLDER,
    BrandMark,
    DocView,
    DropZone,
    Ground,
    LangSwitch,
    ProgressLine,
    Segmented,
    glow,
)


ICON = Path(__file__).with_name("icon.svg")
SITE = "https://besk.tech"
# licences of the bundled components: inside the app, or build/licenses when run from source
NOTICES = (
    Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "build"))
    / "licenses"
    / "THIRD_PARTY_NOTICES.txt"
)
CONTACT = "mailto:admin@besk.tech?subject=pii-roundtrip"  # the company address published on besk.tech
TERMS_VERSION = "2026-10-19"


def _same_text(a: str, b: str) -> bool:
    """The same words in the same order: spaces, line breaks and the invisible marks a PDF
    keeps for soft hyphens do not count."""
    import re

    junk = re.compile(r"[\s\u00ad\ufffe\ufeff\ue000-\uf8ff-]")
    return junk.sub("", a) == junk.sub("", b)


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    """Run a slow call (model loading, detection) off the interface thread."""

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args, self.signals = fn, args, _Signals()

    def run(self) -> None:
        try:
            self.signals.done.emit(self.fn(*self.args))
        except Exception as e:  # shown to the user in the card
            self.signals.failed.emit(str(e))


def _button(text: str, primary: bool = False, link: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        b.setProperty("primary", True)
    if link:
        b.setProperty("link", True)
    if not link:
        glow(b, primary)
    return b


def _fade_in(w: QWidget) -> None:
    effect = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", w)
    anim.setDuration(200)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: w.setGraphicsEffect(None))
    anim.start()


class WhichDocument(QDialog):
    """Sheet: an answer was pasted with no document open. Best match first."""

    def __init__(self, parent: QWidget, t: dict, items: list[tuple[str, str]]):
        super().__init__(parent)
        self.setWindowTitle(t["which"])
        self.setModal(True)
        self.setFixedWidth(480)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)
        title = QLabel(t["which"])
        title.setObjectName("errtitle")
        v.addWidget(title)
        body = QLabel(t["which_body"])
        body.setObjectName("errbody")
        body.setWordWrap(True)
        v.addWidget(body)
        self.list = QListWidget()
        for key, label in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        v.addWidget(self.list)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = _button(t["cancel"])
        cancel.clicked.connect(self.reject)
        ok = _button(t["restore"], primary=True)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class MainWindow(QMainWindow):
    language_changed = Signal(str)

    def __init__(self, store: Store, t: dict, engine: AppEngine | None = None, lang: str = "ru"):
        super().__init__()
        self.store, self.t, self.ui_lang = store, t, lang
        self.engine = engine or AppEngine()
        self.pool = QThreadPool.globalInstance()
        self.loaded = engine is not None and engine.ready
        self.busy = False  # cleaning or restoring is under way
        self._tasks: set[Task] = set()
        # the open document
        self.key: str | None = None
        self.session = None
        self.title = ""
        self.original = ""  # the text before cleaning, kept in memory only
        self.request = ""
        self.answer = ""
        self.lang = "ru"
        self.source: Path | None = None  # the file the document came from
        self.spans: list[tuple[int, int, str]] = []  # where placeholders replaced the original
        # each placeholder occurrence of the cleaned document and the exact text it replaced,
        # so that the cleaned file itself comes back letter for letter (kept encrypted)
        self.surfaces: list[list[str]] = []

        self.setWindowTitle(t["app"])
        self.resize(900, 640)
        self.setMinimumSize(760, 600)
        # the navy ground runs under the native title bar
        self.setWindowFlag(Qt.WindowType.ExpandedClientAreaHint, True)
        self.setWindowFlag(Qt.WindowType.NoTitleBarBackgroundHint, True)

        root = Ground()
        root.names = t["constellations"]
        self.ground = root
        self._typed = ""  # the last letters typed outside text, for the hidden constellation
        QApplication.instance().installEventFilter(self)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        # below the macOS window buttons, left edge in line with the content
        bar.setFixedHeight(76)
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(24, 32, 24, 8)
        self.doctitle = QLabel("")
        self.doctitle.setObjectName("doctitle")
        self.doctitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.segmented = Segmented((t["request"], t["answer"]))
        self.segmented.setFixedWidth(180)
        self.segmented.changed.connect(self._show_view)
        self.segmented.hide()
        self.brand = BrandMark()
        self.brand.setToolTip(t["menu_new"])
        self.brand.clicked.connect(self.go_home)
        brand_box = QWidget()
        brand_box.setFixedWidth(180)
        bx = QHBoxLayout(brand_box)
        bx.setContentsMargins(0, 0, 0, 0)
        bx.addWidget(self.brand, 0, Qt.AlignmentFlag.AlignLeft)
        bh.addWidget(brand_box)
        bh.addWidget(self.doctitle, 1)
        self.trust = QLabel(t["trust"])
        self.trust.setObjectName("trust")
        self.trust.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        right = QWidget()
        right.setMinimumWidth(180)  # same as the brand side, so the document title stays centred
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.addStretch(1)
        rh.addWidget(self.trust)
        rh.addWidget(self.segmented)
        bh.addWidget(right)
        outer.addWidget(bar)
        self.progress = ProgressLine()
        outer.addWidget(self.progress)
        self.status = QLabel(t["loading_models"])
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setVisible(not self.loaded)
        outer.addWidget(self.status)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._empty_page())
        self.pages.addWidget(self._doc_page())
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(24, 12, 24, 24)
        bv.addWidget(self.pages, 1)
        bv.addSpacing(16)
        hair = QFrame()
        hair.setObjectName("hair")
        bv.addWidget(hair)
        bv.addSpacing(14)
        bottom = QHBoxLayout()
        self.new_btn = _button("←  " + t["menu_new"], link=True)
        self.new_btn.clicked.connect(self.go_home)
        link = 'style="color:#FFFFFF; text-decoration:none"'
        maker = QLabel(
            f'<a href="terms" {link}>{t["terms_link"]}</a> &nbsp;·&nbsp; '
            f'<a href="{CONTACT}" {link}>{t["contact"]}</a> &nbsp;·&nbsp; '
            + t["maker_short"].format(year=YEAR, maker=MAKER)
            + f' · <a href="{SITE}" {link}>besk.tech</a>'
        )
        maker.setObjectName("maker")
        maker.setToolTip(t["maker"].format(year=YEAR, maker=MAKER, version=VERSION))
        maker.linkActivated.connect(self._footer_link)
        langs = LangSwitch(lang)
        langs.changed.connect(self.language_changed.emit)
        bottom.addWidget(self.new_btn)
        bottom.addStretch(1)
        bottom.addWidget(maker)
        bottom.addSpacing(14)
        bottom.addWidget(langs)
        bv.addLayout(bottom)
        outer.addWidget(body, 1)
        self.pages.currentChanged.connect(self._page_changed)
        self.setCentralWidget(root)

        self._menus()
        self._shortcuts()
        self.go_empty()
        if not self.loaded:
            self.progress.start()
            self._run(self.engine.load, self._loaded)

    # ---------- pages ----------

    def _empty_page(self) -> QWidget:
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.drop = DropZone(t)
        self.drop.setMinimumHeight(230)
        self.drop.file_dropped.connect(self.open_file)
        self.drop.choose.connect(self.choose_file)
        v.addWidget(self.drop, 5)
        v.addSpacing(24)
        self.recent_box = QWidget()
        rv = QVBoxLayout(self.recent_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(4)
        head_row = QHBoxLayout()
        head_row.setContentsMargins(12, 0, 12, 8)
        head = QLabel(t["recent"])
        head.setObjectName("micro")
        head_row.addWidget(head)
        head_row.addStretch(1)
        clear = _button(t["delete_all"], link=True)
        clear.clicked.connect(self._delete_all)
        head_row.addWidget(clear)
        rv.addLayout(head_row)
        self.recent_rows = QVBoxLayout()
        self.recent_rows.setSpacing(0)
        rv.addLayout(self.recent_rows)
        v.addWidget(self.recent_box)
        v.addStretch(1)
        return w

    def _doc_page(self) -> QWidget:
        t = self.t
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        card = QFrame()
        card.setObjectName("card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(28, 24, 28, 24)
        self.card_stack = QStackedWidget()
        self.doc = DocView()
        self.doc.paste_requested.connect(self.route_paste)
        self.card_stack.addWidget(self.doc)
        self.card_stack.addWidget(self._error_view())
        # a formatted preview of a Word document on a light "paper" sheet
        self.paper = QTextBrowser()
        self.paper.setObjectName("paper")
        self.paper.setOpenLinks(False)
        self.card_stack.addWidget(self.paper)
        cv.addWidget(self.card_stack)
        v.addWidget(card, 1)

        self.note = QLabel("")
        self.note.setObjectName("note")
        self.note.setWordWrap(True)
        self.note.hide()
        v.addWidget(self.note)
        self.saved = QLabel("")
        self.saved.setObjectName("saved")
        self.saved.setTextFormat(Qt.TextFormat.RichText)
        self.saved.setWordWrap(True)
        self.saved.linkActivated.connect(self._saved_link)
        self.saved.hide()
        v.addWidget(self.saved)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.summary = QLabel("")
        self.summary.setObjectName("summary")
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setWordWrap(True)
        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(self.summary)
        self.lang_btn = _button("", link=True)
        self.lang_btn.clicked.connect(self._lang_menu)
        info.addWidget(self.lang_btn, 0, Qt.AlignmentFlag.AlignLeft)
        row.addLayout(info, 1)
        row.addSpacing(16)
        self.save_btn = _button(t["save_docx"])
        self.save_btn.clicked.connect(self.save_docx)
        self.copy_btn = _button(t["copy"], primary=True)
        self.copy_btn.setMinimumWidth(140)
        self.copy_btn.clicked.connect(self.copy_all)
        row.addWidget(self.save_btn)
        row.addWidget(self.copy_btn)
        v.addLayout(row)

        foot = QHBoxLayout()
        foot.setSpacing(12)
        foot.addStretch(1)
        self.footer = QLabel("")
        self.footer.setObjectName("footer")
        foot.addWidget(self.footer)
        self.footer_key = _button(t["paste_btn"])
        self.footer_key.setProperty("small", True)
        self.footer_key.clicked.connect(self.route_paste)
        foot.addWidget(self.footer_key)
        self.as_new = _button(t["as_new"], link=True)
        self.as_new.clicked.connect(self._as_new_document)
        self.as_new.hide()
        foot.addWidget(self.as_new)
        foot.addStretch(1)
        v.addSpacing(4)
        v.addLayout(foot)
        return w

    def _error_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addStretch(1)
        self.err_title = QLabel("")
        self.err_title.setObjectName("errtitle")
        self.err_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.err_body = QLabel("")
        self.err_body.setObjectName("errbody")
        self.err_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.err_body.setWordWrap(True)
        b = _button(self.t["choose_other"])
        b.clicked.connect(self.choose_file)
        v.addWidget(self.err_title)
        v.addSpacing(8)
        v.addWidget(self.err_body)
        v.addSpacing(16)
        v.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addStretch(1)
        return w

    def _menus(self) -> None:
        t = self.t
        m = self.menuBar().addMenu(t["menu_file"])
        about = QAction(t["about"], self)
        about.setMenuRole(QAction.MenuRole.AboutRole)  # goes to the app menu on macOS
        about.triggered.connect(self._about)
        m.addAction(about)
        for label, seq, fn in (
            (t["menu_new"], QKeySequence(QKeySequence.StandardKey.New), self.go_empty),
            (t["menu_open"], QKeySequence(QKeySequence.StandardKey.Open), self.choose_file),
            (t["save_docx"], QKeySequence(QKeySequence.StandardKey.Save), self.save_docx),
            (t["menu_copy_all"], QKeySequence("Shift+Ctrl+C"), self.copy_all),
        ):
            a = QAction(label, self)
            a.setShortcut(seq)
            a.triggered.connect(fn)
            m.addAction(a)
        self.recent_menu = m.addMenu(t["menu_recent"])
        m.addSeparator()
        wipe = QAction(t["delete_all"] + "…", self)
        wipe.triggered.connect(self._delete_all)
        m.addAction(wipe)

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence(QKeySequence.StandardKey.Paste), self, self.route_paste)
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._switch(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._switch(1))

    # ---------- states ----------

    def go_empty(self) -> None:
        self.key, self.session, self.title, self.original, self.request, self.answer = None, None, "", "", "", ""
        self.doctitle.setText("")
        self.segmented.hide()
        self._refresh_recent()
        self.pages.setCurrentIndex(0)
        _fade_in(self.pages.currentWidget())
        self._page_changed(0)

    def go_home(self) -> None:
        if (
            self.progress.isVisible()
            and self.pages.currentIndex() == 1
            and self.card_stack.currentIndex() == 0
            and not self.copy_btn.isVisible()
        ):
            return  # still cleaning
        self.go_empty()

    def eventFilter(self, obj, e) -> bool:
        from PySide6.QtCore import QEvent

        if e.type() == QEvent.Type.KeyPress and e.text() and not self.doc.hasFocus():
            self._typed = (self._typed + e.text().lower())[-4:]
            if self._typed in ("besk", "бэск", "беск"):
                self.ground.show_constellation("besk")
                self._typed = ""
        return False

    def _page_changed(self, i: int) -> None:
        self.trust.setVisible(i == 0)
        self.new_btn.setVisible(i == 1)

    def _saved_done(self, path: str, answer: bool) -> None:
        t = self.t
        name = Path(path).name
        self.saved.setText(
            f'<span style="color:#FFFFFF">✓ {t["saved"].format(name=name)}</span>&nbsp;&nbsp;'
            f'<a href="reveal:{path}" style="color:#FFFFFF">{t["reveal"]}</a>&nbsp;&nbsp;·&nbsp;&nbsp;'
            f'<a href="new" style="color:#FFFFFF">{t["menu_new"]}</a>'
        )
        self.saved.show()
        if not answer:
            self.footer.setText(t["next_send"])

    def _saved_link(self, link: str) -> None:
        if link == "new":
            self.go_home()
        elif link.startswith("reveal:"):
            path = link[len("reveal:") :]
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", path], check=False)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _doc_state(self, text: str, summary_html: str, footer: str, show_lang: bool = True) -> None:
        self.busy = False
        self.card_stack.setCurrentIndex(0)
        self.doc.setStyleSheet("")
        self.doc.mapping = self.session.mapping if self.session else {}
        self.doc.show_text(text, self.original)
        self.summary.setText(summary_html)
        self.lang_btn.setVisible(show_lang and bool(self.original))
        self.lang_btn.setText(self.t["lang_ru"] if self.lang == "ru" else self.t["lang_en"])
        self.lang_btn.setStyleSheet("color: #FFFFFF;" if i18n.mixed(self.original or text) else "")
        self.footer.setText(footer)
        self.footer_key.show()
        self.saved.hide()
        self.copy_btn.show()
        self.save_btn.show()
        self.doctitle.setText(self.title)
        if self.pages.currentIndex() != 1:
            self.pages.setCurrentIndex(1)
            _fade_in(self.pages.currentWidget())

    def _working(self, text: str, title: str) -> None:
        # the card shows the original text until cleaning ends: nothing may be saved or copied
        self.busy = True
        self.title = title
        self.doctitle.setText(title)
        self.card_stack.setCurrentIndex(0)
        self.doc.mapping = {}
        self.doc.show_text(text)
        self.doc.setStyleSheet("color: rgba(250, 250, 250, 0.4);")
        self.summary.setText("")
        self.lang_btn.hide()
        self.note.hide()
        self.saved.hide()
        self.as_new.hide()
        self.footer.setText(self.t["working"] if self.loaded else self.t["preparing"])
        self.footer_key.hide()
        self.copy_btn.hide()
        self.save_btn.hide()
        if self.pages.currentIndex() != 1:
            self.pages.setCurrentIndex(1)
            _fade_in(self.pages.currentWidget())
        self.progress.start()

    def _error(self, title: str, body: str) -> None:
        self.busy = False
        if self.loaded:
            self.progress.stop()
        self.err_title.setText(title)
        self.err_body.setText(body)
        self.card_stack.setCurrentIndex(1)
        self.summary.setText("")
        self.note.hide()
        self.saved.hide()
        self.lang_btn.hide()
        self.copy_btn.hide()
        self.save_btn.hide()
        self.footer.setText("")
        self.footer_key.hide()
        self.segmented.hide()
        self.pages.setCurrentIndex(1)

    def _masked_html(self) -> str:
        n = len(self.session.mapping) if self.session else 0
        if not n:
            return self.t["nothing"]
        count = f"<span style='color:#FFFFFF;font-weight:600'>{n}</span>"
        text = self.t["masked"].format(n=count, summary=i18n.summary(self.session.mapping, self.t))
        if self.engine.rules_only:
            text += "<br>" + self.t["rules_only"]
        return text

    # ---------- actions ----------

    def choose_file(self) -> None:
        exts = " ".join(f"*{e}" for e in documents.SUPPORTED)
        path, _ = QFileDialog.getOpenFileName(self, self.t["menu_open"], str(Path.home()), f"({exts})")
        if path:
            self.open_file(path)

    def open_file(self, path: str) -> None:
        t = self.t
        prev_title = self.title
        self.title = Path(path).name
        self.doctitle.setText(self.title)
        try:
            text = documents.read_text(path)
        except documents.ScannedPDF:
            self._error(t["err_scan_title"], t["err_scan_body"])
            return
        except documents.UnsupportedFormat:
            self._error(t["err_format_title"], t["err_format_body"])
            return
        except documents.DocumentError as e:
            self._error(t["err_other_title"], str(e))
            return
        if PLACEHOLDER.search(text):
            # a file that already has labels (the AI's answer, or the cleaned file itself): bring the values back
            self.title = prev_title
            self.doctitle.setText(prev_title)
            self._restore_text(text, source=Path(path))
            return
        self.clean_new(text, self.title, source=Path(path))

    def _restore_text(self, text: str, source: Path | None = None) -> None:
        """Labelled text: restore into the open document, or ask which one it belongs to.
        ``source`` is the file it came from, so the answer can be saved in its layout."""
        self._answer_from = source
        labels = {m.group() for m in PLACEHOLDER.finditer(text)}
        if self.session is not None and labels & set(self.session.mapping):
            self.restore(text)
        else:
            self._which_document(text)

    def clean_new(self, text: str, title: str, lang: str | None = None, source: Path | None = None) -> None:
        self.key, self.session, self.answer, self.spans, self.surfaces = None, None, "", [], []
        self.source = source
        self.original = text
        self.lang = lang or i18n.detect_language(text)
        self.segmented.hide()
        self._working(text, title)
        lang_now = self.lang

        def work():
            clean, session, spans = self.engine.anonymize_with_spans(text, lang_now, None)
            entry = self.store.save(title, session)
            self.surfaces = [[label, text[a:b]] for a, b, label in sorted(spans)]
            self.store.update_texts(
                entry.key,
                {
                    "request": clean,
                    "surfaces": json.dumps(self.surfaces, ensure_ascii=False),
                    "source": str(source or ""),
                    "source_sha": documents.file_hash(source) if source else "",
                },
            )
            self.spans = spans
            return clean, session, entry.key

        self._run(work, self._cleaned)

    def _cleaned(self, result) -> None:
        clean, self.session, self.key = result
        self.request = clean
        self.progress.stop()
        self.note.hide()
        self._doc_state(clean, self._masked_html(), self.t["paste_answer"])
        self.doc.show_text(clean, self.original, animate=True)
        self._paper_preview()
        if self.answer:
            self.segmented.show()
            self.segmented.select(0)

    def follow_up(self, text: str) -> None:
        self.original = text
        self.source, self.spans = None, []  # a follow-up message is not the original file
        prev_title = self.title
        self._working(text, prev_title)
        session, key, answer, lang_now = self.session, self.key, self.answer, self.lang

        def work():
            clean, s = self.engine.anonymize(text, lang_now, session)
            self.store.save(prev_title, s, key)
            self.store.update_texts(
                key, {"request": clean, "answer": answer, "surfaces": json.dumps(self.surfaces, ensure_ascii=False)}
            )
            return clean, s, key

        def done(result):
            self._cleaned(result)
            self.footer.setText(self.t["added"].format(title=prev_title))
            self.footer_key.hide()
            self.as_new.show()
            QTimer.singleShot(6000, self._end_follow_up_hint)

        self._run(work, done)

    def _end_follow_up_hint(self) -> None:
        self.as_new.hide()
        if self.pages.currentIndex() == 1 and self.card_stack.currentIndex() == 0:
            self.footer.setText(self.t["paste_answer"])
            self.footer_key.show()

    def _as_new_document(self) -> None:
        self.as_new.hide()
        self.clean_new(self.original, self.title, source=None)

    def restore(self, text: str, key: str | None = None) -> None:
        if key and key != self.key:
            self.key = key
            self.session = self.store.load(key)
            texts = self.store.load_texts(key)
            self.request = texts.get("request", "")
            self.surfaces = json.loads(texts.get("surfaces", "[]"))
            self.title = next((e.title for e in self.store.entries() if e.key == key), "")
            self.lang = self.session.lang
            self.original = ""
        session = self.session

        source = getattr(self, "_answer_from", None)
        self._answer_from = None

        def done(result: tuple[str, list[tuple[int, int, str]], bool]):
            restored, spans, exact = result
            self.progress.stop()
            self.answer = restored
            self.answer_source = source
            self.answer_exact = exact
            self.answer_spans = spans
            self.store.update_texts(
                self.key,
                {
                    "request": self.request,
                    "answer": restored,
                    "surfaces": json.dumps(self.surfaces, ensure_ascii=False),
                },
            )
            known = set(session.mapping)
            found = [m.group() for m in PLACEHOLDER.finditer(text)]
            unknown = sorted(set(found) - known)
            n = len([x for x in found if x in known])
            self._doc_state(restored, self.t["restored_n"].format(n=n), self.t["paste_next"], show_lang=False)
            self.doc.mapping = {}
            if unknown:
                self.note.setText(self.t["unknown"].format(labels=", ".join(unknown)))
                self.note.show()
            else:
                self.note.hide()
            self.segmented.show()
            self.segmented.select(1)

        found = PLACEHOLDER.findall(text)
        surfaces = list(self.surfaces)
        # our own cleaned file, unchanged: the same labels in the same order and the same text
        # around them. Labels alone are not enough: an AI tool that edits the text keeps them.
        unchanged = _same_text(text, self.request)

        def work():
            # off the interface thread: a long document takes a while to map back
            if unchanged and found and found == [label for label, _ in surfaces]:
                # the cleaned document itself came back: every value exactly as it was written,
                # and its place is known, so nothing has to be searched for
                spans = [(m.start(), m.end(), v) for m, (_, v) in zip(PLACEHOLDER.finditer(text), surfaces)]
                out, pos = [], 0
                for a, b, v in spans:
                    out += [text[pos:a], v]
                    pos = b
                out.append(text[pos:])
                return "".join(out), spans if source else [], True
            forms: dict[str, str] = {}
            for label, value in surfaces:
                forms.setdefault(label, value)  # how each label was written the first time in the source
            restored = self.engine.deanonymize(text, session, forms)
            spans = documents.replacement_spans(text, restored, session.mapping) if source else []
            return restored, spans, False

        self.busy = True
        self.progress.start()
        self._run(work, done)

    def route_paste(self) -> None:
        if self.doc.hasFocus() and self.doc.textCursor().hasSelection():
            self.doc.paste()
            return
        text = QGuiApplication.clipboard().text()
        if not text.strip():
            return
        has_labels = bool(PLACEHOLDER.search(text))
        if self.session is None:
            if has_labels:
                self._restore_text(text)
            else:
                self.clean_new(text, text.strip().split("\n")[0][:40])
        elif has_labels:
            self.restore(text)
        else:
            self.follow_up(text)

    def _which_document(self, text: str) -> None:
        """An answer with labels and no document open: find its document. Our own cleaned file
        is recognised by its exact sequence of labels; otherwise the documents whose labels cover
        all of the answer's are candidates, the one with most of its labels used first. The user
        is asked only when different documents fit equally well."""
        found = PLACEHOLDER.findall(text)
        labels = set(found)
        entries = self.store.entries()[:50]

        def work():
            # opening each encrypted vault takes a moment: done off the interface thread
            scored = []
            for e in entries:
                try:
                    mapping = self.store.load(e.key).mapping
                except Exception:
                    continue
                texts = self.store.load_texts(e.key)
                own = _same_text(texts.get("request", ""), text)
                hits = len(labels & set(mapping))
                scored.append(((own, hits == len(labels), hits / max(1, len(mapping))), e, mapping, hits))
            return scored

        self.progress.start()
        self._run(work, lambda scored: self._choose_document(text, labels, scored))

    def _choose_document(self, text: str, labels: set, scored: list) -> None:
        self.progress.stop()
        if not scored:
            return
        scored.sort(key=lambda s: (s[0], s[1].created), reverse=True)
        best = scored[0]
        ties = [s for s in scored if s[0] == best[0]]
        same = all(s[2] == best[2] for s in ties)  # the same file cleaned again: identical values
        if best[0][0] or (best[0][1] and (len(ties) == 1 or same)):
            self.restore(text, best[1].key)
            return
        t = self.t
        items = [
            (e.key, f"{e.title}    {self._when(e.created)} · {t['match'].format(n=hits, m=len(labels))}")
            for _, e, _, hits in scored
        ]
        dialog = WhichDocument(self, t, items)
        if dialog.exec() and dialog.chosen():
            self.restore(text, dialog.chosen())

    def open_recent(self, key: str) -> None:
        entry = next((e for e in self.store.entries() if e.key == key), None)
        if not entry:
            return
        self.key, self.session, self.title, self.original = key, self.store.load(key), entry.title, ""
        self.lang = self.session.lang
        texts = self.store.load_texts(key)
        self.request, self.answer = texts.get("request", ""), texts.get("answer", "")
        self.surfaces = json.loads(texts.get("surfaces", "[]"))
        self.note.hide()
        self._doc_state(self.request, self._masked_html(), self.t["paste_answer"], show_lang=False)
        self.segmented.setVisible(bool(self.answer))
        self.segmented.select(0)

    def _paper_preview(self) -> None:
        """For a Word file, show the cleaned document with its formatting instead of plain text."""
        if not (self.source and self.source.suffix.lower() == ".docx" and self.spans):
            return
        import tempfile

        values = sorted({self.original[a:b] for a, b, _ in self.spans}, key=len, reverse=True)
        with tempfile.TemporaryDirectory() as tmp:
            preview = Path(tmp) / "preview.docx"
            try:
                documents.save_clean_docx(self.source, preview, self.spans, values)
                html = documents.docx_to_html(preview)
            except documents.DocumentError:
                return  # keep the plain text view
        self.paper.setHtml(html)
        self.card_stack.setCurrentIndex(2)

    def _show_view(self, i: int) -> None:
        if i == 0:
            self._doc_state(self.request, self._masked_html(), self.t["paste_answer"])
            self._paper_preview()
        else:
            n = len(self.session.mapping) if self.session else 0
            self._doc_state(self.answer, self.t["restored_n"].format(n=n), self.t["paste_next"], show_lang=False)
            self.doc.mapping = {}

    def _switch(self, i: int) -> None:
        if self.segmented.isVisible():
            self.segmented.select(i)
            self._show_view(i)

    def _lang_menu(self) -> None:
        if not self.original:
            return
        menu = QMenu(self)
        for code, label in (("ru", self.t["lang_ru"]), ("en-GB", self.t["lang_en"])):
            a = menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(code == self.lang)
            if code != self.lang:
                a.triggered.connect(
                    lambda _=False, code=code: self.clean_new(self.original, self.title, code, source=self.source)
                )
        menu.exec(self.lang_btn.mapToGlobal(self.lang_btn.rect().bottomLeft()))

    def copy_all(self) -> None:
        if self.busy or self.pages.currentIndex() != 1 or self.card_stack.currentIndex() == 1:
            return
        QGuiApplication.clipboard().setText(self.doc.current_text())
        self.copy_btn.setText(self.t["copied"])
        QTimer.singleShot(1600, lambda: self.copy_btn.setText(self.t["copy"]))

    def save_docx(self) -> None:
        """Save in the format the document came in, keeping its layout: the cleaned document is
        rebuilt from the original file, a restored answer from the file it was dropped in as."""
        if self.busy or self.pages.currentIndex() != 1 or self.card_stack.currentIndex() == 1:
            return
        t = self.t
        answer = self.segmented.isVisible() and self.segmented.buttons[1].isChecked()
        answer_source = getattr(self, "answer_source", None) if answer else None
        base = answer_source if answer else self.source
        src = base.suffix.lower() if base else ".docx"
        if answer:
            # without the places of the values the layout cannot be kept: the restored text is
            # then saved with a simple layout, never the file with its labels
            styled = (
                self.answer_spans is not None
                and answer_source is not None
                and src in (".docx", ".pdf")
                and self.doc.current_text() == self.answer
            )
        else:
            styled = (
                src in (".docx", ".pdf")
                and bool(self.spans)
                and self.source is not None
                and self.doc.current_text() == self.request
            )
        filters = {
            ".docx": f"{t['f_docx'] if styled and src == '.docx' else t['f_docx_plain']} (*.docx)",
            ".pdf": f"{t['f_pdf_layout'] if styled and src == '.pdf' else t['f_pdf']} (*.pdf)",
            ".txt": f"{t['f_txt']} (*.txt)",
        }
        first = src if src in filters else ".docx"
        order = [first] + [k for k in filters if k != first]
        stem = Path(self.title).stem or "document"
        name = f"{stem}.{'answer' if answer else 'clean'}{first}"
        folder = base.parent if base and base.parent.is_dir() else Path.home() / "Downloads"
        path, chosen = QFileDialog.getSaveFileName(
            self, t["save_docx"], str(folder / name), ";;".join(filters[k] for k in order)
        )
        if not path:
            return
        ext = next((k for k, v in filters.items() if v == chosen), Path(path).suffix.lower() or first)
        if not path.lower().endswith(ext):
            path += ext
        text = self.doc.current_text()
        if styled and ext == src and answer and getattr(self, "answer_exact", False):
            original = self._original_file()
            if original is not None and original.suffix.lower() == ext:
                # our own cleaned file came back and the original is untouched: return the original itself
                shutil.copyfile(original, path)
                self._saved_done(path, answer)
                return
        if styled and ext == src and answer:
            try:
                if ext == ".pdf":
                    mapping = self.session.mapping if self.session else None
                    documents.save_restored_pdf(answer_source, path, self.answer_spans, mapping)
                else:
                    documents.save_restored_docx(answer_source, path, self.answer_spans)
                self._saved_done(path, answer)
                return
            except documents.DocumentError:
                Path(path).unlink(missing_ok=True)
                self.note.setText(t["unplaced"])
                self.note.show()
        if styled and ext == src and not answer:
            # the check looks for values the rewrite of the file left behind; a value that the
            # cleaned text itself still shows (the engine kept it elsewhere) is not such a leak
            shown = " ".join(self.request.split())
            values = sorted(
                {v for a, b, _ in self.spans if " ".join((v := self.original[a:b]).split()) not in shown},
                key=len,
                reverse=True,
            )
            try:
                save = documents.save_clean_docx if ext == ".docx" else documents.save_clean_pdf
                save(self.source, path, self.spans, values)
                self._saved_done(path, answer)
                return
            except documents.DocumentError:
                self.note.setText(t["unsafe"])
                self.note.show()
        if answer and answer_source is not None and answer_source.suffix.lower() == ".pdf":
            text = documents.reflow(documents.drop_page_furniture(text))  # lines of a PDF back into paragraphs
        if ext == ".pdf":
            documents.write_pdf(path, text)
        elif ext == ".txt":
            documents.write_text(path, text)
        else:
            documents.write_docx(path, text)
        self._saved_done(path, answer)

    def _original_file(self) -> Path | None:
        """The file the open document was cleaned from, if it is still there and unchanged."""
        if not self.key:
            return None
        texts = self.store.load_texts(self.key)
        path = Path(texts.get("source") or "")
        if texts.get("source") and path.is_file() and documents.file_hash(path) == texts.get("source_sha"):
            return path
        return None

    def _footer_link(self, link: str) -> None:
        if link == "terms":
            terms_dialog(self, self.t, accept=False)
        else:
            QDesktopServices.openUrl(QUrl(link))

    def _about(self) -> None:
        t = self.t
        d = QDialog(self)
        d.setWindowTitle(t["about"])
        d.setFixedWidth(400)
        v = QVBoxLayout(d)
        v.setContentsMargins(32, 32, 32, 28)
        v.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(QIcon(str(ICON)).pixmap(72, 72))
        v.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(8)
        for text, name in (
            ("pii-roundtrip", "aboutname"),
            (t["maker"].format(year=YEAR, maker=MAKER, version=VERSION), "maker"),
            (t["about_body"], "errbody"),
            (t["license"], "maker"),
        ):
            label = QLabel(text)
            label.setObjectName(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            v.addWidget(label)
        site = QLabel(
            '<a href="https://pii-roundtrip.besk.tech" style="color:#FFFFFF">pii-roundtrip.besk.tech</a>'
            f' &nbsp;·&nbsp; <a href="notices" style="color:#FFFFFF">{t["notices"]}</a>'
        )
        site.linkActivated.connect(
            lambda link: QDesktopServices.openUrl(QUrl.fromLocalFile(str(NOTICES)) if link == "notices" else QUrl(link))
        )
        site.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addSpacing(8)
        v.addWidget(site)
        d.exec()

    # ---------- recent ----------

    def _when(self, created: str) -> str:
        when = datetime.fromisoformat(created)
        d, hm = when.date(), when.strftime("%H:%M")
        if d == date.today():
            return f"{self.t['today']}, {hm}"
        if (date.today() - d).days == 1:
            return f"{self.t['yesterday']}, {hm}"
        return f"{d:%d.%m.%Y}, {hm}"

    def _refresh_recent(self) -> None:
        while self.recent_rows.count():
            item = self.recent_rows.takeAt(0)
            if item.widget():
                # detach at once: a row waiting for deleteLater would still be drawn under the new ones
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()
        entries = self.store.entries()
        self.recent_box.setVisible(bool(entries))
        for e in entries[:3]:
            row = QPushButton()
            row.setProperty("recent", True)
            row.setFixedHeight(36)
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            h = QHBoxLayout(row)
            h.setContentsMargins(12, 0, 12, 0)
            name = QLabel(e.title)
            name.setStyleSheet("color: #FAFAFA; font-size: 14px;")
            when = QLabel(self._when(e.created))
            when.setStyleSheet("color: #9CA3AF; font-size: 13px;")
            h.addWidget(name)
            h.addStretch(1)
            h.addWidget(when)
            h.addSpacing(8)
            remove = QPushButton("✕")
            remove.setObjectName("remove")
            remove.setToolTip(self.t["delete"])
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.setFixedSize(26, 26)
            remove.clicked.connect(lambda _=False, k=e.key, title=e.title: self._delete(k, title))
            h.addWidget(remove)
            row.clicked.connect(lambda _=False, k=e.key: self.open_recent(k))
            row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            row.customContextMenuRequested.connect(lambda _p, k=e.key, r=row: self._recent_menu(k, r))
            self.recent_rows.addWidget(row)
        self.recent_menu.clear()
        for e in entries[:20]:
            a = self.recent_menu.addAction(f"{e.title}  ({self._when(e.created)})")
            a.triggered.connect(lambda _=False, k=e.key: self.open_recent(k))

    def _delete(self, key: str, title: str) -> None:
        t = self.t
        if not confirm(self, t["delete_one_title"].format(title=title), t["delete_body"], t["delete"]):
            return
        self.store.delete(key)
        if key == self.key:
            self.go_empty()
        self._refresh_recent()

    def _delete_all(self) -> None:
        t = self.t
        n = len(self.store.entries())
        if not confirm(self, t["delete_all_title"].format(n=n), t["delete_body"], t["delete_all"]):
            return
        self.store.delete_all()
        self.go_empty()
        self._refresh_recent()

    def _recent_menu(self, key: str, row: QWidget) -> None:
        menu = QMenu(self)
        a = menu.addAction(self.t["delete"])
        title = next((e.title for e in self.store.entries() if e.key == key), "")
        a.triggered.connect(lambda: self._delete(key, title))
        menu.exec(row.mapToGlobal(row.rect().center()))

    # ---------- plumbing ----------

    def _run(self, fn, on_done, *args) -> None:
        # the task and its callback are kept alive until the result arrives on this thread
        task = Task(fn, *args)
        task.setAutoDelete(False)
        self._tasks.add(task)

        def finish(result, task=task):
            self._tasks.discard(task)
            on_done(result)

        def fail(message, task=task):
            self._tasks.discard(task)
            self._failed(message)

        task.signals.done.connect(finish, Qt.ConnectionType.QueuedConnection)
        task.signals.failed.connect(fail, Qt.ConnectionType.QueuedConnection)
        task._callbacks = (finish, fail)  # type: ignore[attr-defined]
        self.pool.start(task)

    def _failed(self, message: str) -> None:
        self.progress.stop()
        self._error(self.t["err_other_title"], message)

    def _loaded(self, _=None) -> None:
        self.loaded = True
        self.status.setText(self.t["models_ready"])
        QTimer.singleShot(2500, self.status.hide)
        if self.pages.currentIndex() == 0 or self.card_stack.currentIndex() == 1:
            self.progress.stop()
        elif self.footer.text() == self.t["preparing"]:
            self.footer.setText(self.t["working"])


def confirm(parent: QWidget, title: str, body: str, action: str) -> bool:
    """A small sheet for an action that cannot be undone."""
    d = QDialog(parent)
    d.setWindowTitle(title)
    d.setFixedWidth(440)
    v = QVBoxLayout(d)
    v.setContentsMargins(32, 28, 32, 24)
    v.setSpacing(10)
    head = QLabel(title)
    head.setObjectName("errtitle")
    head.setWordWrap(True)
    v.addWidget(head)
    text = QLabel(body)
    text.setObjectName("errbody")
    text.setWordWrap(True)
    v.addWidget(text)
    v.addSpacing(10)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = _button(parent.t["cancel"] if hasattr(parent, "t") else "Cancel")
    cancel.clicked.connect(d.reject)
    ok = _button(action, primary=True)
    ok.clicked.connect(d.accept)
    cancel.setDefault(True)
    row.addWidget(cancel)
    row.addWidget(ok)
    v.addLayout(row)
    return d.exec() == QDialog.DialogCode.Accepted


def terms_dialog(parent: QWidget | None, t: dict, accept: bool) -> bool:
    """The terms of use. On first launch they must be accepted to continue."""
    d = QDialog(parent)
    d.setWindowTitle(t["terms_title"])
    d.setFixedWidth(520)
    v = QVBoxLayout(d)
    v.setContentsMargins(36, 32, 36, 28)
    v.setSpacing(14)
    icon = QLabel()
    icon.setPixmap(QIcon(str(ICON)).pixmap(56, 56))
    v.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
    head = QLabel(t["terms_title"])
    head.setObjectName("aboutname")
    head.setAlignment(Qt.AlignmentFlag.AlignCenter)
    v.addWidget(head)
    # nine points do not fit a small screen: they scroll inside the dialog
    body = QTextBrowser()
    body.setObjectName("terms")
    body.setOpenExternalLinks(True)
    body.setHtml("".join(f"<p style='margin:0 0 10px 0'>{i}. {para}</p>" for i, para in enumerate(t["terms_body"], 1)))
    body.setMinimumHeight(320)
    body.setMaximumHeight(420)
    v.addWidget(body)
    v.addSpacing(8)
    row = QHBoxLayout()
    row.addStretch(1)
    if accept:
        quit_ = _button(t["quit"])
        quit_.clicked.connect(d.reject)
        row.addWidget(quit_)
    ok = _button(t["accept"] if accept else t["close"], primary=True)
    ok.setMinimumWidth(140)
    ok.clicked.connect(d.accept)
    row.addWidget(ok)
    v.addLayout(row)
    return d.exec() == QDialog.DialogCode.Accepted


def settings():
    from PySide6.QtCore import QSettings

    return QSettings("Besk Tech", "pii-roundtrip")


def forbid_network() -> None:
    """The app never needs the network: model libraries are told to stay offline, and any
    attempt to open a connection fails instead of silently sending data."""
    import os
    import socket

    # the models shipped inside the app (PyInstaller unpacks them next to the code)
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "models" / "hub"
    models = os.environ.get("PII_ROUNDTRIP_MODELS") or (str(bundled) if bundled.is_dir() else "")
    if models:
        os.environ["HF_HUB_CACHE"] = models
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    def refuse(*_args, **_kwargs):
        raise OSError("pii-roundtrip does not use the network")

    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]


def open_store(t: dict, folder: Path = DEFAULT_DIR) -> Store | None:
    """The vault key from the Keychain; on first launch create it, migrating old password vaults once."""
    secret = keys.get()
    if secret:
        return Store(secret, folder)
    probe = Store("migration-probe", folder)
    if probe.entries():
        prompt = t["migrate"]
        while True:
            pw, ok = QInputDialog.getText(None, t["migrate_title"], prompt, QLineEdit.EchoMode.Password)
            if not ok:
                return None
            legacy = Store(pw, folder) if pw else None
            if legacy and legacy.check():
                return legacy.rekey(keys.create())
            prompt = t["wrong"] + ". " + t["migrate"]
    return Store(keys.create(), folder)


def selftest() -> int:
    """Run the engine from the shipped models with the network forbidden; used to check a build."""
    import os

    eng = AppEngine()
    eng.load()
    text = "Договор между Ивановым Петром Сергеевичем, СНИЛС 112-233-445 95, и Сидоровой Анной."
    clean, session = eng.anonymize(text, "ru", None)
    restored = eng.deanonymize("Уважаемый [PERSON_1], договор с [PERSON_2] продлён. СНИЛС [SNILS_1].", session)
    print("models:", os.environ.get("HF_HUB_CACHE", "system cache"))
    print("rules only:", eng.rules_only)
    print("clean:", clean)
    print("restored:", restored)
    ok = not eng.rules_only and "Иванов" not in clean and "112-233" not in clean and "Сидоровой Анной" in restored
    print("SELFTEST", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main() -> None:
    forbid_network()
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    app = QApplication(sys.argv)
    app.setApplicationName("pii-roundtrip")
    app.setApplicationDisplayName("pii-roundtrip")
    app.setOrganizationName(MAKER)
    theme.apply(app)
    app.setWindowIcon(QIcon(str(ICON.with_suffix(".icns"))))
    conf = settings()
    lang = str(conf.value("lang", "")) or i18n.ui_language()
    t = i18n.TEXTS[lang]
    if conf.value("terms") != TERMS_VERSION:
        if not terms_dialog(None, t, accept=True):
            return
        conf.setValue("terms", TERMS_VERSION)
    store = open_store(t)
    if store is None:
        return
    windows: list[MainWindow] = []

    def open_window(code: str, old: MainWindow | None = None) -> None:
        conf.setValue("lang", code)
        win = MainWindow(store, i18n.TEXTS[code], engine=old.engine if old else None, lang=code)
        win.language_changed.connect(lambda c, w=win: open_window(c, w))
        if old is not None:
            win.setGeometry(old.geometry())
            if old.key:
                win.open_recent(old.key)
            old.close()
            windows.remove(old)
        windows.append(win)
        win.show()

    open_window(lang)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
