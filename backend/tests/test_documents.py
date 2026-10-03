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


def create_notebook(token: str, name: str):
    response = client.post(
        "/notebooks",
        json={
            "name": name,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_user_can_upload_txt_document():
    email = "document_upload_owner@test.com"

    register_user(email)

    token = login_user(email)

    notebook_id = create_notebook(
        token,
        "Upload Test Notebook",
    )

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
                    b"Python functions are reusable blocks of code."
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["filename"] == "python.txt"
    assert data["document_type"] == "txt"
    assert data["notebook_id"] == notebook_id
    assert data["processing_status"] == "completed"


def test_user_cannot_upload_to_another_users_notebook():
    owner_email = "document_owner@test.com"
    attacker_email = "document_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(
        owner_token,
        "Private Notebook",
    )

    response = client.post(
        "/documents/upload",
        headers=auth_headers(attacker_token),
        data={
            "notebook_id": str(notebook_id),
        },
        files={
            "file": (
                "attack.txt",
                BytesIO(
                    b"This should never enter another user's notebook."
                ),
                "text/plain",
            )
        },
    )

    assert response.status_code == 404


def test_unsupported_document_type_is_rejected():
    email = "unsupported_document@test.com"

    register_user(email)

    token = login_user(email)

    notebook_id = create_notebook(
        token,
        "Unsupported File Test",
    )

    response = client.post(
        "/documents/upload",
        headers=auth_headers(token),
        data={
            "notebook_id": str(notebook_id),
        },
        files={
            "file": (
                "malicious.exe",
                BytesIO(b"not supported"),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400


def test_unauthenticated_user_cannot_upload():
    response = client.post(
        "/documents/upload?notebook_id=1",
        files={
            "file": (
                "test.txt",
                BytesIO(b"Unauthorized upload"),
                "text/plain",
            )
        },
    )

    assert response.status_code in (401, 403)


def _create_document_row(notebook_id: int, storage_path: str, status: str = "completed"):
    from app.database import SessionLocal
    from app.models import Document, Notebook

    with SessionLocal() as db:
        notebook = db.get(Notebook, notebook_id)
        document = Document(
            user_id=notebook.user_id,
            notebook_id=notebook_id,
            filename="source.txt",
            document_type="txt",
            storage_path=storage_path,
            processing_status=status,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id


def test_user_can_delete_completed_document_and_its_content(monkeypatch, tmp_path):
    from app.api import documents as document_api

    email = "document_delete_owner@test.com"
    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token, "Delete source notebook")
    stored_file = tmp_path / "source.txt"
    stored_file.write_text("Indexed source", encoding="utf-8")
    document_id = _create_document_row(notebook_id, str(stored_file))
    deleted_vector_ids = []
    monkeypatch.setattr(document_api, "delete_document_vectors", deleted_vector_ids.append)

    response = client.delete(
        f"/documents/{document_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 204
    assert not stored_file.exists()
    assert deleted_vector_ids == [document_id]
    assert client.get(
        f"/documents?notebook_id={notebook_id}",
        headers=auth_headers(token),
    ).json() == []


def test_user_cannot_delete_another_users_document(tmp_path):
    owner_email = "document_delete_owner_isolation@test.com"
    other_email = "document_delete_other_isolation@test.com"
    register_user(owner_email)
    register_user(other_email)
    owner_token = login_user(owner_email)
    other_token = login_user(other_email)
    notebook_id = create_notebook(owner_token, "Private source notebook")
    stored_file = tmp_path / "private.txt"
    stored_file.write_text("Private indexed source", encoding="utf-8")
    document_id = _create_document_row(notebook_id, str(stored_file))

    response = client.delete(
        f"/documents/{document_id}",
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert stored_file.exists()


# FILE PURPOSE:
# Verifies document upload, file-type validation, authentication,
# and notebook-level tenant isolation for the document API.
