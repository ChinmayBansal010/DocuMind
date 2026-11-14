import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.database_url_unpooled = os.getenv("DATABASE_URL_UNPOOLED", "").strip()
        self.auth_base_url = os.getenv("NEON_AUTH_BASE_URL", "").strip().rstrip("/")
        self.auth_jwks_url = os.getenv("NEON_AUTH_JWKS_URL", "").strip()
        self.allowed_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ]
        self.data_dir = Path(os.getenv("DOCUMIND_DATA_DIR", "data")).resolve()
        self.upload_dir = self.data_dir / "uploads"
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "900"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
        self.ollama_embedding_model = os.getenv(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
        ).strip()
        self.search_vector_dimensions = int(os.getenv("AZURE_SEARCH_VECTOR_DIMENSIONS", "768"))
        self.encryption_key = os.getenv("DOCUMENT_ENCRYPTION_KEY", "").strip()
        self.rate_limit = os.getenv("API_RATE_LIMIT", "120/minute")
        self.document_intelligence_endpoint = os.getenv(
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", ""
        ).strip().rstrip("/")
        self.document_intelligence_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip()
        self.document_intelligence_model = os.getenv(
            "AZURE_DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout"
        ).strip()
        self.document_intelligence_api_version = os.getenv(
            "AZURE_DOCUMENT_INTELLIGENCE_API_VERSION", "2024-11-30"
        ).strip()
        self.language_endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT", "").strip().rstrip("/")
        self.language_key = os.getenv("AZURE_LANGUAGE_KEY", "").strip()
        self.language_api_version = os.getenv(
            "AZURE_LANGUAGE_API_VERSION", "2023-04-01"
        ).strip()
        self.translator_endpoint = os.getenv("AZURE_TRANSLATOR_ENDPOINT", "").strip().rstrip("/")
        self.translator_key = os.getenv("AZURE_TRANSLATOR_KEY", "").strip()
        self.translator_region = os.getenv("AZURE_TRANSLATOR_REGION", "").strip()
        self.translator_api_version = os.getenv("AZURE_TRANSLATOR_API_VERSION", "3.0").strip()
        self.content_safety_endpoint = os.getenv(
            "AZURE_CONTENT_SAFETY_ENDPOINT", ""
        ).strip().rstrip("/")
        self.content_safety_key = os.getenv("AZURE_CONTENT_SAFETY_KEY", "").strip()
        self.content_safety_api_version = os.getenv(
            "AZURE_CONTENT_SAFETY_API_VERSION", "2024-09-01"
        ).strip()
        self.content_safety_block_severity = int(
            os.getenv("AZURE_CONTENT_SAFETY_BLOCK_SEVERITY", "4")
        )
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip().rstrip("/")
        self.search_key = os.getenv("AZURE_SEARCH_KEY", "").strip()
        self.search_index = os.getenv("AZURE_SEARCH_INDEX", "").strip()
        self.search_api_version = os.getenv("AZURE_SEARCH_API_VERSION", "2024-07-01").strip()

    def validate_azure_configuration(self) -> None:
        required = {
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": self.document_intelligence_endpoint,
            "AZURE_DOCUMENT_INTELLIGENCE_KEY": self.document_intelligence_key,
            "AZURE_DOCUMENT_INTELLIGENCE_MODEL": self.document_intelligence_model,
            "AZURE_DOCUMENT_INTELLIGENCE_API_VERSION": self.document_intelligence_api_version,
            "AZURE_LANGUAGE_ENDPOINT": self.language_endpoint,
            "AZURE_LANGUAGE_KEY": self.language_key,
            "AZURE_LANGUAGE_API_VERSION": self.language_api_version,
            "AZURE_TRANSLATOR_ENDPOINT": self.translator_endpoint,
            "AZURE_TRANSLATOR_KEY": self.translator_key,
            "AZURE_TRANSLATOR_REGION": self.translator_region,
            "AZURE_TRANSLATOR_API_VERSION": self.translator_api_version,
            "AZURE_CONTENT_SAFETY_ENDPOINT": self.content_safety_endpoint,
            "AZURE_CONTENT_SAFETY_KEY": self.content_safety_key,
            "AZURE_CONTENT_SAFETY_API_VERSION": self.content_safety_api_version,
            "AZURE_SEARCH_ENDPOINT": self.search_endpoint,
            "AZURE_SEARCH_KEY": self.search_key,
            "AZURE_SEARCH_INDEX": self.search_index,
            "AZURE_SEARCH_API_VERSION": self.search_api_version,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Required Azure AI configuration is missing: " + ", ".join(missing)
            )
        for name, endpoint in (
            ("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", self.document_intelligence_endpoint),
            ("AZURE_LANGUAGE_ENDPOINT", self.language_endpoint),
            ("AZURE_TRANSLATOR_ENDPOINT", self.translator_endpoint),
            ("AZURE_CONTENT_SAFETY_ENDPOINT", self.content_safety_endpoint),
            ("AZURE_SEARCH_ENDPOINT", self.search_endpoint),
        ):
            if urlsplit(endpoint).scheme != "https" or not urlsplit(endpoint).netloc:
                raise RuntimeError(f"{name} must be a valid HTTPS endpoint.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}[a-z0-9]", self.search_index):
            raise RuntimeError("AZURE_SEARCH_INDEX must be 2-128 lowercase letters, digits, or hyphens.")
        if not 2 <= self.search_vector_dimensions <= 4096:
            raise RuntimeError("AZURE_SEARCH_VECTOR_DIMENSIONS must be between 2 and 4096.")
        if self.content_safety_block_severity not in (0, 2, 4, 6):
            raise RuntimeError("AZURE_CONTENT_SAFETY_BLOCK_SEVERITY must be 0, 2, 4, or 6.")

    def sqlalchemy_url(self, *, unpooled: bool = False) -> str:
        value = self.database_url_unpooled if unpooled else self.database_url
        if not value:
            variable = "DATABASE_URL_UNPOOLED" if unpooled else "DATABASE_URL"
            raise RuntimeError(f"{variable} must be configured; SQLite is not supported.")
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        if not value.startswith("postgresql+psycopg://"):
            raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
        return value


settings = Settings()
