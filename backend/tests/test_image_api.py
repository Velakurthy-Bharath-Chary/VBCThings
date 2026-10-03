from io import BytesIO

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Notebook, User


client = TestClient(app)


fake_user = User(
    id=1,
    email="image-test@example.com",
)

fake_notebook = Notebook(
    id=1,
    user_id=1,
    name="Image Test Notebook",
)


def override_db():
    yield None


def test_image_requires_authentication():
    response = client.post(
        "/image/analyze",
        files={
            "file": (
                "test.png",
                BytesIO(b"fake image"),
                "image/png",
            )
        },
        data={
            "notebook_id": "1",
        },
    )

    assert response.status_code == 401


def test_image_rejects_unsupported_type():
    app.dependency_overrides[get_current_user] = lambda: fake_user

    def fake_db():
        class FakeSession:
            def scalar(self, query):
                return fake_notebook

        yield FakeSession()

    app.dependency_overrides[get_db] = fake_db

    try:
        response = client.post(
            "/image/analyze",
            files={
                "file": (
                    "test.txt",
                    BytesIO(b"not an image"),
                    "text/plain",
                )
            },
            data={
                "notebook_id": "1",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Only JPG, PNG, and WEBP images are supported."
        )

    finally:
        app.dependency_overrides.clear()


def test_image_rejects_oversized_upload():
    app.dependency_overrides[get_current_user] = lambda: fake_user

    def fake_db():
        class FakeSession:
            def scalar(self, query):
                return fake_notebook

        yield FakeSession()

    app.dependency_overrides[get_db] = fake_db

    try:
        oversized_data = b"x" * (20 * 1024 * 1024 + 1)

        response = client.post(
            "/image/analyze",
            files={
                "file": (
                    "large.png",
                    BytesIO(oversized_data),
                    "image/png",
                )
            },
            data={
                "notebook_id": "1",
            },
        )

        assert response.status_code == 413
        assert response.json()["detail"] == (
            "Image size must not exceed 20 MB."
        )

    finally:
        app.dependency_overrides.clear()

def test_image_rejects_other_users_notebook():
    app.dependency_overrides[get_current_user] = lambda: fake_user

    def fake_db():
        class FakeSession:
            def scalar(self, query):
                return None

        yield FakeSession()

    app.dependency_overrides[get_db] = fake_db

    try:
        response = client.post(
            "/image/analyze",
            files={
                "file": (
                    "test.png",
                    BytesIO(b"fake image"),
                    "image/png",
                )
            },
            data={
                "notebook_id": "999",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Notebook not found"

    finally:
        app.dependency_overrides.clear()

# FILE PURPOSE:
# Tests authentication, notebook ownership, and image-upload validation
# for the Image Agent API.
        

# FILE PURPOSE:
# Tests authentication and image-upload validation for the Image Agent API.