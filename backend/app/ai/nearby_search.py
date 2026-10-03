import hashlib
import json
import math
from urllib.parse import urljoin

import httpx

from app.config import settings
from app.core.memory_cache import acquire_rate_limit, get_cached_value, set_cached_value


DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_USER_AGENT = "VBCThings/0.1 (educational resource discovery)"
CATEGORY_TAGS = {
    "library": '"amenity"="library"',
    "college": '"amenity"~"^(university|college)$"',
    "study_space": '"amenity"~"^(library|university|college|community_centre)$"',
}


def _nominatim_request(path: str, params: dict) -> dict | list:
    if not acquire_rate_limit("upstream:nominatim", interval_seconds=1):
        raise RuntimeError("Location lookup is busy. Please retry in a moment.")
    base_url = settings.nominatim_base_url or DEFAULT_NOMINATIM_BASE_URL
    response = httpx.get(
        urljoin(base_url.rstrip("/") + "/", path.lstrip("/")),
        params=params,
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=httpx.Timeout(10.0, connect=3.0),
    )
    response.raise_for_status()
    return response.json()


def _area_label(address: dict) -> str | None:
    locality = next((
        address.get(key)
        for key in ("city", "town", "village", "municipality", "county")
        if address.get(key)
    ), None)
    region = address.get("state") or address.get("region")
    country = address.get("country")
    parts = list(dict.fromkeys(part for part in (locality, region, country) if part))
    return ", ".join(parts) if parts else None


def reverse_geocode(latitude: float, longitude: float) -> str | None:
    """Resolve coordinates to a coarse area label without retaining the location."""
    rounded_latitude = round(latitude, 3)
    rounded_longitude = round(longitude, 3)
    cache_key = "reverse-geocode:" + hashlib.sha256(
        f"{rounded_latitude:.3f}:{rounded_longitude:.3f}".encode("ascii")
    ).hexdigest()
    cached = get_cached_value(cache_key)
    if cached:
        return cached or None

    result = _nominatim_request("reverse", {
        "lat": rounded_latitude,
        "lon": rounded_longitude,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 10,
        "accept-language": "en",
    })
    label = _area_label(result.get("address") or {}) if isinstance(result, dict) else None
    if label:
        set_cached_value(cache_key, label, ttl_seconds=86400)
    return label


def geocode_city(location: str) -> tuple[float, float, str] | None:
    """Resolve an explicit city/town search to coordinates and a coarse label."""
    normalized = " ".join(location.split()).casefold()
    cache_key = "forward-geocode:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cached = get_cached_value(cache_key)
    if cached:
        try:
            value = json.loads(cached)
            return float(value["latitude"]), float(value["longitude"]), value["label"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    results = _nominatim_request("search", {
        "q": location.strip(),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "accept-language": "en",
    })
    if not isinstance(results, list) or not results:
        return None
    result = results[0]
    try:
        latitude = float(result["lat"])
        longitude = float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    label = _area_label(result.get("address") or {}) or location.strip()
    set_cached_value(
        cache_key,
        json.dumps({"latitude": latitude, "longitude": longitude, "label": label}),
        ttl_seconds=86400,
    )
    return latitude, longitude, label


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


def find_nearby_resources(
    latitude: float,
    longitude: float,
    radius_m: int,
    category: str,
) -> list[dict]:
    if category not in CATEGORY_TAGS:
        raise ValueError("Unsupported nearby resource category.")

    cache_material = f"{latitude:.3f}:{longitude:.3f}:{radius_m}:{category}"
    cache_key = "nearby-search:" + hashlib.sha256(
        cache_material.encode("utf-8")
    ).hexdigest()
    cached = get_cached_value(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    query = (
        "[out:json][timeout:20];("
        f"nwr(around:{radius_m},{latitude},{longitude})[{CATEGORY_TAGS[category]}];"
        ");out center tags;"
    )
    endpoint = settings.overpass_api_url or DEFAULT_OVERPASS_URL
    response = httpx.post(
        endpoint,
        data={"data": query},
        headers={
            "User-Agent": "AgenticLearningAssistant/0.1 (nearby educational resources)",
        },
        timeout=httpx.Timeout(25.0, connect=5.0),
    )
    response.raise_for_status()
    elements = response.json().get("elements", [])

    results = []
    seen = set()
    for element in elements:
        tags = element.get("tags") or {}
        name = (tags.get("name") or "").strip()
        center = element.get("center") or element
        place_lat = center.get("lat")
        place_lon = center.get("lon")
        identity = (element.get("type"), element.get("id"))
        if not name or place_lat is None or place_lon is None or identity in seen:
            continue
        seen.add(identity)
        distance_km = _distance_km(latitude, longitude, place_lat, place_lon)
        map_url = (
            "https://www.openstreetmap.org/?mlat="
            f"{place_lat}&mlon={place_lon}#map=17/{place_lat}/{place_lon}"
        )
        resource_type = tags.get("amenity", "learning resource").replace("_", " ")
        address_parts = [
            tags.get("addr:street"),
            tags.get("addr:city"),
        ]
        address = ", ".join(part for part in address_parts if part)
        results.append({
            "title": name,
            "url": map_url,
            "snippet": f"{resource_type.title()} · {distance_km:.1f} km away"
            + (f" · {address}" if address else ""),
            "distance_km": round(distance_km, 2),
            "latitude": place_lat,
            "longitude": place_lon,
        })

    results.sort(key=lambda item: item["distance_km"])
    results = results[:20]
    set_cached_value(cache_key, json.dumps(results), ttl_seconds=900)
    return results


# FILE PURPOSE:
# Geocodes explicit nearby-learning searches and queries OpenStreetMap Overpass,
# caches coarse results, and avoids retaining precise user locations.
