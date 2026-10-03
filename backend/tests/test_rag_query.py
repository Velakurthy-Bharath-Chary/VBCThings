from pathlib import Path

from app.rag.ingestion import ingest_text_document
from app.rag.query import query_rag


DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "documents"
    / "python_basics.txt"
)


def test_rag_query_returns_relevant_results():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=501,
        notebook_id=601,
    )

    result = query_rag(
        question="How are reusable blocks of code created in Python?",
        user_id=501,
        notebook_id=601,
        top_k=3,
    )

    assert result["result_count"] > 0

    combined_text = " ".join(
        item["text"]
        for item in result["results"]
    ).lower()

    assert "function" in combined_text


def test_rag_query_preserves_source_metadata():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=502,
        notebook_id=602,
    )

    result = query_rag(
        question="What are Python data types?",
        user_id=502,
        notebook_id=602,
        top_k=3,
    )

    assert result["result_count"] > 0

    for item in result["results"]:
        assert item["source"] == "python_basics.txt"
        assert isinstance(item["chunk_index"], int)
        assert isinstance(item["distance"], float)


def test_rag_query_respects_tenant_isolation():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=503,
        notebook_id=603,
    )

    result = query_rag(
        question="What are Python functions?",
        user_id=503,
        notebook_id=999,
        top_k=3,
    )

    assert result["result_count"] == 0


def test_empty_question_is_rejected():
    try:
        query_rag(
            question="   ",
            user_id=504,
            notebook_id=604,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "Question cannot be empty."

def test_low_relevance_results_are_filtered():
    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=505,
        notebook_id=605,
    )

    result = query_rag(
        question="What is the history of quantum computing?",
        user_id=505,
        notebook_id=605,
        top_k=3,
        distance_threshold=0.70,
    )

    assert result["result_count"] == 0

# FILE PURPOSE:
# Tests RAG retrieval, source metadata, similarity distance,
# tenant isolation, and query validation.


# FILE PURPOSE:
# Tests RAG question retrieval, source metadata,
# tenant isolation, and query validation.