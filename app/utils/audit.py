from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record(
    db: Session,
    owner_id: str,
    event_type: str,
    *,
    project_id: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            owner_id=owner_id,
            event_type=event_type,
            project_id=project_id,
            target_id=target_id,
            details=details or {},
        )
    )
