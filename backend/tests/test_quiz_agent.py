from pathlib import Path

from app.agents.quiz import generate_quiz
from app.rag.ingestion import ingest_text_document


DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "documents"
    / "python_basics.txt"
)


def test_quiz_agent_generates_quiz():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=801,
        notebook_id=901,
    )

    result = generate_quiz(
        topic="Python basics",
        user_id=801,
        notebook_id=901,
    )

    assert result["quiz"]
    assert len(result["sources"]) > 0
    assert result["sources"][0]["source"] == "python_basics.txt"


def test_quiz_agent_without_context():
    result = generate_quiz(
        topic="Quantum computing",
        user_id=802,
        notebook_id=9999,
    )

    assert result["questions"] == []
    assert result["message"] == (
        "I couldn't find enough information in the uploaded sources."
    )


# FILE PURPOSE:
# Tests grounded quiz generation and no-context handling.