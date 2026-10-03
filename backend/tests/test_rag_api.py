from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

PASSWORD = "Password123!"


def register_user(email: str):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201


def login_user(email: str):
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()["access_token"]


def auth_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
    }


def create_notebook(token: str):
    response = client.post(
        "/notebooks",
        json={
            "name": "RAG API Test Notebook",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    return response.json()["id"]


def upload_document(token: str, notebook_id: int):
    response = client.post(
        "/documents/upload",
        headers=auth_headers(token),
        data={
            "notebook_id": str(notebook_id),
        },
        files={
            "file": (
                "python.txt",
                BytesIO(
                    b"""
                    Python functions are reusable blocks of code.
                    Functions are defined using the def keyword.
                    """
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 201


def test_authenticated_user_can_ask_rag():
    email = "rag_api_owner@test.com"

    register_user(email)

    token = login_user(email)

    notebook_id = create_notebook(token)

    upload_document(
        token,
        notebook_id,
    )

    response = client.post(
        "/rag/ask",
        headers=auth_headers(token),
        json={
            "notebook_id": notebook_id,
            "question": "What are functions in Python?",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["question"] == "What are functions in Python?"
    assert data["answer"]
    assert len(data["sources"]) > 0


def test_user_cannot_ask_another_users_notebook():
    owner_email = "rag_api_owner2@test.com"
    attacker_email = "rag_api_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(owner_token)

    response = client.post(
        "/rag/ask",
        headers=auth_headers(attacker_token),
        json={
            "notebook_id": notebook_id,
            "question": "What is Python?",
        },
    )

    assert response.status_code == 404


def test_unauthenticated_user_cannot_ask_rag():
    response = client.post(
        "/rag/ask",
        json={
            "notebook_id": 1,
            "question": "What is Python?",
        },
    )

    assert response.status_code in (401, 403)

def test_orchestrator_api_generates_quiz():
    email = "orchestrator_quiz@test.com"

    register_user(email)

    token = login_user(email)

    notebook_id = create_notebook(token)

    upload_document(
        token,
        notebook_id,
    )

    response = client.post(
        "/orchestrator/run",
        headers=auth_headers(token),
        json={
            "notebook_id": notebook_id,
            "question": "Create a quiz about Python functions",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["agent"] == "quiz"
    assert data["quiz"]
    assert len(data["sources"]) > 0
    assert data["sources"][0]["source"] == "python.txt"


# FILE PURPOSE:
# Tests authenticated orchestrator API routing to the grounded Quiz Agent.

# FILE PURPOSE:
# Tests authenticated RAG API access, notebook ownership isolation,
# document-grounded answers, and authentication requirements.