# backend/routers/shares_router.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, Project, ProjectShare, User, generate_uuid
from backend.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["Project Sharing"])


class CreateShareRequest(BaseModel):
    email: str
    permission: str = "view"


class UpdateShareRequest(BaseModel):
    permission: str


class ShareResponse(BaseModel):
    id: str
    project_id: str
    shared_with_email: str
    permission: str
    created_at: str


def _to_response(s: ProjectShare, email: str) -> ShareResponse:
    return ShareResponse(
        id=s.id,
        project_id=s.project_id,
        shared_with_email=email,
        permission=s.permission,
        created_at=str(s.created_at),
    )


@router.post("/{project_id}/shares", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
def create_share(
    project_id: str,
    payload: CreateShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with yourself.")

    existing = db.query(ProjectShare).filter(
        ProjectShare.project_id == project_id,
        ProjectShare.shared_with_user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already shared with this user.")

    share = ProjectShare(
        id=generate_uuid(),
        project_id=project_id,
        shared_with_user_id=user.id,
        permission=payload.permission,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _to_response(share, user.email)


@router.get("/{project_id}/shares", response_model=List[ShareResponse])
def list_shares(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    shares = db.query(ProjectShare).filter(ProjectShare.project_id == project_id).all()
    result = []
    for s in shares:
        user = db.query(User).filter(User.id == s.shared_with_user_id).first()
        if user:
            result.append(_to_response(s, user.email))
    return result


@router.patch("/{project_id}/shares/{share_id}", response_model=ShareResponse)
def update_share(
    project_id: str,
    share_id: str,
    payload: UpdateShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    share = db.query(ProjectShare).filter(
        ProjectShare.id == share_id,
        ProjectShare.project_id == project_id,
    ).first()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found.")

    share.permission = payload.permission
    db.commit()
    db.refresh(share)

    user = db.query(User).filter(User.id == share.shared_with_user_id).first()
    return _to_response(share, user.email if user else "unknown")


@router.delete("/{project_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    project_id: str,
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    share = db.query(ProjectShare).filter(
        ProjectShare.id == share_id,
        ProjectShare.project_id == project_id,
    ).first()
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found.")

    db.delete(share)
    db.commit()
