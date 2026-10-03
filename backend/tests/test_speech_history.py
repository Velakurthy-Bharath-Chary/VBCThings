from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def auth_token(email):
    password = "SpeechHistory123!"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


@patch("app.api.orchestrator.run_orchestrator")
def test_orchestrated_speech_is_saved_and_isolated(mock_run):
    mock_run.return_value = {
        "agent": "speech",
        "transcript": "A function returns a value.",
        "semantic_analysis": {
            "cefr_estimate": {"level": "B1", "basis": "heuristic"},
            "answer_relevance": {"similarity": 0.9, "interpretation": "close"},
        },
        "tone_analysis": {"sentiment": "neutral"},
    }
    owner = auth_token("speech_history_owner@example.com")
    other = auth_token("speech_history_other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner}"}
    other_headers = {"Authorization": f"Bearer {other}"}

    created = client.post(
        "/orchestrator/speech",
        headers=owner_headers,
        data={"reference_text": "A function returns a result."},
        files={"file": ("answer.wav", BytesIO(b"test audio"), "audio/wav")},
    )

    assert created.status_code == 200
    created_data = created.json()
    assert created_data["assessment_id"] > 0
    assert created_data["semantic_analysis"]["answer_relevance"]["similarity"] == 0.9
    assert mock_run.call_args.kwargs["reference_text"] == "A function returns a result."

    owner_history = client.get("/orchestrator/speech/history", headers=owner_headers)
    other_history = client.get("/orchestrator/speech/history", headers=other_headers)
    assert owner_history.status_code == 200
    assert len(owner_history.json()) == 1
    assert owner_history.json()[0]["transcript"] == "A function returns a value."
    assert other_history.status_code == 200
    assert other_history.json() == []

    assessment_id = created_data["assessment_id"]
    assert client.delete(
        f"/orchestrator/speech/history/{assessment_id}",
        headers=other_headers,
    ).status_code == 404
    assert client.delete(
        f"/orchestrator/speech/history/{assessment_id}",
        headers=owner_headers,
    ).status_code == 204
    assert client.get("/orchestrator/speech/history", headers=owner_headers).json() == []


def test_speech_history_requires_auth():
    assert client.get("/orchestrator/speech/history").status_code in (401, 403)


# FILE PURPOSE:
# Verifies speech-history persistence, reference-answer integration,
# deletion, authentication, and cross-user isolation.
