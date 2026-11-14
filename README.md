# DocuMind

**Your documents, in focus.** A personal document companion for keeping files together, finding information and getting answers grounded in your documents.

## What you can do
- Add PDF, Word, PowerPoint, Excel, CSV, text, Markdown and image files.
- Keep a searchable document library on your computer.
- Ask questions across your library or a selected document.
- Review the source passages used to form an answer.
- Delete documents from your local library.

## Run with Docker
Requirements: Docker Engine with Compose and Ollama installed on the host if you want local AI answers.

    git clone https://github.com/ChinmayBansal010/DocuMind.git
    cd DocuMind
    cp .env.example .env
    docker compose up --build -d

Open http://127.0.0.1:8000. Stop with 'docker compose down'. Your files and database remain in the named Docker volume.

## Connect Ollama (Llama 3.1 8B)

DocuMind calls Ollama's HTTP API from the Python backend. Running 'ollama run llama3.1:8b' starts the local model, but 'localhost:11434' inside a Docker container refers to the container itself, not your host computer.

On the host, check the model and Ollama API:

    ollama pull llama3.1:8b
    ollama list
    curl http://127.0.0.1:11434/api/tags

On Linux/Fedora, the host Ollama service must listen on the host interface for Docker to reach it. If Ollama is managed by systemd:

    sudo systemctl edit ollama

Add:

    [Service]
    Environment="OLLAMA_HOST=0.0.0.0:11434"

Then run:

    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    curl http://127.0.0.1:11434/api/tags
    docker compose up --build -d

Test connectivity from the DocuMind container:

    docker compose exec documind python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"

Docker Compose explicitly configures the backend to use 'http://host.docker.internal:11434', regardless of an old OLLAMA_URL value in your .env file. For a native (non-Docker) run, set OLLAMA_URL=http://localhost:11434 in .env instead. Keep your firewall restrictive. Do not expose Ollama's port to the public internet or untrusted networks. Without Docker, use 'OLLAMA_URL=http://localhost:11434' in .env. The default model is 'llama3.1:8b'; change OLLAMA_MODEL in .env if required. If Ollama is unavailable, DocuMind falls back to retrieved passages and includes the connection/model error.

## Native run
Requires Python 3.11+, Node.js 20+, npm and Tesseract OCR for scanned documents.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    cd frontend && npm install && npm run build
    cd ..
    uvicorn main:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000. On Windows, activate with .venv\Scripts\Activate.ps1.

## Privacy and cloud processing
Local parsing, search and storage run on your device. If configured, Azure AI Search receives extracted text chunks; Azure Document Intelligence receives selected original files during extraction; Azure AI Content Safety may receive submitted text for moderation. Ollama receives the question and retrieved passages for local generation. Azure credentials stay on the backend. Read PRIVACY.md, TERMS.md and SECURITY.md.

Local files and SQLite data are not encrypted by DocuMind. Deleting local copies does not delete data already sent to third-party providers. This release is single-user and local-only; it has no login or multi-user isolation and must not be exposed as a public hosted service.

## Legal documents
PRIVACY.md, TERMS.md and SECURITY.md are initial templates, not legal advice or compliance certification. Publisher legal identity, privacy contact, jurisdiction, retention periods, processor list and user-rights procedures must be completed before commercial distribution.

## Tests

    python -m compileall main.py documind tests
    pytest -q
