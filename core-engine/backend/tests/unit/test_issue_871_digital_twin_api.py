# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests cho Issue #871 — NGSI-LD 9 Plugins & API Digital Twin."""

from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.domain.entities import TenantContext
from app.core.use_cases.manifest_validator import (
    _PROHIBITED_NGSI_COLUMNS,
    ManifestValidator,
)
from app.entrypoints.dependencies import get_current_tenant_context
from app.infrastructure.database import get_db_readonly
from main import app


def _load_contract_verifier():
    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "scripts" / "verify_plugin_contracts.py"
    spec = importlib.util.spec_from_file_location(
        "verify_plugin_contracts", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, repo_root


def test_all_9_plugins_pass_ngsi_contract_and_manifest_validator():
    """Cả 9 plugins phải có khối ngsi hợp lệ, không BOM và không lộ cột PII."""
    verifier, repo_root = _load_contract_verifier()
    plugins_root = repo_root / "plugins"

    errors = verifier.verify_all_plugins(plugins_root)
    assert errors == [], f"Plugin contract errors: {errors}"

    validator = ManifestValidator()
    plugin_dirs = sorted(
        p
        for p in plugins_root.iterdir()
        if p.is_dir() and (p / "manifest.yaml").exists()
    )
    assert len(plugin_dirs) == 9

    for plugin_dir in plugin_dirs:
        manifest_path = plugin_dir / "manifest.yaml"
        raw_bytes = manifest_path.read_bytes()
        assert not raw_bytes.startswith(
            b"\xef\xbb\xbf"
        ), f"UTF-8 BOM detected in {manifest_path}"

        entity = validator.validate_yaml_string(raw_bytes.decode("utf-8"))
        assert entity.ngsi is not None, f"{entity.name} missing ngsi block"
        assert len(entity.ngsi.entities) >= 1, f"{entity.name} has empty ngsi.entities"
        for ngsi_ent in entity.ngsi.entities:
            assert ngsi_ent.table in entity.tables
            assert len(ngsi_ent.attributes) >= 1
            for attr in ngsi_ent.attributes:
                assert attr.column.lower() not in _PROHIBITED_NGSI_COLUMNS
                assert attr.target.lower() not in _PROHIBITED_NGSI_COLUMNS


def test_contract_verifier_rejects_missing_ngsi_and_prohibited_pii(tmp_path: Path):
    """Script verify_plugin_contracts bắt được lỗi thiếu ngsi hoặc lộ cột PII."""
    verifier, _ = _load_contract_verifier()

    plugin_dir = tmp_path / "demo-module"
    (plugin_dir / "db").mkdir(parents=True)
    (plugin_dir / "db" / "seed_data.sql").write_text(
        "CREATE TABLE IF NOT EXISTS demo_items ("
        "id UUID PRIMARY KEY, name VARCHAR(100), salary NUMERIC(12,2));",
        encoding="utf-8",
    )

    # 1. Thiếu khối ngsi
    (plugin_dir / "manifest.yaml").write_text(
        "name: demo-module\n"
        "display_name: Demo\n"
        "version: 1.0.0\n"
        "description: Demo\n"
        "author: ICTU\n"
        "license: AGPL-3.0-or-later\n"
        "database:\n"
        "  tables: [demo_items]\n"
        "  seed_file: db/seed_data.sql\n",
        encoding="utf-8",
    )
    missing_errs = verifier.verify_all_plugins(tmp_path)
    assert any("ngsi" in err for err in missing_errs)

    # 2. Chứa cột nhạy cảm salary
    (plugin_dir / "manifest.yaml").write_text(
        "name: demo-module\n"
        "display_name: Demo\n"
        "version: 1.0.0\n"
        "description: Demo\n"
        "author: ICTU\n"
        "license: AGPL-3.0-or-later\n"
        "database:\n"
        "  tables: [demo_items]\n"
        "  seed_file: db/seed_data.sql\n"
        "ngsi:\n"
        "  entities:\n"
        "    - table: demo_items\n"
        "      type: DemoItem\n"
        "      attributes:\n"
        "        - column: salary\n"
        "          target: salary\n",
        encoding="utf-8",
    )
    pii_errs = verifier.verify_all_plugins(tmp_path)
    assert any("salary" in err for err in pii_errs)


@pytest.mark.asyncio
async def test_get_context_entities_zero_risk_ictu_campus_fallback():
    """Khi entity_state rỗng, trả dữ liệu mẫu Khuôn viên số ICTU gắn đúng tenant_id."""
    tid = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tid, user_id=uuid.uuid4(), roles=["tenant_admin"], email="a@ictu.vn"
    )

    mock_session = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_session.execute.return_value = mock_cursor

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db_readonly] = _override_db

    try:
        with patch(
            "app.entrypoints.routers.context.set_session_tenant",
            new_callable=AsyncMock,
        ) as mock_set_tenant:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/context/entities")
                assert resp.status_code == 200
                body = resp.json()

                assert body["source"] == "campus_seed_preview"
                assert body["tenant_id"] == str(tid)
                assert body["total"] == 9
                assert len(body["entities"]) == 9
                mock_set_tenant.assert_awaited_once_with(mock_session, str(tid))

                for ent in body["entities"]:
                    assert ent["tenant_id"] == str(tid)
                    assert f":{tid}:" in ent["entity_id"]
                    assert ent["coordinates"] is not None
                    lon, lat = ent["coordinates"]
                    assert 105.80 <= lon <= 105.82
                    assert 21.58 <= lat <= 21.59
                    assert ent["status_indicator"] in {
                        "normal",
                        "busy",
                        "warning",
                        "critical",
                    }
                    assert "@context" in ent["payload"]

                # Lọc type=Room trên dữ liệu mẫu
                room_resp = await client.get(
                    "/api/v1/context/entities", params={"type": "Room"}
                )
                assert room_resp.status_code == 200
                room_body = room_resp.json()
                assert room_body["source"] == "campus_seed_preview"
                assert room_body["total"] == 1
                assert room_body["entities"][0]["type"] == "Room"

                # Lọc type lệch -> trả danh sách rỗng
                mismatch_resp = await client.get(
                    "/api/v1/context/entities", params={"type": "Spaceship"}
                )
                assert mismatch_resp.status_code == 200
                assert mismatch_resp.json()["entities"] == []

                # Tắt include_demo_fallback -> trả rỗng với source=entity_state
                no_fb_resp = await client.get(
                    "/api/v1/context/entities",
                    params={"include_demo_fallback": "false"},
                )
                assert no_fb_resp.status_code == 200
                assert no_fb_resp.json()["source"] == "entity_state"
                assert no_fb_resp.json()["entities"] == []
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_context_entities_real_data_bbox_relationships_and_tenant_filter():
    """Khi có dữ liệu thật: lọc cứng tenant_id, bbox PostGIS, ẩn PII, trích quan hệ."""
    tid = uuid.uuid4()
    other_tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["user"])

    entity_urn = f"urn:ngsi-ld:Ticket:{tid}:tkt-001"
    asset_urn = f"urn:ngsi-ld:Asset:{tid}:srv-01"
    foreign_urn = f"urn:ngsi-ld:Asset:{other_tid}:foreign-asset"

    payload = {
        "id": entity_urn,
        "type": "Ticket",
        "title": {"type": "Property", "value": "Sự cố máy chủ C6"},
        "priority": {"type": "Property", "value": "P1"},
        "status": {"type": "Property", "value": "OPEN"},
        "salary": {"type": "Property", "value": 99999999},
        "relatedAsset": {"type": "Relationship", "object": asset_urn},
        "leakedLink": {"type": "Relationship", "object": foreign_urn},
        "assignee_id": "emp-42",
    }
    geojson_str = json.dumps({"type": "Point", "coordinates": [105.8059, 21.5848]})

    mock_session = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (
            tid,
            entity_urn,
            "Ticket",
            json.dumps(payload),
            geojson_str,
            datetime.now(UTC),
        )
    ]
    mock_session.execute.return_value = mock_cursor

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db_readonly] = _override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/context/entities",
                params={
                    "type": "Ticket",
                    "q": "máy chủ",
                    "bbox": "105.8000,21.5800,105.8100,21.5900",
                    "limit": 50,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "entity_state"
            assert data["total"] == 1

            ent = data["entities"][0]
            assert ent["entity_id"] == entity_urn
            assert ent["coordinates"] == [105.8059, 21.5848]
            assert ent["status_indicator"] == "critical"
            assert "salary" not in ent["payload"]

            rel_targets = {r["target"] for r in ent["relationships"]}
            assert asset_urn in rel_targets
            assert f"urn:ngsi-ld:Employee:{tid}:emp-42" in rel_targets
            # Tuyệt đối không lộ quan hệ sang tenant khác
            assert foreign_urn not in rel_targets

            # Kiểm tra câu SQL có lọc cứng tenant_id và ST_Intersects + ST_MakeEnvelope
            sql_calls = [
                (str(c.args[0]), c.args[1] if len(c.args) > 1 else {})
                for c in mock_session.execute.call_args_list
                if "context.entity_state" in str(c.args[0])
            ]
            assert len(sql_calls) == 1
            stmt_str, bound_params = sql_calls[0]
            assert "WHERE tenant_id = :tenant_id" in stmt_str
            assert "ST_Intersects" in stmt_str
            assert "ST_MakeEnvelope" in stmt_str
            assert bound_params["tenant_id"] == tid
            assert bound_params["min_lon"] == 105.8
            assert bound_params["max_lat"] == 21.59
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_context_entities_rejects_invalid_bbox():
    """Validate chặt biên kinh/vĩ độ và định dạng 4 số thực cho tham số bbox."""
    tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["user"])
    mock_session = AsyncMock()

    async def _override_db():
        yield mock_session

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db_readonly] = _override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for bad_bbox in (
                "105.8,21.5",
                "a,b,c,d",
                "-190,20,105,22",
                "105,-95,106,22",
                "106.0,21.5,105.0,21.6",
                "105.0,22.0,106.0,21.0",
            ):
                resp = await client.get(
                    "/api/v1/context/entities", params={"bbox": bad_bbox}
                )
                assert resp.status_code == 400, f"Expected 400 for bbox={bad_bbox}"
    finally:
        app.dependency_overrides.clear()
