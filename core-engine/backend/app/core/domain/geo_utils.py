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


def parse_ngsi_ld_geoproperty(geo_prop: Any) -> tuple[float, float] | None:
    """Extract (lon, lat) tuple from an NGSI-LD GeoProperty, or None if invalid."""
    if not isinstance(geo_prop, dict):
        return None

    val = geo_prop.get("value")
    if not isinstance(val, dict) or val.get("type") != "Point":
        return None

    coords = val.get("coordinates")
    if not isinstance(coords, list | tuple) or len(coords) < 2:
        return None

    raw_lon, raw_lat = coords[0], coords[1]
    if (
        isinstance(raw_lon, bool)
        or isinstance(raw_lat, bool)
        or not isinstance(raw_lon, int | float)
        or not isinstance(raw_lat, int | float)
    ):
        return None

    lon, lat = float(raw_lon), float(raw_lat)
    if not (math.isfinite(lon) and math.isfinite(lat)):
        return None
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        return None

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
