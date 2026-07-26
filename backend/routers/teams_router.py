# backend/routers/teams_router.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, Team, TeamMember, User, generate_uuid
from backend.auth import get_current_user

router = APIRouter(prefix="/teams", tags=["Teams"])


class CreateTeamRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddMemberRequest(BaseModel):
    email: str
    role: str = "member"


class UpdateMemberRoleRequest(BaseModel):
    role: str


class TeamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    member_count: int
    created_at: str
    updated_at: str


class TeamDetailResponse(TeamResponse):
    members: list


class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    joined_at: str


def _to_response(t: Team, member_count: int = 0) -> TeamResponse:
    return TeamResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        owner_id=t.owner_id,
        member_count=member_count,
        created_at=str(t.created_at),
        updated_at=str(t.updated_at),
    )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: CreateTeamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = Team(
        id=generate_uuid(),
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(team)
    db.flush()

    member = TeamMember(
        id=generate_uuid(),
        team_id=team.id,
        user_id=current_user.id,
        role="admin",
    )
    db.add(member)
    db.commit()
    db.refresh(team)
    return _to_response(team, 1)


@router.get("", response_model=List[TeamResponse])
def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).all()
    team_ids = [m.team_id for m in memberships]
    teams = db.query(Team).filter(Team.id.in_(team_ids)).order_by(Team.created_at.desc()).all()
    result = []
    for t in teams:
        count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        result.append(_to_response(t, count))
    return result


@router.get("/{team_id}", response_model=TeamDetailResponse)
def get_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this team.")

    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    member_list = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            member_list.append(MemberResponse(
                id=m.id,
                user_id=user.id,
                email=user.email,
                name=user.name,
                role=m.role,
                joined_at=str(m.joined_at),
            ))

    return TeamDetailResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        owner_id=team.owner_id,
        member_count=len(member_list),
        created_at=str(team.created_at),
        updated_at=str(team.updated_at),
        members=member_list,
    )


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: str,
    payload: UpdateTeamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id, Team.owner_id == current_user.id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found or not owner.")

    if payload.name is not None:
        team.name = payload.name
    if payload.description is not None:
        team.description = payload.description

    db.commit()
    db.refresh(team)
    count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    return _to_response(team, count)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id, Team.owner_id == current_user.id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found or not owner.")

    db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()
    db.delete(team)
    db.commit()


@router.post("/{team_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    team_id: str,
    payload: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    admin = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.role == "admin",
    ).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can add members.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member.")

    member = TeamMember(
        id=generate_uuid(),
        team_id=team_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberResponse(
        id=member.id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=member.role,
        joined_at=str(member.joined_at),
    )


@router.patch("/{team_id}/members/{user_id}", response_model=MemberResponse)
def update_member_role(
    team_id: str,
    user_id: str,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    admin = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.role == "admin",
    ).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update roles.")

    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    member.role = payload.role
    db.commit()
    db.refresh(member)

    user = db.query(User).filter(User.id == user_id).first()
    return MemberResponse(
        id=member.id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=member.role,
        joined_at=str(member.joined_at),
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    team_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_admin = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.role == "admin",
    ).first()
    is_self = user_id == current_user.id

    if not is_admin and not is_self:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")

    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    if member.role == "admin" and not is_self:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove another admin.")

    db.delete(member)
    db.commit()
