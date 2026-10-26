"""Sessions of the desktop app: one encrypted vault per document, plus its last texts.

The vault key is a random 256-bit secret kept in the macOS login Keychain (see keys.py),
so the user never types a password; copying the vault folder to another computer or into
a backup is useless without it. The texts shown when a recent document is reopened (the
cleaned request and the last answer) are encrypted with the same key (AES-256-GCM).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pii_roundtrip import vault
from pii_roundtrip.core import Session

# the standard place for app data on macOS, never inside a user folder such as ~/pii-roundtrip
if os.name == "nt":  # %APPDATA%\pii-roundtrip on Windows
    DEFAULT_DIR = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "pii-roundtrip"
else:
    DEFAULT_DIR = Path.home() / "Library" / "Application Support" / "pii-roundtrip"
_INDEX = "index.json"


@dataclass
class Entry:
    key: str  # file name of the vault
    title: str  # what the user sees: the document name
    lang: str
    created: str


class Store:
    def __init__(self, secret: str, folder: Path = DEFAULT_DIR):
        if not secret:
            raise ValueError("empty secret")
        self.folder = folder
        self.secret = secret
        self._aes = AESGCM(hashlib.sha256(("texts:" + secret).encode()).digest())
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)

    # ---------- index ----------

    def _index_path(self) -> Path:
        return self.folder / _INDEX

    def entries(self) -> list[Entry]:
        p = self._index_path()
        if not p.exists():
            return []
        raw = json.loads(p.read_text(encoding="utf-8"))
        return [Entry(**e) for e in raw if (self.folder / e["key"]).exists()]

    def _write_index(self, entries: list[Entry]) -> None:
        tmp = self._index_path().with_suffix(".tmp")
        tmp.write_text(json.dumps([e.__dict__ for e in entries], ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self._index_path())

    # ---------- sessions ----------

    def save(self, title: str, session: Session, key: str | None = None) -> Entry:
        """Store a new session, or overwrite the one with ``key`` (a follow-up message)."""
        now = datetime.now()
        if key is None:
            slug = re.sub(r"[^\w.-]+", "_", title)[:40] or "document"
            key = f"{now:%Y%m%d-%H%M%S}-{slug}.vault"
        vault.save(self.folder / key, session, self.secret, overwrite=True)
        entries = [e for e in self.entries() if e.key != key]
        entry = Entry(key=key, title=title, lang=session.lang, created=now.isoformat(timespec="minutes"))
        self._write_index([entry, *entries])
        return entry

    def load(self, key: str) -> Session:
        return vault.load(self.folder / key, self.secret)

    def delete(self, key: str) -> None:
        for p in (self.folder / key, self.folder / (key + ".texts")):
            p.unlink(missing_ok=True)
        self._write_index([e for e in self.entries() if e.key != key])

    def delete_all(self) -> None:
        """Every document of the app: vaults, their texts and the index, including vaults
        that the index no longer lists."""
        for p in self.folder.iterdir():
            if p.name.endswith((".vault", ".vault.texts", ".tmp")) or p.name == _INDEX:
                p.unlink(missing_ok=True)

    def check(self) -> bool:
        """True if the secret opens the existing vaults (or there are none yet)."""
        entries = self.entries()
        if not entries:
            return True
        try:
            self.load(entries[0].key)
            return True
        except Exception:
            return False

    # ---------- texts shown when a document is reopened ----------

    def save_texts(self, key: str, texts: dict[str, str]) -> None:
        nonce = os.urandom(12)
        blob = nonce + self._aes.encrypt(nonce, json.dumps(texts, ensure_ascii=False).encode(), key.encode())
        p = self.folder / (key + ".texts")
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.chmod(tmp, 0o600)
        tmp.replace(p)

    def update_texts(self, key: str, texts: dict[str, str]) -> None:
        """Change some of the saved texts, keeping the others."""
        merged = self.load_texts(key)
        merged.update(texts)
        self.save_texts(key, merged)

    def load_texts(self, key: str) -> dict[str, str]:
        p = self.folder / (key + ".texts")
        if not p.exists():
            return {}
        blob = p.read_bytes()
        return json.loads(self._aes.decrypt(blob[:12], blob[12:], key.encode()))

    def rekey(self, new_secret: str) -> "Store":
        """Re-encrypt every vault and text file with a new secret (migration from a typed password)."""
        new = Store(new_secret, self.folder)
        for e in self.entries():
            session = self.load(e.key)
            texts = self.load_texts(e.key)
            vault.save(self.folder / e.key, session, new_secret, overwrite=True)
            if texts:
                new.save_texts(e.key, texts)
        return new
