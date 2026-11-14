from pathlib import Path
import csv
import re

SUPPORTED = {".pdf",".docx",".txt",".md",".pptx",".xlsx",".csv",".png",".jpg",".jpeg",".tif",".tiff"}

def extract_document(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type: {ext}")
    text, pages = "", None
    if ext == ".pdf":
        import fitz
        doc = fitz.open(path)
        pages = len(doc)
        text = "\n\n".join(f"[Page {i+1}]\n{page.get_text('text')}" for i, page in enumerate(doc))
        if not text.strip():
            text = _ocr_pdf(path)
    elif ext == ".docx":
        from docx import Document
        d = Document(path)
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        text = "\n".join(parts)
    elif ext == ".pptx":
        from pptx import Presentation
        prs = Presentation(path)
        pages = len(prs.slides)
        text = "\n\n".join(f"[Slide {i+1}]\n" + "\n".join(s.text for s in slide.shapes if getattr(s, "has_text_frame", False) and s.text.strip()) for i, slide in enumerate(prs.slides))
    elif ext == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f"[Sheet: {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                vals = [str(v) for v in row if v is not None]
                if vals: out.append(" | ".join(vals))
        text = "\n".join(out)
        pages = len(wb.worksheets)
    elif ext == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            text = "\n".join(" | ".join(row) for row in csv.reader(f))
    elif ext in {".txt",".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        from PIL import Image
        import pytesseract
        text = pytesseract.image_to_string(Image.open(path))
    if not text.strip():
        raise ValueError("No readable text was found. For scanned files, install Tesseract OCR.")
    return {"text": text, "pages": pages, "file_type": ext.lstrip(".")}

def _ocr_pdf(path):
    import fitz
    import pytesseract
    from PIL import Image
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        pages.append(pytesseract.image_to_string(image))
    return "\n\n".join(pages)

def split_text(text, chunk_size=900, overlap=120):
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text: return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end), text.rfind(" ", start, end))
            if boundary > start + chunk_size * .55: end = boundary + 1
        chunk = text[start:end].strip()
        if chunk: chunks.append(chunk)
        if end >= len(text): break
        start = max(end - overlap, start + 1)
    return chunks
