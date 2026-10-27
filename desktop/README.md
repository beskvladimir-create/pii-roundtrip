# pii-roundtrip for macOS and Windows

[Русская версия](README.ru.md)

A desktop app for people who do not use the command line. Drop in a document, send the cleaned version to any AI tool, drop or paste the answer back, and get it with the real names, numbers and addresses restored. Everything runs on your computer.

## Download

The installers are attached to the latest release on the [Releases page](https://github.com/beskvladimir-create/pii-roundtrip/releases): `pii-roundtrip-mac.dmg` for macOS and `pii-roundtrip-windows-setup.exe` for Windows. Each is about 2 GB because the recognition models are inside: after installation the app needs no internet. The release notes list the SHA-256 of each file.

Requirements:
- macOS 14 (Sonoma) or later on a Mac with Apple silicon (M1 or newer). Intel Macs are not supported.
- Windows 10 or 11, 64-bit. The Windows version is a beta: it is built and checked by a scripted run of the installed program on a Windows machine, and has been used by few people so far.

The app is not yet signed, so the system asks once before the first launch.

On a Mac:
1. Drag pii-roundtrip into Applications.
2. Open it. macOS warns that the developer cannot be verified.
3. Open System Settings, Privacy & Security, and click Open Anyway next to the message about pii-roundtrip.

On Windows:
1. Run `pii-roundtrip-windows-setup.exe`. If Windows shows "Windows protected your PC", click More info, then Run anyway.
2. The installer installs the app for your user, without administrator rights, and adds it to the Start menu.

The app does not check for updates, because it makes no network connections. New versions are announced on [pii-roundtrip.besk.tech](https://pii-roundtrip.besk.tech) and on the Releases page.

## How it works

1. Drop a Word file, a PDF or a text file into the window, or paste text with ⌘V (Ctrl+V on Windows). Personal data are replaced with labels such as `[PERSON_1]` or `[INN_1]`.
2. Save the cleaned file in the same format, or copy the text, and send it to the AI tool of your choice.
3. When the answer comes back, paste it with ⌘V (Ctrl+V) or drop the file the AI tool returned. The app finds the matching document itself and puts the real values back, with Russian names in the right grammatical case.

What is kept when restoring:

| The AI tool returns | Result |
| --- | --- |
| Text in the chat | Values restored, names inflected for their context |
| A Word file | Values restored in the AI tool's document, its formatting kept |
| A new PDF with text | Values restored in the AI tool's layout |
| Your cleaned file unchanged | Your original file, byte for byte |
| A PDF whose pages were redrawn as pictures | Values restored, simple layout, with a note why |

## Privacy

- The app blocks its own network connections and has no telemetry or accounts.
- The link between labels and real values is stored encrypted (AES-256-GCM): on macOS in `~/Library/Application Support/pii-roundtrip` with the key in the macOS Keychain, on Windows in `%APPDATA%\pii-roundtrip` with the key in Windows Credential Manager.
- A cleaned Word file has its author and other properties erased; a cleaned PDF is rebuilt so that the masked values are removed from the file, not just covered. Before a cleaned file is saved, the app checks every part of it for the masked values.
- Detection is not perfect: on held-out set 7 engine 0.5 leaves at least one value in 0.3% of Russian and 0.2% of UK documents (see the [report](../REPORT.en.md)). Read the cleaned text before you send it.

## Build from source

```bash
cd desktop
uv sync --extra models                          # the window, the engine and its models
PYTHONPATH=.. uv run python -m pii_roundtrip_desktop
uv run pytest -q
```

The installer on macOS:

```bash
PYTHONPATH=.. uv run python scripts/collect_models.py   # the pinned models into build/models
PYTHONPATH=.. uv run pyinstaller -y pii-roundtrip.spec  # dist/pii-roundtrip.app
./dist/pii-roundtrip.app/Contents/MacOS/pii-roundtrip --selftest
./dist/pii-roundtrip.app/Contents/MacOS/pii-roundtrip --uitest uitest   # drives the window, screenshots in uitest/
bash scripts/make_dmg.sh 0.5.3                          # dist/pii-roundtrip-0.5.3.dmg
```

On Windows the same steps build `dist\pii-roundtrip\pii-roundtrip.exe`, and `iscc /DVersion=0.5.3 scripts\windows.iss` makes the installer. The workflow `.github/workflows/windows.yml` does this on a Windows machine on GitHub, runs `--selftest` and `--uitest` on the installed program, and attaches the installer to a release.

The desktop app has its own environment so that its libraries do not change the benchmark environment. Licences of the bundled components are listed in the app (About, Third-party licences) and shipped with it.
