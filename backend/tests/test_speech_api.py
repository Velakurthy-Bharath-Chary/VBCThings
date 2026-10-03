from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def get_auth_token():
    email = "speech_test@example.com"
    password = "SpeechTest123!"

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


def test_speech_transcribe_requires_auth():
    response = client.post(
        "/speech/transcribe",
        files={
            "file": (
                "test.wav",
                BytesIO(b"fake audio"),
                "audio/wav",
            )
        },
    )

    assert response.status_code in (401, 403)


def test_speech_analyze_requires_auth():
    response = client.post(
        "/speech/analyze",
        files={
            "file": (
                "test.wav",
                BytesIO(b"fake audio"),
                "audio/wav",
            )
        },
    )

    assert response.status_code in (401, 403)


def test_speech_transcribe_rejects_unsupported_extension():
    token = get_auth_token()

    response = client.post(
        "/speech/transcribe",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "test.txt",
                BytesIO(b"not audio"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400


@patch("app.api.speech.transcribe_audio")
def test_speech_transcribe_success(mock_transcribe):
    mock_transcribe.return_value = "This is a speech transcription."

    token = get_auth_token()

    response = client.post(
        "/speech/transcribe",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "test.wav",
                BytesIO(b"fake audio"),
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filename"] == "test.wav"
    assert data["transcript"] == "This is a speech transcription."


@patch("app.api.speech.analyze_tone")
@patch("app.api.speech.analyze_semantics")
@patch("app.api.speech.transcribe_audio")
def test_speech_analyze_success(
    mock_transcribe,
    mock_semantics,
    mock_tone,
):
    mock_transcribe.return_value = "This is a learning speech."
    mock_semantics.return_value = {
        "mode": "semantic",
        "cefr_estimate": {
            "level": "B1",
            "basis": "heuristic linguistic signals; not a certified CEFR assessment",
        },
    }
    mock_tone.return_value = {
        "mode": "tone",
        "sentiment": "positive",
        "positive_signals": 2,
        "negative_signals": 0,
    }

    token = get_auth_token()

    response = client.post(
        "/speech/analyze",
        headers={
            "Authorization": f"Bearer {token}",
        },
        files={
            "file": (
                "test.wav",
                BytesIO(b"fake audio"),
                "audio/wav",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filename"] == "test.wav"
    assert data["transcript"] == "This is a learning speech."
    assert data["semantic_analysis"]["mode"] == "semantic"
    assert data["tone_analysis"]["sentiment"] == "positive"
    assert isinstance(data["id"], int)


# FILE PURPOSE:
# Tests authentication, validation, transcription, and combined
# speech-analysis API behavior without making real external API calls.
