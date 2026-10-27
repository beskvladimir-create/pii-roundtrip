"""Gather the licences of everything shipped inside the app into build/licenses.

pii-roundtrip.spec runs it at the start of every build; it can also be run on its own:
    uv run python scripts/collect_licenses.py

The result is shipped with the app (inside the .app on macOS, in the program folder on Windows) and next to the app in the .dmg:
THIRD_PARTY_NOTICES.txt lists every component with its licence and source, and
licenses/ holds the full licence texts, copied from each installed package where it ships
them and from desktop/licenses for the models, fonts, Qt and the Russian dictionary.
"""

from __future__ import annotations

import importlib.metadata as md
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TEXTS = HERE / "licenses"
OUT = HERE / "build" / "licenses"

# build and test tools: installed in the environment, not shipped in the app
DEV_ONLY = {
    "altgraph",
    "iniconfig",
    "macholib",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "pytest",
    "ruff",
}
# Qt packages that are installed with PySide6 but left out of the app by the .spec
NOT_SHIPPED = {"pyside6-addons", "pyside6-webengine", "pyside6-pdf"}

# standard texts for packages that ship no licence file of their own
FALLBACK = {"LGPL": "LGPL-3.0.txt", "Apache": "Apache-2.0.txt"}
# licence files taken from the project repository when the package ships none
FROM_REPO = {"presidio-analyzer": "MIT-presidio.txt", "presidio-anonymizer": "MIT-presidio.txt"}
# same project and copyright holder, licence file shipped by the sibling package
COPY_FROM = {"pymorphy3-dicts-ru": "pymorphy3"}

MODELS = [
    (
        "GLiNER Guard Omni",
        "HiveTrace",
        "https://huggingface.co/hivetrace/gliner-guard-omni",
        "Apache-2.0",
    ),
    (
        "rubert-base-pii-ner",
        "Red Madrobot (redmadrobot-rnd)",
        "https://huggingface.co/redmadrobot-rnd/rubert-base-pii-ner",
        "Apache-2.0",
    ),
]
FONTS = [
    ("Inter", "Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter)", "OFL-Inter.txt"),
    (
        "Space Grotesk",
        "Copyright 2020 The Space Grotesk Project Authors (https://github.com/floriankarsten/space-grotesk)",
        "OFL-SpaceGrotesk.txt",
    ),
    (
        "Playfair Display",
        "Copyright 2017 The Playfair Display Project Authors (https://github.com/clauseggers/Playfair-Display), "
        'with Reserved Font Name "Playfair Display"',
        "OFL-PlayfairDisplay.txt",
    ),
]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _licence(dist) -> str:
    m = dist.metadata
    expr = (m.get("License-Expression") or "").strip()
    if expr:
        return expr
    classifiers = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers)
    return (m.get("License") or "see licence file").strip().splitlines()[0][:80]


def _home(dist) -> str:
    m = dist.metadata
    for entry in m.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("source", "source code", "repository", "homepage", "home"):
            return url.strip()
    return (m.get("Home-page") or f"https://pypi.org/project/{m['Name']}/").strip()


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "packages").mkdir(parents=True)
    for f in TEXTS.glob("*.txt"):
        shutil.copy(f, OUT / f.name)

    lines = [
        "pii-roundtrip: third-party components",
        "=====================================",
        "",
        "pii-roundtrip is open-source software by Besk Tech under the Apache License 2.0.",
        "It includes the components below, each under its own licence. Full licence texts are in",
        "the licenses folder next to this file.",
        "",
        "Models",
        "------",
    ]
    for name, author, url, lic in MODELS:
        lines.append(f"{name}, by {author}. {lic}. {url}")
    lines.append("Both models are included unmodified. Licence text: Apache-2.0.txt.")
    lines += [
        "",
        "Russian morphological dictionary",
        "--------------------------------",
        "pymorphy3-dicts-ru: package code under the MIT licence; dictionary data from OpenCorpora",
        "(http://opencorpora.org) under Creative Commons Attribution-ShareAlike 3.0, included",
        "unmodified. Licence text: CC-BY-SA-3.0.txt.",
        "",
        "Fonts (SIL Open Font License 1.1)",
        "---------------------------------",
    ]
    for name, copyright_, text in FONTS:
        lines.append(f"{name}: {copyright_}. Licence text: {text}.")
    lines += [
        "",
        "Qt and PySide6 (GNU LGPL 3.0)",
        "-----------------------------",
        "The interface uses Qt 6 (QtCore, QtGui, QtDBus, QtWidgets, QtSvg) through PySide6, under the",
        "GNU Lesser General Public License version 3. They are included as separate, unmodified",
        "dynamic libraries in Contents/Frameworks and can be replaced with other compatible builds.",
        "Source code: https://download.qt.io/official_releases/qt/ and",
        "https://code.qt.io/cgit/pyside/pyside-setup.git. Licence texts: LGPL-3.0.txt, GPL-3.0.txt.",
        "",
        "Python packages",
        "---------------",
    ]
    seen = set()
    for dist in sorted(md.distributions(), key=lambda d: _norm(d.metadata["Name"])):
        name = _norm(dist.metadata["Name"])
        if name in seen or name in DEV_ONLY or name in NOT_SHIPPED:
            continue
        seen.add(name)
        lines.append(f"{dist.metadata['Name']} {dist.version}: {_licence(dist)}. {_home(dist)}")
        target = OUT / "packages" / name
        for f in dist.files or []:
            parts = [x.upper() for x in Path(str(f)).parts]
            if any(k in x for x in parts for k in ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")):
                src = Path(dist.locate_file(f))
                if src.is_file() and src.suffix not in (".py", ".pyc"):
                    target.mkdir(exist_ok=True)
                    shutil.copy(src, target / Path(str(f)).name)
        if not target.exists():
            # the package ships no licence file: record its licence and add the standard text
            target.mkdir()
            licence = _licence(dist)
            note = [f"{dist.metadata['Name']} {dist.version}", f"Licence: {licence}", f"Source: {_home(dist)}"]
            for key, text in FALLBACK.items():
                if key in licence:
                    note.append(f"Licence text: ../../{text}")
                    break
            if name in COPY_FROM:
                donor = md.distribution(COPY_FROM[name])
                for f in donor.files or []:
                    if Path(str(f)).name.upper().startswith("LICENSE") and Path(str(f)).suffix != ".py":
                        shutil.copy(Path(donor.locate_file(f)), target / Path(str(f)).name)
                note.append(f"The licence file of {COPY_FROM[name]}, from the same project, is included.")
            if name in FROM_REPO:
                note.append(f"Licence text from the project repository: ../../{FROM_REPO[name]}")
            (target / "LICENSE-NOTE.txt").write_text("\n".join(note) + "\n", encoding="utf-8")
    python_licence = (
        Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    )
    if python_licence.is_file():
        shutil.copy(python_licence, OUT / "Python-PSF.txt")
    lines += [
        "",
        f"Python {sys.version.split()[0]}: PSF License Agreement. Licence text: Python-PSF.txt.",
        "",
    ]
    (OUT / "THIRD_PARTY_NOTICES.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(seen)} packages, notices in {OUT}")


if __name__ == "__main__":
    main()
