from datetime import datetime, timezone
from math import ceil

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import AzureUsageCounter
from app.services.errors import AzureServiceError

MONTHLY_LIMITS = {
    "document_intelligence": 500,
    "language": 5_000,
    "content_safety": 5_000,
    "translator": 2_000_000,
}


def text_records(text: str) -> int:
    return max(1, ceil(len(text) / 1000))


def reserve_monthly_usage(db: Session, service: str, units: int) -> None:
    limit = MONTHLY_LIMITS[service]
    if units <= 0:
        return
    if units > limit:
        raise AzureServiceError(
            service.replace("_", " "),
            f"this request exceeds the F0 monthly allowance of {limit} units.",
            status_code=429,
        )
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    table: Table = AzureUsageCounter.__table__
    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise RuntimeError(f"Azure usage tracking does not support database dialect {dialect}.")
    statement = insert(table).values(service=service, period=period, units=units)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.service, table.c.period],
        set_={"units": table.c.units + units},
        where=table.c.units + units <= limit,
    ).returning(table.c.units)
    with db.get_bind().begin() as connection:
        consumed = connection.execute(statement).scalar_one_or_none()
    if consumed is None:
        raise AzureServiceError(
            service.replace("_", " "),
            f"the application's F0 monthly allowance of {limit} units has been reached.",
            status_code=429,
        )
