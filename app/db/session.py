from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from fastapi import HTTPException, status


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        settings.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
        connect_args={"connect_timeout": 10},
    )


def get_db() -> Generator[Session, None, None]:
    try:
        db = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        yield db
    finally:
        db.close()


def database_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
            ).scalar_one_or_none()
        return revision is not None
    except (SQLAlchemyError, RuntimeError):
        return False
