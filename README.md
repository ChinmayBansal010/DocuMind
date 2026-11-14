# DocuMind

**A document intelligence workspace built with React, FastAPI and Azure AI services.**

DocuMind brings document ingestion, searchable knowledge, grounded Q&A, structured extraction and content safety into a clean React workspace. The browser contains no Azure credentials: every integration is called by the Python backend, which reads secrets from the server-side `.env` file.

## Stack

- **Frontend:** React, Vite, Lucide icons, responsive light UI.
- **Backend:** FastAPI, Python 3.11, Uvicorn.
- **Local data:** SQLite catalogue, local document storage, format parsers, Tesseract OCR and TF-IDF retrieval.
- **Azure integrations:** Azure AI Search for lexical chunk indexing/retrieval; Document Intelligence for structured extraction; Content Safety for moderation.
- **Optional generation:** Ollama running locally. Without it, the app returns an extractive answer from retrieved passages.

## Features

- Upload PDF, DOCX, TXT, Markdown, PPTX, XLSX, CSV and image files.
- Extract digital text with local parsers and scanned text with Tesseract OCR.
- Browse and delete stored documents.
- Ask questions against all documents or selected files; inspect retrieved source passages.
- Use Azure AI Search when configured, with local TF-IDF fallback.
- Extract invoice/document fields through Azure Document Intelligence or local pattern matching.
- Run content moderation through Azure AI Content Safety or the explicitly labelled local keyword fallback.
- Review activity and export CSV/JSON results.
- Configure Azure and Ollama integrations entirely through backend environment variables.

## Architecture

```text
React + Vite browser
       | same-origin /api requests
FastAPI backend
       |-- local parsers + Tesseract OCR
       |-- SQLite + local uploads
       |-- Azure AI Search (optional cloud index and retrieval)
       |-- Azure Document Intelligence (optional extraction)
       |-- Azure AI Content Safety (optional moderation)
       |-- local TF-IDF fallback + optional Ollama
```

The React application never receives service keys. Do not add secrets to `frontend/`, Vite environment variables, source maps or browser storage. All Azure requests originate from FastAPI.

## Run with Docker (recommended)

Requirements: Docker Engine with Compose, or Docker Desktop.

```bash
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd DocuMind
cp .env.example .env
```

Edit `.env` with the integrations you want to enable, then:

```bash
docker compose up --build -d
```

Open **http://localhost:8000**. Logs: `docker compose logs -f`. Stop: `docker compose down`. The named volume preserves SQLite and uploaded documents.

## Native development

Requirements: Python 3.11+, Node.js 20+, npm and (for OCR) Tesseract.

### Fedora

```bash
sudo dnf install -y python3 python3-pip tesseract nodejs npm
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd DocuMind
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd frontend
npm install
npm run build
cd ..
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**.

For frontend hot reload, use two terminals: run `uvicorn main:app --reload` from the project root and `npm run dev` from `frontend/`. Open **http://localhost:5173**; Vite proxies `/api` to FastAPI.

### Windows PowerShell

```powershell
git clone https://github.com/ChinmayBansal010/DocuMind.git
Set-Location DocuMind
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
Set-Location frontend
npm install
npm run build
Set-Location ..
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**. Install Node.js 20+ and Tesseract separately. If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that session.

## Environment configuration

Start from `.env.example`. Leave an integration blank to disable it. Azure services are optional and are not provisioned by the app.

```env
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_KEY=
AZURE_SEARCH_INDEX=documind-index
AZURE_SEARCH_API_VERSION=2024-07-01

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_KEY=
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-invoice

AZURE_CONTENT_SAFETY_ENDPOINT=
AZURE_CONTENT_SAFETY_KEY=

OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=

DOCUMIND_DATA_DIR=data
MAX_UPLOAD_MB=20
CHUNK_SIZE=900
CHUNK_OVERLAP=120
```

Never commit `.env`. Keep keys in the backend environment only. When using Docker, `localhost` inside the container is not the host; configure the Ollama host address or put Ollama on the same Compose network.

## Azure usage and cost

- Azure AI Search is used for lexical search only; no vector embeddings, semantic ranker or Azure OpenAI deployment is required.
- Document Intelligence is called only when extraction is requested and credentials are configured.
- Content Safety is called for question prompts and text submitted on the Responsible AI page when configured.
- Local processing and local TF-IDF retrieval remain available without Azure.
- Select only free SKUs where available, confirm region/subscription eligibility and check current pricing/quota in the Azure portal. Free offers can change. The application never upgrades or provisions resources.

Document text chunks are sent to Azure AI Search when cloud indexing is configured. The selected original file is sent to Document Intelligence during extraction. Text submitted for moderation is sent to Content Safety. Review data-handling requirements before processing sensitive files. Local SQLite and uploads are not encrypted by this prototype.

## API

- `GET /api/health` — service health and non-secret integration status.
- `GET /api/overview` — counts, recent documents and integration status.
- `GET /api/documents` — document metadata (never local file paths or extracted full text).
- `POST /api/documents` — multipart upload; repeat the `files` field for multiple files.
- `DELETE /api/documents/{id}` — delete a document from local storage.
- `POST /api/ask` — grounded question answering.
- `POST /api/extract` — structured field extraction by document ID.
- `POST /api/moderate` — text moderation.
- `GET /api/activity` — recent activity.
- `GET /api/settings` — non-secret runtime configuration.

Interactive API documentation is available at **/docs**.

## Tests

```bash
python -m compileall main.py documind tests
pytest -q
```

Tests cover local chunking and invoice field extraction. They do not validate Azure credentials or live cloud quotas.

## Project structure

```text
DocuMind/
├── main.py
├── frontend/
│   ├── src/App.jsx
│   ├── src/main.jsx
│   ├── src/styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── documind/
├── tests/
├── data/
├── .env.example
├── Dockerfile
├── compose.yaml
└── requirements.txt
```
