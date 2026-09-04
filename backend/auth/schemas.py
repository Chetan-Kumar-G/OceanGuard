"""Pydantic request/response models for the auth API."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator

from shared.validation import validate_email_format

Role = Literal["investigator", "admin"]


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=120)

    _validate_email = field_validator("email")(validate_email_format)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordResetRequest(BaseModel):
    email: str
    _validate_email = field_validator("email")(validate_email_format)


class PasswordResetRequestResponse(BaseModel):
    message: str
    dev_reset_token: str | None = Field(
        None,
        description="Returned only because no email service is configured. "
        "In a real deployment this token is emailed to the user, never returned in the API response.",
    )


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class RoleUpdateRequest(BaseModel):
    role: Role
