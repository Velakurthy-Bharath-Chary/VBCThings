from app.rag.vector_store import search_documents


def query_rag(
    question: str,
    user_id: int,
    notebook_id: int,
    top_k: int = 3,
    distance_threshold: float | None = 0.70,
) -> dict:
    """
    Retrieve relevant document chunks for a user's question.
    Removes duplicate source chunks before returning results.
    """

    if not question.strip():
        raise ValueError("Question cannot be empty.")

    if top_k <= 0:
        raise ValueError("top_k must be greater than 0.")

    if distance_threshold is not None and distance_threshold <= 0:
        raise ValueError("distance_threshold must be greater than 0")

    results = search_documents(
        query=question,
        user_id=user_id,
        notebook_id=notebook_id,
        top_k=top_k,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    sources = []
    seen_chunks = set()

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        if (
            distance_threshold is not None
            and distance > distance_threshold
        ):
            continue

        source = metadata.get("source")
        chunk_index = metadata.get("chunk_index")

        chunk_key = (source, chunk_index)

        if chunk_key in seen_chunks:
            continue

        seen_chunks.add(chunk_key)

        sources.append(
            {
                "text": document,
                "source": source,
                "chunk_index": chunk_index,
                "distance": distance,
            }
        )

    if not sources and distance_threshold is None:
        fallback_results = search_documents(
            query="document content overview summary details information",
            user_id=user_id,
            notebook_id=notebook_id,
            top_k=top_k,
        )
        fb_docs = fallback_results.get("documents", [[]])[0]
        fb_metas = fallback_results.get("metadatas", [[]])[0]
        fb_dists = fallback_results.get("distances", [[]])[0]

        for document, metadata, distance in zip(fb_docs, fb_metas, fb_dists):
            source = metadata.get("source")
            chunk_index = metadata.get("chunk_index")
            if not source or (source, chunk_index) in seen_chunks:
                continue
            seen_chunks.add((source, chunk_index))
            sources.append(
                {
                    "text": document,
                    "source": source,
                    "chunk_index": chunk_index,
                    "distance": distance,
                }
            )

    return {
        "question": question,
        "results": sources,
        "result_count": len(sources),
    }


# FILE PURPOSE:
# Provides tenant-aware RAG retrieval, removes duplicate document chunks,
# and returns source metadata with Chroma similarity distance information.

# FILE PURPOSE:
# Provides tenant-aware RAG retrieval with document source metadata
# and Chroma similarity distance information.


# FILE PURPOSE:
# Provides a clean tenant-aware RAG query service that retrieves
# relevant document chunks and their source metadata.
