import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.ai.nearby_search import find_nearby_resources, geocode_city, reverse_geocode
from app.api.auth import get_current_user
from app.models import User


router = APIRouter(prefix="/resources", tags=["Resources"])
logger = logging.getLogger(__name__)


class NearbySearchRequest(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location: str | None = Field(default=None, min_length=2, max_length=160)
    radius_m: int = Field(default=2000, ge=100, le=5000)
    category: Literal["library", "college", "study_space"] = "study_space"

    @model_validator(mode="after")
    def require_location_or_coordinate_pair(self):
        has_coordinates = self.latitude is not None and self.longitude is not None
        has_location = bool(self.location and self.location.strip())
        if (self.latitude is None) != (self.longitude is None) or has_coordinates == has_location:
            raise ValueError("Provide either a city/town or both latitude and longitude.")
        if self.location:
            self.location = self.location.strip()
        return self


@router.post("/nearby")
def search_nearby(
    request: NearbySearchRequest,
    current_user: User = Depends(get_current_user),
):
    location_label = None
    if request.location:
        try:
            geocoded = geocode_city(request.location)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Location lookup is busy. Please retry in a moment.",
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("City geocoding failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="City lookup is temporarily unavailable.",
            ) from exc
        if geocoded is None:
            raise HTTPException(status_code=404, detail="No matching city or town was found.")
        latitude, longitude, location_label = geocoded
    else:
        latitude = request.latitude
        longitude = request.longitude
        try:
            location_label = reverse_geocode(latitude, longitude)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning("Reverse geocoding failed: %s", type(exc).__name__)

    try:
        results = find_nearby_resources(
            latitude=latitude,
            longitude=longitude,
            radius_m=request.radius_m,
            category=request.category,
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Nearby resource search failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nearby resource search is temporarily unavailable.",
        ) from exc

    return {
        "agent": "resource",
        "category": request.category,
        "radius_m": request.radius_m,
        "location_label": location_label,
        "results": results,
        "attribution": "© OpenStreetMap contributors",
        "attribution_url": "https://www.openstreetmap.org/copyright",
    }


# FILE PURPOSE:
# Exposes authenticated, bounded nearby-learning-place searches and
# returns distance-ranked results with OpenStreetMap attribution.
