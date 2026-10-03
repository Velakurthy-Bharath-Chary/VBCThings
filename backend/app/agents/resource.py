from dataclasses import dataclass
from typing import Callable


class ResourceSearchError(RuntimeError):
    """A safe, user-presentable message for external search failures."""


@dataclass
class ResourceResult:
    title: str
    url: str
    snippet: str


class ResourceAgent:
    """
    Provider-independent interface for external web intelligence.
    """

    def __init__(
        self,
        search_provider: Callable[
            [str, int],
            list[ResourceResult],
        ],
    ):
        self.search_provider = search_provider

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[ResourceResult]:
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if max_results <= 0:
            raise ValueError(
                "max_results must be greater than 0."
            )

        results = self.search_provider(
            query.strip(),
            max_results,
        )

        # Deduplicate by URL.
        unique_results = []
        seen_urls = set()

        for result in results:
            if result.url in seen_urls:
                continue

            seen_urls.add(result.url)
            unique_results.append(result)

            if len(unique_results) >= max_results:
                break

        return unique_results


# FILE PURPOSE:
# Provides a provider-independent external intelligence agent.
# Validates queries, limits results, and removes duplicate URLs.
