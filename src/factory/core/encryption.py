from cryptography.fernet import Fernet

from factory.core.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    if not settings.encryption_key:
        raise RuntimeError(
            "ARCHITECT_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(settings.encryption_key.encode())


def encrypt(data: str) -> bytes:
    return _get_fernet().encrypt(data.encode())


def decrypt(data: bytes) -> str:
    return _get_fernet().decrypt(data).decode()
