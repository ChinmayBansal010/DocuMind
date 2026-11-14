# DocuMind

**Azure-powered document intelligence and knowledge workspace**

DocuMind combines Azure AI services with local Python processing. Azure AI Search provides cloud indexing and retrieval, Azure AI Document Intelligence provides structured document analysis, and Azure AI Content Safety provides text moderation. SQLite, format-specific parsers, TF-IDF retrieval and optional Ollama keep the application usable when a cloud service is unavailable or its free allowance is exhausted.

The application does not provision Azure resources. You create the resources yourself and provide credentials through `.env`. No Azure OpenAI deployment, paid model endpoint, always-on VM, Blob Storage account or paid hosting is required.

## Features

- Upload PDF, DOCX, TXT, Markdown, PPTX, XLSX, CSV and image documents.
- Extract digital text using local parsers; use Tesseract for scanned PDFs and images.
- Store originals, document metadata, chunks and activity history locally in SQLite.
- Upload extracted chunks to Azure AI Search and retrieve matching passages from the cloud index.
- Fall back to local TF-IDF retrieval if Search is not configured or a cloud request fails.
- Ask questions against retrieved passages and inspect source chunks. Optional Ollama generates answers locally; otherwise DocuMind returns an extractive answer.
- Submit a selected document to Azure AI Document Intelligence for structured extraction. Local pattern extraction is the fallback.
- Analyze text with Azure AI Content Safety. A local keyword check is the fallback.
- Export extraction results as JSON and activity history as CSV.

## Architecture

```text
Browser -> Streamlit application
             |-- Local parsers + Tesseract OCR
             |-- SQLite catalogue, local uploads and activity history
             |-- Azure AI Search: cloud chunk index and lexical retrieval
             |-- Azure AI Document Intelligence: structured analysis
             |-- Azure AI Content Safety: text moderation
             |-- Local TF-IDF fallback and optional Ollama generation
```

Azure AI Search uses the standard lexical search API. This avoids requiring vectorization, Azure OpenAI embeddings, semantic-ranker billing or a paid Search tier. The app creates its index automatically on the first successful document indexing operation. Use one Search service and one index for this project.

## Azure services and free-tier planning

| Azure service | DocuMind usage | Free-tier planning |
|---|---|---|
| Azure AI Search | Cloud chunk indexing and keyword retrieval | Free tier: 50 MB storage, up to 10,000 hosted documents and 3 indexes per service. Microsoft currently limits Free to one Search service per subscription. |
| Azure AI Document Intelligence | Invoice/document field analysis | Create **F0 (Free)**. F0 analysis is limited to the first 2 pages per request and a 4 MB input file. Microsoft's pricing page separately lists a 500-page S0 allowance; do not mistake that S0 allowance for permission to create a paid S0 resource. |
| Azure AI Content Safety | Text moderation in Responsible AI and before question answering | Microsoft currently lists 5,000 text records or 5,000 images in its free allowance. Confirm the current quota and region in the portal. |

Free offers, eligible regions, subscription limits and allowances can change. Verify current pricing and quotas before creating resources. Temporary Azure account credits are not the same as a permanently free SKU. Never select a paid tier just because the portal recommends it.

Official references:
- [Azure free account and free services](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account)
- [Azure AI Search free tier quickstart](https://learn.microsoft.com/en-us/azure/search/search-try-for-free)
- [Azure AI Search service limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity)
- [Document Intelligence service limits](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits)
- [Document Intelligence layout model](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout)

## 1. Create and configure Azure resources

Create these resources in your Azure subscription. Resource names and portal labels can change; the configuration values required by DocuMind remain the same.

### 1.1 Azure AI Search (Free)

1. Sign in to the [Azure portal](https://portal.azure.com/).
2. Select **Create a resource**, search **Azure AI Search**, and select **Create**.
3. Choose your subscription and resource group (for example, `rg-documind-free`).
4. Enter a globally unique service name and select an available region.
5. Under Pricing tier, explicitly select **Free (F)**. Do not select Basic, Standard or another paid tier.
6. Review and create the service.
7. Open the deployed service. From **Overview**, copy the URL/endpoint, in the form `https://<service-name>.search.windows.net`.
8. Open **Settings → Keys** and copy the **Primary admin key**. Treat it as a password.
9. Do not manually create an index. DocuMind creates `documind-index` on the first upload.

Add these values to `.env`:

```env
AZURE_SEARCH_ENDPOINT=https://<service-name>.search.windows.net
AZURE_SEARCH_KEY=<primary-admin-key>
AZURE_SEARCH_INDEX=documind-index
AZURE_SEARCH_API_VERSION=2024-07-01
```

The free service has only 50 MB storage. Keep documents/chunks concise, avoid duplicate uploads and remove unused test documents. Original files remain local; extracted text chunks are sent to Search.

### 1.2 Azure AI Document Intelligence (F0)

1. In the Azure portal, select **Create a resource** and search **Azure AI Document Intelligence** (it may appear under Azure AI services / Foundry Tools).
2. Create the resource in a supported region and resource group.
3. Select **Free F0**. If F0 is unavailable for your region or subscription, stop; do not substitute S0 if you want to avoid paid usage.
4. After deployment, open **Keys and Endpoint** and copy the endpoint and one key.
5. Add them to `.env`:

```env
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_DOCUMENT_INTELLIGENCE_KEY=<resource-key>
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-invoice
```

The Extraction page uses `prebuilt-invoice` by default. For general layout/text extraction, set the model to `prebuilt-layout`. The selected original file is sent to the configured model. F0 requests are constrained to 4 MB and the first 2 pages. The invoice model is intended for invoice fields; general layout output may not map to invoice-style fields.

### 1.3 Azure AI Content Safety (Free)

1. In the Azure portal, search for **Azure AI Content Safety**.
2. Create a resource in a supported region. Verify that the selected offer is free before deployment; do not choose a paid tier.
3. Open **Keys and Endpoint** and copy the endpoint and one key.
4. Add them to `.env`:

```env
AZURE_CONTENT_SAFETY_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_CONTENT_SAFETY_KEY=<content-safety-key>
```

DocuMind sends text from the Responsible AI page and question prompts to this service. If it is not configured or the request fails, the app indicates that it is using a local keyword demonstration; that fallback is not equivalent to an AI safety classifier.

### 1.4 Complete environment file

Your `.env` should contain all three integrations. Start from `.env.example`, then replace the values:

```env
AZURE_SEARCH_ENDPOINT=https://<service-name>.search.windows.net
AZURE_SEARCH_KEY=<search-admin-key>
AZURE_SEARCH_INDEX=documind-index
AZURE_SEARCH_API_VERSION=2024-07-01

AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_DOCUMENT_INTELLIGENCE_KEY=<document-intelligence-key>
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-invoice

AZURE_CONTENT_SAFETY_ENDPOINT=https://<resource-name>.cognitiveservices.azure.com
AZURE_CONTENT_SAFETY_KEY=<content-safety-key>
```

Do not add quotation marks unless they are part of the value. Never commit `.env` or paste keys into source files. Restart DocuMind after editing. The Settings page reports whether values are present; a configured status does not prove that a key is valid or a service is reachable. The first upload/search and analysis calls validate connectivity.

## 2. Run DocuMind

### Requirements

- Python 3.11 or newer.
- Windows 10/11, Fedora Linux or another supported Python platform.
- Tesseract OCR for scanned PDFs and images.
- Azure resources and `.env` for cloud indexing, Azure extraction and moderation.
- Optional Docker Engine with Compose, or Docker Desktop on Windows.
- Optional Ollama for locally generated answers.

### Option A: Docker (recommended)

Install Docker Desktop on Windows or Docker Engine plus the Compose plugin on Fedora.

**Fedora/Linux**
```bash
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd DocuMind
cp .env.example .env
$EDITOR .env
docker compose up --build -d
```

**Windows PowerShell**
```powershell
git clone https://github.com/ChinmayBansal010/DocuMind.git
Set-Location DocuMind
Copy-Item .env.example .env
notepad .env
docker compose up --build -d
```

Open [http://localhost:8501](http://localhost:8501). Follow logs with `docker compose logs -f`. Stop with `docker compose down`. The Compose volume preserves uploads and SQLite data. The supplied Docker image installs Tesseract; Azure calls require outbound internet access.

### Option B: Fedora native

```bash
sudo dnf install -y python3 python3-pip tesseract
git clone https://github.com/ChinmayBansal010/DocuMind.git
cd DocuMind
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
$EDITOR .env
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

### Option C: Windows native

1. Install Python 3.11+ and enable **Add Python to PATH**.
2. Install Tesseract OCR and ensure `tesseract.exe` is on PATH.
3. Run in PowerShell:

```powershell
git clone https://github.com/ChinmayBansal010/DocuMind.git
Set-Location DocuMind
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
streamlit run app.py
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window and activate again. Open [http://localhost:8501](http://localhost:8501).

### Launch scripts

- Fedora/Linux: `chmod +x run.sh && ./run.sh`
- Windows PowerShell: `Set-ExecutionPolicy -Scope Process Bypass` then `.\run.ps1`

## 3. First-run workflow

1. Start DocuMind and open **Settings**. Confirm Azure Search, Document Intelligence and Content Safety show as configured.
2. Open **Documents**, upload a small test PDF or DOCX and select **Process uploaded files**.
3. DocuMind extracts text locally, splits it into chunks, stores the document in SQLite, creates the Search index if needed and uploads chunks to Azure AI Search.
4. Open **Ask your documents** and ask a question answered by the test document. When Search is reachable, retrieved passages come from the cloud index. If the cloud request fails, DocuMind displays a warning and uses local TF-IDF retrieval.
5. Open **Extraction**, select a supported document and run extraction. The configured Document Intelligence model is called; local pattern extraction is used if Azure is unavailable or returns no fields.
6. Open **Responsible AI**, submit a short test sentence and inspect the Content Safety result.
7. Open **Activity** to review processing history.

## 4. Optional local answer generation with Ollama

Ollama is not an Azure dependency and does not require Azure OpenAI. Install Ollama, download a model suitable for your hardware and set:

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=<installed-model-name>
```

Inside Docker, `localhost` refers to the container. Use the appropriate host address for your Docker platform or run Ollama in the same Compose network. Without Ollama, DocuMind returns an extractive answer based on retrieved passages.

## 5. Cost and security controls

- Select **Free (F)** for Azure AI Search and **F0** for Document Intelligence. Verify Content Safety's free offer in your region. Never accept an automatic paid-tier upgrade.
- Azure resources are created manually; the application never provisions or scales resources.
- No Azure OpenAI, paid embeddings, vector search, semantic ranker, Blob Storage, virtual machines or always-on hosting are needed for this implementation.
- Monitor the Search free service's 50 MB storage and hosted-document limits.
- Document Intelligence F0 accepts at most 4 MB and analyzes only the first 2 pages per request.
- Free quotas and eligibility can change. A budget alert is a notification, not a hard spending cap and does not stop a resource.
- Keep `.env` private. Rotate any key that is exposed.
- Document text chunks are sent to Azure AI Search; the selected original file is sent to Document Intelligence during extraction; submitted text is sent to Content Safety. Check your organization's data-handling requirements before using real documents.
- Local SQLite and uploads are not encrypted by this application. Protect the host machine and Docker volume.
- To stop ongoing Azure charges, delete the relevant resources in the portal and verify deletion. Stopping DocuMind does not delete Azure resources.

## 6. Troubleshooting

**Azure integration shows not configured:** check variable names in `.env`, ensure endpoint and key are both present, then restart Streamlit/container.

**401/403 from Azure:** verify that the key belongs to that resource and that the endpoint matches it. Regenerate the key if needed.

**Search index request fails:** confirm the Search service is Free, the admin key is used, the endpoint ends in `.search.windows.net`, and the API version is supported. The index is created automatically on first upload.

**Search quota exceeded:** remove unused test documents/index data. Do not upgrade to a paid tier without checking cost implications.

**Document Intelligence rejects a file:** check file type, 4 MB F0 size limit, page count and model ID. F0 analyzes only the first two pages. Use `prebuilt-invoice` for invoices or `prebuilt-layout` for general layout/text.

**Tesseract not found:** install Tesseract and confirm `tesseract --version` works in the same environment/container as Streamlit.

**No relevant results:** confirm upload and Search indexing succeeded and that the question uses terms present in the document. Compare against the local fallback if necessary.

**Port 8501 is occupied:** run `streamlit run app.py --server.port 8502` and open port 8502.

## Project structure

```text
DocuMind/
├── app.py
├── documind/
│   ├── azure_search.py
│   ├── azure_services.py
│   ├── config.py
│   ├── database.py
│   ├── documents.py
│   ├── extraction.py
│   ├── search.py
│   └── storage.py
├── tests/
├── data/
├── .env.example
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── run.sh
└── run.ps1
```

## Tests and validation

```bash
python -m compileall app.py documind tests
pytest -q
```

The tests cover local chunking and invoice-field extraction. They do not contact Azure or verify live credentials, quotas or remote indexing. Perform the first-run workflow to validate your own resources.

## Current limitations

- Local invoice patterns are illustrative and are not a trained extraction model.
- Custom Document Intelligence model training is not included; train separately in Document Intelligence Studio.
- Azure AI Search currently uses lexical keyword retrieval, not semantic/vector search.
- Local retrieval fallback uses TF-IDF, not neural embeddings.
- Local keyword moderation is a demonstration fallback, not equivalent to Azure AI Content Safety.
- This is an educational prototype, not a production records-management, legal, medical or compliance system.
