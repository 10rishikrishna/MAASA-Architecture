# backend/routers/projects.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.database import get_db, User, Project, Analysis, ProjectShare
from backend.auth import get_current_user

router = APIRouter(prefix="/api/v1/projects", tags=["Project Portfolio"])

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    analysis_id: str
    tags: List[str] = []
    visibility: str = "private"  # private or public

class ProjectUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = []
    visibility: str = "private"

class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    analysis_ids: List[str]
    tags: List[str]
    visibility: str
    created_at: str

@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify analysis exists and belongs to user
    analysis = db.query(Analysis).filter(
        Analysis.id == payload.analysis_id,
        Analysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Associated architecture analysis not found")
        
    db_project = Project(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        analysis_ids=[payload.analysis_id],
        tags=payload.tags,
        visibility=payload.visibility
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return {
        "project_id": db_project.id,
        "name": db_project.name,
        "created_at": db_project.created_at.isoformat()
    }

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    filter: str = Query("all", regex="^(all|mine|shared)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Project)
    if filter == "mine" or filter == "all":
        query = query.filter(Project.user_id == current_user.id)
    # Extensible for team sharing query later
    
    projects = query.order_by(Project.created_at.desc()).all()
    
    return [
        ProjectResponse(
            project_id=p.id,
            name=p.name,
            description=p.description,
            analysis_ids=p.analysis_ids or [],
            tags=p.tags or [],
            visibility=p.visibility,
            created_at=p.created_at.isoformat()
        ) for p in projects
    ]

@router.get("/{project_id}")
def get_project_details(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Check authorization (if private, must be owner)
    if project.visibility == "private" and project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this project")
        
    # Load analysis details
    analyses = []
    for aid in (project.analysis_ids or []):
        an = db.query(Analysis).filter(Analysis.id == aid).first()
        if an:
            analyses.append({
                "analysis_id": an.id,
                "business_problem": an.business_problem,
                "requirements": an.requirements,
                "architecture_design": an.architecture_design,
                "database_schema": an.database_schema,
                "api_specification": an.api_specification,
                "deployment_config": an.deployment_config,
                "security_audit": an.security_audit,
                "performance_strategies": an.performance_strategies,
                "diagrams": an.diagrams,
                "status": an.status,
                "created_at": an.created_at.isoformat()
            })
            
    return {
        "project_id": project.id,
        "name": project.name,
        "description": project.description,
        "tags": project.tags or [],
        "visibility": project.visibility,
        "created_at": project.created_at.isoformat(),
        "analyses": analyses
    }

@router.put("/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    project.name = payload.name
    project.description = payload.description
    project.tags = payload.tags
    project.visibility = payload.visibility
    project.updated_at = datetime.utcnow()
    
    db.commit()
    return {"success": True, "message": "Project updated successfully"}

@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db.delete(project)
    db.commit()
    return {"success": True, "message": "Project deleted successfully"}
