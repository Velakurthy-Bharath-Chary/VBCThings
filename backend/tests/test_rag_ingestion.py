from pathlib import Path

from app.rag.ingestion import ingest_text_document
from app.rag.vector_store import search_documents


DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "documents"
    / "python_basics.txt"
)


def test_document_ingestion_and_tenant_retrieval():
    user_1 = 101
    notebook_1 = 201

    chunks_created = ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=user_1,
        notebook_id=notebook_1,
    )

    assert chunks_created > 0

    results = search_documents(
        "How are reusable blocks of code created in Python?",
        user_id=user_1,
        notebook_id=notebook_1,
        top_k=3,
    )

    assert len(results["documents"][0]) > 0


def test_tenant_isolation():
    user_1 = 102
    notebook_1 = 202

    user_2 = 103
    notebook_2 = 203

    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=user_1,
        notebook_id=notebook_1,
    )

    ingest_text_document(
        file_path=DOCUMENT_PATH,
        user_id=user_2,
        notebook_id=notebook_2,
    )

    attacker_results = search_documents(
        "How are reusable blocks of code created in Python?",
        user_id=user_1,
        notebook_id=notebook_2,
        top_k=3,
    )

    assert attacker_results["documents"][0] == []


# FILE PURPOSE:
# Tests reusable document ingestion, semantic retrieval,
# and tenant isolation in the RAG pipeline.