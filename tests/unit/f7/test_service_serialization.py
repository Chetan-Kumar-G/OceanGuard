"""Regression tests for a NaN-vs-None pandas/pydantic interop bug in
``get_graph_response``: a nullable column (e.g. ``timestamp`` on an
ENVIRONMENTAL_STATE node, which is always ``None``) can come back from
pandas as a float ``NaN`` instead of Python ``None`` - reliably so via
``pd.read_sql`` (SQL NULL -> NaN), and in some pandas versions even for a
plain ``pd.DataFrame([{...}])`` build. ``NodeSchema``/``EdgeSchema`` declare
those fields ``Optional[str]``, which accepts ``None`` but not a bare float,
so an un-sanitized NaN raised ``pydantic_core.ValidationError`` and turned
``GET /events/{id}/graph`` into a 500 for every event.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.f7_graph.service import _records_with_nan_as_none, get_graph_response
from shared.schemas.envelope import EdgeSchema, NodeSchema


def test_records_with_nan_as_none_replaces_float_nan():
    df = pd.DataFrame([
        {"node_id": "A", "timestamp": float("nan"), "latitude": None, "confidence": 0.5},
    ])
    assert df["timestamp"].dtype == float  # confirms the scenario actually forces NaN, not None

    records = _records_with_nan_as_none(df)
    assert records == [{"node_id": "A", "timestamp": None, "latitude": None, "confidence": 0.5}]


def test_records_with_nan_as_none_on_empty_df_returns_empty_list():
    assert _records_with_nan_as_none(pd.DataFrame()) == []


def test_records_with_nan_as_none_leaves_real_values_untouched():
    df = pd.DataFrame([{"a": "x", "b": 1.5, "c": True, "d": None}])
    assert _records_with_nan_as_none(df) == [{"a": "x", "b": 1.5, "c": True, "d": None}]


def test_node_schema_construction_would_crash_without_the_fix():
    """Documents the exact bug: NodeSchema(**row) on an un-sanitized NaN row
    raises - this is what get_graph_response must never do."""
    bad_row = {
        "node_id": "EVT0001-ENV", "event_id": "EVT0001", "node_type": "ENVIRONMENTAL_STATE",
        "timestamp": float("nan"), "latitude": None, "longitude": None,
        "confidence": None, "uncertainty": None, "provenance": "x",
    }
    with pytest.raises(Exception):  # pydantic ValidationError
        NodeSchema(**bad_row)

    # ... but the sanitized version constructs fine.
    df = pd.DataFrame([bad_row])
    node = NodeSchema(**_records_with_nan_as_none(df)[0])
    assert node.timestamp is None


@pytest.mark.parametrize("event_id", ["EVT0001", "EVT0002", "EVT0006", "EVT0010"])
def test_get_graph_response_does_not_crash_for_any_event(event_id):
    """These are the exact events reported crashing with a NaN ValidationError."""
    envelope = get_graph_response(event_id, engine=None, data_root=None)
    assert envelope.success is True
    assert envelope.data.node_count > 0
    for node in envelope.data.nodes:
        assert node.timestamp is None or isinstance(node.timestamp, str)
        for field in (node.latitude, node.longitude, node.confidence, node.uncertainty):
            assert field is None or (isinstance(field, float) and not math.isnan(field))
