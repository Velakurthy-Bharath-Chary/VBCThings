from fastapi.testclient import TestClient
from unittest.mock import patch
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


def create_notebook(token: str, name: str = "Test Notebook"):
    response = client.post(
        "/notebooks",
        json={
            "name": name,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    return response.json()["id"]


def create_chat(token: str, notebook_id: int, title: str = "Test Chat"):
    response = client.post(
        f"/chats?notebook_id={notebook_id}",
        json={
            "title": title,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    return response.json()


def test_user_can_create_and_read_own_chat():
    email = "chat_owner@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)

    chat = create_chat(
        token,
        notebook_id,
        "My First Chat",
    )

    assert chat["title"] == "My First Chat"
    assert chat["notebook_id"] == notebook_id

    response = client.get(
        f"/chats/{chat['id']}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == chat["id"]


def test_user_can_list_own_chats():
    email = "chat_list@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)

    create_chat(token, notebook_id, "Chat One")
    create_chat(token, notebook_id, "Chat Two")

    response = client.get(
        f"/chats?notebook_id={notebook_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    chats = response.json()

    assert len(chats) == 2
    assert {chat["title"] for chat in chats} == {
        "Chat One",
        "Chat Two",
    }


def test_user_can_update_own_chat():
    email = "chat_update@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)

    chat = create_chat(token, notebook_id)

    response = client.patch(
        f"/chats/{chat['id']}",
        json={
            "title": "Updated Chat",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Chat"


def test_user_can_delete_own_chat():
    email = "chat_delete@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)

    chat = create_chat(token, notebook_id)

    response = client.delete(
        f"/chats/{chat['id']}",
        headers=auth_headers(token),
    )

    assert response.status_code == 204

    response = client.get(
        f"/chats/{chat['id']}",
        headers=auth_headers(token),
    )

    assert response.status_code == 404


def test_user_cannot_access_another_users_chat():
    owner_email = "chat_owner_isolation@test.com"
    attacker_email = "chat_attacker_isolation@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(
        owner_token,
        "Private Notebook",
    )

    chat = create_chat(
        owner_token,
        notebook_id,
        "Private Chat",
    )

    response = client.get(
        f"/chats/{chat['id']}",
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_user_cannot_update_another_users_chat():
    owner_email = "chat_update_owner@test.com"
    attacker_email = "chat_update_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(owner_token)

    chat = create_chat(
        owner_token,
        notebook_id,
        "Protected Chat",
    )

    response = client.patch(
        f"/chats/{chat['id']}",
        json={
            "title": "Unauthorized Change",
        },
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_user_cannot_delete_another_users_chat():
    owner_email = "chat_delete_owner@test.com"
    attacker_email = "chat_delete_attacker@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(owner_token)

    chat = create_chat(
        owner_token,
        notebook_id,
        "Protected Chat",
    )

    response = client.delete(
        f"/chats/{chat['id']}",
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_user_can_create_and_read_messages():
    email = "message_owner@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)
    chat = create_chat(token, notebook_id)

    response = client.post(
        f"/chats/{chat['id']}/messages",
        json={
            "role": "user",
            "content": "Explain operating systems.",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201

    message = response.json()

    assert message["chat_id"] == chat["id"]
    assert message["role"] == "user"
    assert message["content"] == "Explain operating systems."

    response = client.get(
        f"/chats/{chat['id']}/messages",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    messages = response.json()

    assert len(messages) == 1
    assert messages[0]["content"] == "Explain operating systems."

    assistant_payload = (
        '{"kind":"assistant-message-v1","message":'
        '{"role":"assistant","agent":"tutor",'
        '"content":"An operating system manages computer resources.",'
        '"sources":[]}}'
    )
    assistant_response = client.post(
        f"/chats/{chat['id']}/messages",
        json={"role": "assistant", "content": assistant_payload},
        headers=auth_headers(token),
    )
    assert assistant_response.status_code == 201

    response = client.get(
        f"/chats/{chat['id']}/messages",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    messages = response.json()
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[1]["content"] == assistant_payload


def test_message_role_is_validated():
    email = "message_role@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)
    chat = create_chat(token, notebook_id)

    response = client.post(
        f"/chats/{chat['id']}/messages",
        json={
            "role": "admin",
            "content": "Invalid role",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 400


def test_user_cannot_access_another_users_messages():
    owner_email = "message_owner_isolation@test.com"
    attacker_email = "message_attacker_isolation@test.com"

    register_user(owner_email)
    register_user(attacker_email)

    owner_token = login_user(owner_email)
    attacker_token = login_user(attacker_email)

    notebook_id = create_notebook(owner_token)
    chat = create_chat(owner_token, notebook_id)

    response = client.post(
        f"/chats/{chat['id']}/messages",
        json={
            "role": "user",
            "content": "Private message",
        },
        headers=auth_headers(owner_token),
    )

    assert response.status_code == 201

    response = client.get(
        f"/chats/{chat['id']}/messages",
        headers=auth_headers(attacker_token),
    )

    assert response.status_code == 404


def test_unauthenticated_user_cannot_access_chats():
    response = client.get("/chats")

    assert response.status_code in (401, 403)

def test_chat_ask_routes_through_orchestrator():
    email = "chat_orchestrator@test.com"

    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)

    chat = create_chat(
        token,
        notebook_id,
        "AI Chat",
    )

    fake_result = {
        "agent": "tutor",
        "question": "Explain operating systems.",
        "answer": "An operating system manages computer resources.",
        "sources": [],
    }

    with patch(
        "app.api.chats.run_orchestrator",
        return_value=fake_result,
    ) as mock_orchestrator:

        response = client.post(
            f"/chats/{chat['id']}/ask",
            json={
                "role": "user",
                "content": "Explain operating systems.",
            },
            headers=auth_headers(token),
        )

    assert response.status_code == 201

    message = response.json()

    assert message["chat_id"] == chat["id"]
    assert message["role"] == "assistant"
    assert (
        message["content"]
        == "An operating system manages computer resources."
    )

    mock_orchestrator.assert_called_once_with(
        question="Explain operating systems.",
        user_id=message["user_id"],
        notebook_id=notebook_id,
    )


def test_user_can_pin_archive_and_restore_a_chat():
    email = "chat_archive_owner@test.com"
    register_user(email)
    token = login_user(email)
    notebook_id = create_notebook(token)
    chat = create_chat(token, notebook_id, "Revision session")

    pinned = client.patch(
        f"/chats/{chat['id']}",
        json={"is_pinned": True},
        headers=auth_headers(token),
    )
    assert pinned.status_code == 200
    assert pinned.json()["is_pinned"] is True

    archived = client.patch(
        f"/chats/{chat['id']}",
        json={"is_archived": True},
        headers=auth_headers(token),
    )
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True

    active_chats = client.get(
        f"/chats?notebook_id={notebook_id}",
        headers=auth_headers(token),
    )
    assert chat["id"] not in {item["id"] for item in active_chats.json()}

    all_chats = client.get(
        f"/chats?notebook_id={notebook_id}&include_archived=true",
        headers=auth_headers(token),
    )
    assert chat["id"] in {item["id"] for item in all_chats.json()}

    restored = client.patch(
        f"/chats/{chat['id']}",
        json={"is_archived": False},
        headers=auth_headers(token),
    )
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False


# FILE PURPOSE:
# Verifies chat CRUD, message management, authentication,
# validation, conversation flags, ownership, and cross-user isolation.
