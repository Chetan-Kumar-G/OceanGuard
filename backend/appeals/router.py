"""Appeals API.

    POST /appeals             - PUBLIC, no auth. Submit a false-positive dispute.
    GET  /appeals              - investigator+. Review queue, filterable.
    GET  /appeals/{id}         - investigator+. One appeal with full history.
    PATCH /appeals/{id}/review - investigator+. Append a status decision (never overwrites).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user, require_role
from backend.auth.schemas import UserOut
from backend.appeals.repository import AppealsRepository, get_appeals_repository
from backend.appeals.schemas import AppealOut, AppealReviewRequest, AppealSubmission

router = APIRouter(tags=["Appeals"])


@router.post("/appeals", response_model=AppealOut, status_code=status.HTTP_201_CREATED, summary="Submit a false-positive dispute (public, no account needed)")
def submit_appeal(body: AppealSubmission, repo: AppealsRepository = Depends(get_appeals_repository)):
    appeal_id = repo.submit(
        event_id=body.event_id, subject=body.subject, mmsi=body.mmsi,
        contact_name=body.contact_name, contact_email=body.contact_email, statement=body.statement,
    )
    return repo.get(appeal_id)


@router.get("/appeals", response_model=list[AppealOut], summary="Review queue (investigator+)")
def list_appeals(
    event_id: Optional[str] = None,
    status: Optional[str] = None,  # noqa: A002 - matches the field name
    _: UserOut = Depends(require_role("investigator", "admin")),
    repo: AppealsRepository = Depends(get_appeals_repository),
):
    return repo.list(event_id=event_id, status=status)


@router.get("/appeals/{appeal_id}", response_model=AppealOut, summary="One appeal with full review history (investigator+)")
def get_appeal(
    appeal_id: str,
    _: UserOut = Depends(require_role("investigator", "admin")),
    repo: AppealsRepository = Depends(get_appeals_repository),
):
    result = repo.get(appeal_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "APPEAL_NOT_FOUND", "message": f"No appeal {appeal_id!r}."})
    return result


@router.patch("/appeals/{appeal_id}/review", response_model=AppealOut, summary="Record a review decision (investigator+, appends - never overwrites)")
def review_appeal(
    appeal_id: str,
    body: AppealReviewRequest,
    current: UserOut = Depends(require_role("investigator", "admin")),
    repo: AppealsRepository = Depends(get_appeals_repository),
):
    result = repo.review(appeal_id, status=body.status, notes=body.notes, reviewer_display_name=current.display_name)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "APPEAL_NOT_FOUND", "message": f"No appeal {appeal_id!r}."})
    return result
