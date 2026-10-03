from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "Password123!"):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201

    return response.json()


def login_user(email: str, password: str = "Password123!"):
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def auth_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
    }


def test_user_can_create_and_read_own_notebook():
    email = "notebook_owner@test.com"

    register_user(email)
    token = login_user(email)

    response = client.post(
        "/notebooks",
        json={
            "name": "My Test Notebook",
            "description": "Testing notebook ownership",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    notebook = response.json()

    assert notebook["name"] == "My Test Notebook"

    notebook_id = notebook["id"]

    response = client.get(
        f"/notebooks/{notebook_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == notebook_id


def test_user_cannot_access_another_users_notebook():
    owner_email = "owner_isolation@test.com"
    attacker_email = "attacker_isolation@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    response = client.post(
        "/notebooks",
        json={
            "name": "Private Notebook",
            "description": "This belongs to the owner",
        },
        headers=auth_headers(owner_token),
    )

    assert response.status_code == 201

    notebook_id = response.json()["id"]

    response = client.get(
        f"/notebooks/{notebook_id}",
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_user_cannot_update_another_users_notebook():
    owner_email = "update_owner@test.com"
    attacker_email = "update_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    response = client.post(
        "/notebooks",
        json={
            "name": "Protected Notebook",
        },
        headers=auth_headers(owner_token),
    )

    assert response.status_code == 201

    notebook_id = response.json()["id"]

    response = client.patch(
        f"/notebooks/{notebook_id}",
        json={
            "name": "Unauthorized Change",
        },
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_user_cannot_delete_another_users_notebook():
    owner_email = "delete_owner@test.com"
    attacker_email = "delete_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    response = client.post(
        "/notebooks",
        json={
            "name": "Protected Delete Test",
        },
        headers=auth_headers(owner_token),
    )

    assert response.status_code == 201

    notebook_id = response.json()["id"]

    response = client.delete(
        f"/notebooks/{notebook_id}",
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_unauthenticated_user_cannot_access_notebooks():
    response = client.get("/notebooks")

    assert response.status_code in (401, 403)

def test_wrong_password_is_rejected():
    email = "wrong_password@test.com"

    register_user(email)

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_duplicate_email_is_rejected():
    email = "duplicate@test.com"

    register_user(email)

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Password123!",
        },
    )

    assert response.status_code == 409


def test_invalid_token_is_rejected():
    response = client.get(
        "/notebooks",
        headers=auth_headers("this-is-not-a-valid-jwt"),
    )

    assert response.status_code == 401


def test_missing_token_is_rejected():
    response = client.get("/notebooks")

    assert response.status_code in (401, 403)


def test_invalid_notebook_data_is_rejected():
    email = "invalid_notebook@test.com"

    register_user(email)
    token = login_user(email)

    response = client.post(
        "/notebooks",
        json={
            "name": "",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422


# FILE PURPOSE:
# Verifies authentication failures, duplicate registration,
# token validation, and request validation.

# FILE PURPOSE:
# Verifies notebook ownership, tenant isolation, authorization, and unauthenticated access behavior.