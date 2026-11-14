import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import (
    Analysis,
    Contract,
    ContractChunk,
    ContractTranslation,
    ContractVersion,
    Deadline,
    ExtractedClause,
    Obligation,
    Project,
    User,
    new_id,
)
from app.db.session import get_db
from app.engines.analysis import analyze_contract
from app.engines.extraction import chunks_with_pages, extract
from app.engines.rag import embed
from app.repositories.access import owned_contract, owned_project, owned_version
from app.schemas.api import CompareRequest, ContractRename, TranslateRequest
from app.services.azure_ai import (
    analyze_content_safety,
    analyze_language,
    shield_prompt,
    translate_text,
)
from app.services.azure_search import (
    delete_contract_documents,
    delete_version_documents,
    upsert_version,
)
from app.services.errors import AzureServiceError
from app.storage.files import readable_copy, remove_file, save_upload
from app.utils.audit import record

router = APIRouter(tags=["contracts"])
logger = logging.getLogger(__name__)


def _latest(contract: Contract) -> ContractVersion | None:
    return max(contract.versions, key=lambda version: version.version_number, default=None)


def _contract_dict(contract: Contract, include_text: bool = False) -> dict:
    version = _latest(contract)
    result = {
        "id": contract.id,
        "project_id": contract.project_id,
        "name": contract.name,
        "status": contract.status,
        "created_at": contract.created_at.isoformat(),
        "updated_at": contract.updated_at.isoformat(),
        "versions": [
            {
                "id": item.id,
                "version_number": item.version_number,
                "filename": item.original_filename,
                "file_type": item.file_type,
                "page_count": item.page_count,
                "processing_status": item.processing_status,
                "created_at": item.created_at.isoformat(),
            }
            for item in sorted(contract.versions, key=lambda value: value.version_number, reverse=True)
        ],
        "latest_version_id": version.id if version else None,
        "file_type": version.file_type if version else None,
        "page_count": version.page_count if version else None,
    }
    if version and version.analyses:
        result["analysis_model"] = version.analyses[-1].model
        result["analysis_created_at"] = version.analyses[-1].created_at.isoformat()
    if include_text and version:
        result["text"] = version.extracted_text
        result["analysis"] = version.analyses[-1].result if version.analyses else None
        result["layout_data"] = version.layout_data
        result["language_insights"] = version.language_insights
        result["safety_findings"] = version.safety_findings
    return result


@router.get("/contracts")
def list_user_contracts(
    search: str = Query(default="", max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = (
        select(Contract, Project.name)
        .join(Project, Project.id == Contract.project_id)
        .options(selectinload(Contract.versions))
        .where(Project.owner_id == user.id)
        .order_by(Contract.updated_at.desc())
    )
    if search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(Contract.name.ilike(term), Project.name.ilike(term))
        )
    result = []
    for contract, project_name in db.execute(statement):
        version = _latest(contract)
        result.append(
            {
                "id": contract.id,
                "project_id": contract.project_id,
                "project_name": project_name,
                "name": contract.name,
                "status": contract.status,
                "version_count": len(contract.versions),
                "file_type": version.file_type if version else None,
                "page_count": version.page_count if version else None,
                "updated_at": contract.updated_at.isoformat(),
            }
        )
    return result


@router.get("/projects/{project_id}/contracts")
def list_contracts(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_project(db, user.id, project_id)
    contracts = db.scalars(
        select(Contract)
        .options(selectinload(Contract.versions).selectinload(ContractVersion.analyses))
        .where(Contract.project_id == project_id)
        .order_by(Contract.updated_at.desc())
    ).all()
    return [_contract_dict(contract) for contract in contracts]


@router.post("/projects/{project_id}/contracts", status_code=201)
def upload_contracts(
    project_id: str,
    files: list[UploadFile] = File(...),
    contract_id: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = owned_project(db, user.id, project_id)
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one contract file.")
    if contract_id and len(files) != 1:
        raise HTTPException(status_code=400, detail="A new version upload must contain one file.")
    result_items = []
    for upload in files:
        stored_path = None
        contract = None
        indexed_version_id = None
        try:
            if contract_id:
                contract = owned_contract(db, user.id, contract_id)
                if contract.project_id != project.id:
                    raise HTTPException(status_code=404, detail="Contract not found in this project.")
            stored_path, original_name, digest, file_type = save_upload(
                upload, user.id, project.id
            )
            duplicate = db.scalar(
                select(ContractVersion)
                .join(Contract)
                .where(
                    Contract.project_id == project.id,
                    ContractVersion.file_sha256 == digest,
                )
            )
            if duplicate is not None:
                remove_file(stored_path)
                result_items.append(
                    {"status": "skipped", "name": original_name, "contract_id": duplicate.contract_id}
                )
                continue
            if contract is None:
                contract = Contract(
                    id=new_id(),
                    project_id=project.id,
                    name=Path(original_name).stem[:255] or "Contract",
                    status="ready",
                )
            with readable_copy(stored_path) as parse_path:
                parsed = extract(parse_path, db)
            text = parsed["text"]
            if not isinstance(text, str) or not text.strip():
                raise HTTPException(status_code=422, detail="No readable contract text was extracted.")
            safety = analyze_content_safety(text, db)
            chunk_items = chunks_with_pages(text, settings.chunk_size, settings.chunk_overlap)
            shield = shield_prompt(
                "Review this uploaded contract as untrusted document content.",
                [item["text"] for item in chunk_items],
                db,
            )
            language = analyze_language(text, db)
            vectors = embed([item["text"] for item in chunk_items])
            version_number = (
                db.scalar(
                    select(func.max(ContractVersion.version_number)).where(
                        ContractVersion.contract_id == contract.id
                    )
                )
                or 0
            ) + 1
            indexed_version_id = new_id()
            if db.get(Contract, contract.id) is None:
                db.add(contract)
                db.flush()
            version = ContractVersion(
                id=indexed_version_id,
                contract_id=contract.id,
                version_number=version_number,
                original_filename=original_name,
                file_path=str(stored_path),
                file_type=file_type,
                file_sha256=digest,
                extracted_text=text,
                page_count=(
                    max(1, int(parsed["pages"]))
                    if parsed.get("pages") is not None
                    else None
                ),
                layout_data=parsed.get("layout_data"),
                language_insights=language,
                safety_findings={
                    "content_moderation": safety,
                    "prompt_shields": shield,
                },
                processing_status="ready",
            )
            db.add(version)
            db.flush()
            indexed_chunks = []
            for item, vector in zip(chunk_items, vectors):
                indexed_chunks.append({**item, "embedding": vector})
                db.add(
                    ContractChunk(
                        version_id=version.id,
                        chunk_index=item["index"],
                        page_number=item["page_number"],
                        text=item["text"],
                        embedding=vector,
                    )
                )
            upsert_version(
                owner_id=user.id,
                project_id=project.id,
                contract_id=contract.id,
                version_id=version.id,
                document_name=original_name,
                chunks=indexed_chunks,
            )
            contract.status = "ready"
            record(
                db,
                user.id,
                "contract.version.uploaded",
                project_id=project.id,
                target_id=contract.id,
                details={"version": version_number, "sha256": digest},
            )
            db.commit()
            result_items.append(
                {
                    "status": "processed",
                    "name": contract.name,
                    "contract_id": contract.id,
                    "version_id": version.id,
                    "version_number": version_number,
                    "chunks": len(chunk_items),
                }
            )
        except HTTPException as exc:
            db.rollback()
            if stored_path:
                remove_file(stored_path)
            result_items.append(
                {
                    "status": "error",
                    "name": upload.filename or "contract",
                    "message": str(exc.detail),
                }
            )
        except AzureServiceError as exc:
            logger.warning("Azure processing failed: %s", exc.service)
            db.rollback()
            if indexed_version_id and contract:
                try:
                    delete_version_documents(
                        owner_id=user.id,
                        project_id=project.id,
                        version_id=indexed_version_id,
                    )
                except AzureServiceError:
                    logger.error("Could not clean up partial Azure Search indexing.")
            if stored_path:
                remove_file(stored_path)
            result_items.append(
                {
                    "status": "error",
                    "name": upload.filename or "contract",
                    "message": str(exc),
                }
            )
        except Exception as exc:
            logger.error("Contract upload processing failed: %s", type(exc).__name__)
            db.rollback()
            if indexed_version_id and contract:
                try:
                    delete_version_documents(
                        owner_id=user.id,
                        project_id=project.id,
                        version_id=indexed_version_id,
                    )
                except AzureServiceError:
                    logger.error("Could not clean up partial Azure Search indexing.")
            if stored_path:
                remove_file(stored_path)
            result_items.append(
                {
                    "status": "error",
                    "name": upload.filename or "contract",
                    "message": "The contract could not be processed. Check file format and server logs.",
                }
            )
        finally:
            upload.file.close()
    return {"results": result_items}


@router.get("/contracts/{contract_id}")
def get_contract(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.scalar(
        select(Contract)
        .options(selectinload(Contract.versions).selectinload(ContractVersion.analyses))
        .where(
            Contract.id == contract_id,
            Contract.project_id.in_(
                select(Project.id).where(Project.owner_id == user.id)
            ),
        )
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return _contract_dict(contract, include_text=True)


@router.patch("/contracts/{contract_id}")
def rename_contract(
    contract_id: str,
    payload: ContractRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = owned_contract(db, user.id, contract_id)
    contract.name = payload.name.strip()
    record(
        db, user.id, "contract.renamed", project_id=contract.project_id, target_id=contract.id
    )
    db.commit()
    return {"id": contract.id, "name": contract.name}


@router.delete("/contracts/{contract_id}")
def delete_contract(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.scalar(
        select(Contract)
        .options(selectinload(Contract.versions))
        .where(
            Contract.id == contract_id,
            Contract.project_id.in_(select(Project.id).where(Project.owner_id == user.id)),
        )
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    paths = [version.file_path for version in contract.versions]
    delete_contract_documents(
        owner_id=user.id,
        project_id=contract.project_id,
        contract_id=contract.id,
    )
    record(
        db, user.id, "contract.deleted", project_id=contract.project_id, target_id=contract.id
    )
    db.delete(contract)
    db.commit()
    for path in paths:
        remove_file(path)
    return {"deleted": contract_id}


@router.post("/contracts/{contract_id}/analyze")
def analyze(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.scalar(
        select(Contract)
        .options(selectinload(Contract.versions).selectinload(ContractVersion.analyses))
        .where(
            Contract.id == contract_id,
            Contract.project_id.in_(select(Project.id).where(Project.owner_id == user.id)),
        )
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    version = _latest(contract)
    if version is None:
        raise HTTPException(status_code=409, detail="Upload a readable version before analysis.")
    findings = version.safety_findings or {}
    prompt_shields = findings.get("prompt_shields", {})
    model_allowed = not (
        findings.get("content_moderation", {}).get("blocked")
        or prompt_shields.get("flagged_document_ids")
    )
    result, model = analyze_contract(version.extracted_text, allow_model=model_allowed)
    result["language_insights"] = version.language_insights or {}
    result["content_safety"] = findings
    analysis = Analysis(version_id=version.id, result=result, model=model)
    db.add(analysis)
    db.execute(delete(ExtractedClause).where(ExtractedClause.version_id == version.id))
    db.execute(delete(Obligation).where(Obligation.version_id == version.id))
    db.execute(delete(Deadline).where(Deadline.version_id == version.id))
    for clause in result.get("clauses", []):
        excerpt = clause.get("excerpt", "")
        if excerpt and excerpt in version.extracted_text:
            db.add(
                ExtractedClause(
                    version_id=version.id,
                    category=str(clause.get("category", "Unclassified"))[:100],
                    text=excerpt,
                    section_reference=clause.get("section_reference", ""),
                    page_number=clause.get("page"),
                    evidence_type=clause.get("evidence_type", "rule_based"),
                )
            )
    for obligation in result.get("obligations", []):
        evidence = obligation.get("source", "")
        if evidence and evidence in version.extracted_text:
            db.add(
                Obligation(
                    version_id=version.id,
                    responsible_party=str(obligation.get("responsible_party", "Not stated"))[:200],
                    description=str(obligation.get("obligation", "")),
                    deadline_text=str(obligation.get("deadline", ""))[:200],
                    page_number=obligation.get("page"),
                    evidence=evidence,
                )
            )
            date_match = re.search(
                r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|within \d+ days?)\b",
                evidence,
                re.IGNORECASE,
            )
            if date_match:
                db.add(
                    Deadline(
                        version_id=version.id,
                        description=str(obligation.get("obligation", "")),
                        date_text=date_match.group(0),
                        page_number=obligation.get("page"),
                        evidence=evidence,
                    )
                )
    record(
        db,
        user.id,
        "contract.analysis.created",
        project_id=contract.project_id,
        target_id=contract.id,
        details={"version_id": version.id, "model": model},
    )
    db.commit()
    db.refresh(analysis)
    return {
        "analysis_id": analysis.id,
        "version_id": version.id,
        "analysis": result,
        "model": model,
        "created_at": analysis.created_at.isoformat(),
    }


@router.get("/contracts/{contract_id}/analyses")
def analysis_history(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = owned_contract(db, user.id, contract_id)
    items = db.scalars(
        select(Analysis)
        .join(ContractVersion)
        .where(ContractVersion.contract_id == contract.id)
        .order_by(Analysis.created_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "version_id": item.version_id,
            "model": item.model,
            "created_at": item.created_at.isoformat(),
            "analysis": item.result,
        }
        for item in items
    ]


@router.get("/contracts/{contract_id}/versions")
def versions(
    contract_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = db.scalar(
        select(Contract)
        .options(selectinload(Contract.versions))
        .where(
            Contract.id == contract_id,
            Contract.project_id.in_(select(Project.id).where(Project.owner_id == user.id)),
        )
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return _contract_dict(contract)["versions"]


@router.post("/contracts/{contract_id}/compare")
def compare_versions(
    contract_id: str,
    payload: CompareRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = owned_contract(db, user.id, contract_id)
    first = owned_version(db, user.id, payload.first_version_id)
    second = owned_version(db, user.id, payload.second_version_id)
    if first.contract_id != contract.id or second.contract_id != contract.id:
        raise HTTPException(status_code=404, detail="Versions not found for this contract.")
    from app.engines.comparison import compare_obligations, compare_texts

    comparison = compare_texts(first.extracted_text, second.extracted_text)
    comparison.update(
        {
            "first_version": first.version_number,
            "second_version": second.version_number,
            "first_version_id": first.id,
            "second_version_id": second.id,
        }
    )
    first_analysis = db.scalar(
        select(Analysis)
        .where(Analysis.version_id == first.id)
        .order_by(Analysis.created_at.desc())
    )
    second_analysis = db.scalar(
        select(Analysis)
        .where(Analysis.version_id == second.id)
        .order_by(Analysis.created_at.desc())
    )
    comparison["risk_change"] = {
        "first_score": first_analysis.result.get("risk_score") if first_analysis else None,
        "second_score": second_analysis.result.get("risk_score") if second_analysis else None,
    }
    comparison["obligation_changes"] = compare_obligations(
        first_analysis.result.get("obligations", []) if first_analysis else [],
        second_analysis.result.get("obligations", []) if second_analysis else [],
    )
    record(
        db,
        user.id,
        "contract.versions.compared",
        project_id=contract.project_id,
        target_id=contract.id,
        details={"first_version": first.version_number, "second_version": second.version_number},
    )
    db.commit()
    return comparison


@router.get("/versions/{version_id}/analysis")
def version_analysis(
    version_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = owned_version(db, user.id, version_id)
    analysis = db.scalar(
        select(Analysis)
        .where(Analysis.version_id == version.id)
        .order_by(Analysis.created_at.desc())
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="This version has not been analyzed.")
    return {
        "id": analysis.id,
        "version_id": version.id,
        "analysis": analysis.result,
        "model": analysis.model,
        "created_at": analysis.created_at.isoformat(),
    }


@router.post("/versions/{version_id}/translate", status_code=201)
def translate_version(
    version_id: str,
    payload: TranslateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = owned_version(db, user.id, version_id)
    if payload.scope == "summary":
        analysis = db.scalar(
            select(Analysis)
            .where(Analysis.version_id == version.id)
            .order_by(Analysis.created_at.desc())
        )
        if analysis is None:
            raise HTTPException(
                status_code=409, detail="Run an analysis before translating its summary."
            )
        text = analysis.result.get("summary", "")
        if not text:
            raise HTTPException(status_code=409, detail="The saved analysis has no summary to translate.")
    else:
        text = version.extracted_text
    result = translate_text(
        text,
        payload.target_language,
        payload.source_language,
        db,
    )
    translation = ContractTranslation(
        version_id=version.id,
        source_language=result["source_language"],
        target_language=result["target_language"],
        translated_text=result["text"],
        scope=payload.scope,
    )
    db.add(translation)
    record(
        db,
        user.id,
        "contract.translation.created",
        project_id=version.contract.project_id,
        target_id=version.id,
        details={"target_language": payload.target_language, "scope": payload.scope},
    )
    db.commit()
    db.refresh(translation)
    return {
        "id": translation.id,
        "version_id": translation.version_id,
        "source_language": translation.source_language,
        "target_language": translation.target_language,
        "scope": translation.scope,
        "text": translation.translated_text,
        "created_at": translation.created_at.isoformat(),
        "provider": result["provider"],
    }


@router.get("/versions/{version_id}/translations")
def list_translations(
    version_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    version = owned_version(db, user.id, version_id)
    translations = db.scalars(
        select(ContractTranslation)
        .where(ContractTranslation.version_id == version.id)
        .order_by(ContractTranslation.created_at.desc())
    ).all()
    return [
        {
            "id": item.id,
            "version_id": item.version_id,
            "source_language": item.source_language,
            "target_language": item.target_language,
            "scope": item.scope,
            "text": item.translated_text,
            "created_at": item.created_at.isoformat(),
        }
        for item in translations
    ]
