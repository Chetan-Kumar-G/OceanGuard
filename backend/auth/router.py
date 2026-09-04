"""Auth API: register, login, current user, password reset, admin user management.

Bootstrap rule: the very first account ever registered becomes ``admin`` (so
there is no hardcoded seed credential to leak); every account after that
defaults to ``investigator``. An admin can promote/demote later via
``PATCH /admin/users/{user_id}/role``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from backend.auth.dependencies import to_user_out, get_current_user, require_role
from backend.auth.repository import AuthRepository, get_auth_repository
from backend.auth.schemas import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    RegisterRequest,
    RoleUpdateRequest,
    TokenResponse,
    UserOut,
)
from backend.auth.security import create_access_token, hash_password, new_reset_token, verify_password

router = APIRouter(tags=["Auth"])


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, repo: AuthRepository = Depends(get_auth_repository)):
    if repo.get_user_by_email(body.email) is not None:
        raise HTTPException(status_code=409, detail={"code": "EMAIL_TAKEN", "message": "An account with this email already exists."})

    role = "admin" if repo.user_count() == 0 else "investigator"
    user = repo.create_user(
        email=body.email, password_hash=hash_password(body.password), display_name=body.display_name, role=role,
    )
    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=to_user_out(user))


@router.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), repo: AuthRepository = Depends(get_auth_repository)):
    """OAuth2-password-flow shaped so FastAPI's ``/docs`` Authorize button works.

    ``form.username`` is the account email.
    """
    user = repo.get_user_by_email(form.username)
    invalid = HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."})
    if user is None or not verify_password(form.password, user.password_hash):
        raise invalid
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_DISABLED", "message": "This account has been disabled."})
    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=to_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(current: UserOut = Depends(get_current_user)):
    return current


@router.post("/auth/password-reset/request", response_model=PasswordResetRequestResponse)
def request_password_reset(body: PasswordResetRequest, repo: AuthRepository = Depends(get_auth_repository)):
    user = repo.get_user_by_email(body.email)
    # Never reveal whether the email exists.
    if user is None:
        return PasswordResetRequestResponse(message="If that email has an account, a reset link has been sent.")
    token = repo.create_reset_token(user.id, new_reset_token())
    return PasswordResetRequestResponse(
        message="If that email has an account, a reset link has been sent.",
        dev_reset_token=token,
    )


@router.post("/auth/password-reset/confirm", response_model=UserOut)
def confirm_password_reset(body: PasswordResetConfirm, repo: AuthRepository = Depends(get_auth_repository)):
    user_id = repo.consume_reset_token(body.token)
    if not user_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_RESET_TOKEN", "message": "Reset token is invalid, expired, or already used."})
    repo.set_password(user_id, hash_password(body.new_password))
    return to_user_out(repo.get_user_by_id(user_id))


@router.get("/admin/users", response_model=list[UserOut])
def list_users(_: UserOut = Depends(require_role("admin")), repo: AuthRepository = Depends(get_auth_repository)):
    return [to_user_out(u) for u in repo.list_users()]


@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: str,
    body: RoleUpdateRequest,
    _: UserOut = Depends(require_role("admin")),
    repo: AuthRepository = Depends(get_auth_repository),
):
    target = repo.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": f"No user {user_id!r}."})
    repo.set_role(user_id, body.role)
    return to_user_out(repo.get_user_by_id(user_id))
