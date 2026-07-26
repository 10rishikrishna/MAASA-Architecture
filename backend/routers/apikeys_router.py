# backend/routers/apikeys_router.py
import secrets
import hashlib
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db, ApiKey, User, generate_uuid
from backend.auth import get_current_user

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class CreateApiKeyRequest(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_preview: str
    created_at: str
    expires_at: str | None
    last_used_at: str | None


class ApiKeyCreatedResponse(ApiKeyResponse):
    full_key: str


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _to_response(k: ApiKey, full_key: str | None = None) -> ApiKeyResponse:
    preview = full_key[:8] + "..." if full_key else k.key_hash[:12] + "..."
    return ApiKeyResponse(
        id=k.id,
        name=k.name or "Unnamed",
        key_preview=preview,
        created_at=str(k.created_at),
        expires_at=str(k.expires_at) if k.expires_at else None,
        last_used_at=str(k.last_used_at) if k.last_used_at else None,
    )


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_key = f"maasa_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)

    api_key = ApiKey(
        id=generate_uuid(),
        user_id=current_user.id,
        key_hash=key_hash,
        name=payload.name,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    resp = _to_response(api_key, raw_key)
    return ApiKeyCreatedResponse(
        id=resp.id,
        name=resp.name,
        key_preview=resp.key_preview,
        created_at=resp.created_at,
        expires_at=resp.expires_at,
        last_used_at=resp.last_used_at,
        full_key=raw_key,
    )


@router.get("", response_model=List[ApiKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).order_by(ApiKey.created_at.desc()).all()
    return [_to_response(k) for k in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id,
    ).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

    db.delete(key)
    db.commit()
