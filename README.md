# DocuMind AI

**Intelligent Document Processing & Knowledge Assistant**

A cross-platform, local-first document intelligence workspace. It supports document ingestion, OCR, structured field extraction, document-grounded question answering, optional content moderation and activity history.

## Features

- Upload PDF, DOCX, TXT, Markdown, PPTX, XLSX, CSV and image files.
- Extract digital text and run local Tesseract OCR on scanned PDFs and images.
- Store documents and indexed chunks in SQLite.
- Search with TF-IDF cosine similarity.
- Ask questions and inspect retrieved source passages.
- Optionally use a local Ollama model for generated answers.
- Extract common invoice fields locally or call Azure AI Document Intelligence.
- Use Azure AI Content Safety when configured.
- Export extraction results as JSON and activity as CSV.
- Docker deployment for Windows, Fedora and other Docker-supported platforms.

## Architecture

```text
Browser -> Streamlit UI -> Python application services
                              |-- SQLite + local files
                              |-- TF-IDF retrieval
                              |-- Tesseract OCR
                              |-- Optional Ollama
                              |-- Optional Azure Document Intelligence
                              |-- Optional Azure Content Safety
                              |-- Optional Azure AI Search helper
```

## Run with Docker (recommended)

Install Docker Desktop on Windows or Docker Engine and the Compose plugin on Fedora.

```bash
docker compose up --build -d
```

Open http://localhost:8501. Stop with `docker compose down`. Uploaded documents and SQLite data persist in the Docker named volume `documind_data`.

## Run natively on Fedora

```bash
sudo dnf install -y python3 python3-pip tesseract
cp .env.example .env
chmod +x run.sh
./run.sh
```

## Run natively on Windows

Install Python 3.11+ and Tesseract OCR. In PowerShell, from the repository directory:

```powershell
Copy-Item .env.example .env
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run.ps1
```

Open http://localhost:8501.

## Optional local LLM

Install Ollama separately, download a model compatible with your machine, and set `OLLAMA_MODEL` in `.env`. If unset, DocuMind returns retrieved passages rather than pretending to generate an LLM answer.

## Optional Azure integrations — strict cost strategy

The application never creates Azure resources. Azure connections are disabled unless their endpoint and key are configured.

- **Document Intelligence:** set `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY` and optionally `AZURE_DOCUMENT_INTELLIGENCE_MODEL`. Select F0/free only if available for your region and subscription. Check current page/request limits before use.
- **Content Safety:** set `AZURE_CONTENT_SAFETY_ENDPOINT` and `AZURE_CONTENT_SAFETY_KEY`. Check free quota availability. Local keyword screening is not equivalent.
- **AI Search:** `documind/azure_search.py` demonstrates index creation, vector upload and vector query APIs. The main application uses local TF-IDF by default. A compatible embedding generator and an F0 search service are required before cloud vector search can be used.
- **No Azure OpenAI, paid compute or always-on Azure host is required.**
- Local storage is the default; Blob Storage is intentionally not enabled.
- Free-tier availability varies by region, subscription and date. Budget alerts do not stop resources or guarantee a zero bill. Check the SKU before creating resources and monitor Cost Management.

## Project structure

```text
DocuMind/
├── app.py
├── documind/
├── tests/
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── .env.example
├── run.sh
└── run.ps1
```

## Tests

```bash
python -m compileall app.py documind tests
pip install pytest
pytest -q
```

## Limitations

- Local invoice patterns are illustrative, not a trained extraction model.
- Custom Document Intelligence model training must be performed separately in Document Intelligence Studio.
- Local moderation is a keyword-based fallback, not a safety classifier.
- Local retrieval is TF-IDF lexical retrieval, not semantic embeddings.
- Azure AI Search vector helpers require a compatible embedding generator and are not wired into the default UI.
- This is an educational prototype, not a production compliance or records-management system.
