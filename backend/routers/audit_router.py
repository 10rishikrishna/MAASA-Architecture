# backend/routers/audit_router.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, AuditLog, User
from backend.auth import get_current_user

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


class AuditLogResponse(BaseModel):
    id: str
    user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    ip_address: str | None
    created_at: str


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = Query(None),
):
    """List audit logs for the current user. Admin users can see all logs."""
    query = db.query(AuditLog)

    if current_user.plan != "enterprise":
        query = query.filter(AuditLog.user_id == current_user.id)
    elif action:
        query = query.filter(AuditLog.action == action)

    logs = (
        query.order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=str(log.created_at),
        )
        for log in logs
    ]
