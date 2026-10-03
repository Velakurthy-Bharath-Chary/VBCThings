from pathlib import Path
import json
from unittest.mock import patch

from app.rag.answer import generate_rag_answer, generate_rag_answer_stream
from app.rag.ingestion import ingest_text_document


DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "documents"
    / "python_basics.txt"
)


def test_rag_answer_generation():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=701,
        notebook_id=801,
    )

    result = generate_rag_answer(
        question="What are functions in Python?",
        user_id=701,
        notebook_id=801,
        top_k=3,
    )

    assert result["answer"]
    assert len(result["sources"]) > 0
    assert result["sources"][0]["source"] == "python_basics.txt"


def test_rag_answer_without_context():
    result = generate_rag_answer(
        question="What is quantum teleportation?",
        user_id=702,
        notebook_id=9999,
        top_k=3,
    )

    assert result["answer"].startswith("Not in uploaded sources — ")
    assert len(result["answer"]) > len("Not in uploaded sources — ")

    assert result["sources"] == []


def test_stream_history_flattens_saved_quiz_and_resource_messages():
    assistant_message = {
        "role": "assistant",
        "agent": "quiz",
        "content": "Select one answer for each question.",
        "quiz": {
            "questions": [{
                "question": "What does a function return?",
                "options": {"A": "A value", "B": "A loop"},
                "correct_option": "A",
            }],
        },
        "resources": [{"title": "Python Guide", "snippet": "A learning resource."}],
        "sources": [],
    }
    history = [
        {
            "role": "assistant",
            "content": json.dumps({
                "kind": "assistant-message-v1",
                "message": assistant_message,
            }),
        },
    ]
    rag_result = {"results": [{
        "source": "notes.txt",
        "chunk_index": 0,
        "text": "A function returns a value.",
    }]}
    prompts = []

    def fake_stream(*, system_prompt, user_prompt):
        assert system_prompt
        prompts.append(user_prompt)
        yield "Grounded answer."

    with patch("app.rag.answer.query_rag", return_value=rag_result), patch(
        "app.rag.answer.generate_answer_stream", side_effect=fake_stream,
    ):
        list(generate_rag_answer_stream(
            question="Explain that quiz item.",
            user_id=1,
            notebook_id=2,
            conversation_history=history,
        ))

    assert "Quiz questions previously shown: What does a function return?" in prompts[0]
    assert "Python Guide — A learning resource." in prompts[0]
    assert "assistant-message-v1" not in prompts[0]
    assert "correct_option" not in prompts[0]


# FILE PURPOSE:
# Tests grounded Groq answer generation and no-context handling.
