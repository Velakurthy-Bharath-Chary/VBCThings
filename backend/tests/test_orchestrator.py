import json
from app.agents.orchestrator import classify_request
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agents.resource import ResourceSearchError
from app.agents.resource import ResourceResult
from app.agents.orchestrator import (
    classify_request,
    run_orchestrator,
)
from app.main import app

client = TestClient(app)

def test_explanation_goes_to_tutor():
    assert classify_request("Explain Python functions") == "tutor"


def test_quiz_request_goes_to_quiz():
    assert classify_request("Create a quiz about Python") == "quiz"


def test_mcq_request_goes_to_quiz():
    assert classify_request("Give me 5 MCQs on OOP") == "quiz"


def test_topic_question_routes_to_tutor():
    assert classify_request("What are Python functions?") == "tutor"


def test_recent_ai_trends_route_to_resource_agent():
    assert classify_request("Find recent AI trends") == "resource"


def test_local_study_space_search_routes_to_resource_agent():
    assert classify_request("Find libraries near me") == "resource"


def test_image_question_routes_to_image_agent():
    assert classify_request("Analyze this image") == "image"

def test_orchestrator_resource_route():
    fake_results = [
        ResourceResult(
            title="Python News",
            url="https://python.org",
            snippet="Latest Python information.",
        )
    ]

    with patch(
        "app.agents.orchestrator.create_groq_resource_agent"
    ) as mock_agent_factory:
        mock_agent = mock_agent_factory.return_value
        mock_agent.search.return_value = fake_results

        result = run_orchestrator(
            question="What is the latest Python news?",
            user_id=1,
            notebook_id=1,
        )

    assert result["agent"] == "resource"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Python News"
    assert result["results"][0]["url"] == "https://python.org"


def test_resource_stream_reports_selected_agent_and_provider_error():
    email = "resource_stream_error@test.com"
    registered = client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    notebook = client.post(
        "/notebooks",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Resource error test"},
    )
    assert notebook.status_code == 201

    with patch(
        "app.api.orchestrator.run_orchestrator",
        side_effect=ResourceSearchError("Search provider quota is unavailable."),
    ):
        response = client.post(
            "/orchestrator/run/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "notebook_id": notebook.json()["id"],
                "question": "What are the latest developments in AI?",
            },
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events == [
        {"type": "agent", "agent": "resource"},
        {
            "type": "error",
            "agent": "resource",
            "message": "Search provider quota is unavailable.",
        },
    ]


def test_resource_route_uses_the_single_groq_provider():
    with patch("app.agents.orchestrator.create_groq_resource_agent") as factory:
        factory.return_value.search.return_value = []
        result = run_orchestrator("latest AI news", user_id=1, notebook_id=1)

    assert result == {"agent": "resource", "question": "latest AI news", "results": []}
    factory.assert_called_once_with()

# FILE PURPOSE:
# Tests request classification and resource routing for the agent orchestrator.
