import re
from urllib.parse import urlparse

from app.agents.resource import ResourceResult, ResourceSearchError
from app.config import settings
from app.ai.llm import _client


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def search_with_groq(query: str, max_results: int = 5) -> list[ResourceResult]:
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty.")
    try:
        response = _client().chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Research the user's request using browser search. "
                        "Return a concise answer and cite sources as Markdown links "
                        "with a short factual snippet for each source."
                    ),
                },
                {"role": "user", "content": query.strip()},
            ],
            tools=[{"type": "browser_search"}],
            tool_choice="required",
            temperature=0.2,
        )
    except Exception as exc:
        raise ResourceSearchError(
            "Groq web search is currently unavailable. Check that the configured Groq model supports browser search."
        ) from exc

    message = response.choices[0].message
    content = (message.content or "").strip()
    results: list[ResourceResult] = []
    seen: set[str] = set()

    # The browser-search model may return source links inline in its answer.
    for title, url in _LINK_PATTERN.findall(content):
        if url in seen or urlparse(url).scheme not in {"http", "https"}:
            continue
        seen.add(url)
        results.append(ResourceResult(title=title[:300], url=url, snippet=content[:600]))
        if len(results) >= max_results:
            break

    # Some Groq response versions expose raw executed search results.
    for tool in getattr(message, "executed_tools", None) or []:
        payload = tool if isinstance(tool, dict) else getattr(tool, "model_dump", lambda: {})()
        raw_results = payload.get("search_results", [])
        if isinstance(raw_results, dict):
            raw_results = raw_results.get("results", [])
        for item in raw_results:
            item = item if isinstance(item, dict) else getattr(item, "model_dump", lambda: {})()
            url = str(item.get("url") or "")
            if url in seen or urlparse(url).scheme not in {"http", "https"}:
                continue
            seen.add(url)
            results.append(ResourceResult(
                title=str(item.get("title") or url)[:300],
                url=url,
                snippet=str(item.get("content") or item.get("snippet") or "")[:600],
            ))
            if len(results) >= max_results:
                break

    if not results and content:
        results.append(ResourceResult(title="Web search summary", url="", snippet=content[:600]))
    return results[:max_results]


def create_groq_resource_agent():
    from app.agents.resource import ResourceAgent
    return ResourceAgent(search_provider=search_with_groq)
