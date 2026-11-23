# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Layer 3 migrations, PostGIS schema, Geo utils, and RLS policies."""

import importlib.util
from pathlib import Path
import pytest

from app.core.domain.geo_utils import (
    to_geojson_point,
    to_wkt_point,
    to_ngsi_ld_geoproperty,
    parse_ngsi_ld_geoproperty,
    haversine_distance_meters,
)


def test_geo_utils_geojson_and_wkt():
    lon, lat = 105.804817, 21.028511
    geojson = to_geojson_point(lon, lat)
    assert geojson == {"type": "Point", "coordinates": [lon, lat]}

    wkt = to_wkt_point(lon, lat)
    assert wkt == "SRID=4326;POINT(105.804817 21.028511)"

    ngsi_geo = to_ngsi_ld_geoproperty(lon, lat)
    assert ngsi_geo["type"] == "GeoProperty"
    assert ngsi_geo["value"]["type"] == "Point"
    assert ngsi_geo["value"]["coordinates"] == [lon, lat]

    parsed_lon, parsed_lat = parse_ngsi_ld_geoproperty(ngsi_geo)
    assert parsed_lon == pytest.approx(lon)
    assert parsed_lat == pytest.approx(lat)


def test_geo_utils_haversine_distance():
    # Hanoi: (105.804817, 21.028511)
    # Thai Nguyen (ICTU): (105.8038, 21.5853)
    dist = haversine_distance_meters(105.804817, 21.028511, 105.8038, 21.5853)
    # Khoảng cách xấp xỉ 61-63 km
    assert 60000 <= dist <= 64000


def test_geo_utils_invalid_bounds():
    with pytest.raises(ValueError, match="Invalid longitude"):
        to_geojson_point(190.0, 10.0)

    with pytest.raises(ValueError, match="Invalid latitude"):
        to_geojson_point(100.0, 95.0)


def test_migration_postgis_and_context_schema():
    versions_dir = Path(__file__).parents[2] / "migrations" / "versions"
    assert versions_dir.exists()

    postgis_migration = list(versions_dir.glob("*_enable_postgis_extension.py"))
    assert len(postgis_migration) == 1
    postgis_path = postgis_migration[0]

    context_migration = list(versions_dir.glob("*_create_context_schema_and_tables.py"))
    assert len(context_migration) == 1
    context_path = context_migration[0]

    # Verify postgis migration revisions
    spec_postgis = importlib.util.spec_from_file_location("postgis_mod", postgis_path)
    postgis_mod = importlib.util.module_from_spec(spec_postgis)
    spec_postgis.loader.exec_module(postgis_mod)
    assert postgis_mod.revision == "m7h8i9j0k1l2"
    assert postgis_mod.down_revision == "l6g7h8i9j0k1"

    # Verify context tables migration revisions
    spec_context = importlib.util.spec_from_file_location("context_mod", context_path)
    context_mod = importlib.util.module_from_spec(spec_context)
    spec_context.loader.exec_module(context_mod)
    assert context_mod.revision == "n8i9j0k1l2m3"
    assert context_mod.down_revision == "m7h8i9j0k1l2"


def test_init_sql_contains_layer3_schema_and_rls():
    repo_root = Path(__file__).parents[4]
    init_sql_path = repo_root / "deploy" / "postgres" / "init.sql"
    assert init_sql_path.exists()

    content = init_sql_path.read_text(encoding="utf-8")

    # PostGIS extension
    assert 'CREATE EXTENSION IF NOT EXISTS "postgis";' in content

    # Schema context
    assert "CREATE SCHEMA IF NOT EXISTS context;" in content

    # Tables in schema context
    assert "CREATE TABLE IF NOT EXISTS context.context_outbox" in content
    assert "CREATE TABLE IF NOT EXISTS context.entity_state" in content
    assert "CREATE TABLE IF NOT EXISTS context.sync_cursor" in content
    assert "CREATE TABLE IF NOT EXISTS context.subscriptions" in content

    # Spatial column and GiST index
    assert (
        "location        GEOGRAPHY(Point, 4326)" in content
        or "location geography(Point, 4326)" in content
    )
    assert "USING GIST (location)" in content

    # RLS checks on context tables
    context_tables = [
        "context.context_outbox",
        "context.entity_state",
        "context.sync_cursor",
        "context.subscriptions",
    ]
    for tbl in context_tables:
        assert f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;" in content
        assert f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;" in content

    # Check Hasura user session variable integration
    assert "hasura.user" in content
    assert "x-hasura-tenant-id" in content
