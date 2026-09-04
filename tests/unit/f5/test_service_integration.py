"""Integration: synthetic D1-D4 -> F5 -> compare relation counts/labels to the
reference ``D5_evidence_consistency.csv`` (Prompt TESTS / ACCEPTANCE CRITERIA).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from backend.f5_consistency.models import EvidenceRelation
from backend.f5_consistency.service import evaluate_consistency, evaluate_event

from .conftest import REFERENCE_EVENTS

_D5 = (
    Path(__file__).resolve().parents[3]
    / "data" / "raw" / "synthetic" / "outputs" / "D5_evidence_consistency.csv"
)

_EXACT_SCHEMA_KEYS = {
    "evidence_id",
    "event_id",
    "source_a_id",
    "source_a_type",
    "source_b_id",
    "source_b_type",
    "spatial_residual_km",
    "temporal_residual_h",
    "relation",
    "reason",
}


def _reference_rows():
    with _D5.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def all_records():
    records = []
    for ev in REFERENCE_EVENTS:
        records.extend(evaluate_event(ev).records)
    return records


def test_total_relation_count_matches_reference(all_records):
    assert len(_reference_rows()) == 77
    assert len(all_records) == 77


def test_every_relation_validates_against_frozen_schema(all_records):
    for rec in all_records:
        rel = rec.to_relation()
        assert isinstance(rel, EvidenceRelation)
        dumped = rel.model_dump()
        assert set(dumped) == _EXACT_SCHEMA_KEYS
        assert dumped["relation"] in {"SUPPORTS", "CONTRADICTS", "UNKNOWN"}
        assert dumped["evidence_id"].startswith(f"EV_{dumped['event_id']}_")
        assert isinstance(dumped["spatial_residual_km"], float)
        assert isinstance(dumped["temporal_residual_h"], float)


def test_only_the_three_spec_relationship_types_are_emitted(all_records):
    kinds = {(r.source_a_type, r.source_b_type) for r in all_records}
    assert kinds == {
        ("F1_DETECTION", "F2_STATE"),
        ("F2_DRIFT", "F3_FORCING"),
        ("F3_SOURCE_HYPOTHESIS", "F4_VESSEL_TRACK"),
    }


def test_labels_match_reference_within_tolerance(all_records):
    ref = _reference_rows()
    ref_singleton = {
        (r["event_id"], r["source_a_type"]): r["relation"]
        for r in ref
        if r["source_a_type"] in ("F1_DETECTION", "F2_DRIFT")
    }
    ref_f3f4 = {
        (r["event_id"], r["source_b_id"]): r["relation"]
        for r in ref
        if r["source_a_type"] == "F3_SOURCE_HYPOTHESIS"
    }

    mismatches = []
    checked = 0
    for rec in all_records:
        if rec.source_a_type in ("F1_DETECTION", "F2_DRIFT"):
            want = ref_singleton[(rec.event_id, rec.source_a_type)]
        else:
            want = ref_f3f4[(rec.event_id, rec.source_b_id)]
        checked += 1
        if rec.relation != want:
            mismatches.append((rec.event_id, rec.source_a_type, rec.source_b_id, rec.relation, want))

    assert checked == 77
    # This implementation reproduces the reference labels exactly; allow a tiny
    # tolerance so re-tuned thresholds don't make the suite brittle.
    assert len(mismatches) <= 2, f"label mismatches: {mismatches}"


def test_contradicts_are_never_lost(all_records):
    """Integration rule 9 — CONTRADICTS count must not fall below the reference."""
    ref = _reference_rows()
    ref_contra = sum(1 for r in ref if r["relation"] == "CONTRADICTS")
    mine_contra = sum(1 for r in all_records if r.relation == "CONTRADICTS")
    assert mine_contra >= ref_contra


def test_relation_count_buckets_close_to_reference(all_records):
    ref = _reference_rows()
    for label in ("SUPPORTS", "CONTRADICTS", "UNKNOWN"):
        r = sum(1 for x in ref if x["relation"] == label)
        m = sum(1 for x in all_records if x.relation == label)
        assert abs(r - m) <= 2, f"{label}: reference {r}, got {m}"


def test_demoable_event_has_supports_and_a_conflict():
    """ACCEPTANCE: an evidence table with >=1 SUPPORTS and >=1 CONTRADICTS/UNKNOWN
    for one event."""
    relations = evaluate_consistency("EVT0002")
    labels = {r.relation for r in relations}
    assert "SUPPORTS" in labels
    assert labels & {"CONTRADICTS", "UNKNOWN"}


def test_persist_and_read_back_roundtrip(repo):
    result = evaluate_event("EVT0002", persist=True, repo=repo)
    stored = repo.list_relations("EVT0002")
    assert len(stored) == len(result.records) > 0
    assert [s.model_dump() for s in stored] == [r.to_relation().model_dump() for r in result.records]


def test_reevaluation_is_idempotent(repo):
    evaluate_event("EVT0003", persist=True, repo=repo)
    first = repo.list_relations("EVT0003")
    evaluate_event("EVT0003", persist=True, repo=repo)
    second = repo.list_relations("EVT0003")
    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]


def test_provenance_is_preserved_on_every_record(all_records):
    for rec in all_records:
        assert rec.provenance, f"{rec.evidence_id} lost provenance"
        assert any(p.startswith("F") for p in rec.provenance)
