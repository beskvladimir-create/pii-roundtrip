"""Command line.

  pii-roundtrip download-models
  pii-roundtrip anonymize -l en-GB -i letter.txt -o letter.clean.txt --vault letter.vault
  pii-roundtrip restore   -i answer.txt -o answer.restored.txt --vault letter.vault

The vault password is read from --password-file, from PII_ROUNDTRIP_PASSWORD, or asked
for (twice when a vault is created). Environment variables can be read by other
processes of the same user; prefer --password-file or the prompt on shared machines.
Models are downloaded once with download-models; after that no network is used.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import warnings
from collections import Counter


def _password(confirm: bool, password_file: str | None) -> str:
    if password_file:
        try:
            with open(password_file, encoding="utf-8") as f:
                return f.readline().rstrip("\n")
        except OSError as e:
            sys.exit(f"Cannot read the password file {password_file}: {e.strerror}")
    env = os.environ.get("PII_ROUNDTRIP_PASSWORD")
    if env:
        return env
    try:
        p = getpass.getpass("Vault password: ")
        if confirm and getpass.getpass("Repeat password: ") != p:
            sys.exit("Passwords do not match")
    except (EOFError, OSError):
        sys.exit("No password: there is no terminal to ask; use --password-file or PII_ROUNDTRIP_PASSWORD")
    return p


def _read(path: str | None, encoding: str) -> str:
    try:
        if path:
            with open(path, encoding=encoding) as f:
                return f.read()
        return sys.stdin.buffer.read().decode(encoding)
    except UnicodeDecodeError:
        sys.exit(f"Cannot decode the input as {encoding}; pass --encoding (for example cp1251)")
    except OSError as e:
        sys.exit(f"Cannot read {path}: {e.strerror}")


def _write(path: str | None, text: str) -> None:
    """Write with mode 0600, without following a symbolic link at the destination."""
    if not path:
        sys.stdout.write(text)
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as e:
        sys.exit(f"Cannot write {path}: {e.strerror}")
    os.fchmod(fd, 0o600)  # an existing file keeps its old mode otherwise
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="pii-roundtrip", description="Local reversible anonymisation of documents (ru, en-GB)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("download-models", help="download the models once (needs network)")
    a = sub.add_parser("anonymize", help="replace personal data with placeholders")
    a.add_argument("-l", "--lang", required=True, help="ru or en-GB")
    a.add_argument("-i", "--input", help="input file (default: stdin)")
    a.add_argument("-o", "--output", help="output file (default: stdout)")
    a.add_argument("--vault", required=True, help="encrypted vault file")
    a.add_argument("--append", action="store_true", help="continue the session stored in an existing vault")
    a.add_argument("--force", action="store_true", help="overwrite an existing vault")
    a.add_argument("--password-file", help="read the vault password from the first line of this file")
    a.add_argument("--encoding", default="utf-8")
    r = sub.add_parser("restore", help="put the original values back into an LLM answer")
    r.add_argument("-i", "--input")
    r.add_argument("-o", "--output")
    r.add_argument("--vault", required=True)
    r.add_argument("--password-file")
    r.add_argument("--encoding", default="utf-8")
    args = ap.parse_args(argv)

    from pii_roundtrip import vault
    from pii_roundtrip.core import Engine
    from pii_roundtrip.detect import Models
    from pii_roundtrip.errors import PiiRoundtripError

    warnings.simplefilter("default", DeprecationWarning)
    try:
        if args.cmd == "download-models":
            from pii_roundtrip.adapters import GlinerDetector, PiiGuardDetector

            for d in (PiiGuardDetector(offline=False), GlinerDetector(offline=False)):
                d.detect(
                    "Иван Петров" if "ru" in d.languages else "John Smith", "ru" if "ru" in d.languages else "en-GB"
                )
            print("Models downloaded; pii-roundtrip now works offline.", file=sys.stderr)
            return
        if args.cmd == "anonymize":
            exists = os.path.exists(args.vault)
            if exists and not (args.append or args.force):
                sys.exit(f"{args.vault} already exists; use --append to continue the session or --force to overwrite")
            password = _password(confirm=not exists, password_file=args.password_file)
            session = vault.load(args.vault, password) if args.append and exists else None
            text, session = Engine(Models(offline=True)).anonymize(_read(args.input, args.encoding), args.lang, session)
            vault.save(args.vault, session, password, overwrite=args.append or args.force)
            _write(args.output, text)
            kinds = Counter(lab.strip("[]").rsplit("_", 1)[0] for lab in session.mapping)
            print("Masked: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())), file=sys.stderr)
        else:
            session = vault.load(args.vault, _password(confirm=False, password_file=args.password_file))
            _write(args.output, Engine(Models(offline=True)).deanonymize(_read(args.input, args.encoding), session))
    except PiiRoundtripError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
