"""Encrypted local vault for sessions.

AES-256-GCM with a key derived from the password by scrypt. File layout:
    MAGIC(4) | log2(n)(1) | r(1) | p(1) | salt(16) | nonce(12) | ciphertext
The whole header is authenticated data, so tampering with the parameters breaks
decryption. Writes are atomic: a 0600 temporary file, fsync, then rename. The magic
"ANV2" is format 2; format 1 existed only before the first public release.

The vault protects the mapping at rest. While the process runs, the session and the
restored text are in memory in plain form.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from pii_roundtrip.core import Session
from pii_roundtrip.errors import VaultError

MAGIC = b"ANV2"
N_LOG2, R, P = 17, 8, 1  # about 128 MB of memory and a fraction of a second per key


def _key(password: str, salt: bytes, n_log2: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**n_log2, r=r, p=p).derive(password.encode("utf-8"))


def save(path: str | Path, session: Session, password: str, overwrite: bool = False) -> None:
    if not password:
        raise VaultError("The vault password must not be empty")
    path = Path(path)
    if path.is_symlink():
        raise VaultError(f"{path} is a symbolic link; not writing")
    if path.exists() and not overwrite:
        raise VaultError(
            f"{path} already exists; choose another file, use --append to continue the session, or --force to overwrite"
        )
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + bytes([N_LOG2, R, P]) + salt + nonce
    data = json.dumps(session.to_dict(), ensure_ascii=False).encode("utf-8")
    blob = header + AESGCM(_key(password, salt, N_LOG2, R, P)).encrypt(nonce, data, header)

    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load(path: str | Path, password: str) -> Session:
    path = Path(path)
    try:
        blob = path.read_bytes()
    except OSError as e:
        raise VaultError(f"Cannot read {path}: {e.strerror}") from None
    if len(blob) < 4 + 3 + 16 + 12 + 16 or blob[:4] != MAGIC:
        raise VaultError(f"{path} is not a pii-roundtrip vault or is damaged")
    n_log2, r, p = blob[4], blob[5], blob[6]
    if not (10 <= n_log2 <= 22 and 1 <= r <= 32 and 1 <= p <= 16):
        raise VaultError(f"{path}: invalid key parameters, the file is damaged")
    header, ct = blob[:35], blob[35:]
    salt, nonce = header[7:23], header[23:35]
    try:
        data = AESGCM(_key(password, salt, n_log2, r, p)).decrypt(nonce, ct, header)
    except InvalidTag:
        raise VaultError("Wrong password, or the vault file is damaged") from None
    return Session.from_dict(json.loads(data))
