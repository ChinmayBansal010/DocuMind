import re
from pathlib import Path
from documind.config import settings
from documind.database import list_documents as fetch_documents, delete_document as remove_document

def safe_name(name):
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or "document"

def save_upload(name, data):
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds the {settings.max_upload_mb} MB upload limit.")
    target = settings.upload_dir / safe_name(name)
    if target.exists():
        target = settings.upload_dir / f"{target.stem}_{len(list(settings.upload_dir.iterdir()))}{target.suffix}"
    target.write_bytes(data)
    return target

def list_documents():
    return fetch_documents()

def delete_document(doc_id):
    remove_document(doc_id)
