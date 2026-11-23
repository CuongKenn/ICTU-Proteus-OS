# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Geospatial utilities for PostGIS and NGSI-LD GeoProperty conversions.

Tham chiếu: Issue #825 [L3-203], ETSI GS CIM 009 (NGSI-LD specification).
"""

import math
from typing import Any


def to_geojson_point(longitude: float, latitude: float) -> dict[str, Any]:
    """Convert longitude and latitude to a GeoJSON Point dictionary."""
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"Invalid longitude: {longitude}. Must be in [-180, 180].")
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"Invalid latitude: {latitude}. Must be in [-90, 90].")

    return {
        "type": "Point",
        "coordinates": [float(longitude), float(latitude)],
    }


def to_wkt_point(longitude: float, latitude: float) -> str:
    """Convert longitude and latitude to WKT representation: POINT(lon lat)."""
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"Invalid longitude: {longitude}. Must be in [-180, 180].")
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"Invalid latitude: {latitude}. Must be in [-90, 90].")

    return f"SRID=4326;POINT({longitude} {latitude})"


def to_ngsi_ld_geoproperty(longitude: float, latitude: float) -> dict[str, Any]:
    """Format coordinates as a standard NGSI-LD GeoProperty object."""
    return {
        "type": "GeoProperty",
        "value": to_geojson_point(longitude, latitude),
    }


def parse_ngsi_ld_geoproperty(geo_prop: dict[str, Any]) -> tuple[float, float]:
    """Extract (longitude, latitude) tuple from an NGSI-LD GeoProperty."""
    if not isinstance(geo_prop, dict):
        raise ValueError("Invalid GeoProperty: must be a dict.")

    val = geo_prop.get("value", {})
    if val.get("type") != "Point":
        raise ValueError(
            f"Unsupported geometry type: {val.get('type')}. Expected Point."
        )

    coords = val.get("coordinates")
    if not coords or len(coords) < 2:
        raise ValueError("Coordinates must contain at least [longitude, latitude].")

    lon, lat = float(coords[0]), float(coords[1])
    return lon, lat


def haversine_distance_meters(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """Calculate the great-circle distance between two points on the Earth in meters."""
    earth_radius_m = 6371000.0  # Earth mean radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return earth_radius_m * c
