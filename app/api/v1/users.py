from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.api import ProfileUpdate
from app.utils.audit import record
from app.core.config import settings

router = APIRouter(tags=["profile"])


@router.get("/profile")
def profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


@router.get("/settings")
def settings_view(user: User = Depends(get_current_user)):
    return {
        "upload_limit_mb": settings.max_upload_mb,
        "supported_file_types": ["pdf", "docx", "txt"],
        "ollama_configured": bool(settings.ollama_model),
        "ollama_embedding_model": settings.ollama_embedding_model,
        "document_encryption_enabled": bool(settings.encryption_key),
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
            "search": bool(
                settings.search_endpoint and settings.search_key and settings.search_index
            ),
        },
        "azure_free_tier_limits": {
            "document_intelligence_pages_month": 500,
            "document_intelligence_pages_per_request": 2,
            "document_intelligence_request_mb": 4,
            "language_records_month": 5000,
            "translator_characters_month": 2_000_000,
            "content_safety_records_month": 5000,
            "search_storage_mb": 50,
        },
        "translator_document_format_preservation": False,
    }


@router.patch("/profile")
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.name = payload.name.strip()
    record(db, user.id, "profile.updated", target_id=user.id)
    db.commit()
    return {"id": user.id, "email": user.email, "name": user.name}
