# backend/routers/analyze_router.py
import json
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, Analysis, generate_uuid
from backend.auth import get_current_user
from backend.database import User
from backend.agents.engine import run_agent_orchestrator
from backend.database import SessionLocal

router = APIRouter(prefix="/analyze", tags=["Analysis"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    business_problem: str
    architecture_tier: Optional[str] = "professional"
    scale_estimates: Optional[dict] = {}
    constraints: Optional[List[str]] = []

class AnalysisSummary(BaseModel):
    id: str
    business_problem: str
    status: str
    analysis_time_seconds: Optional[float]
    created_at: str

class AnalysisDetail(AnalysisSummary):
    requirements: Optional[dict]
    architecture_design: Optional[dict]
    database_schema: Optional[dict]
    api_specification: Optional[dict]
    deployment_config: Optional[dict]
    security_audit: Optional[dict]
    performance_strategies: Optional[dict]
    diagrams: Optional[dict]
    architecture_model: Optional[dict]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_analysis(
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Starts a new analysis and streams SSE-style progress events.
    The frontend should consume this as a Server-Sent Event stream.
    """
    # Create a placeholder Analysis record
    analysis_id = generate_uuid()
    new_analysis = Analysis(
        id=analysis_id,
        user_id=current_user.id,
        business_problem=payload.business_problem,
        status="processing",
    )
    db.add(new_analysis)
    db.commit()

    async def event_generator():
        async for chunk in run_agent_orchestrator(
            business_problem=payload.business_problem,
            architecture_tier=payload.architecture_tier or "professional",
            scale_estimates=payload.scale_estimates or {},
            constraints=payload.constraints or [],
            analysis_id=analysis_id,
            db_session_factory=SessionLocal,
        ):
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0)  # allow event loop to breathe

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=AnalysisSummary, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Starts a new analysis (non-streaming). Returns 202 with the analysis ID.
    Results are available via GET /analyze/{id} once status = 'completed'.
    """
    analysis_id = generate_uuid()
    new_analysis = Analysis(
        id=analysis_id,
        user_id=current_user.id,
        business_problem=payload.business_problem,
        status="processing",
    )
    db.add(new_analysis)
    db.commit()
    db.refresh(new_analysis)

    # Run the orchestrator in the background (fire and forget)
    import asyncio
    import threading

    def run_bg():
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        async def _run():
            async for _ in run_agent_orchestrator(
                business_problem=payload.business_problem,
                architecture_tier=payload.architecture_tier or "professional",
                scale_estimates=payload.scale_estimates or {},
                constraints=payload.constraints or [],
                analysis_id=analysis_id,
                db_session_factory=SessionLocal,
            ):
                pass
        loop.run_until_complete(_run())
        loop.close()

    thread = threading.Thread(target=run_bg, daemon=True)
    thread.start()

    return AnalysisSummary(
        id=new_analysis.id,
        business_problem=new_analysis.business_problem,
        status=new_analysis.status,
        analysis_time_seconds=new_analysis.analysis_time_seconds,
        created_at=str(new_analysis.created_at),
    )


@router.get("", response_model=List[AnalysisSummary])
def list_analyses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    """List all analyses for the current user, most recent first."""
    analyses = (
        db.query(Analysis)
        .filter(Analysis.user_id == current_user.id)
        .order_by(Analysis.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        AnalysisSummary(
            id=a.id,
            business_problem=a.business_problem,
            status=a.status,
            analysis_time_seconds=a.analysis_time_seconds,
            created_at=str(a.created_at),
        )
        for a in analyses
    ]


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the full result of a specific analysis."""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")

    return AnalysisDetail(
        id=analysis.id,
        business_problem=analysis.business_problem,
        status=analysis.status,
        analysis_time_seconds=analysis.analysis_time_seconds,
        created_at=str(analysis.created_at),
        requirements=analysis.requirements,
        architecture_design=analysis.architecture_design,
        database_schema=analysis.database_schema,
        api_specification=analysis.api_specification,
        deployment_config=analysis.deployment_config,
        security_audit=analysis.security_audit,
        performance_strategies=analysis.performance_strategies,
        diagrams=analysis.diagrams,
        architecture_model=analysis.architecture_model,
    )


@router.get("/{analysis_id}/validation")
def validate_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the cross-tab consistency checks against the stored canonical model.
    Returns the raw issues plus an error/warning/pass summary.
    """
    from backend.agents.model import validate_model, summarize_validation

    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")
    if analysis.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis not ready for validation")
    if not analysis.architecture_model:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Analysis predates the canonical model; re-run to validate.")

    issues = validate_model(analysis.architecture_model)
    return summarize_validation(issues)


@router.get("/{analysis_id}/export")
def export_analysis(
    analysis_id: str,
    format: str = Query("markdown", pattern="^(markdown|json)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export analysis as downloadable markdown or JSON."""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis or analysis.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Analysis not ready for export")

    if format == "json":
        data = {
            "business_problem": analysis.business_problem,
            "architecture_model": analysis.architecture_model,
            "requirements": analysis.requirements,
            "architecture_design": analysis.architecture_design,
            "database_schema": analysis.database_schema,
            "api_specification": analysis.api_specification,
            "deployment_config": analysis.deployment_config,
            "security_audit": analysis.security_audit,
            "performance_strategies": analysis.performance_strategies,
        }
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=mosaic-export-{analysis_id}.json"},
        )

    arch = analysis.architecture_design or {}
    reqs = analysis.requirements or {}
    db_schema = analysis.database_schema or {}
    api = analysis.api_specification or {}
    dep = analysis.deployment_config or {}
    sec = analysis.security_audit or {}

    md = f"""# Mosaic Studio - Architecture Design Report
Generated for: {analysis.business_problem}
Analysis ID: {analysis_id}
Status: Completed in {analysis.analysis_time_seconds}s

## 1. System Requirements
### Functional
"""
    for r in reqs.get("functional", []):
        md += f"- {r}\n"
    md += "\n### Non-Functional\n"
    for r in reqs.get("non_functional", []):
        md += f"- {r}\n"

    md += f"\n## 2. Architecture & Design Pattern\n**System Type:** {arch.get('system_type', 'N/A')}\n**Pattern:** {arch.get('pattern', 'N/A')}\n\n### Justification\n{arch.get('justification', '')}\n\n### Components\n"
    for comp in arch.get("components", []):
        md += f"- **{comp.get('name')}:** {comp.get('description')} *(Stack: {comp.get('technology')})*\n"

    md += f"\n## 3. Database Design\n**Database Type:** {db_schema.get('database_type', 'N/A')}\n\n### Schemas\n"
    for sc in db_schema.get("schemas", []):
        md += f"#### Table: {sc.get('table_name')}\n```sql\n{sc.get('sql')}\n```\n"

    md += f"\n## 4. API Specification\n**Protocol:** {api.get('protocol', 'N/A')}\n\n"
    for ep in api.get("endpoints", []):
        md += f"### `{ep.get('method')}` {ep.get('path')}\n*{ep.get('description')}*\n\n"

    md += f"## 5. Infrastructure & Deployment\n**IaC Tool:** {dep.get('infrastructure_as_code', 'N/A')}\n**Orchestrator:** {dep.get('orchestration', 'N/A')}\n\n### Terraform Template\n```hcl\n{dep.get('terraform_sample', '')}\n```\n\n### Kubernetes Manifest\n```yaml\n{dep.get('kubernetes_manifest', '')}\n```\n"

    md += f"\n## 6. Security\n**Auth Strategy:** {sec.get('authentication_strategy', 'N/A')}\n**Compliance:** {sec.get('compliance', 'N/A')}\n\n### Mitigations\n"
    for v in (analysis.security_audit or {}).get("vulnerability_mitigations", []):
        if isinstance(v, dict):
            md += f"- {v.get('vulnerability', '')}: {v.get('mitigation', '')}\n"
        else:
            md += f"- {v}\n"

    review = (analysis.architecture_model or {}).get("review") or {}
    if review:
        md += f"\n## 7. Architecture Review\n**Overall Score:** {review.get('overall_score', 'N/A')}/100\n"
        if review.get("critical_issues"):
            md += "### Critical Issues\n"
            for i in review.get("critical_issues", []):
                md += f"- {i}\n"
        if review.get("recommendations"):
            md += "### Recommendations\n"
            for r in review.get("recommendations", []):
                md += f"- {r}\n"

    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=mosaic-export-{analysis_id}.md"},
    )


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an analysis."""
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found.")

    db.delete(analysis)
    db.commit()
