# DocuMind

**Contract intelligence and document understanding, running locally with Azure AI integrations.**

DocuMind is a Dockerized document workspace. It combines local document storage and Ollama-based generation with optional Azure AI services for search, document layout extraction, content moderation, prompt-injection protection, language insights and translation.

## Product capabilities

### Contract intelligence
- Identify contract type, parties and key commercial terms.
- Classify termination, payment, confidentiality, indemnification, liability, intellectual property, data protection, renewal, dispute resolution and other clauses.
- Surface potential risk signals with evidence excerpts and page references.
- Extract obligations, responsible parties and deadlines.
- Flag provisions that may deserve review.
- Ask questions about one selected contract, with supporting passages restricted to that contract.
- Save and reopen analysis reports from SQLite.

### Document workspace
- Upload PDF, DOCX, PPTX, XLSX, CSV, TXT, Markdown and common image formats.
- Search across the library or a selected document.
- Ask natural-language questions and inspect source passages.
- Delete documents and remove their corresponding chunks from Azure AI Search when cloud indexing is enabled.
- Use Azure AI Language to detect language, extract key phrases and identify possible PII from the first 5,000 characters of a selected document.
- Use Azure AI Translator to translate selected clauses and passages.
- Use Azure Document Intelligence to extract layout text and tables from supported documents.

### Safety pipeline
- Azure AI Content Safety checks user questions and generated answers for harmful content.
- Azure AI Content Safety Prompt Shields checks user prompts and retrieved passages for prompt-injection attempts before they are sent to the model.
- When a configured Azure moderation or Prompt Shields request fails, the affected AI request is blocked rather than silently treated as safe.
- Contract text is treated as untrusted evidence, not as instructions to the model.
- Local keyword and prompt-pattern checks are used only when the corresponding Azure integration is not configured. The UI/API should identify the fallback provider.

Content Safety is a safety signal, not a legal-compliance certification. Review flagged content and tune severity thresholds for your use case.

## Azure services: what the project actually uses

All Azure keys are read by FastAPI from the server-side `.env` file. They are not sent to React or returned by the settings endpoint.

| Azure service | Where it is used in DocuMind | What to demonstrate |
|---|---|---|
| Azure AI Search (Free) | Upload indexes document chunks; general Q&A and contract Q&A retrieve relevant chunks; delete removes the document's cloud chunks | Upload a file, ask a question, check that retrieval reports Azure AI Search |
| Azure AI Document Intelligence (F0) | On-demand layout analysis extracts document text, pages and tables; selected extraction endpoint can return detected fields | AI tools → choose a file → Run layout extraction |
| Azure AI Content Safety (F0) | Moderates user questions and generated answers | Ask a question and inspect the returned safety metadata/activity |
| Azure AI Content Safety Prompt Shields (F0) | Checks user prompts and retrieved document passages for prompt injection before LLM generation | Ask a normal question; the API reports the Prompt Shields provider |
| Azure AI Language (F0) | Detects language, extracts key phrases and identifies possible PII entities | AI tools → choose a file → Analyse with Azure Language |
| Azure AI Translator (F0) | Translates selected text into a chosen language | AI tools → paste text → Translate with Azure |

### F0 allowances and practical limits

Free tiers are limited; they are not unlimited production capacity. Published allowances can vary by resource type, region, subscription and product version. Check your Azure portal Cost Management and each resource's pricing page before demonstrations.

| Service | Published free-tier limit / constraint |
|---|---|
| Azure AI Search Free | One free search service per subscription; 50 MB storage. The shared free service can be removed after extended inactivity. |
| Document Intelligence F0 | Maximum 4 MB per document and first 2 pages per analysis request. The app reports the limitation rather than treating a partial analysis as a full-document review. |
| Content Safety Free/F0 | Free web pricing lists 5,000 text records per month; F0 API rate is 5 requests/second. A text record is measured in 1,000-character units for the listed web pricing. |
| Azure AI Language F0 | 5,000 free text records per month shared by supported features such as language detection, key phrase extraction, PII detection and other Language features. |
| Azure AI Translator F0 | 2 million characters per month for standard translation features; the F0 service limit is also documented as 2 million characters per hour. |

References:
- [Azure AI Search service limits](https://learn.microsoft.com/azure/search/search-limits-quotas-capacity)
- [Document Intelligence service limits](https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits)
- [Content Safety pricing](https://azure.microsoft.com/en-us/pricing/details/content-safety/)
- [Content Safety overview and rate limits](https://learn.microsoft.com/azure/ai-services/content-safety/overview)
- [Azure Language pricing](https://azure.microsoft.com/en-us/pricing/details/language/)
- [Translator F0 pricing](https://azure.microsoft.com/en-us/pricing/details/translator/)
- [Translator service limits](https://learn.microsoft.com/azure/ai-services/translator/service-limits)

### Azure resource setup

Create the following resources in the Azure portal. Select the **Free F0** tier wherever it is offered and available in your region.

1. **Azure AI Search**: create a Free service. Copy the service endpoint and an admin key. DocuMind creates the configured index automatically on first upload.
2. **Azure AI Document Intelligence**: create a Document Intelligence resource with F0 pricing. Copy the endpoint and key. The default model is `prebuilt-layout`.
3. **Azure AI Content Safety**: create a supported Content Safety resource with F0 pricing. Copy the endpoint and key. Text moderation and Prompt Shields use the same resource.
4. **Azure AI Language**: create a Language resource with F0 pricing. Copy the endpoint and key.
5. **Azure AI Translator**: create a Translator resource with F0 pricing. Copy the key and resource region.

Add the values to `.env`:

```dotenv
AZURE_SEARCH_ENDPOINT=https://YOUR-SEARCH.search.windows.net
AZURE_SEARCH_KEY=YOUR_SEARCH_ADMIN_KEY
AZURE_SEARCH_INDEX=documind-index
AZURE_SEARCH_API_VERSION=2024-07-01

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://YOUR-DOCUMENT-INTELLIGENCE.cognitiveservices.azure.com
AZURE_DOCUMENT_INTELLIGENCE_KEY=YOUR_DOCUMENT_INTELLIGENCE_KEY
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-layout

AZURE_CONTENT_SAFETY_ENDPOINT=https://YOUR-CONTENT-SAFETY.cognitiveservices.azure.com
AZURE_CONTENT_SAFETY_KEY=YOUR_CONTENT_SAFETY_KEY

AZURE_LANGUAGE_ENDPOINT=https://YOUR-LANGUAGE.cognitiveservices.azure.com
AZURE_LANGUAGE_KEY=YOUR_LANGUAGE_KEY

AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
AZURE_TRANSLATOR_KEY=YOUR_TRANSLATOR_KEY
AZURE_TRANSLATOR_REGION=YOUR_RESOURCE_REGION

OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
```

Do not commit `.env`. Keep the Azure keys server-side. Use the same resource region value shown in the Azure portal for Translator. Never paste keys into screenshots, frontend code or public issue reports.

## Run DocuMind with Docker

Requirements: Docker Engine/Desktop and the Docker Compose v2 plugin.

```bash
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd DocuMind
cp .env.example .env
```

Edit `.env` and add the Azure resource values you have created. Then:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f documind
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The web service binds to localhost by default. Persistent documents, SQLite data and model data use Docker volumes. Stop the app with:

```bash
docker compose down
```

The named volumes are retained. To delete all local application data and model data as well, use `docker compose down -v` only when you intentionally want to erase them.

## Ollama setup on Fedora Linux

### Option A: Ollama installed on the Fedora host

Install Ollama on Fedora using the official installer, then download the model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```

Then download the model:

```bash
ollama pull llama3.1:8b
ollama list
curl http://127.0.0.1:11434/api/tags
```

When Ollama runs as a systemd service, configure it to listen on the host interface so the Docker container can reach it through Docker's host gateway:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\\nEnvironment="OLLAMA_HOST=0.0.0.0:11434"\\n' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl status ollama
sudo ss -lntp | grep 11434
```

Keep the port restricted to the local Docker/host environment. Do not open port 11434 to the public internet or an untrusted LAN. Keep this in `.env`:

```dotenv
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
```

Rebuild/restart DocuMind and test the connection:

```bash
docker compose up --build -d
docker compose exec documind python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"
```

### Option B: Ollama in Docker (CPU)

Use the optional Ollama service already defined in `compose.yaml`. Set this in `.env`:

```dotenv
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
```

Start both containers and pull the model:

```bash
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama list
```

The model is stored in the persistent `ollama_models` Docker volume.

### Option C: Ollama in Docker with an NVIDIA GPU

This requires a working NVIDIA driver and NVIDIA Container Toolkit on the Linux host. Verify Docker GPU access before using the override:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Then run:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml --profile ollama up --build -d
docker compose exec ollama ollama pull llama3.1:8b
```

If the NVIDIA test fails, use host-installed Ollama or the CPU container option. Do not add GPU reservations on a machine without NVIDIA Container Toolkit.

## Ollama setup on Windows

### Option A: Ollama installed on Windows host

1. Install Ollama for Windows from [ollama.com/download/windows](https://ollama.com/download/windows).
2. Open PowerShell and run:

```powershell
ollama pull llama3.1:8b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

3. Docker Desktop must use the WSL 2 backend. Set the Ollama host variable for the Windows user:

```powershell
setx OLLAMA_HOST "0.0.0.0:11434"
```

4. Quit Ollama completely from the system tray and start it again so it reads the new environment variable.
5. In the project `.env`, use:

```dotenv
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
```

6. Start DocuMind:

```powershell
docker compose up --build -d
docker compose exec documind python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5).read().decode())"
```

Do not create a public inbound firewall rule for Ollama. Docker Desktop's host gateway is the intended path from the application container.

### Option B: Ollama in Docker on Windows

Docker Desktop with WSL 2 can run the optional CPU-based Ollama service:

```powershell
Copy-Item .env.example .env
```

Set in `.env`:

```dotenv
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
```

Then run:

```powershell
docker compose --profile ollama up --build -d
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama list
```

For NVIDIA GPU acceleration inside Docker Desktop, enable GPU support in the WSL 2 environment and verify that the Docker engine exposes the GPU before using `compose.gpu.yaml`. If it is unavailable, use Ollama installed on Windows or the CPU container.

## Verify the integrations

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/settings
docker compose logs --tail=100 documind
```

The health response shows which integrations have credentials configured. It does not claim that a configured service is reachable; run the corresponding workflow in the AI tools or Contracts workspace to verify a real request.

## Data flow and privacy

- Uploaded files, extracted text, metadata and contract reports are stored in the local Docker volume.
- Azure AI Search receives extracted chunks when indexing is enabled.
- Azure Document Intelligence receives the original selected file only when layout extraction is explicitly run.
- Azure AI Content Safety receives user questions, generated answers and generated contract reports for moderation; Prompt Shields receives user prompts, retrieved passages and the first 10,000 characters of a contract during contract analysis.
- Azure AI Language receives document text when the user explicitly runs document insights.
- Azure AI Translator receives only the text submitted for translation.
- Ollama receives the full extracted contract text (up to 40,000 characters) during contract analysis, and questions plus retrieved passages during Q&A. If Ollama runs on the host, inference remains on that host; if Ollama runs in Docker, it runs in the Ollama container.

Review [PRIVACY.md](PRIVACY.md), [TERMS.md](TERMS.md) and [SECURITY.md](SECURITY.md). This release is single-user and has no login or multi-user isolation. Do not expose it as a public hosted service. Local files and SQLite data are not encrypted by DocuMind.

## Contract analysis disclaimer

Contract findings are AI-assisted review signals, not legal advice. Missing-clause flags are prompts for human review, not proof of invalidity. Verify every finding against the complete original agreement and consult a qualified professional before making legal or commercial decisions.

## Development checks

```bash
python -m compileall main.py documind
pytest -q
cd frontend && npm ci && npm run build
```
