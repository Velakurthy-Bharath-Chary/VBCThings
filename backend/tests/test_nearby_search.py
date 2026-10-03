import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.nearby_search import _distance_km, find_nearby_resources, geocode_city, reverse_geocode
from app.api.resources import NearbySearchRequest, search_nearby
from app.main import app


def test_distance_calculation_returns_kilometers():
    assert _distance_km(0, 0, 0, 1) == pytest.approx(111.2, abs=0.2)


def test_overpass_results_are_named_deduplicated_and_sorted_by_distance():
    response = Mock()
    response.json.return_value = {
        "elements": [
            {"type": "node", "id": 2, "lat": 0, "lon": 0.02,
             "tags": {"name": "Far Library", "amenity": "library"}},
            {"type": "way", "id": 3, "center": {"lat": 0, "lon": 0.01},
             "tags": {"name": "Near Library", "amenity": "library", "addr:city": "Example"}},
            {"type": "node", "id": 4, "lat": 0, "lon": 0.005,
             "tags": {"amenity": "library"}},
        ]
    }
    with patch("app.ai.nearby_search.get_cached_value", return_value=None), patch(
        "app.ai.nearby_search.set_cached_value"
    ), patch("app.ai.nearby_search.httpx.post", return_value=response) as post:
        results = find_nearby_resources(0, 0, 2000, "library")

    assert [item["title"] for item in results] == ["Near Library", "Far Library"]
    assert "Example" in results[0]["snippet"]
    assert results[0]["distance_km"] < results[1]["distance_km"]
    assert "around:2000,0,0" in post.call_args.kwargs["data"]["data"]
    assert "User-Agent" in post.call_args.kwargs["headers"]


def test_cached_nearby_results_skip_external_request():
    cached_results = [{"title": "Cached Library", "url": "https://example.test"}]
    with patch(
        "app.ai.nearby_search.get_cached_value",
        return_value=json.dumps(cached_results),
    ), patch("app.ai.nearby_search.httpx.post") as post:
        results = find_nearby_resources(10, 20, 1000, "library")

    assert results == cached_results
    post.assert_not_called()


def test_nearby_route_returns_openstreetmap_attribution():
    results = [{"title": "City Library", "url": "https://www.openstreetmap.org"}]
    with patch("app.api.resources.reverse_geocode", return_value="Test City, Test Region"), patch(
        "app.api.resources.find_nearby_resources", return_value=results,
    ):
        response = search_nearby(
            NearbySearchRequest(latitude=10, longitude=20),
            current_user=SimpleNamespace(id=9),
        )

    assert response["results"] == results
    assert response["attribution"] == "© OpenStreetMap contributors"
    assert response["location_label"] == "Test City, Test Region"


def test_city_search_geocodes_once_then_uses_nearby_search():
    results = [{"title": "City Library", "url": "https://www.openstreetmap.org"}]
    with patch("app.api.resources.geocode_city", return_value=(10.0, 20.0, "Test City, Test Country")) as geocode, patch(
        "app.api.resources.find_nearby_resources", return_value=results,
    ) as nearby:
        response = search_nearby(
            NearbySearchRequest(location=" Test City "),
            current_user=SimpleNamespace(id=9),
        )

    geocode.assert_called_once_with("Test City")
    assert nearby.call_args.kwargs["latitude"] == 10.0
    assert nearby.call_args.kwargs["longitude"] == 20.0
    assert response["location_label"] == "Test City, Test Country"


def test_reverse_geocoding_uses_coarse_cached_location_and_identifying_user_agent(monkeypatch):
    monkeypatch.setattr("app.ai.nearby_search.settings.nominatim_base_url", "https://geo.example")
    response = Mock()
    response.json.return_value = {"address": {
        "city": "Test City", "state": "Test Region", "country": "Test Country",
        "road": "Private Road",
    }}
    with patch("app.ai.nearby_search.get_cached_value", return_value=None), patch(
        "app.ai.nearby_search.set_cached_value"
    ) as cache_write, patch("app.ai.nearby_search.acquire_rate_limit", return_value=True), patch(
        "app.ai.nearby_search.httpx.get", return_value=response,
    ) as upstream:
        label = reverse_geocode(12.34567, 67.89123)

    assert label == "Test City, Test Region, Test Country"
    assert upstream.call_args.args[0] == "https://geo.example/reverse"
    assert upstream.call_args.kwargs["params"]["lat"] == 12.346
    assert upstream.call_args.kwargs["params"]["lon"] == 67.891
    assert "Private Road" not in label
    assert upstream.call_args.kwargs["headers"]["User-Agent"].startswith("VBCThings/")
    assert cache_write.call_args.kwargs["ttl_seconds"] == 86400


def test_city_geocoding_is_cached_and_returns_coordinates(monkeypatch):
    monkeypatch.setattr("app.ai.nearby_search.settings.nominatim_base_url", "https://geo.example")
    response = Mock()
    response.json.return_value = [{
        "lat": "12.5", "lon": "67.5",
        "address": {"town": "Test Town", "country": "Test Country"},
    }]
    with patch("app.ai.nearby_search.get_cached_value", return_value=None), patch(
        "app.ai.nearby_search.set_cached_value"
    ) as cache_write, patch("app.ai.nearby_search.acquire_rate_limit", return_value=True), patch(
        "app.ai.nearby_search.httpx.get", return_value=response,
    ) as upstream:
        result = geocode_city("Test Town")

    assert result == (12.5, 67.5, "Test Town, Test Country")
    assert upstream.call_args.args[0] == "https://geo.example/search"
    assert cache_write.call_args.kwargs["ttl_seconds"] == 86400


def test_nearby_radius_is_bounded():
    with pytest.raises(ValueError):
        NearbySearchRequest(latitude=0, longitude=0, radius_m=50)


def test_nearby_request_requires_exactly_one_search_mode():
    with pytest.raises(ValueError):
        NearbySearchRequest()
    with pytest.raises(ValueError):
        NearbySearchRequest(latitude=0, longitude=0, location="Test City")
    with pytest.raises(ValueError):
        NearbySearchRequest(latitude=0)


def test_nearby_route_requires_authentication():
    response = TestClient(app).post(
        "/resources/nearby",
        json={"latitude": 10, "longitude": 20},
    )

    assert response.status_code in {401, 403}


# FILE PURPOSE:
# Tests nearby-search validation, distance ranking, caching, result handling,
# and required OpenStreetMap attribution without making external requests.
