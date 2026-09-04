from __future__ import annotations


def _register(client, email, password="supersecret1", name="Test User"):
    return client.post("/auth/register", json={"email": email, "password": password, "display_name": name})


def test_first_registered_user_becomes_admin(client):
    r = _register(client, "first@investigators.example")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "admin"


def test_second_registered_user_is_investigator(client):
    _register(client, "first@investigators.example")
    r = _register(client, "second@investigators.example")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "investigator"


def test_cannot_register_duplicate_email(client):
    _register(client, "dup@investigators.example")
    r = _register(client, "dup@investigators.example")
    assert r.status_code == 409


def test_register_rejects_malformed_email(client):
    r = _register(client, "not-an-email")
    assert r.status_code == 422


def test_register_rejects_short_password(client):
    r = client.post("/auth/register", json={"email": "a@investigators.example", "password": "short", "display_name": "A"})
    assert r.status_code == 422


def test_login_with_correct_credentials(client):
    _register(client, "user@investigators.example", password="supersecret1")
    r = client.post("/auth/login", data={"username": "user@investigators.example", "password": "supersecret1"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    _register(client, "user@investigators.example", password="supersecret1")
    r = client.post("/auth/login", data={"username": "user@investigators.example", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_email_is_rejected(client):
    r = client.post("/auth/login", data={"username": "ghost@investigators.example", "password": "whatever1"})
    assert r.status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client):
    token = _register(client, "user@investigators.example").json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "user@investigators.example"


def test_admin_can_promote_another_user(client):
    admin_token = _register(client, "admin@investigators.example").json()["access_token"]
    inv = _register(client, "inv@investigators.example").json()["user"]
    assert inv["role"] == "investigator"

    r = client.patch(f"/admin/users/{inv['id']}/role", json={"role": "admin"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_non_admin_cannot_list_users(client):
    _register(client, "admin@investigators.example")
    inv_token = _register(client, "inv@investigators.example").json()["access_token"]
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {inv_token}"})
    assert r.status_code == 403


def test_password_reset_flow(client):
    _register(client, "user@investigators.example", password="original-pass1")

    req = client.post("/auth/password-reset/request", json={"email": "user@investigators.example"})
    assert req.status_code == 200
    token = req.json()["dev_reset_token"]
    assert token

    confirm = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "brand-new-pass1"})
    assert confirm.status_code == 200

    old_login = client.post("/auth/login", data={"username": "user@investigators.example", "password": "original-pass1"})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", data={"username": "user@investigators.example", "password": "brand-new-pass1"})
    assert new_login.status_code == 200


def test_password_reset_request_does_not_leak_account_existence(client):
    r = client.post("/auth/password-reset/request", json={"email": "nobody@investigators.example"})
    assert r.status_code == 200
    assert r.json()["dev_reset_token"] is None


def test_password_reset_token_is_single_use(client):
    _register(client, "user@investigators.example", password="original-pass1")
    token = client.post("/auth/password-reset/request", json={"email": "user@investigators.example"}).json()["dev_reset_token"]

    first = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "second-pass1"})
    assert first.status_code == 200
    second = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "third-pass1"})
    assert second.status_code == 400
