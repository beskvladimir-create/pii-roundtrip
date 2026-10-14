"""Command line.

  pii-roundtrip download-models
  pii-roundtrip anonymize -l uk -i letter.txt -o letter.clean.txt --vault letter.vault
  pii-roundtrip restore   -i answer.txt -o answer.restored.txt --vault letter.vault

The vault password is read from PII_ROUNDTRIP_PASSWORD or asked for (twice when a vault is created).
Models are downloaded once with download-models; after that no network is used.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections import Counter


def _password(confirm: bool) -> str:
    env = os.environ.get("PII_ROUNDTRIP_PASSWORD")
    if env:
        return env
    p = getpass.getpass("Vault password: ")
    if confirm and getpass.getpass("Repeat password: ") != p:
        sys.exit("Passwords do not match")
    return p


def _read(path: str | None, encoding: str) -> str:
    try:
        if path:
            with open(path, encoding=encoding) as f:
                return f.read()
        return sys.stdin.buffer.read().decode(encoding)
    except UnicodeDecodeError:
        sys.exit(f"Cannot decode the input as {encoding}; pass --encoding (for example cp1251)")


def _write(path: str | None, text: str, private: bool) -> None:
    if not path:
        sys.stdout.write(text)
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if private else 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pii-roundtrip", description="Local reversible anonymisation of documents (ru, uk)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("download-models", help="download the models once (needs network)")
    a = sub.add_parser("anonymize", help="replace personal data with placeholders")
    a.add_argument("-l", "--lang", required=True, help="ru or uk")
    a.add_argument("-i", "--input", help="input file (default: stdin)")
    a.add_argument("-o", "--output", help="output file (default: stdout)")
    a.add_argument("--vault", required=True, help="encrypted vault file")
    a.add_argument("--append", action="store_true", help="continue the session stored in an existing vault")
    a.add_argument("--force", action="store_true", help="overwrite an existing vault")
    a.add_argument("--encoding", default="utf-8")
    r = sub.add_parser("restore", help="put the original values back into an LLM answer")
    r.add_argument("-i", "--input")
    r.add_argument("-o", "--output")
    r.add_argument("--vault", required=True)
    r.add_argument("--encoding", default="utf-8")
    args = ap.parse_args(argv)

    from pii_roundtrip import vault
    from pii_roundtrip.core import Engine
    from pii_roundtrip.detect import Models

    try:
        if args.cmd == "download-models":
            m = Models(offline=False)
            _ = m.gliner, m.pii_guard
            print("Models downloaded; pii-roundtrip now works offline.", file=sys.stderr)
            return
        engine = Engine(Models(offline=True))
        if args.cmd == "anonymize":
            exists = os.path.exists(args.vault)
            password = _password(confirm=not exists)
            session = vault.load(args.vault, password) if args.append and exists else None
            text, session = engine.anonymize(_read(args.input, args.encoding), args.lang, session)
            vault.save(args.vault, session, password, overwrite=args.append or args.force)
            _write(args.output, text, private=False)
            kinds = Counter(lab.strip("[]").rsplit("_", 1)[0] for lab in session.mapping)
            print("Masked: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())), file=sys.stderr)
        else:
            session = vault.load(args.vault, _password(confirm=False))
            _write(args.output, engine.deanonymize(_read(args.input, args.encoding), session), private=True)
    except vault.VaultError as e:
        sys.exit(str(e))
    except OSError as e:
        if "local_files_only" in str(e) or "offline" in str(e).lower():
            sys.exit("Models are not available locally. Run once: pii-roundtrip download-models")
        raise


if __name__ == "__main__":
    main()
