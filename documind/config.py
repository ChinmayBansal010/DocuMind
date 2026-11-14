import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.data_dir = Path(os.getenv("DOCUMIND_DATA_DIR", "data")).resolve()
        self.upload_dir = self.data_dir / "uploads"
        self.database_path = self.data_dir / "documind.sqlite3"
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "900"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
        self.document_intelligence_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").rstrip("/")
        self.document_intelligence_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
        self.document_intelligence_model = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout")
        self.content_safety_endpoint = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT", "").rstrip("/")
        self.content_safety_key = os.getenv("AZURE_CONTENT_SAFETY_KEY", "")
        self.language_endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT", "").rstrip("/")
        self.language_key = os.getenv("AZURE_LANGUAGE_KEY", "")
        self.translator_endpoint = os.getenv("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com").rstrip("/")
        self.translator_key = os.getenv("AZURE_TRANSLATOR_KEY", "")
        self.translator_region = os.getenv("AZURE_TRANSLATOR_REGION", "")
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
        self.search_key = os.getenv("AZURE_SEARCH_KEY", "")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX", "documind-index")
        self.search_api_version = os.getenv("AZURE_SEARCH_API_VERSION", "2024-07-01")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.azure_configured = bool((self.document_intelligence_endpoint and self.document_intelligence_key) or (self.content_safety_endpoint and self.content_safety_key) or (self.language_endpoint and self.language_key) or (self.translator_key and self.translator_region) or (self.search_endpoint and self.search_key))

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
