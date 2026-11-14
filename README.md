# DocuMind

**Your documents, in focus.** A personal document companion for keeping files together, finding information and getting answers grounded in your documents.

## Use DocuMind
- Add PDF, Word, PowerPoint, Excel, CSV, text, Markdown and image files.
- Keep a searchable document library on your computer.
- Ask questions across your library or a selected document.
- Review the source passages used to form an answer.
- Delete documents from your local library.

## Run locally with Docker
Requirements: Docker Engine with Compose and Ollama installed on the host if you want local AI answers.

    git clone https://github.com/ChinmayBansal010/DocuMind.git
    cd DocuMind
    cp .env.example .env
    docker compose up --build -d

Open http://127.0.0.1:8000. Stop with 'docker compose down'. Your files and database remain in the named Docker volume.

## Connect Ollama (Llama 3.1 8B)

DocuMind calls Ollama's HTTP API from the Python backend. Running 'ollama run llama3.1:8b' downloads/runs the model in Ollama, but 'localhost:11434' inside a Docker container is the container itself, not the host computer. This is the reason the connection often fails in Docker.

On the host computer, confirm that the model is installed and Ollama responds:

    ollama pull llama3.1:8b
    ollama list
    curl http://127.0.0.1:11434/api/tags

For Docker on Linux (including Fedora), Ollama must listen on the host interface so the container can connect. If Ollama is managed by systemd, run:

    sudo systemctl edit ollama

Add this service override:

    [Service]
    Environment="OLLAMA_HOST=0.0.0.0:11434"

Then restart and verify the service:

    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    curl http://127.0.0.1:11434/api/tags

Rebuild/restart DocuMind:

    docker compose up --build -d

Verify connectivity from inside the container:

    docker compose exec documind python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"

The Compose configuration maps 'host.docker.internal' to the host gateway and points the backend to 'http://host.docker.internal:11434'. Keep the host firewall restrictive. Do not expose Ollama's port to the public internet or untrusted networks. If running DocuMind without Docker, keep 'OLLAMA_URL=http://localhost:11434' in .env.

The default model is 'llama3.1:8b'. Change OLLAMA_MODEL in .env if needed, then restart/rebuild the container. If Ollama is unavailable, DocuMind shows retrieved document passages as a fallback and includes the connection/model error.

## Native run (without Docker)
Requirements: Python 3.11+, Node.js 20+, npm and Tesseract OCR for scanned files.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    cd frontend && npm install && npm run build
    cd ..
    uvicorn main:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000. On Windows, activate with .venv\Scripts\Activate.ps1.

## Privacy and optional cloud processing
The local-first configuration stores uploaded files and extracted text on the machine running DocuMind. If configured, Azure AI Search receives extracted text chunks for indexing; Azure Document Intelligence receives a selected original file when cloud extraction is requested; Azure AI Content Safety may receive submitted text for moderation. Azure credentials are read by the backend and are never sent to the browser. Review PRIVACY.md, TERMS.md and SECURITY.md.

Local files and SQLite data are not encrypted by DocuMind. Deleting a local file does not delete copies already sent to third-party services. This release is a local, single-user application. It has no login, authentication or multi-user isolation and must not be exposed as a public hosted service. A commercial hosted launch needs identity, tenant isolation, encrypted storage, secure deletion workflows, monitoring, incident response and legal review.

## Legal information
The included Privacy Policy, Terms of Use and Security page are starter templates, not legal advice or a compliance certification. The publisher's legal identity, contact details, jurisdiction, retention periods, processor/subprocessor list and user-rights process still need to be confirmed before commercial distribution.

## Tests

    python -m compileall main.py documind tests
    pytest -q
