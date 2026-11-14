import io
import json
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.db.models import Analysis, Contract, ContractVersion, Project, User
from app.db.session import get_db
from app.repositories.access import owned_version

router = APIRouter(tags=["reports"])


def _report_payload(version: ContractVersion, analysis: Analysis) -> dict:
    contract = version.contract
    return {
        "contract": contract.name,
        "project_id": contract.project_id,
        "version": version.version_number,
        "source_file": version.original_filename,
        "page_count": version.page_count,
        "analysis_id": analysis.id,
        "analysis_date": analysis.created_at.isoformat(),
        "model": analysis.model,
        "deadlines": [
            {
                "description": item.description,
                "date": item.date_text,
                "page": item.page_number,
                "evidence": item.evidence,
            }
            for item in version.deadlines
        ],
        **analysis.result,
    }


def _markdown(payload: dict) -> str:
    output = [
        f"# Contract review: {payload['contract']}",
        "",
        f"- Version: {payload['version']}",
        f"- Source: {payload['source_file']}",
        f"- Pages: {payload['page_count']}",
        f"- Analysis date: {payload['analysis_date']}",
        f"- Method: {payload['model']}",
        "",
        "## Executive summary",
        "",
        payload.get("summary", "No summary was produced."),
        "",
        f"## Risk score: {payload.get('risk_score', 'Not scored')}",
        "",
        payload.get("risk_methodology", ""),
        "",
        "## Risks",
        "",
    ]
    risks = payload.get("risks", [])
    output.extend(
        f"- **{risk.get('severity', 'Unrated')} — {risk.get('title', 'Finding')}** "
        f"(page {risk.get('page', 'not stated')}): {risk.get('reason', '')}\n"
        f"  Evidence: “{risk.get('evidence', '')}”\n"
        f"  Suggested action: {risk.get('recommendation', '')}"
        for risk in risks
    )
    output.extend(["", "## Clauses", ""])
    output.extend(
        f"- **{item.get('category', 'Clause')}** — page {item.get('page', 'not stated')}: "
        f"{item.get('summary', '')}\n  > {item.get('excerpt', '')}"
        for item in payload.get("clauses", [])
    )
    output.extend(["", "## Missing or weak provisions", ""])
    output.extend(
        f"- **{item.get('category', 'Provision')}** ({item.get('importance', 'Review')}): "
        f"{item.get('explanation', '')}"
        for item in payload.get("missing_clauses", [])
    )
    output.extend(["", "## Obligations", ""])
    output.extend(
        f"- {item.get('responsible_party', 'Party not stated')}: {item.get('obligation', '')}; "
        f"deadline: {item.get('deadline') or 'not stated'}; page {item.get('page', 'not stated')}."
        for item in payload.get("obligations", [])
    )
    output.extend(["", "## Deadlines", ""])
    output.extend(
        f"- {item['date']}: {item['description']} "
        f"(page {item['page'] if item['page'] is not None else 'not available'}). Evidence: {item['evidence']}"
        for item in payload.get("deadlines", [])
    )
    output.extend(
        [
            "",
            "## Limitations",
            "",
            "AI-generated findings are informational, may be incomplete, and are not legal advice. "
            "Check every statement against the original agreement.",
        ]
    )
    return "\n".join(output)


def _pdf(payload: dict) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter, title=f"Contract review — {payload['contract']}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(escape(f"Contract review: {payload['contract']}"), styles["Title"]),
        Spacer(1, 12),
        Paragraph(escape(f"Version {payload['version']} · {payload['source_file']} · {payload['page_count']} pages"), styles["Normal"]),
        Spacer(1, 12),
    ]
    sections = [
        ("Executive summary", payload.get("summary", "No summary was produced.")),
        ("Risk score and method", f"{payload.get('risk_score', 'Not scored')}. {payload.get('risk_methodology', '')}"),
    ]
    sections += [
        (
            f"Risk: {item.get('title', 'Finding')} ({item.get('severity', 'Unrated')})",
            f"{item.get('reason', '')} Evidence: {item.get('evidence', '')} "
            f"Suggested action: {item.get('recommendation', '')} Page {item.get('page', 'not stated')}.",
        )
        for item in payload.get("risks", [])
    ]
    sections += [
        (
            f"Clause: {item.get('category', 'Clause')}",
            f"{item.get('summary', '')} Evidence: {item.get('excerpt', '')} "
            f"Page {item.get('page', 'not stated')}.",
        )
        for item in payload.get("clauses", [])
    ]
    sections += [
        (
            f"Review provision: {item.get('category', 'Provision')}",
            item.get("explanation", ""),
        )
        for item in payload.get("missing_clauses", [])
    ]
    sections += [
        (
            f"Obligation: {item.get('responsible_party', 'Party not stated')}",
            f"{item.get('obligation', '')} Deadline: {item.get('deadline') or 'not stated'}. "
            f"Evidence: {item.get('source', '')} Page {item.get('page', 'not stated')}.",
        )
        for item in payload.get("obligations", [])
    ]
    sections += [
        (
            f"Deadline: {item['date']}",
            f"{item['description']} Evidence: {item['evidence']} "
            f"Page {item['page'] if item['page'] is not None else 'not available'}.",
        )
        for item in payload.get("deadlines", [])
    ]
    for heading, body in sections:
        story.append(Paragraph(escape(heading), styles["Heading2"]))
        story.append(Paragraph(escape(str(body)), styles["BodyText"]))
        story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            escape("Informational only; AI findings can be incomplete. Verify against the original contract."),
            styles["Italic"],
        )
    )
    document.build(story)
    return buffer.getvalue()


@router.get("/versions/{version_id}/report")
def export_report(
    version_id: str,
    format: str = Query(default="json", pattern="^(json|md|pdf)$"),
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
        raise HTTPException(status_code=404, detail="Run an analysis before exporting a report.")
    payload = _report_payload(version, analysis)
    filename = f"contract-review-v{version.version_number}"
    if format == "md":
        return Response(
            _markdown(payload),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )
    if format == "pdf":
        return Response(
            _pdf(payload),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
        )
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )
