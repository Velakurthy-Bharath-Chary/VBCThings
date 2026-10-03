import json

from langchain_core.prompts import ChatPromptTemplate

from app.ai.llm import generate_answer, generate_answer_stream
from app.rag.query import query_rag


SYSTEM_PROMPT = """You are VBC Things, an AI learning tutor.

Use the uploaded notebook context first when it directly answers the user's question.
If the context is empty or does not contain the answer, answer from general knowledge. Do not imply that general knowledge came from the user's files; the application labels answers that are not grounded in uploaded sources. If a question asks about current events, say when you cannot verify current information.
Explain concepts clearly at a student-friendly level. Cite source filenames only when the answer is supported by those sources."""

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{user_prompt}"),
    ]
)


def _format_rag_prompts(user_prompt: str) -> tuple[str, str]:
    """Format the grounded tutoring prompt through LangChain's chat prompt API."""
    messages = RAG_PROMPT.format_messages(user_prompt=user_prompt)
    return messages[0].content, messages[1].content


def _history_message_text(message: dict[str, str]) -> str:
    content = str(message.get("content", ""))[:4000]
    if message.get("role") != "assistant":
        return content

    try:
        stored = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    if not isinstance(stored, dict) or stored.get("kind") != "assistant-message-v1":
        return content

    assistant_message = stored.get("message")
    if not isinstance(assistant_message, dict):
        return content
    parts = []
    assistant_content = assistant_message.get("content")
    if isinstance(assistant_content, str) and assistant_content.strip():
        parts.append(assistant_content.strip())

    resources = assistant_message.get("resources")
    if isinstance(resources, list):
        resource_lines = []
        for item in resources[:5]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if title or snippet:
                resource_lines.append(" — ".join(value for value in (title, snippet) if value))
        if resource_lines:
            parts.append("Resources previously shared: " + "; ".join(resource_lines))

    quiz = assistant_message.get("quiz")
    questions = quiz.get("questions") if isinstance(quiz, dict) else None
    if isinstance(questions, list):
        question_texts = [
            str(item.get("question", "")).strip()
            for item in questions[:10]
            if isinstance(item, dict) and item.get("question")
        ]
        if question_texts:
            parts.append("Quiz questions previously shown: " + "; ".join(question_texts))

    return "\n".join(parts)[:4000] or content


def generate_rag_answer_stream(
    question: str,
    user_id: int,
    notebook_id: int,
    top_k: int = 3,
    conversation_history: list[dict[str, str]] | None = None,
):
    rag_result = query_rag(
        question=question,
        user_id=user_id,
        notebook_id=notebook_id,
        top_k=top_k,
    )

    results = rag_result["results"]

    if not results:
        yield json.dumps({"type": "chunk", "content": "Not in uploaded sources — "}) + "\n"
    context_parts = []

    for index, result in enumerate(results, start=1):
        context_parts.append(
            f"[Source {index}]\n"
            f"Filename: {result['source']}\n"
            f"Chunk: {result['chunk_index']}\n"
            f"Content:\n{result['text']}"
        )

    context = "\n\n".join(context_parts)

    history_parts = []
    for message in (conversation_history or [])[-8:]:
        content = _history_message_text(message)
        if content.strip():
            role = message.get("role", "user")
            history_parts.append(f"{role}: {content}")
    conversation_context = "\n".join(history_parts) or "No earlier conversation."

    user_prompt = f"""
Notebook context:

{context}

Recent conversation for continuity (notebook sources remain authoritative):
{conversation_context}

User question:

{question}

Use the notebook context above when it supports the answer. If it does not, answer from general knowledge
"""

    system_prompt, formatted_user_prompt = _format_rag_prompts(user_prompt)
    for chunk in generate_answer_stream(
        system_prompt=system_prompt,
        user_prompt=formatted_user_prompt,
    ):
        yield json.dumps({
            "type": "chunk",
            "content": chunk,
        }) + "\n"

    sources = [
        {
            "source": result["source"],
            "chunk_index": result["chunk_index"],
        }
        for result in results
    ]

    yield json.dumps({
        "type": "sources",
        "sources": sources,
    }) + "\n"


def generate_rag_answer(
    question: str,
    user_id: int,
    notebook_id: int,
    top_k: int = 3,
) -> dict:
    rag_result = query_rag(
        question=question,
        user_id=user_id,
        notebook_id=notebook_id,
        top_k=top_k,
    )

    results = rag_result["results"]

    context_parts = []

    for index, result in enumerate(results, start=1):
        context_parts.append(
            f"[Source {index}]\n"
            f"Filename: {result['source']}\n"
            f"Chunk: {result['chunk_index']}\n"
            f"Content:\n{result['text']}"
        )

    context = "\n\n".join(context_parts)

    user_prompt = f"""
Notebook context:

{context}

User question:

{question}

Use the notebook context above when it supports the answer. If it does not, answer from general knowledge
"""

    system_prompt, formatted_user_prompt = _format_rag_prompts(user_prompt)
    answer = generate_answer(
        system_prompt=system_prompt,
        user_prompt=formatted_user_prompt,
    )
    if not results:
        answer = "Not in uploaded sources — " + answer

    sources = [
        {
            "source": result["source"],
            "chunk_index": result["chunk_index"],
        }
        for result in results
    ]

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }


# FILE PURPOSE:
# Combines tenant-aware RAG retrieval with Groq to generate
# grounded learning answers, stream responses, and return source metadata.


# FILE PURPOSE:
# Combines tenant-aware RAG retrieval with Groq to generate
# grounded learning answers and return their source metadata.
