from __future__ import annotations


def _submit(client, **overrides):
    body = {
        "event_id": "EVT0002",
        "subject": "candidate_vessel",
        "mmsi": "480469227",
        "contact_name": "Capt. Smith",
        "contact_email": "capt@ship.example",
        "statement": "We were docked the entire time; AIS logs attached separately for review.",
        **overrides,
    }
    return client.post("/appeals", json=body)


def test_submit_appeal_requires_no_auth(client):
    r = _submit(client)
    assert r.status_code == 201
    assert r.json()["status"] == "open"
    assert len(r.json()["history"]) == 1


def test_submit_appeal_rejects_bad_event_id(client):
    r = _submit(client, event_id="not-an-event")
    assert r.status_code == 422


def test_submit_appeal_rejects_short_statement(client):
    r = _submit(client, statement="too short")
    assert r.status_code == 422


def test_submit_appeal_rejects_bad_email(client):
    r = _submit(client, contact_email="not-an-email")
    assert r.status_code == 422


def test_list_appeals_requires_authentication(client):
    _submit(client)
    assert client.get("/appeals").status_code == 401


def test_list_appeals_as_investigator(client, investigator_token):
    _submit(client)
    _submit(client, event_id="EVT0003")
    r = client.get("/appeals", headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_appeals_filters_by_event(client, investigator_token):
    _submit(client, event_id="EVT0002")
    _submit(client, event_id="EVT0003")
    r = client.get("/appeals", params={"event_id": "EVT0003"}, headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["event_id"] == "EVT0003"


def test_get_single_appeal(client, investigator_token):
    appeal_id = _submit(client).json()["id"]
    r = client.get(f"/appeals/{appeal_id}", headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 200
    assert r.json()["id"] == appeal_id


def test_get_unknown_appeal_404s(client, investigator_token):
    r = client.get("/appeals/does-not-exist", headers={"Authorization": f"Bearer {investigator_token}"})
    assert r.status_code == 404


def test_review_requires_authentication(client):
    appeal_id = _submit(client).json()["id"]
    r = client.patch(f"/appeals/{appeal_id}/review", json={"status": "dismissed"})
    assert r.status_code == 401


def test_review_appends_history_without_losing_the_original_submission(client, investigator_token):
    appeal_id = _submit(client).json()["id"]
    headers = {"Authorization": f"Bearer {investigator_token}"}

    r = client.patch(f"/appeals/{appeal_id}/review", json={"status": "reviewing", "notes": "Checking AIS logs."}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "reviewing"
    assert len(r.json()["history"]) == 2

    r = client.patch(f"/appeals/{appeal_id}/review", json={"status": "dismissed", "notes": "AIS confirms vessel in port."}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"
    history = r.json()["history"]
    assert len(history) == 3
    # every prior decision is preserved, in order - nothing overwritten.
    assert [h["status"] for h in history] == ["open", "reviewing", "dismissed"]
    assert history[0]["notes"] == "Appeal submitted."


def test_review_records_reviewer_name(client, investigator_token):
    appeal_id = _submit(client).json()["id"]
    r = client.patch(
        f"/appeals/{appeal_id}/review",
        json={"status": "upheld", "notes": "Confirmed false positive."},
        headers={"Authorization": f"Bearer {investigator_token}"},
    )
    assert r.json()["history"][-1]["reviewer_display_name"] == "Inv"
