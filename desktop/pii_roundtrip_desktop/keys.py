"""The vault key: a random 256-bit secret in the macOS login Keychain.

It replaces a typed password. Anything running as the logged-in user can use it, as with
other Keychain items; a copy of the vault folder on another computer cannot be opened.
"""

from __future__ import annotations

import secrets

SERVICE = "tech.besk.pii-roundtrip"
ACCOUNT = "vault-key"


def get() -> str | None:
    import keyring

    return keyring.get_password(SERVICE, ACCOUNT)


def create() -> str:
    import keyring

    secret = secrets.token_hex(32)
    keyring.set_password(SERVICE, ACCOUNT, secret)
    return secret
