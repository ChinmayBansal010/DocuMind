from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.db.models import Contract, ContractVersion, Project, User
from app.db.session import get_db
from app.repositories.access import owned_project
from app.schemas.api import ProjectCreate, ProjectUpdate
from app.services.azure_search import delete_project_documents
from app.storage.files import remove_file
from app.utils.audit import record

router = APIRouter(tags=["projects"])


def _project_dict(project: Project, contract_count: int | None = None) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "contract_count": contract_count
        if contract_count is not None
        else len(project.contracts),
    }


@router.get("/projects")
def list_projects(
    search: str = Query(default="", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count_query = (
        select(Contract.project_id, func.count(Contract.id).label("contract_count"))
        .group_by(Contract.project_id)
        .subquery()
    )
    statement = (
        select(Project, func.coalesce(count_query.c.contract_count, 0))
        .outerjoin(count_query, Project.id == count_query.c.project_id)
        .where(Project.owner_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    if search.strip():
        statement = statement.where(Project.name.ilike(f"%{search.strip()}%"))
    return [_project_dict(project, count) for project, count in db.execute(statement)]


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        owner_id=user.id, name=payload.name.strip(), description=payload.description.strip()
    )
    db.add(project)
    db.flush()
    record(db, user.id, "project.created", project_id=project.id, target_id=project.id)
    db.commit()
    db.refresh(project)
    return _project_dict(project, 0)


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.contracts).selectinload(Contract.versions))
        .where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    contracts = []
    for contract in project.contracts:
        latest = max(contract.versions, key=lambda version: version.version_number, default=None)
        contracts.append(
            {
                "id": contract.id,
                "name": contract.name,
                "status": contract.status,
                "version_count": len(contract.versions),
                "latest_version_id": latest.id if latest else None,
                "file_type": latest.file_type if latest else None,
                "page_count": latest.page_count if latest else None,
                "updated_at": contract.updated_at.isoformat(),
            }
        )
    return {**_project_dict(project), "contracts": contracts}


@router.patch("/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = owned_project(db, user.id, project_id)
    project.name = payload.name.strip()
    project.description = payload.description.strip()
    record(db, user.id, "project.updated", project_id=project.id, target_id=project.id)
    db.commit()
    db.refresh(project)
    return _project_dict(project)


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.scalar(
        select(Project)
        .options(selectinload(Project.contracts).selectinload(Contract.versions))
        .where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    paths = [version.file_path for contract in project.contracts for version in contract.versions]
    delete_project_documents(owner_id=user.id, project_id=project.id)
    record(db, user.id, "project.deleted", target_id=project.id, details={"name": project.name})
    db.delete(project)
    db.commit()
    for path in paths:
        remove_file(path)
    return {"deleted": project_id}
