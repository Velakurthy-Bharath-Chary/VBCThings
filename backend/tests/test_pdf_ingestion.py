from pathlib import Path

from app.rag.ingestion import ingest_text_document
from app.rag.vector_store import search_documents


PDF_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "documents"
    / "python_basics.pdf"
)


def test_pdf_ingestion_and_retrieval():
    chunks_created = ingest_text_document(
        file_path=PDF_PATH,
        user_id=301,
        notebook_id=401,
    )

    assert chunks_created > 0

    results = search_documents(
        "What are functions in Python?",
        user_id=301,
        notebook_id=401,
        top_k=3,
    )

    documents = results["documents"][0]

    assert len(documents) > 0

    combined_text = " ".join(documents).lower()

    assert "function" in combined_text


# FILE PURPOSE:
# Verifies PDF text extraction, ingestion, embedding,
# Chroma storage, and semantic retrieval.