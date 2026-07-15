# backend/routers/analyze.py
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database import get_db, User, Analysis, SessionLocal
from backend.auth import get_current_user
from backend.agents.engine import run_agent_orchestrator

router = APIRouter(prefix="/api/v1", tags=["Architecture Analysis"])

class ScaleEstimates(BaseModel):
    users: str = "100K"
    daily_requests: str = "1M"
    budget: str = "$5,000/month"

class AnalysisCreateRequest(BaseModel):
    business_problem: str
    scale_estimates: ScaleEstimates
    constraints: List[str] = []

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    created_at: str

@router.post("/analyze", status_code=status.HTTP_201_CREATED)
def trigger_analysis(
    payload: AnalysisCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Initialize a new database entry in 'processing' state
    db_analysis = Analysis(
        user_id=current_user.id,
        business_problem=payload.business_problem,
        status="processing",
        # Store input params in requirements temporarily or metadata
        requirements={
            "scale_estimates": payload.scale_estimates.model_dump(),
            "constraints": payload.constraints
        }
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    
    return {
        "analysis_id": db_analysis.id,
        "status": "processing",
        "created_at": db_analysis.created_at.isoformat()
    }

@router.get("/analyze/{analysis_id}/stream")
async def stream_analysis_progress(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    # Retrieve the analysis metadata
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    scale_estimates = {}
    constraints = []
    if analysis.requirements and "scale_estimates" in analysis.requirements:
        scale_estimates = analysis.requirements["scale_estimates"]
        constraints = analysis.requirements.get("constraints", [])
        
    # We yield the stream generator
    # To avoid thread block, we pass a SessionLocal creator to the orchestrator to update status on thread safety.
    async def sse_generator():
        generator = run_agent_orchestrator(
            business_problem=analysis.business_problem,
            scale_estimates=scale_estimates,
            constraints=constraints,
            analysis_id=analysis_id,
            db_session_factory=SessionLocal
        )
        async for item in generator:
            yield f"data: {item}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@router.get("/analyze/{analysis_id}")
def get_analysis_result(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    return {
        "analysis_id": analysis.id,
        "business_problem": analysis.business_problem,
        "requirements": analysis.requirements,
        "architecture_design": analysis.architecture_design,
        "database_schema": analysis.database_schema,
        "api_specification": analysis.api_specification,
        "deployment_config": analysis.deployment_config,
        "security_audit": analysis.security_audit,
        "performance_strategies": analysis.performance_strategies,
        "diagrams": analysis.diagrams,
        "status": analysis.status,
        "analysis_time_seconds": analysis.analysis_time_seconds,
        "created_at": analysis.created_at.isoformat()
    }

@router.get("/analyze/{analysis_id}/export")
def export_analysis(
    analysis_id: str,
    format: str = Query("markdown", regex="^(markdown|json)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id
    ).first()
    
    if not analysis or analysis.status != "completed":
        raise HTTPException(status_code=400, detail="Analysis not ready for export")
        
    if format == "json":
        data = {
            "business_problem": analysis.business_problem,
            "requirements": analysis.requirements,
            "architecture_design": analysis.architecture_design,
            "database_schema": analysis.database_schema,
            "api_specification": analysis.api_specification,
            "deployment_config": analysis.deployment_config,
            "security_audit": analysis.security_audit,
            "performance_strategies": analysis.performance_strategies
        }
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=maasa-export-{analysis_id}.json"}
        )
        
    # Markdown format
    md = f"""# MAASA Architecture Design Report
Generated for: {analysis.business_problem}
Analysis ID: {analysis_id}
Status: Completed in {analysis.analysis_time_seconds}s

## 1. System Requirements
### Functional
"""
    for req in (analysis.requirements.get("functional", []) if analysis.requirements else []):
        md += f"- {req}\n"
    md += "\n### Non-Functional\n"
    for req in (analysis.requirements.get("non_functional", []) if analysis.requirements else []):
        md += f"- {req}\n"
        
    arch = analysis.architecture_design or {}
    md += f"\n## 2. Architecture & Design Pattern\n**System Type:** {arch.get('system_type', 'N/A')}\n**Pattern:** {arch.get('pattern', 'N/A')}\n\n### Justification\n{arch.get('justification', '')}\n\n### Components\n"
    for comp in arch.get("components", []):
        md += f"- **{comp.get('name')}:** {comp.get('description')} *(Stack: {comp.get('technology')})*\n"
        
    db_schema = analysis.database_schema or {}
    md += f"\n## 3. Database Design\n**Database Type:** {db_schema.get('database_type', 'N/A')}\n\n### Schemas\n"
    for sc in db_schema.get("schemas", []):
        md += f"#### Table: {sc.get('table_name')}\n```sql\n{sc.get('sql')}\n```\n"
        
    api = analysis.api_specification or {}
    md += f"\n## 4. API Specification\n**Protocol:** {api.get('protocol', 'N/A')}\n\n"
    for ep in api.get("endpoints", []):
        md += f"### `{ep.get('method')}` {ep.get('path')}\n*{ep.get('description')}*\nRequest Body:\n```json\n{ep.get('request_body')}\n```\nResponse Body:\n```json\n{ep.get('response_body')}\n```\n\n"
        
    dep = analysis.deployment_config or {}
    md += f"## 5. Infrastructure & Deployment\n**IaC Tool:** {dep.get('infrastructure_as_code', 'N/A')}\n**Orchestrator:** {dep.get('orchestration', 'N/A')}\n\n### Terraform Template\n```hcl\n{dep.get('terraform_sample')}\n```\n\n### Kubernetes Manifest\n```yaml\n{dep.get('kubernetes_manifest')}\n```\n"
    
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=maasa-export-{analysis_id}.md"}
    )

@router.delete("/analyze/{analysis_id}")
def delete_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    db.delete(analysis)
    db.commit()
    return {"success": True, "message": "Analysis deleted successfully"}
