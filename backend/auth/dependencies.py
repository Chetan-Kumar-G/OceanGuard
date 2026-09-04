"""FastAPI dependencies enforcing authentication and role checks."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend.auth.repository import AuthRepository, UserRecord, get_auth_repository
from backend.auth.schemas import UserOut
from backend.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def to_user_out(u: UserRecord) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, display_name=u.display_name, role=u.role,  # type: ignore[arg-type]
        is_active=u.is_active, created_at=u.created_at,
    )


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    repo: AuthRepository = Depends(get_auth_repository),
) -> UserOut:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "NOT_AUTHENTICATED", "message": "Sign in to access the investigation API."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    payload = decode_access_token(token)
    if not payload:
        raise unauthorized
    user = repo.get_user_by_id(payload.get("sub", ""))
    if user is None or not user.is_active:
        raise unauthorized
    return to_user_out(user)


def require_role(*roles: str):
    def _check(user: UserOut = Depends(get_current_user)) -> UserOut:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"Requires role in {roles}, got {user.role!r}."},
            )
        return user

    return _check
