"""Tests for the candidate-vessel PDF report generator."""
from __future__ import annotations

import io
import re

import pytest
from pypdf import PdfReader

from backend.f5_consistency.service import evaluate_consistency
from backend.f6_ranking.service import rank_event
from backend.reports.pdf_builder import build_vessel_report_pdf

REFERENCE_EVENTS = [f"EVT{n:04d}" for n in range(1, 13)]


def _text(pdf_bytes: bytes) -> str:
    """Extracted text with whitespace normalized to single spaces - reportlab
    wraps Paragraph text across lines, so a raw newline can land in the
    middle of a phrase a test wants to match as one substring."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", raw)


@pytest.mark.parametrize("event_id", REFERENCE_EVENTS)
def test_report_generates_a_valid_pdf_for_every_reference_event(event_id):
    """Must never crash - including EVT0001, which has only one OBSERVED
    state and typically insufficient evidence for any candidate."""
    pdf_bytes = build_vessel_report_pdf(event_id)
    assert pdf_bytes.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    assert event_id in _text(pdf_bytes)


def test_report_includes_generated_by_byline():
    with_byline = _text(build_vessel_report_pdf("EVT0002", generated_by="Ava Investigator"))
    without_byline = _text(build_vessel_report_pdf("EVT0002", generated_by=None))
    assert "Ava Investigator" in with_byline
    assert "Ava Investigator" not in without_byline


def test_report_for_unknown_event_does_not_crash():
    """No candidates, no source hypothesis, no observations - should render
    a report saying so, not raise."""
    text = _text(build_vessel_report_pdf("EVT9999"))
    assert "No candidate vessels" in text or "No observed satellite passes" in text


def test_report_lists_every_ranked_candidate_mmsi_and_rank():
    ranking = rank_event("EVT0002")
    text = _text(build_vessel_report_pdf("EVT0002"))
    assert ranking.n_candidates >= 1
    for c in ranking.candidates:
        assert c.candidate_mmsi in text
        assert f"Rank {c.rank}" in text
        assert c.confidence_band in text.lower() or c.confidence_band in text


def test_report_includes_the_f6_explanation_string_for_each_candidate():
    ranking = rank_event("EVT0002")
    text = _text(build_vessel_report_pdf("EVT0002"))
    for c in ranking.candidates:
        # explanation strings are long and reportlab may wrap them across
        # lines; _text() normalizes whitespace so a short fragment still matches.
        assert f"final={c.final_score:.2f}" in text


def test_report_reflects_evidence_relations_for_top_candidate():
    ranking = rank_event("EVT0002")
    relations = evaluate_consistency("EVT0002")
    top = ranking.candidates[0]
    top_relations = [r for r in relations if r.source_b_id.endswith(f"-{top.candidate_mmsi}")]
    text = _text(build_vessel_report_pdf("EVT0002"))
    for r in top_relations:
        assert r.relation in text


def test_report_flags_insufficient_evidence_when_the_dashboard_would():
    ranking = rank_event("EVT0001")
    text = _text(build_vessel_report_pdf("EVT0001"))
    if ranking.event_insufficient_evidence:
        assert "Insufficient evidence" in text
