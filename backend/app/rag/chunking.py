def chunk_text(
    text: str,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Clean text and split it into overlapping chunks.
    """

    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size."
        )

    words = text.split()

    if not words:
        return []

    chunks = []

    start = 0
    step = chunk_size - chunk_overlap

    while start < len(words):
        end = min(start + chunk_size, len(words))

        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end == len(words):
            break

        start += step

    return chunks


# FILE PURPOSE:
# Cleans document text and creates overlapping word-based chunks
# for embedding and semantic retrieval.

# FILE PURPOSE:
# Provides tenant-aware RAG retrieval, removes duplicate document chunks,
# and returns source metadata with Chroma similarity distance information.

# FILE PURPOSE:
# Cleans document text and creates word-boundary-aware overlapping chunks for RAG.

# FILE PURPOSE:
# Cleans and splits document text into overlapping chunks for embedding and retrieval.