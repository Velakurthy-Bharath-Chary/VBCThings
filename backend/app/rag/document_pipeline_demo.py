from pathlib import Path

from app.rag.chunking import chunk_text
from app.rag.loaders import load_text_file
from app.rag.vector_store import add_document, search_documents


DOCUMENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "documents"
    / "python_basics.txt"
)


def ingest_document(
    user_id: str,
    notebook_id: str,
    source: str,
) -> None:
    text = load_text_file(DOCUMENT_PATH)

    chunks = chunk_text(
        text,
        chunk_size=300,
        chunk_overlap=50,
    )

    for index, chunk in enumerate(chunks):
        add_document(
            document_id=f"{user_id}_{notebook_id}_{index}",
            text=chunk,
            metadata={
                "user_id": user_id,
                "notebook_id": notebook_id,
                "document_id": f"{user_id}_{notebook_id}_{index}",
                "source": source,
                "chunk_index": index,
                "document_type": "txt",
            },
        )

    print(
        f"Ingested {len(chunks)} chunks "
        f"for user={user_id}, notebook={notebook_id}"
    )


def print_results(
    title: str,
    results: dict,
) -> None:
    print(f"\n{title}")

    documents = results.get("documents", [[]])[0]

    if not documents:
        print("NO RESULTS")
        return

    for index, document in enumerate(documents):
        print(f"\n--- Result {index + 1} ---")
        print(document)


def main() -> None:
    # User 1 owns notebook 1.
    ingest_document(user_id="1", notebook_id="1", source="python_basics.txt")

    # User 2 owns notebook 2. The same sample is stored under another tenant.
    ingest_document(user_id="2", notebook_id="2", source="python_basics.txt")

    user_1_results = search_documents(
        "How are reusable blocks of code created in Python?",
        user_id=1,
        notebook_id=1,
        top_k=3,
    )
    print_results("USER 1 / NOTEBOOK 1 RESULTS", user_1_results)

    user_2_results = search_documents(
        "How are reusable blocks of code created in Python?",
        user_id=2,
        notebook_id=2,
        top_k=3,
    )
    print_results("USER 2 / NOTEBOOK 2 RESULTS", user_2_results)

    # User 1 attempts to query User 2's notebook.
    cross_tenant_results = search_documents(
        "How are reusable blocks of code created in Python?",
        user_id=1,
        notebook_id=2,
        top_k=3,
    )
    print_results("USER 1 / USER 2 NOTEBOOK RESULTS", cross_tenant_results)


if __name__ == "__main__":
    main()


# FILE PURPOSE:
# Offers a manually invoked tenant-isolation demonstration without running
# ingestion or vector writes as an import side effect.
