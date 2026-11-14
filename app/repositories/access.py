from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Contract, ContractVersion, Project


def owned_project(db: Session, owner_id: str, project_id: str) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def owned_contract(db: Session, owner_id: str, contract_id: str) -> Contract:
    contract = db.scalar(
        select(Contract)
        .join(Project)
        .where(Contract.id == contract_id, Project.owner_id == owner_id)
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract


def owned_version(
    db: Session, owner_id: str, version_id: str
) -> ContractVersion:
    version = db.scalar(
        select(ContractVersion)
        .join(Contract)
        .join(Project)
        .where(ContractVersion.id == version_id, Project.owner_id == owner_id)
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Contract version not found.")
    return version
