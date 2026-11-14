import base64
import hashlib
import io
import os
import re
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, UploadFile

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ENCRYPTED_PREFIX = b"DMENC1"


def _cipher() -> AESGCM | None:
    if not settings.encryption_key:
        return None
    try:
        key = base64.urlsafe_b64decode(settings.encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("DOCUMENT_ENCRYPTION_KEY must be URL-safe base64 for 32 bytes.") from exc
    if len(key) != 32:
        raise RuntimeError("DOCUMENT_ENCRYPTION_KEY must decode to exactly 32 bytes.")
    return AESGCM(key)


def sanitize_display_name(filename: str) -> str:
    basename = Path(filename.replace("\\", "/")).name
    clean = re.sub(r"[\x00-\x1f/\\]", "_", basename).strip(" .")
    return clean[:255] or "contract"


def _validate_signature(data: bytes, extension: str) -> None:
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The file content is not a valid PDF.")
    if extension == ".docx" and not (
        data.startswith(b"PK\x03\x04") and zipfile.is_zipfile(io.BytesIO(data))
    ):
        raise HTTPException(status_code=415, detail="The file content is not a valid DOCX document.")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise HTTPException(
                        status_code=415, detail="The file content is not a valid DOCX document."
                    )
                if archive.testzip() is not None:
                    raise HTTPException(
                        status_code=415, detail="The DOCX file is malformed or corrupted."
                    )
        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=415, detail="The DOCX file is malformed or corrupted."
            ) from exc
    if extension == ".txt":
        if b"\x00" in data:
            raise HTTPException(status_code=415, detail="The text file contains unsupported binary data.")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Text uploads must use UTF-8 encoding.") from exc


def _read_limited(upload: UploadFile) -> tuple[bytes, str, str]:
    name = sanitize_display_name(upload.filename or "contract")
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only PDF, DOCX, and TXT files are supported.")

    digest = hashlib.sha256()
    content = bytearray()
    limit = settings.max_upload_mb * 1024 * 1024
    stream: BinaryIO = upload.file
    while True:
        block = stream.read(min(1024 * 1024, limit + 1 - len(content)))
        if not block:
            break
        content.extend(block)
        digest.update(block)
        if len(content) > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
            )
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    _validate_signature(bytes(content), extension)
    return bytes(content), name, digest.hexdigest()


def save_upload(upload: UploadFile, owner_id: str, project_id: str) -> tuple[Path, str, str, str]:
    content, name, digest = _read_limited(upload)
    extension = Path(name).suffix.lower()
    owner_key = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:32]
    project_key = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:32]
    directory = settings.upload_dir / owner_key / project_key
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"{uuid.uuid4().hex}{extension}"
    cipher = _cipher()
    stored = content
    if cipher is not None:
        nonce = os.urandom(12)
        stored = ENCRYPTED_PREFIX + nonce + cipher.encrypt(nonce, content, None)
    with path.open("xb") as file:
        os.chmod(path, 0o600)
        file.write(stored)
    return path, name, digest, extension.removeprefix(".")


@contextmanager
def readable_copy(path: str | Path):
    source = Path(path)
    with source.open("rb") as file:
        data = file.read()
    if data.startswith(ENCRYPTED_PREFIX):
        cipher = _cipher()
        if cipher is None:
            raise RuntimeError("DOCUMENT_ENCRYPTION_KEY is required to read this encrypted document.")
        nonce = data[len(ENCRYPTED_PREFIX) : len(ENCRYPTED_PREFIX) + 12]
        data = cipher.decrypt(nonce, data[len(ENCRYPTED_PREFIX) + 12 :], None)
        suffix = source.suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temporary:
            os.chmod(temporary.name, 0o600)
            temporary.write(data)
            temporary.flush()
            yield Path(temporary.name)
    else:
        yield source


def remove_file(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
