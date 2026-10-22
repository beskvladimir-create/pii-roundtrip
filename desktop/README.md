# pii-roundtrip for macOS

[Русская версия](README.ru.md)

A desktop app for people who do not use the command line. Drop in a document, send the cleaned version to any AI tool, drop or paste the answer back, and get it with the real names, numbers and addresses restored. Everything runs on your Mac.

## Download

The installer is attached to the latest desktop release on the [Releases page](https://github.com/beskvladimir-create/pii-roundtrip/releases). It is about 2 GB because the recognition models are inside: after installation the app needs no internet.

Requirements: macOS 12 or later, Apple silicon (M1 or newer).

The app is not yet signed with an Apple certificate, so macOS asks once before the first launch:

1. Drag pii-roundtrip into Applications.
2. Open it. macOS warns that the developer cannot be verified.
3. Open System Settings, Privacy & Security, and click Open Anyway next to the message about pii-roundtrip.

## How it works

1. Drop a Word file, a PDF or a text file into the window, or paste text with ⌘V. Personal data are replaced with labels such as `[PERSON_1]` or `[INN_1]`.
2. Save the cleaned file in the same format, or copy the text, and send it to the AI tool of your choice.
3. When the answer comes back, paste it with ⌘V or drop the file the AI tool returned. The app finds the matching document itself and puts the real values back, with Russian names in the right grammatical case.

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
- The link between labels and real values is stored encrypted (AES-256-GCM) in `~/Library/Application Support/pii-roundtrip`; the key is kept in the macOS Keychain.
- A cleaned Word file has its author and other properties erased; a cleaned PDF is rebuilt so that the masked values are removed from the file, not just covered. Before a cleaned file is saved, the app checks every part of it for the masked values.
- Detection is not perfect: on held-out set 5 the engine leaves at least one value in 0.2% of Russian and 0.7% of UK documents (see the [report](../REPORT.en.md)). Read the cleaned text before you send it.

## Build from source

```bash
cd desktop
uv sync --extra models                          # the window, the engine and its models
PYTHONPATH=.. uv run python -m pii_roundtrip_desktop
uv run pytest -q
```

The installer:

```bash
uv run python scripts/collect_models.py         # the pinned models into build/models
uv run pyinstaller -y pii-roundtrip.spec        # dist/pii-roundtrip.app
./dist/pii-roundtrip.app/Contents/MacOS/pii-roundtrip --selftest
bash scripts/make_dmg.sh 0.3.1                  # dist/pii-roundtrip-0.3.1.dmg
```

The desktop app has its own environment so that its libraries do not change the benchmark environment. Licences of the bundled components are listed in the app (About, Third-party licences) and next to it in the installer.
