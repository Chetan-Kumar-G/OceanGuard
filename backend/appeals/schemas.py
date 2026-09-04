"""Pydantic models for the appeals API."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

from shared.validation import validate_email_format

AppealSubject = Literal["detection", "source_hypothesis", "candidate_vessel", "other"]
AppealStatus = Literal["open", "reviewing", "upheld", "dismissed"]


class AppealSubmission(BaseModel):
    """Public, unauthenticated submission - the whole point is no account is required."""
    event_id: str = Field(..., pattern=r"^EVT\d{4}$")
    subject: AppealSubject
    mmsi: Optional[str] = Field(None, description="Vessel MMSI, if disputing a candidate-vessel flag")
    contact_name: str = Field(..., min_length=1, max_length=200)
    contact_email: str
    statement: str = Field(..., min_length=10, max_length=4000, description="Why this is a false positive")

    _validate_email = field_validator("contact_email")(validate_email_format)


class AppealHistoryEntry(BaseModel):
    status: AppealStatus
    notes: Optional[str] = None
    reviewer_display_name: Optional[str] = None
    timestamp: str


class AppealOut(BaseModel):
    id: str
    event_id: str
    subject: AppealSubject
    mmsi: Optional[str] = None
    contact_name: str
    contact_email: str
    statement: str
    status: AppealStatus
    submitted_at: str
    history: list[AppealHistoryEntry] = Field(default_factory=list)


class AppealReviewRequest(BaseModel):
    status: AppealStatus
    notes: Optional[str] = Field(None, max_length=2000)
