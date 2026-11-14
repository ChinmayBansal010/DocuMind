import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.azure_ai import analyze_document_bytes
from app.services.errors import AzureServiceError
from documind.documents import extract_document, split_text

MAX_DI_REQUEST_BYTES = 4 * 1024 * 1024
MAX_DI_REQUEST_PAGES = 2


def _pdf_bytes(document: fitz.Document, first_page: int, last_page: int) -> bytes:
    segment = fitz.open()
    segment.insert_pdf(document, from_page=first_page, to_page=last_page)
    content = segment.tobytes(garbage=4, deflate=True)
    segment.close()
    if len(content) > MAX_DI_REQUEST_BYTES and first_page < last_page:
        raise OverflowError
    if len(content) > MAX_DI_REQUEST_BYTES:
        raise AzureServiceError(
            "Document Intelligence",
            "a single PDF page exceeds the 4 MB F0 request limit, even after PDF compression.",
            status_code=413,
        )
    return content


def _analyze_pdf(path: Path, db: Session) -> dict:
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise ValueError("The PDF could not be opened.") from exc
    if document.page_count == 0:
        document.close()
        raise ValueError("The PDF has no pages.")
    total_pages = document.page_count
    all_pages = []
    all_tables = []
    all_paragraphs = []
    content_parts = []
    start = 0
    try:
        while start < total_pages:
            end = min(start + MAX_DI_REQUEST_PAGES - 1, total_pages - 1)
            try:
                payload = _pdf_bytes(document, start, end)
            except OverflowError:
                end = start
                payload = _pdf_bytes(document, start, end)
            page_units = end - start + 1
            result = analyze_document_bytes(
                payload,
                content_type="application/pdf",
                db=db,
                page_units=page_units,
            )
            result_pages = result.get("pages", [])
            if len(result_pages) != page_units:
                raise AzureServiceError(
                    "Document Intelligence",
                    "returned an unexpected page count; no page citations were saved.",
                    status_code=502,
                )
            for local_index, page in enumerate(result_pages):
                page_number = start + local_index + 1
                lines = [
                    line.get("content", "").strip()
                    for line in page.get("lines", [])
                    if line.get("content", "").strip()
                ]
                text = "\n".join(lines)
                if not text and page_units == 1:
                    text = result.get("content", "").strip()
                if text:
                    content_parts.append(f"[Page {page_number}]\n{text}")
                all_pages.append({**page, "pageNumber": page_number})
            for collection, destination in (
                (result.get("tables", []), all_tables),
                (result.get("paragraphs", []), all_paragraphs),
            ):
                for item in collection:
                    for region in item.get("boundingRegions", []):
                        if isinstance(region.get("pageNumber"), int):
                            region["pageNumber"] += start
                    destination.append(item)
            start = end + 1
    finally:
        document.close()
    extracted = "\n\n".join(content_parts).strip()
    if not extracted:
        raise ValueError("Azure Document Intelligence found no readable text.")
    return {
        "text": extracted,
        "pages": total_pages,
        "layout_data": {
            "model_id": settings.document_intelligence_model,
            "pages": all_pages,
            "tables": all_tables,
            "paragraphs": all_paragraphs,
        },
    }


def _convert_office_to_pdf(path: Path, output_dir: Path) -> Path:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        raise AzureServiceError(
            "Document Intelligence",
            "DOCX page conversion requires LibreOffice in the application runtime.",
        )
    profile = output_dir / "libreoffice-profile"
    try:
        result = subprocess.run(
            [
                executable,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AzureServiceError(
            "Document Intelligence", "could not convert this Office file into bounded PDF pages."
        ) from exc
    converted = output_dir / f"{path.stem}.pdf"
    if result.returncode or not converted.is_file():
        raise AzureServiceError(
            "Document Intelligence", "could not convert this Office file into bounded PDF pages."
        )
    return converted


def extract(path: Path, db: Session) -> dict:
    extension = path.suffix.casefold()
    if extension in {".pdf", ".docx"}:
        if extension == ".pdf":
            return _analyze_pdf(path, db)
        with tempfile.TemporaryDirectory(prefix="documind-di-") as directory:
            pdf_path = _convert_office_to_pdf(path, Path(directory))
            parsed = _analyze_pdf(pdf_path, db)
            parsed["layout_data"]["converted_from"] = "docx"
            return parsed
    if extension in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
        }[extension]
        result = analyze_document_bytes(
            path.read_bytes(),
            content_type=content_type,
            db=db,
            page_units=1,
        )
        pages = result.get("pages", [])
        if not pages:
            raise ValueError("Azure Document Intelligence found no readable text.")
        lines = [
            line.get("content", "").strip()
            for page in pages
            for line in page.get("lines", [])
            if line.get("content", "").strip()
        ]
        if not lines:
            raise ValueError("Azure Document Intelligence found no readable text.")
        return {
            "text": "[Page 1]\n" + "\n".join(lines),
            "pages": len(pages),
            "layout_data": result,
        }
    return extract_document(path)


def chunks_with_pages(text: str, chunk_size: int, overlap: int) -> list[dict]:
    result = []
    markers = list(re.finditer(r"\[Page (\d+)\]", text))
    if markers:
        page_texts = [
            (
                int(marker.group(1)),
                text[marker.end() : markers[index + 1].start() if index + 1 < len(markers) else len(text)],
            )
            for index, marker in enumerate(markers)
        ]
    else:
        page_texts = [(None, text)]
    for page_number, page_text in page_texts:
        for chunk in split_text(page_text, chunk_size=chunk_size, overlap=overlap):
            result.append(
                {"index": len(result), "page_number": page_number, "text": chunk}
            )
    return result
