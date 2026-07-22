"""Encrypt / decrypt sensitive configuration values."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def get_fernet() -> Fernet:
    settings = get_settings()
    raw = (settings.encryption_key or settings.secret_key).strip()
    if not raw:
        raw = "dev-insecure-default-key-change-me"
    # Accept either a valid Fernet key or derive one from an arbitrary secret.
    try:
        if len(raw) == 44:
            return Fernet(raw.encode("utf-8"))
    except Exception:
        pass
    return Fernet(_derive_fernet_key(raw))


def encrypt_value(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    try:
        return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Value may already be plaintext (migration / first write).
        return value


def mask_secret(value: str | None, *, visible: int = 4) -> str | None:
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]
