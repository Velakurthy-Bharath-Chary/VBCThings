from app.agents.resource import ResourceAgent, ResourceResult


def fake_search(
    query: str,
    max_results: int = 5,
) -> list[ResourceResult]:
    return [
        ResourceResult(
            title="Python Documentation",
            url="https://python.org",
            snippet=f"Search result for {query}",
        )
    ]


def test_resource_agent_rejects_empty_query():
    agent = ResourceAgent(fake_search)

    try:
        agent.search("")
        assert False
    except ValueError as exc:
        assert str(exc) == "Search query cannot be empty."


def test_resource_agent_uses_search_provider():
    agent = ResourceAgent(fake_search)

    results = agent.search("Python 3.14")

    assert len(results) == 1
    assert results[0].title == "Python Documentation"
    assert results[0].url == "https://python.org"
    assert results[0].snippet == "Search result for Python 3.14"

def test_resource_agent_deduplicates_and_limits_results():
    def fake_multiple_results(
        query: str,
        max_results: int = 5,
    ) -> list[ResourceResult]:
        return [
            ResourceResult(
                title="One",
                url="https://example.com/1",
                snippet="First",
            ),
            ResourceResult(
                title="One duplicate",
                url="https://example.com/1",
                snippet="Duplicate",
            ),
            ResourceResult(
                title="Two",
                url="https://example.com/2",
                snippet="Second",
            ),
            ResourceResult(
                title="Three",
                url="https://example.com/3",
                snippet="Third",
            ),
            ResourceResult(
                title="Four",
                url="https://example.com/4",
                snippet="Fourth",
            ),
            ResourceResult(
                title="Five",
                url="https://example.com/5",
                snippet="Fifth",
            ),
            ResourceResult(
                title="Six",
                url="https://example.com/6",
                snippet="Sixth",
            ),
        ]

    agent = ResourceAgent(fake_multiple_results)

    results = agent.search(
        "latest Python news",
        max_results=5,
    )

    assert len(results) == 5

    assert [result.url for result in results] == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
        "https://example.com/4",
        "https://example.com/5",
    ]
# FILE PURPOSE:
# Tests Resource Agent validation and provider integration.