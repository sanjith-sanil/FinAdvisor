import os
import uuid

from fastapi import UploadFile

from app.core.config import settings


def ensure_upload_dir() -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


def save_upload_file(upload: UploadFile, prefix: str = "") -> str:
    ensure_upload_dir()
    ext = os.path.splitext(upload.filename or "")[1]
    filename = f"{prefix}{uuid.uuid4()}{ext}"
    path = os.path.join(settings.upload_dir, filename)
    with open(path, "wb") as f:
        f.write(upload.file.read())
    return path


def save_file_bytes(data: bytes, filename: str, prefix: str = "") -> str:
    ensure_upload_dir()
    ext = os.path.splitext(filename or "")[1]
    new_filename = f"{prefix}{uuid.uuid4()}{ext}"
    path = os.path.join(settings.upload_dir, new_filename)
    with open(path, "wb") as f:
        f.write(data)
    return path

