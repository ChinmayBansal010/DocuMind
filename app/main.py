import logging
import hashlib
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import router as api_v1
from app.core.config import settings
from app.db.session import database_ready, get_engine
from app.services.errors import AzureServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("documind")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_azure_configuration()
    yield


app = FastAPI(
    title="DocuMind Contract Intelligence",
    version="3.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.state.rate_limit_disabled = False


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _rate_limit_settings() -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(second|minute|hour)s?\s*", settings.rate_limit)
    if not match:
        raise RuntimeError("API_RATE_LIMIT must look like '120/minute'.")
    multiplier = {"second": 1, "minute": 60, "hour": 3600}[match.group(2)]
    return max(1, int(match.group(1))), multiplier


@app.middleware("http")
async def postgres_rate_limit(request: Request, call_next):
    if (
        app.state.rate_limit_disabled
        or not request.url.path.startswith("/api/")
        or request.url.path == "/api/health"
        or request.method == "OPTIONS"
    ):
        return await call_next(request)
    try:
        limit, period = _rate_limit_settings()
        now = int(time.time())
        window_start = now - (now % period)
        client = request.client.host if request.client else "unknown"
        bucket = hashlib.sha256(client.encode("utf-8")).hexdigest()
        with get_engine().begin() as connection:
            count = connection.execute(
                text(
                    "INSERT INTO api_rate_limit_windows (client_key, window_start, request_count) "
                    "VALUES (:key, :window, 1) "
                    "ON CONFLICT (client_key, window_start) DO UPDATE "
                    "SET request_count = api_rate_limit_windows.request_count + 1 "
                    "RETURNING request_count"
                ),
                {"key": bucket, "window": window_start},
            ).scalar_one()
            if count % 200 == 0:
                connection.execute(
                    text("DELETE FROM api_rate_limit_windows WHERE window_start < :expired"),
                    {"expired": window_start - period * 2},
                )
        if count > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Request rate limit exceeded. Retry after the current time window."},
                headers={"Retry-After": str(period - now % period)},
            )
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.error("Request rate limiter unavailable: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Request protection is temporarily unavailable."},
        )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    auth_origin = urlsplit(settings.auth_base_url)
    connect_origin = (
        f"{auth_origin.scheme}://{auth_origin.netloc}" if auth_origin.scheme and auth_origin.netloc else ""
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"script-src 'self'; connect-src 'self' {connect_origin}; frame-src 'self' {connect_origin}; "
        f"base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.exception_handler(AzureServiceError)
async def azure_service_error(request: Request, exc: AzureServiceError):
    logger.warning(
        "Azure integration failed: %s (HTTP %s)",
        exc.service,
        exc.status_code,
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc), "service": exc.service},
    )


@app.get("/api/health")
def health():
    ready = database_ready()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "degraded",
            "database": "connected" if ready else "unavailable",
            "auth_configured": bool(settings.auth_base_url and settings.auth_jwks_url),
            "azure_services": {
                "document_intelligence": bool(
                    settings.document_intelligence_endpoint and settings.document_intelligence_key
                ),
                "language": bool(settings.language_endpoint and settings.language_key),
                "translator": bool(
                    settings.translator_endpoint
                    and settings.translator_key
                    and settings.translator_region
                ),
                "content_safety": bool(
                    settings.content_safety_endpoint and settings.content_safety_key
                ),
                "search": bool(settings.search_endpoint and settings.search_key and settings.search_index),
            },
        },
    )


app.include_router(api_v1)

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(frontend_dist / "index.html")
