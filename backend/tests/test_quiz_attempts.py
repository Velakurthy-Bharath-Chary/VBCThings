import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_user(email):
    password = "QuizHistory123!"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_quiz_message(headers):
    notebook = client.post("/notebooks", json={"name": "Quiz notebook"}, headers=headers).json()
    chat = client.post(f"/chats?notebook_id={notebook['id']}", json={"title": "Practice"}, headers=headers).json()
    quiz = {
        "questions": [
            {
                "question": f"Question {index + 1}",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "correct_answer": "A",
                "explanation": "A is supported by the source.",
            }
            for index in range(5)
        ],
    }
    assistant_content = json.dumps({
        "kind": "assistant-message-v1",
        "message": {"role": "assistant", "agent": "quiz", "quiz": quiz},
    })
    message = client.post(
        f"/chats/{chat['id']}/messages",
        json={"role": "assistant", "content": assistant_content},
        headers=headers,
    ).json()
    return notebook["id"], chat["id"], message["id"]


def test_quiz_attempt_scoring_persistence_and_tenant_isolation():
    owner_headers = create_user("quiz_history_owner@example.com")
    other_headers = create_user("quiz_history_other@example.com")
    notebook_id, chat_id, message_id = create_quiz_message(owner_headers)

    response = client.post(
        "/quiz-attempts",
        headers=owner_headers,
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "answers": ["A", "B", "A", "A", "D"],
        },
    )
    assert response.status_code == 201
    assert response.json()["score"] == 3
    assert response.json()["total_questions"] == 5
    assert response.json()["percentage"] == 60

    assert client.get(
        f"/quiz-attempts?notebook_id={notebook_id}",
        headers=owner_headers,
    ).json()[0]["score"] == 3
    progress = client.get(
        f"/studio/progress?notebook_id={notebook_id}",
        headers=owner_headers,
    ).json()
    assert progress["quiz_attempt_count"] == 1
    assert progress["average_quiz_score_percent"] == 60.0
    assert client.get("/quiz-attempts", headers=other_headers).json() == []
    assert client.post(
        "/quiz-attempts",
        headers=owner_headers,
        json={"chat_id": chat_id, "message_id": message_id, "answers": ["A"] * 5},
    ).status_code == 409
    assert client.post(
        "/quiz-attempts",
        headers=other_headers,
        json={"chat_id": chat_id, "message_id": message_id, "answers": ["A"] * 5},
    ).status_code == 404


def test_quiz_attempts_require_authentication():
    assert client.get("/quiz-attempts").status_code in (401, 403)


# FILE PURPOSE:
# Verifies server-side quiz scoring, one-attempt behavior, persistence,
# authentication, and multi-tenant access restrictions.
