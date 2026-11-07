from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

DBSession = Annotated[Session, Depends(get_db)]


def require_admin(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str:
    """MVP: API key tunggal untuk admin. Ganti dengan JWT + RBAC sebelum produksi."""
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key tidak valid",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return "admin"


AdminUser = Annotated[str, Depends(require_admin)]