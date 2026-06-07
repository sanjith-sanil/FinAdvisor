from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.email_encryption_key.encode("utf-8")
    return Fernet(key)


def encrypt_text(value: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    fernet = _get_fernet()
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
