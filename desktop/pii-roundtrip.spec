# PyInstaller build of the app: on macOS one .app, on Windows a folder with pii-roundtrip.exe; with the
# engine, the models and no Python needed.
# uv run pyinstaller pii-roundtrip.spec --noconfirm
import runpy
import sys

from PyInstaller.utils.hooks import collect_all

runpy.run_path("scripts/collect_licenses.py", run_name="__main__")  # build/licenses, shipped below

datas, binaries, hiddenimports = [("build/models", "models"), ("pii_roundtrip_desktop/fonts", "pii_roundtrip_desktop/fonts"), ("pii_roundtrip_desktop/icon.svg", "pii_roundtrip_desktop"), ("pii_roundtrip_desktop/icon.ico", "pii_roundtrip_desktop"), ("build/licenses", "licenses")], [], []
for pkg in ("presidio_analyzer", "presidio_anonymizer", "pymorphy3", "pymorphy3_dicts_ru", "ru_core_news_sm", "spacy", "pii_guard", "gliner2", "transformers", "tokenizers", "huggingface_hub", "docx", "pypdf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += ["pii_roundtrip", "pii_roundtrip.adapters.pii_guard", "pii_roundtrip.adapters.gliner"]

a = Analysis(
    ["pii_roundtrip_desktop/__main__.py"],
    pathex=[".", ".."],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "torchvision", "torchaudio", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL"],
    noarchive=False,
)
# Only QtCore, QtGui (with QtDBus), QtWidgets and QtSvg are used. The rest is left out, notably
# Qt Virtual Keyboard, which is GPL-only and must not ship in this Apache-licensed app.
QT_UNUSED = ("QtQuick", "QtQml", "QtVirtualKeyboard", "QtPdf", "QtNetwork", "QtOpenGL",
             "platforminputcontexts", "networkinformation", "/tls/", "qtvirtualkeyboard")
a.binaries = [b for b in a.binaries if not any(q in b[0] for q in QT_UNUSED)]
a.datas = [d for d in a.datas if not any(q in d[0] for q in QT_UNUSED)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pii-roundtrip",
    console=False,
    argv_emulation=False,
    icon="pii_roundtrip_desktop/icon.ico" if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="pii-roundtrip")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="pii-roundtrip.app",
        icon="pii_roundtrip_desktop/icon.icns",
        bundle_identifier="tech.besk.pii-roundtrip",
        version="0.5.4",
        info_plist={
            "CFBundleDisplayName": "pii-roundtrip",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "14.0",
            "NSHumanReadableCopyright": "Besk Tech. Apache License 2.0.",
        },
    )
