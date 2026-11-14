from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.core.config import settings
from app.db.models import (
    Contract,
    ContractVersion,
    Conversation,
    Message,
    Project,
    User,
)
from app.db.session import get_db
from app.engines.rag import answer, retrieve
from app.repositories.access import owned_contract, owned_project
from app.schemas.api import ContractQuestion, ProjectQuestion
from app.services.azure_ai import analyze_content_safety, shield_prompt
from app.utils.audit import record

router = APIRouter(tags=["assistant"])


def _ask(
    *,
    project_id: str,
    contract_id: str | None,
    payload: ContractQuestion | ProjectQuestion,
    owner_id: str,
    db: Session,
) -> dict:
    if payload.conversation_id:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.project_id == project_id,
                Conversation.contract_id == contract_id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        conversation = Conversation(
            project_id=project_id,
            contract_id=contract_id,
            title=payload.question.strip()[:200],
        )
        db.add(conversation)
        db.flush()

    latest = (
        select(
            ContractVersion.contract_id.label("contract_id"),
            func.max(ContractVersion.version_number).label("version_number"),
        )
        .join(Contract)
        .where(Contract.project_id == project_id)
        .group_by(ContractVersion.contract_id)
        .subquery()
    )
    latest_statement = (
        select(ContractVersion.id)
        .join(Contract, Contract.id == ContractVersion.contract_id)
        .join(latest, (latest.c.contract_id == ContractVersion.contract_id)
              & (latest.c.version_number == ContractVersion.version_number))
        .where(Contract.project_id == project_id)
    )
    if contract_id:
        latest_statement = latest_statement.where(Contract.id == contract_id)
    latest_version_ids = db.scalars(latest_statement).all()
    sources = []
    blocked_reason = None
    content_moderation = analyze_content_safety(payload.question.strip(), db)
    if content_moderation["blocked"]:
        blocked_reason = "Azure Content Safety flagged the question; no contract answer was generated."
    else:
        sources = retrieve(
            payload.question.strip(),
            owner_id=owner_id,
            project_id=project_id,
            latest_version_ids=latest_version_ids,
            contract_id=contract_id,
            top_k=5,
        )
        shields = shield_prompt(
            payload.question.strip(),
            [
                f"{source['document_name']}\n{source['text']}"
                for source in sources
            ],
            db,
        )
        if shields["user_prompt_attack"]:
            blocked_reason = "Azure Prompt Shields detected a prompt-injection attempt; no contract answer was generated."
        else:
            flagged_indices = {
                int(value)
                for value in shields["flagged_document_ids"]
                if str(value).isdigit()
            }
            sources = [
                source
                for index, source in enumerate(sources)
                if index not in flagged_indices
            ]
    result = blocked_reason or answer(payload.question.strip(), sources)
    citations = [
        {
            "source_number": index,
            "document": source["document_name"],
            "contract_id": source["contract_id"],
            "version_id": source["version_id"],
            "page": source["page"],
            "chunk_id": source["chunk_id"],
            "excerpt": source["text"],
        }
        for index, source in enumerate(sources, start=1)
    ]
    db.add(
        Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.question.strip(),
        )
    )
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result,
            citations=citations,
        )
    )
    record(
        db,
        owner_id,
        "assistant.question.asked",
        project_id=project_id,
        target_id=conversation.id,
        details={"contract_id": contract_id, "source_count": len(citations)},
    )
    db.commit()
    if blocked_reason:
        model = "Azure Content Safety blocked"
    elif sources and settings.ollama_model and not result.startswith("I could not generate"):
        model = "Ollama"
    elif sources:
        model = "Extractive fallback"
    else:
        model = "No evidence retrieved"
    return {
        "conversation_id": conversation.id,
        "answer": result,
        "citations": citations,
        "model": model,
    }


@router.post("/projects/{project_id}/assistant/ask")
def ask_project(
    project_id: str,
    payload: ProjectQuestion,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_project(db, user.id, project_id)
    return _ask(
        project_id=project_id,
        contract_id=None,
        payload=payload,
        owner_id=user.id,
        db=db,
    )


@router.post("/contracts/{contract_id}/ask")
def ask_contract(
    contract_id: str,
    payload: ContractQuestion,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = owned_contract(db, user.id, contract_id)
    return _ask(
        project_id=contract.project_id,
        contract_id=contract.id,
        payload=payload,
        owner_id=user.id,
        db=db,
    )


@router.get("/projects/{project_id}/conversations")
def list_conversations(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_project(db, user.id, project_id)
    conversations = db.scalars(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.created_at.desc())
    ).unique().all()
    return [
        {
            "id": item.id,
            "contract_id": item.contract_id,
            "title": item.title,
            "created_at": item.created_at.isoformat(),
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "citations": message.citations,
                    "created_at": message.created_at.isoformat(),
                }
                for message in item.messages
            ],
        }
        for item in conversations
    ]
