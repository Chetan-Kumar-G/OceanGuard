"""
Unit tests for F2 router.py (FastAPI)

Covers:
- POST /f2/reconstruct/{event_id} returns 200 with TemporalProgressionResult
- GET /events/{event_id}/states returns 200 with list of states
- GET /events/{event_id}/states?observed_only=true returns only is_observed=True states
- GET /events/{event_id}/states?state_type=PREDICTED returns only predicted states
- Invalid state_type returns 422
- Unknown event_id returns 404
"""
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)

VALID_EVENT = "EVT0001"   # present in D1_satellite_scenes.csv
MISSING_EVENT = "EVT9999"  # not in any CSV


class TestF2ReconstructEndpoint:
    def test_reconstruct_returns_200(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        assert resp.status_code == 200, resp.text

    def test_reconstruct_response_has_data_and_meta(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert "run_id" in body["meta"]

    def test_reconstruct_data_has_expected_fields(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        data = resp.json()["data"]
        assert "event_id" in data
        assert "total_states" in data
        assert "observed_count" in data
        assert "interpolated_count" in data
        assert "predicted_count" in data
        assert "states" in data
        assert "insufficient_temporal_data" in data

    def test_reconstruct_states_all_have_observation_id(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        states = resp.json()["data"]["states"]
        assert len(states) > 0
        for s in states:
            assert "observation_id" in s
            assert s["observation_id"].startswith("OBS_")

    def test_reconstruct_no_nonobserved_state_with_is_observed_true(self):
        """Critical: INTERPOLATED/PREDICTED must never have is_observed=True."""
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        states = resp.json()["data"]["states"]
        for s in states:
            if s["state_type"] in ("INTERPOLATED", "PREDICTED"):
                assert s["is_observed"] is False, (
                    f"State {s['observation_id']} is {s['state_type']} but has is_observed=True"
                )

    def test_reconstruct_missing_event_returns_404(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{MISSING_EVENT}")
        assert resp.status_code == 404

    def test_reconstruct_counts_add_up(self):
        resp = client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")
        data = resp.json()["data"]
        total = data["total_states"]
        summed = data["observed_count"] + data["interpolated_count"] + data["predicted_count"]
        assert total == summed


class TestF2StatesEndpoint:
    def setup_method(self):
        # Pre-populate the store via reconstruct
        client.post(f"/api/v1/f2/reconstruct/{VALID_EVENT}")

    def test_list_states_returns_200(self):
        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states")
        assert resp.status_code == 200

    def test_list_states_has_data_list(self):
        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states")
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    def test_observed_only_filter(self):
        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states?observed_only=true")
        data = resp.json()["data"]
        assert all(s["is_observed"] is True for s in data), \
            "observed_only=true must return only is_observed=True states"
        assert all(s["state_type"] == "OBSERVED" for s in data)

    def test_state_type_filter_predicted(self):
        # First get all states to check if predicted exist
        all_resp = client.get(f"/api/v1/events/{VALID_EVENT}/states")
        all_states = all_resp.json()["data"]
        n_predicted = sum(1 for s in all_states if s["state_type"] == "PREDICTED")

        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states?state_type=PREDICTED")
        data = resp.json()["data"]
        assert len(data) == n_predicted
        assert all(s["state_type"] == "PREDICTED" for s in data)

    def test_state_type_filter_interpolated(self):
        all_resp = client.get(f"/api/v1/events/{VALID_EVENT}/states")
        all_states = all_resp.json()["data"]
        n_interp = sum(1 for s in all_states if s["state_type"] == "INTERPOLATED")

        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states?state_type=INTERPOLATED")
        data = resp.json()["data"]
        assert len(data) == n_interp

    def test_invalid_state_type_returns_422(self):
        resp = client.get(f"/api/v1/events/{VALID_EVENT}/states?state_type=INVALID")
        assert resp.status_code == 422

    def test_missing_event_returns_404(self):
        resp = client.get(f"/api/v1/events/{MISSING_EVENT}/states")
        assert resp.status_code == 404
