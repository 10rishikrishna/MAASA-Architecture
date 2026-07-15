# backend/routers/projects_router.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, Project, generate_uuid
from backend.auth import get_current_user
from backend.database import User

router = APIRouter(prefix="/projects", tags=["Projects"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    visibility: Optional[str] = "private"

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    visibility: Optional[str] = None
    analysis_ids: Optional[List[str]] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    tags: Optional[List[str]]
    visibility: str
    analysis_ids: Optional[List[str]]
    created_at: str
    updated_at: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new project to group analyses."""
    project = Project(
        id=generate_uuid(),
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags or [],
        visibility=payload.visibility or "private",
        analysis_ids=[],
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    """List all projects owned by the current user."""
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_to_response(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific project by ID."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return _to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: UpdateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a project's metadata or add/remove analyses."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.tags is not None:
        project.tags = payload.tags
    if payload.visibility is not None:
        project.visibility = payload.visibility
    if payload.analysis_ids is not None:
        project.analysis_ids = payload.analysis_ids

    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a project. Does NOT delete the linked analyses."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    db.delete(project)
    db.commit()


# ── Helper ───────────────────────────────────────────────────────────────────

def _to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        tags=p.tags or [],
        visibility=p.visibility,
        analysis_ids=p.analysis_ids or [],
        created_at=str(p.created_at),
        updated_at=str(p.updated_at),
    )
