from pathlib import Path
import os

import chromadb

from app.rag.embeddings import embed_text, embed_texts


CHROMA_DB_PATH = Path(
    os.environ.get("CHROMA_DB_PATH")
    or Path(__file__).resolve().parents[2] / "chroma_db"
)
_chroma_collection = None


def _get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        _chroma_collection = client.get_or_create_collection(name="rag_pipeline_test")
    return _chroma_collection


def delete_document_vectors(document_id: int) -> None:
    _get_chroma_collection().delete(where={"document_id": str(document_id)})


def add_documents(document_ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
    if not (len(document_ids) == len(texts) == len(metadatas)):
        raise ValueError("Document IDs, texts, and metadata must have matching lengths.")
    if not texts:
        return
    required_metadata = {"user_id", "notebook_id", "source", "chunk_index", "document_id"}
    for metadata in metadatas:
        missing_fields = required_metadata - metadata.keys()
        if missing_fields:
            raise ValueError(f"Missing required metadata: {sorted(missing_fields)}")
    _get_chroma_collection().upsert(
        ids=document_ids,
        documents=texts,
        embeddings=embed_texts(texts),
        metadatas=metadatas,
    )


def add_document(document_id: str, text: str, metadata: dict) -> None:
    add_documents([document_id], [text], [metadata])


def search_documents(query: str, user_id: int, notebook_id: int, top_k: int = 3) -> dict:
    return _get_chroma_collection().query(
        query_embeddings=[embed_text(query)],
        n_results=top_k,
        where={
            "$and": [
                {"user_id": str(user_id)},
                {"notebook_id": str(notebook_id)},
            ]
        },
    )


# Chroma stores persistent vectors and filters every query by user and notebook.
