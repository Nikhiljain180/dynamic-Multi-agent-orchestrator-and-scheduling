from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet | None:
    key = settings.encryption_key.strip()
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(raw_key: str) -> str | None:
    f = _fernet()
    if not f:
        return None
    return f.encrypt(raw_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str | None:
    f = _fernet()
    if not f or not encrypted:
        return None
    try:
        return f.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None


def mask_api_key(raw_key: str) -> str:
    key = raw_key.strip()
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}_••••{key[-4:]}"
