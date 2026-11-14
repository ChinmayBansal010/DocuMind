# DocuMind

DocuMind is a self-hostable contract intelligence workspace built with FastAPI, React/Vite, Neon PostgreSQL, Neon Auth, Azure AI, and local Ollama. It manages contract versions, performs source-grounded review, supports project and contract Q&A, translates extracted text, compares versions, and exports reports.

Contract analysis is informational and is not legal advice. Always check output against the original agreement.

## What is implemented

- Neon Managed Auth email/password sign-up and sign-in, persistent browser sessions, session expiry handling, profile, and logout.
- JWT verification by FastAPI using the configured Neon JWKS URL, EdDSA signatures, and issuer, audience, and expiry checks.
- PostgreSQL persistence with SQLAlchemy 2.x and Alembic migrations; application traffic uses the pooled `DATABASE_URL`, migrations prefer `DATABASE_URL_UNPOOLED`.
- Owner-scoped project, contract, version, analysis, conversation, message, obligation, deadline, chunk, and audit records.
- PDF and DOCX extraction with Azure AI Document Intelligence, 2-page/4 MB PDF request splitting, layout/table retention, and original page numbering; UTF-8 TXT is decoded locally.
- Azure AI Language entity, key-phrase, and language detection; Azure AI Content Safety moderation and Prompt Shields on uploads and assistant interactions.
- Azure AI Search full-text plus vector hybrid retrieval with strict owner/project/latest-version filters. Ollama supplies local embeddings and optional local reasoning.
- Source-checked clause, risk, and obligation analysis, analysis history, page citations, F0 text translation, version comparison, and JSON, Markdown, and PDF reports.
- PDF, DOCX, and UTF-8 TXT upload with size/type validation, generated storage paths, SHA-256 duplicate detection, and optional AES-GCM encryption of source files.
- Contract version diffs and JSON, Markdown, and PDF exports.
- PostgreSQL-backed request limits, security headers, CORS allow-listing, and a database/migration health check.

All five Azure AI services are required and their endpoint/key configuration is validated before FastAPI starts. Provider, quota, and schema failures are reported explicitly; the application does not silently substitute local extraction or retrieval. Azure usage is restricted to the documented F0/Free capabilities: Translator uses its text API (not paid native document translation), Search Free has a 50 MB index limit and allows one Free service per subscription, and Language/Content Safety/Document Intelligence quotas are tracked and enforced per month by the application. Azure may impose additional subscription-wide limits.

DOCX files are converted to PDF locally with LibreOffice before being sent to Document Intelligence in F0-compliant page batches. TXT extraction is local because Document Intelligence does not accept plain text as a document input; Language, Content Safety, embeddings, and Search still run in the processing pipeline. All contract content sent to Azure is subject to the configured Azure resources' data processing terms. Ollama embeddings must be available locally; Ollama reasoning is optional.

## Existing Neon project setup

Keep the existing [`neon.ts`](./neon.ts) configuration (`auth: true`). Do not create another Neon project. Obtain the values for the same project branch from your existing Neon environment:

```dotenv
DATABASE_URL=                     # pooled app connection
DATABASE_URL_UNPOOLED=            # direct connection for migrations
NEON_AUTH_BASE_URL=               # Managed Auth URL
NEON_AUTH_JWKS_URL=               # Managed Auth JWKS endpoint
```

Copy `.env.example` to `.env` and add the Neon values and all five Azure service configurations. Use only Azure AI F0/Free resources, in regions that offer those tiers. Startup intentionally fails if required endpoints, keys, translator region, Search index name, or effective API settings are invalid. The application does not print or expose credentials. Neon Auth stores credentials and sessions; DocuMind synchronizes the verified token subject into its own `users` table. No local password hashes are stored.

Add the origin you will open in a browser to the Neon Auth trusted domains for that branch. For example:

- Vite development: `http://localhost:5173`
- Docker/FastAPI-served frontend: `http://localhost:8000`
- Production: your HTTPS application origin

`VITE_NEON_AUTH_URL` can be set to the same Auth URL for a Vite build. The Vite configuration otherwise exposes only `NEON_AUTH_BASE_URL` to the browser. Do not put database URLs or secret values in variables prefixed with `VITE_`.

When email verification by code is enabled for the Neon Auth branch, DocuMind prompts new users to enter the emailed code before signing them in. Users can request a replacement code from the verification screen.

Run the app's schema migrations after configuring the Neon URLs:

```bash
alembic upgrade head
```

The initial migration creates only DocuMind's application tables and leaves Neon's `neon_auth` schema untouched. Run migrations from a trusted environment. Do not point tests at a production database.

## Linux and macOS development

Requirements: Python 3.11+, Node.js 22+, npm, LibreOffice Writer, a configured Neon branch, five Azure AI F0/Free services, and Ollama with the configured embedding model.

```bash
cp .env.example .env
# Fill the Neon and Azure values in .env; configure Ollama for embeddings.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run dev
```

In another terminal:

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The Vite server proxies `/api` to FastAPI. Visit `http://localhost:5173`.

## Windows development and deployment

Use **Command Prompt (CMD)** for every command below. Install Python 3.11+, Node.js 22+, Docker Desktop with the WSL 2 backend, Ollama for Windows, and LibreOffice Writer using their official installers:

- [Python](https://www.python.org/downloads/windows/)
- [Node.js LTS](https://nodejs.org/en/download)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama for Windows](https://ollama.com/download/windows)
- [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)

After installation, start Docker Desktop and Ollama, open a new CMD window, and verify:

```cmd
py -3.11 --version
node --version
npm --version
docker --version
docker compose version
ollama --version
```

If you do not already have a working copy, clone it; otherwise skip the clone command. Change to the repository root:

```cmd
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd /d DocuMind
```

Download Ollama's required embedding model and the optional local reasoning model:

```cmd
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

Create `.env` only if it does not already exist, then edit it:

```cmd
if not exist .env copy .env.example .env
notepad .env
```

Set the existing Neon branch's database, Auth base/JWKS URLs, and all five required Azure AI F0/Free service settings. Keep `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`; set `OLLAMA_MODEL=llama3.1:8b` to enable local reasoning. Leave it blank to disable model-generated reasoning. For Docker with Ollama installed on Windows, set `OLLAMA_URL=http://host.docker.internal:11434`. Add `http://localhost:8000` to that Neon Auth branch's trusted domains for Docker, or `http://localhost:5173` for Vite development. Startup will fail if the required Azure configuration is missing.

For Vite development, open one CMD window at the repository root:

```cmd
py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run dev
```

Open a second CMD window at the repository root to run FastAPI:

```cmd
call .venv\Scripts\activate.bat
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://localhost:5173`. Alternatively, run `run.cmd` from CMD to install dependencies, build the frontend, apply migrations, and serve the app at `http://127.0.0.1:8000`.

### Run DocuMind in Docker on Windows

Ensure Docker Desktop is running, then run these commands from CMD in the repository root:

```cmd
if not exist .env copy .env.example .env
notepad .env
docker compose up --build -d
docker compose ps
docker compose logs -f documind
```

Open `http://localhost:8000`. The container validates Azure settings, applies Alembic migrations, and starts the app. To run Ollama inside Compose instead of on Windows, change `.env` to `OLLAMA_URL=http://ollama:11434` and start both services:

```cmd
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.1:8b
```

`docker compose logs -f documind` shows server logs; press Ctrl+C to stop following logs without stopping the app. Stop containers with `docker compose down`; this retains uploaded documents and model volumes. Do not run `run.cmd` at the same time as Docker because both use port 8000.

The `run.sh` helper is for Linux/macOS, and `run.cmd` is for Windows CMD. Review `.env` before running either helper; database migrations target the configured environment.

## Ollama

Set `OLLAMA_URL` and `OLLAMA_EMBEDDING_MODEL` in `.env`; `OLLAMA_MODEL` enables optional local reasoning:

```dotenv
OLLAMA_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_MODEL=llama3.1:8b
```

Pull the embedding model and, if desired, the reasoning model:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

For Docker Compose, use `OLLAMA_URL=http://host.docker.internal:11434` for a host-installed Ollama, or `OLLAMA_URL=http://ollama:11434` with the optional Ollama container:

```bash
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text
```

Embeddings are required for hybrid Azure AI Search indexing and retrieval; an unavailable model or dimension mismatch fails the operation clearly. Reasoning is optional: if `OLLAMA_MODEL` is unavailable or produces invalid output, analysis remains rule-based and assistant responses use only retrieved source passages. Model-generated clauses, risks, and obligations are retained only when supported by exact source excerpts.

## Azure AI F0 / Free setup

Provision the existing five Azure AI resources in supported regions and use their F0/Free SKUs only. Put their endpoints and keys in `.env`; never commit `.env` or `.env.local`.

- **Document Intelligence F0:** 500 pages/month, at most 2 pages and 4 MB per request. PDFs are split and page references are remapped; DOCX is locally rendered to PDF first.
- **Language F0:** 5,000 text records/month shared across features (1,000 characters per record); requests are kept within the synchronous text limit.
- **Translator F0:** text translation only, up to 2 million characters/month and 50,000 characters/request. Native document translation/layout preservation is S1 and is not called.
- **Content Safety F0:** 5,000 text records/month, 5 requests/second, 10,000 characters/request; Prompt Shields document batches are capped at 5 documents and 10,000 document characters.
- **Azure AI Search Free:** 50 MB storage and up to 3 indexes; vector and hybrid search use embeddings generated by Ollama. Use a server-side admin key because the application creates the configured index and writes/deletes documents; it refuses incompatible existing schemas without deleting them.

The application keeps per-month counters for Document Intelligence pages, Language and Content Safety 1,000-character records, and Translator characters. These counters prevent application traffic from exceeding the published F0 limits; other applications using the same Azure subscription may consume shared quotas independently. Azure service errors and exhausted quotas are never converted into local-success fallbacks.

## Docker deployment

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f documind
```

On Windows, use the [Windows Docker deployment](#run-documind-in-docker-on-windows) instructions above.

The image builds the SPA with the Auth URL, applies `alembic upgrade head`, then starts FastAPI. The host port binds to `127.0.0.1:8000` by default. Change the bind address only when deploying behind a TLS-terminating reverse proxy with an appropriate network policy. Persist `/app/data`; it contains uploaded source files. Configure a strong `DOCUMENT_ENCRYPTION_KEY` if file-level encryption is required.

Health endpoint:

```text
GET /api/health
```

The endpoint reports database readiness and whether all five Azure configurations are present. It does not claim that provider credentials or remote service availability have been verified with a live request.

## Configuration

See [`.env.example`](./.env.example). Important values:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Pooled PostgreSQL application connection |
| `DATABASE_URL_UNPOOLED` | Direct PostgreSQL connection for migrations |
| `NEON_AUTH_BASE_URL` | Existing branch's Managed Auth endpoint |
| `NEON_AUTH_JWKS_URL` | JWKS endpoint used for server token verification |
| `VITE_NEON_AUTH_URL` | Optional explicit browser Auth URL for builds |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins permitted by FastAPI |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Optional local inference and embeddings |
| `OLLAMA_EMBEDDING_MODEL` | Required local Ollama embedding model for hybrid Search |
| `DOCUMIND_DATA_DIR` | Local source-file storage directory |
| `MAX_UPLOAD_MB` | Maximum size of each uploaded file |
| `DOCUMENT_ENCRYPTION_KEY` | Optional URL-safe base64 32-byte AES-GCM key |
| `API_RATE_LIMIT` | PostgreSQL-backed per-client request limit, e.g. `120/minute` |
| `AZURE_DOCUMENT_INTELLIGENCE_*` | Required endpoint/key/model/API version for F0 extraction |
| `AZURE_LANGUAGE_*` | Required endpoint/key/API version for contract text analytics |
| `AZURE_TRANSLATOR_*` | Required endpoint/key/region/API version for F0 text translation |
| `AZURE_CONTENT_SAFETY_*` | Required endpoint/key/API version and severity threshold |
| `AZURE_SEARCH_*` | Required endpoint/key/index/API version/vector dimensions |

Generate a file encryption key with:

```bash
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Back up this key separately. Losing it makes encrypted source files unreadable. Encryption applies to files stored in the local storage directory only; extracted text, chunks, metadata, messages, and analysis are stored in PostgreSQL without application-level encryption. Do not claim that those records are application-encrypted.

## Project structure

```text
app/
  api/v1/       FastAPI endpoints
  core/         configuration and Neon JWT validation
  db/           SQLAlchemy models and PostgreSQL sessions
  engines/      extraction, contract analysis, retrieval, comparison
  repositories/ ownership-scoped data access
  services/    Azure AI REST clients, F0 quota accounting, and tenant-scoped Search
  schemas/      request and response validation
  storage/      scoped local storage and optional file encryption
  utils/        audit helpers
migrations/     Alembic schema history
frontend/src/
  app/          session-protected application shell
  features/     auth, dashboard, projects, contracts, settings
  services/     Neon Auth and authenticated API clients
  styles/       responsive UI styles
tests/          backend behavior and isolation tests
```

## Tests, lint, and builds

`tests/fixtures/contract-test-sample.pdf` is a one-page synthetic contract for manual upload and extraction checks. Its parties and terms are fictional.

```bash
pytest -q
python -m compileall app documind main.py
cd frontend
npm test
npm run lint
npm run build
```

Backend tests use a temporary SQLite database strictly as an isolated test fixture; the application rejects SQLite connection URLs and requires PostgreSQL at runtime. No tests or migrations should write to a production branch.

## Known boundaries

- Existing SQLite documents are not migrated automatically; export/import them through a deliberate, separately reviewed migration if needed.
- Neon schema changes are applied by Alembic at deployment; this repository cannot confirm a live deployment until an operator runs migrations against the intended branch.
- The application has not been through an external security or legal compliance audit. Configure production trusted domains, SMTP, TLS, backups, key management, and monitoring before public launch.
- Rate limiting uses PostgreSQL buckets keyed by client IP. When deployed behind a proxy, configure network access so `request.client.host` is the intended client address; forwarded headers are not trusted by default.
