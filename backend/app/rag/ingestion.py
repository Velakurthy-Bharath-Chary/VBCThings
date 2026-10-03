from pathlib import Path

from app.rag.chunking import chunk_text
from app.rag.loaders import load_docx_file, load_pdf_file, load_pptx_file, load_text_file
from app.rag.vector_store import add_documents, delete_document_vectors


def load_document(file_path: str | Path) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()
    if extension in {".txt", ".py"}:
        return load_text_file(path)
    if extension == ".pdf":
        return load_pdf_file(path)
    if extension == ".docx":
        return load_docx_file(path)
    if extension == ".pptx":
        return load_pptx_file(path)
    raise ValueError(f"Unsupported document type: {extension}")


def ingest_text_document(
    file_path: str | Path,
    user_id: int,
    notebook_id: int,
    source_name: str | None = None,
    document_id: int | None = None,
) -> int:
    path = Path(file_path)
    source_name = source_name or path.name
    if document_id is not None:
        delete_document_vectors(document_id)
    text = load_document(path)
    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)
    if not chunks:
        raise ValueError("Document contains no usable text.")
    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        end = min(start + batch_size, len(chunks))
        add_documents(
            document_ids=[
                f"{document_id}_{index}" if document_id is not None else f"{user_id}_{notebook_id}_{path.name}_{index}"
                for index in range(start, end)
            ],
            texts=chunks[start:end],
            metadatas=[
                {
                    "user_id": str(user_id),
                    "notebook_id": str(notebook_id),
                    "document_id": str(document_id) if document_id is not None else "manual",
                    "source": source_name,
                    "chunk_index": index,
                    "document_type": path.suffix.lower().lstrip("."),
                }
                for index in range(start, end)
            ],
        )
    return len(chunks)
