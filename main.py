import hashlib
import json
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from documind.database import initialize_db, add_document, record_event, get_stats, get_events
from documind.documents import extract_document, split_text, SUPPORTED
from documind.storage import save_upload, list_documents, delete_document
from documind.search import search_chunks, answer_question
from documind.azure_services import analyze_with_document_intelligence, moderate_text
from documind.azure_search import is_configured as search_configured, upload_chunks, search_chunks as azure_search_chunks
from documind.config import settings
from documind.extraction import extract_fields_locally

app = FastAPI(title="DocuMind API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
initialize_db()

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    documents: list[str] = []
    top: int = Field(default=5, ge=1, le=10)

class ExtractionRequest(BaseModel):
    document_id: int
    fields: list[str] = ["InvoiceNumber", "InvoiceDate", "CustomerName", "TaxAmount", "TotalAmount"]

class ModerationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)

def public_document(doc):
    return {key: doc[key] for key in ("id", "name", "file_type", "pages", "sha256", "created_at", "chunk_count")}

def integrations():
    return {
        "azure_search": search_configured(),
        "document_intelligence": bool(settings.document_intelligence_endpoint and settings.document_intelligence_key),
        "content_safety": bool(settings.content_safety_endpoint and settings.content_safety_key),
        "ollama": bool(settings.ollama_model),
        "answer_model": settings.ollama_model or "Extractive answers"
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "integrations": integrations()}

@app.get("/api/overview")
def overview():
    docs = list_documents()
    return {"stats": get_stats(), "documents": [public_document(d) for d in docs[:8]], "integrations": integrations()}

@app.get("/api/documents")
def documents():
    return [public_document(d) for d in list_documents()]

@app.post("/api/documents")
async def upload_documents(files: list[UploadFile] = File(...)):
    results = []
    for file in files:
        name = Path(file.filename or "document").name
        raw = await file.read()
        digest = hashlib.sha256(raw).hexdigest()
        if any(d["sha256"] == digest for d in list_documents()):
            results.append({"name": name, "status": "skipped", "message": "This file is already in your library."})
            continue
        saved_path = None
        try:
            if Path(name).suffix.lower() not in SUPPORTED:
                raise ValueError("Unsupported file format.")
            saved_path = save_upload(name, raw)
            parsed = extract_document(saved_path)
            chunks = split_text(parsed["text"], settings.chunk_size, settings.chunk_overlap)
            doc_id = add_document(name, saved_path, parsed["file_type"], parsed["text"], parsed["pages"], digest, chunks)
            search_message = "Local index ready"
            if search_configured():
                try:
                    upload_chunks(name, digest, chunks)
                    search_message = "Indexed in Azure AI Search"
                except Exception as exc:
                    search_message = f"Local index ready; Azure indexing failed: {str(exc)[:240]}"
            record_event("upload", name, f"{len(chunks)} chunks processed")
            results.append({"id": doc_id, "name": name, "status": "processed", "chunks": len(chunks), "message": search_message})
        except Exception as exc:
            if saved_path and saved_path.exists():
                saved_path.unlink(missing_ok=True)
            results.append({"name": name, "status": "error", "message": str(exc)})
    return {"results": results, "documents": [public_document(d) for d in list_documents()]}

@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int):
    doc = next((d for d in list_documents() if d["id"] == document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_document(document_id)
    record_event("delete", doc["name"], "Document removed")
    return {"deleted": document_id}

@app.post("/api/ask")
def ask(payload: QuestionRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")
    safety = moderate_text(question)
    if safety.get("blocked"):
        raise HTTPException(status_code=400, detail="The content safety check flagged this query.")
    hits = []
    retrieval = "Local TF-IDF"
    if search_configured():
        try:
            hits = azure_search_chunks(question, payload.documents or None, payload.top)
            retrieval = "Azure AI Search"
        except Exception:
            hits = search_chunks(question, payload.documents or None, payload.top_k if hasattr(payload, "top_k") else payload.top)
    else:
        hits = search_chunks(question, payload.documents or None, payload.top)
    answer = answer_question(question, hits)
    record_event("query", "Knowledge Assistant", question[:240])
    return {"answer": answer, "sources": hits, "retrieval": retrieval, "answer_model": settings.ollama_model or "Extractive"}

@app.post("/api/extract")
def extract(payload: ExtractionRequest):
    doc = next((d for d in list_documents() if d["id"] == payload.document_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = analyze_with_document_intelligence(doc["path"])
    if result.get("fields"):
        fields, method = result["fields"], "Azure Document Intelligence"
    else:
        fields = extract_fields_locally(doc["text"], payload.fields)
        method = "Local pattern-based extraction"
    record_event("extraction", doc["name"], method)
    return {"fields": fields, "method": method, "warning": result.get("error")}

@app.post("/api/moderate")
def moderate(payload: ModerationRequest):
    result = moderate_text(payload.text)
    record_event("moderation", "Content Safety", f"{len(payload.text)} characters analyzed")
    return result

@app.get("/api/activity")
def activity():
    return get_events(250)

@app.get("/api/settings")
def get_settings():
    return {
        "integrations": integrations(),
        "limits": {"max_upload_mb": settings.max_upload_mb, "chunk_size": settings.chunk_size, "chunk_overlap": settings.chunk_overlap},
        "privacy": "Credentials are read by the backend from environment variables and are never returned by this API."
    }

frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
