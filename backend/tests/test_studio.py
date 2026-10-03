from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_and_login(email, password="Password123!"):
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
    }


def create_notebook(token, name="Test Notebook"):
    response = client.post(
        "/notebooks",
        json={
            "name": name,
            "description": "Studio test notebook",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_studio_generate_requires_auth():
    response = client.post(
        "/studio/generate",
        json={
            "notebook_id": 1,
            "artifact_type": "summary",
        },
    )

    assert response.status_code == 401


def test_studio_generate_rejects_unsupported_type():
    token = register_and_login(
        "studio-invalid@example.com",
    )

    notebook_id = create_notebook(token)

    response = client.post(
        "/studio/generate",
        json={
            "notebook_id": notebook_id,
            "artifact_type": "invalid_type",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported artifact type."


def test_studio_generate_blocks_other_users_notebook():
    owner_token = register_and_login(
        "studio-owner@example.com",
    )

    attacker_token = register_and_login(
        "studio-attacker@example.com",
    )

    notebook_id = create_notebook(
        owner_token,
        "Owner Notebook",
    )

    response = client.post(
        "/studio/generate",
        json={
            "notebook_id": notebook_id,
            "artifact_type": "summary",
        },
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


@patch("app.api.studio.query_rag")
@patch("app.api.studio.generate_answer")
def test_studio_generate_creates_artifact(
    mock_generate_answer,
    mock_query_rag,
):
    token = register_and_login(
        "studio-generate@example.com",
    )

    notebook_id = create_notebook(
        token,
        "AI Notebook",
    )

    mock_query_rag.return_value = {
        "question": "Create summary",
        "results": [
            {
                "text": "FastAPI is a Python web framework.",
                "source": "fastapi.txt",
                "chunk_index": 0,
                "distance": 0.20,
            }
        ],
        "result_count": 1,
    }

    mock_generate_answer.return_value = (
        "FastAPI is a Python framework used for building APIs."
    )

    response = client.post(
        "/studio/generate",
        json={
            "notebook_id": notebook_id,
            "artifact_type": "summary",
            "title": "FastAPI Summary",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["notebook_id"] == notebook_id
    assert data["artifact_type"] == "summary"
    assert data["title"] == "FastAPI Summary"
    assert "FastAPI" in data["content"]

    mock_query_rag.assert_called_once()
    mock_generate_answer.assert_called_once()


@patch("app.api.studio.query_rag")
def test_studio_generate_requires_sources(mock_query_rag):
    token = register_and_login(
        "studio-empty@example.com",
    )

    notebook_id = create_notebook(
        token,
        "Empty Notebook",
    )

    mock_query_rag.return_value = {
        "question": "Create notes",
        "results": [],
        "result_count": 0,
    }

    response = client.post(
        "/studio/generate",
        json={
            "notebook_id": notebook_id,
            "artifact_type": "notes",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert "No relevant uploaded sources" in response.json()["detail"]


@patch("app.api.studio.query_rag")
@patch("app.api.studio.generate_answer")
def test_learning_progress_is_notebook_scoped_and_owner_only(
    mock_generate_answer,
    mock_query_rag,
):
    owner_token = register_and_login("studio_progress_owner@example.com")
    other_token = register_and_login("studio_progress_other@example.com")
    notebook_id = create_notebook(owner_token, "Progress Notebook")
    owner_headers = auth_headers(owner_token)
    other_headers = auth_headers(other_token)

    initial = client.get(
        f"/studio/progress?notebook_id={notebook_id}",
        headers=owner_headers,
    )
    assert initial.status_code == 200
    assert initial.json()["source_count"] == 0
    assert initial.json()["artifact_count"] == 0
    assert any(item["key"] == "add_sources" for item in initial.json()["recommendations"])
    assert client.get(
        f"/studio/progress?notebook_id={notebook_id}",
        headers=other_headers,
    ).status_code == 404

    mock_query_rag.return_value = {
        "question": "Create notes",
        "results": [{"text": "A source chunk", "source": "notes.txt", "chunk_index": 0}],
        "result_count": 1,
    }
    mock_generate_answer.return_value = "Generated notes"
    created = client.post(
        "/studio/generate",
        json={"notebook_id": notebook_id, "artifact_type": "notes"},
        headers=owner_headers,
    )
    assert created.status_code == 201

    updated = client.get(
        f"/studio/progress?notebook_id={notebook_id}",
        headers=owner_headers,
    )
    assert updated.json()["artifact_count"] == 1
    assert updated.json()["artifacts_by_type"] == {"notes": 1}
    assert updated.json()["quiz_attempt_count"] == 0
    assert updated.json()["average_quiz_score_percent"] is None


# FILE PURPOSE:
# Tests Learning Studio authentication, tenant isolation,
# artifact generation, and source validation.


# FILE PURPOSE:
# Tests Learning Studio authentication, tenant isolation,
# artifact generation, source validation, and ownership controls.
