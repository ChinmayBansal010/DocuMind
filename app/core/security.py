import logging
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.auth_jwks_url:
        raise RuntimeError("NEON_AUTH_JWKS_URL is not configured.")
    return PyJWKClient(settings.auth_jwks_url, cache_keys=True)


def decode_access_token(token: str) -> dict[str, Any]:
    if not settings.auth_base_url or not settings.auth_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neon Auth is not configured on this server.",
        )
    auth_url = urlsplit(settings.auth_base_url)
    if auth_url.scheme != "https" or not auth_url.netloc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neon Auth is not configured with a valid HTTPS URL.",
        )
    auth_origin = f"{auth_url.scheme}://{auth_url.netloc}"
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            issuer=auth_origin,
            audience=auth_origin,
            leeway=60,
            options={"require": ["exp", "iss", "sub", "aud"]},
        )
    except (jwt.PyJWTError, ValueError, RuntimeError) as exc:
        logger.warning("Neon Auth rejected an access token: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The access token has no valid subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(credentials.credentials)
    user_id = claims["sub"]
    user = db.get(User, user_id)
    if user is None:
        email = claims.get("email")
        name = claims.get("name")
        user = User(
            id=user_id,
            email=email if isinstance(email, str) else "",
            name=name if isinstance(name, str) else "",
        )
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            user = db.get(User, user_id)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unable to initialize the authenticated user profile.",
                )
    return user
