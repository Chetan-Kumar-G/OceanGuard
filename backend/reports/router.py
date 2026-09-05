"""Report API — investigator-only PDF export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from backend.auth.dependencies import get_current_user
from backend.auth.schemas import UserOut
from backend.reports.pdf_builder import build_vessel_report_pdf

router = APIRouter(tags=["Reports"])


@router.get(
    "/api/v1/reports/{event_id}/vessels.pdf",
    summary="Candidate vessel PDF report — rank, score, and the evidence behind each vessel",
)
def get_vessel_report(event_id: str, current: UserOut = Depends(get_current_user)):
    try:
        pdf_bytes = build_vessel_report_pdf(event_id, generated_by=current.display_name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REPORT_GENERATION_FAILED", "message": str(e)},
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="oceanguard-{event_id}-vessel-report.pdf"'},
    )
