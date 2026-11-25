# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for GitHub Issues #879, #880, #881, #884, #885, and #887."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.adapters.external.orion_adapter import OrionAdapterError
from app.ai.plugin_synthesizer import PluginSynthesizer
from app.core.domain.entities import TenantContext
from app.core.domain.exceptions import DSLInvalidParametersError
from app.core.dynamic_loader import DynamicPluginLoader
from app.core.use_cases.manifest_validator import (
    PROHIBITED_NGSI_COLUMNS,
    ManifestValidator,
)
from app.entrypoints.dependencies import (
    get_current_tenant_context,
    get_db_readonly,
    get_llm_port,
    get_role_repo,
)
from app.infrastructure.database import Base
from main import app

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
SDK_DIR = REPO_ROOT / "sdk"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from proteus_sdk.cli import (  # noqa: E402
    PROHIBITED_NGSI_COLUMNS as SDK_PROHIBITED_NGSI_COLUMNS,
)
from proteus_sdk.cli import (  # noqa: E402
    init_plugin,
    validate_plugin,
)

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #879: Database Schema Sync, env.py PostGIS Filter, Migration & init.sql
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_879_alembic_env_include_object_filters_postgis_and_non_public():
    """migrations/env.py include_object ignores PostGIS/Tiger/Topology & non-public schemas."""
    env_path = BACKEND_ROOT / "migrations" / "env.py"
    content = env_path.read_text(encoding="utf-8")
    assert "def include_object(" in content
    assert "include_object=include_object" in content

    # Extract and evaluate _IGNORED_SCHEMAS, _IGNORED_EXTENSION_TABLES, include_object
    ns: dict = {}
    start_idx = content.index("_IGNORED_SCHEMAS")
    end_idx = content.index("def run_migrations_offline")
    exec(content[start_idx:end_idx], ns)  # noqa: S102
    include_object = ns["include_object"]

    for ext_tbl in (
        "spatial_ref_sys",
        "geometry_columns",
        "geography_columns",
        "addr",
        "edges",
        "faces",
        "topology",
        "layer",
        "zip_lookup_all",
    ):
        fake_tbl = SimpleNamespace(schema=None, name=ext_tbl)
        assert include_object(fake_tbl, ext_tbl, "table", True, None) is False
        fake_idx = SimpleNamespace(schema=None, table=fake_tbl)
        assert include_object(fake_idx, f"idx_{ext_tbl}", "index", True, None) is False

    for ext_schema in ("tiger", "tiger_data", "topology", "context"):
        schema_tbl = SimpleNamespace(schema=ext_schema, name="some_table")
        assert include_object(schema_tbl, "some_table", "table", True, None) is False

    for core_tbl in (
        "tenants",
        "users",
        "plugins",
        "ai_commands",
        "audit_logs",
        "ai_sessions",
        "ai_messages",
        "plugin_schema_migrations",
    ):
        real_tbl = SimpleNamespace(schema=None, name=core_tbl)
        assert include_object(real_tbl, core_tbl, "table", False, None) is True


def test_issue_879_migration_q1l2m3n4o5p6_and_init_sql_complete():
    """Verify q1l2m3n4o5p6 migration & init.sql cover all schema, RLS, and trigger fixes."""
    mig_path = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / "q1l2m3n4o5p6_sync_schema_and_rls_fixes.py"
    )
    assert mig_path.exists()
    spec = importlib.util.spec_from_file_location("q1l2m3n4o5p6", mig_path)
    assert spec and spec.loader
    mig_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig_mod)

    assert mig_mod.revision == "q1l2m3n4o5p6"
    assert mig_mod.down_revision == "p0k1l2m3n4o5"

    mig_text = mig_path.read_text(encoding="utf-8")
    for snippet in (
        "ADD COLUMN IF NOT EXISTS raw_input TEXT",
        "ADD COLUMN IF NOT EXISTS parsed_dsl JSONB",
        "ADD COLUMN IF NOT EXISTS details JSONB",
        "ALTER TABLE plugins ALTER COLUMN category SET NOT NULL",
        "users_tenant_id_email_key",
        "user_roles_user_role_key",
        "ix_ai_sessions_id",
        "ix_ai_sessions_deleted_at",
        "ix_ai_messages_id",
        "ix_ai_messages_deleted_at",
        "plugin_schema_migrations_tenant_id_fkey",
        "plugin_schema_migrations_plugin_id_fkey",
        "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid",
        "SECURITY DEFINER SET search_path = context, public, pg_temp",
        "PERFORM set_config('app.current_tenant_id', v_tenant_id::text, true)",
    ):
        assert snippet in mig_text, f"Missing '{snippet}' in q1l2m3n4o5p6"

    init_sql = (REPO_ROOT / "deploy" / "postgres" / "init.sql").read_text(
        encoding="utf-8"
    )
    for snippet in (
        "mattermost_user_id VARCHAR(255)",
        "CREATE TABLE IF NOT EXISTS ai_sessions",
        "CREATE TABLE IF NOT EXISTS ai_messages",
        "tenant_isolation_policy_ai_sessions",
        "tenant_isolation_policy_ai_messages",
        "SECURITY DEFINER SET search_path = context, public, pg_temp",
        "PERFORM set_config('app.current_tenant_id', v_tenant_id::text, true)",
        "VALUES ('q1l2m3n4o5p6')",
    ):
        assert snippet in init_sql, f"Missing '{snippet}' in deploy/postgres/init.sql"

    # Ensure obsolete NOT NULL columns session_id / dsl_payload are absent from ai_commands
    ai_cmd_section = init_sql.split("CREATE TABLE IF NOT EXISTS ai_commands")[1].split(
        ");"
    )[0]
    assert "session_id" not in ai_cmd_section
    assert "dsl_payload" not in ai_cmd_section
    assert "raw_input" in ai_cmd_section
    assert "parsed_dsl" in ai_cmd_section

    # Verify ORM metadata includes composite index on plugin_schema_migrations
    psm_table = Base.metadata.tables["plugin_schema_migrations"]
    idx_names = {idx.name for idx in psm_table.indexes}
    assert "idx_plugin_schema_migrations_tenant_plugin" in idx_names
    assert "ix_plugin_schema_migrations_tenant_id" in idx_names
    assert "ix_plugin_schema_migrations_plugin_id" in idx_names


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #880: PluginSynthesizer & DynamicPluginLoader Security + Blueprint API
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_880_plugins_dir_resolution_on_non_docker():
    """Both PluginSynthesizer & DynamicPluginLoader resolve repo_root/plugins accurately."""
    expected_plugins_dir = (REPO_ROOT / "plugins").resolve()
    with patch("app.infrastructure.config.settings.PLUGINS_DIR", "/plugins"):
        synth = PluginSynthesizer()
        loader = DynamicPluginLoader(FastAPI())
        if not Path("/plugins").exists():
            assert synth._plugins_dir == expected_plugins_dir
            assert loader._plugins_dir == expected_plugins_dir


@pytest.mark.asyncio
async def test_issue_880_synthesizer_blocks_overwrite_strips_rce_and_sanitizes(
    tmp_path: Path,
):
    """Synthesizer blocks existing/official overwrite, strips main.py, and sanitizes manifest."""
    mock_llm = AsyncMock()

    # 1. Attempt to overwrite official hr-module -> blocked even if directory doesn't exist in tmp_path
    mock_llm.ainvoke.return_value = SimpleNamespace(
        content=json.dumps(
            {
                "code_name": "hr-module",
                "manifest_yaml": "name: hr-module\n",
                "seed_sql": "CREATE TABLE hr_items (id UUID PRIMARY KEY);",
            }
        )
    )
    synth = PluginSynthesizer(llm=mock_llm)
    synth._plugins_dir = tmp_path
    with pytest.raises(ValueError, match="đã tồn tại"):
        await synth.synthesize("overwrite hr-module")

    # 2. Attempt to overwrite an existing custom directory -> blocked
    existing_dir = tmp_path / "lab-custom-module"
    existing_dir.mkdir()
    (existing_dir / "manifest.yaml").write_text("name: lab-custom-module\n")
    mock_llm.ainvoke.return_value = SimpleNamespace(
        content=json.dumps(
            {
                "code_name": "lab-custom-module",
                "manifest_yaml": "name: lab-custom-module\n",
                "seed_sql": "",
            }
        )
    )
    with pytest.raises(ValueError, match="đã tồn tại"):
        await synth.synthesize("overwrite lab-custom-module")

    # 3. Malicious LLM output trying to set is_official=true, reviewed=true, compatibility.proteus,
    #    and python_main RCE payload -> sanitized to declarative-only untrusted draft!
    mock_llm.ainvoke.return_value = SimpleNamespace(
        content=json.dumps(
            {
                "code_name": "clinic-ops-module",
                "manifest_yaml": (
                    "name: wrong-name\n"
                    "display_name: Clinic Ops\n"
                    "version: '1.0.0'\n"
                    "description: Clinic module\n"
                    "author: Attacker\n"
                    "license: AGPL-3.0-or-later\n"
                    "is_official: true\n"
                    "reviewed: true\n"
                    "compatibility:\n"
                    "  proteus: '>=1.0.0'\n"
                    "database:\n"
                    "  tables:\n"
                    "    - name: clinic_items\n"
                    "      description: Clinic table\n"
                ),
                "seed_sql": (
                    "CREATE TABLE IF NOT EXISTS clinic_items ("
                    "id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), "
                    "name VARCHAR(255) NOT NULL, description TEXT);"
                ),
                "python_main": "import os; os.system('whoami')",
            }
        )
    )
    code_name = await synth.synthesize("Tạo phân hệ phòng khám")
    assert code_name == "clinic-ops-module"

    gen_dir = tmp_path / "clinic-ops-module"
    assert not (
        gen_dir / "main.py"
    ).exists(), "RCE vector main.py must NEVER be written"

    parsed_manifest = yaml.safe_load(
        (gen_dir / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert parsed_manifest["name"] == "clinic-ops-module"
    assert parsed_manifest["is_official"] is False
    assert parsed_manifest["synthesized"] is True
    assert parsed_manifest["reviewed"] is False
    assert parsed_manifest["compatibility"]["proteus_os_min_version"] == "1.0.0"
    assert "proteus" not in parsed_manifest["compatibility"]
    assert parsed_manifest["database"]["tables"] == ["clinic_items"]

    # Validate generated manifest passes both ManifestValidator and SDK validate_plugin
    ManifestValidator().validate_yaml_string(
        (gen_dir / "manifest.yaml").read_text(encoding="utf-8")
    )
    val_code, val_errs = validate_plugin(gen_dir)
    assert val_code == 0, f"SDK validation errors: {val_errs}"

    assert synth.last_result is not None
    assert synth.last_result["code_name"] == "clinic-ops-module"
    assert "proteus_os_min_version" in synth.last_result["manifest_yaml"]
    assert "CREATE TABLE" in synth.last_result["seed_sql"]


def test_issue_880_dynamic_loader_blocks_synthesized_even_with_spoofed_official_or_sig(
    tmp_path: Path,
):
    """DynamicPluginLoader._is_plugin_trusted rejects unreviewed synthesized plugins unconditionally."""
    loader = DynamicPluginLoader(FastAPI())
    loader._plugins_dir = tmp_path

    spoof_dir = tmp_path / "spoof-synth"
    spoof_dir.mkdir()
    (spoof_dir / "main.py").write_text("def register_plugin(app): pass\n")
    (spoof_dir / ".signature").write_text("forged-signature")
    (spoof_dir / "manifest.yaml").write_text(
        "name: spoof-synth\n"
        "synthesized: true\n"
        "is_official: true\n"
        "reviewed: 'yes'\n",
        encoding="utf-8",
    )

    assert loader._is_plugin_trusted(spoof_dir) is False
    assert loader.load_plugin("spoof-synth") is False

    # Only strictly boolean `reviewed: true` allows loading after human review
    (spoof_dir / "manifest.yaml").write_text(
        "name: spoof-synth\nsynthesized: true\nreviewed: true\n",
        encoding="utf-8",
    )
    assert loader._is_plugin_trusted(spoof_dir) is True


@pytest.mark.asyncio
async def test_issue_880_synthesize_endpoint_returns_blueprint_and_409_on_duplicate(
    tmp_path: Path,
):
    """POST /api/v1/plugins/synthesize returns manifest_yaml & seed_sql, and 409 on overwrite."""
    tid = uuid.uuid4()
    admin_ctx = TenantContext(
        tenant_id=tid, user_id=uuid.uuid4(), roles=["tenant_admin"]
    )
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["plugins.install"]

    app.dependency_overrides[get_current_tenant_context] = lambda: admin_ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_llm_port] = lambda: None

    try:
        with patch.object(
            PluginSynthesizer,
            "__init__",
            lambda self, llm=None: (
                setattr(self, "_plugins_dir", tmp_path)
                or setattr(self, "llm", None)
                or setattr(self, "last_result", None)
            ),
        ):
            transport = ASGITransport(app=app, client=("198.51.100.88", 12345))
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                r1 = await client.post(
                    "/api/v1/plugins/synthesize",
                    json={"prompt": "Tạo plugin bệnh viện thông minh"},
                )
                assert r1.status_code == 200
                body = r1.json()
                assert body["plugin_code_name"] == "hospital-module"
                assert body["status"] == "pending_review"
                assert "proteus_os_min_version" in body["manifest_yaml"]
                assert "CREATE TABLE IF NOT EXISTS hospital_items" in body["seed_sql"]

                # Second call with same target must return 409 Conflict (no overwrite)
                r2 = await client.post(
                    "/api/v1/plugins/synthesize",
                    json={"prompt": "Tạo plugin bệnh viện thông minh"},
                )
                assert r2.status_code == 409
    finally:
        app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #881: Context Entity Detail (PostGIS + PII + Seed Fallback) & Subscriptions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_881_get_context_entity_sanitizes_pii_extracts_geo_and_seed_fallback():
    """GET /api/v1/context/entities/{id} strips PII, parses GeoJSON, and falls back to campus seed."""
    tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["user"])
    entity_urn = f"urn:ngsi-ld:Room:{tid}:room-lab-1"
    asset_urn = f"urn:ngsi-ld:Asset:{tid}:proj-1"

    mock_db = AsyncMock()
    db_row_cursor = MagicMock()
    db_row_cursor.fetchone.return_value = (
        tid,
        entity_urn,
        "Room",
        json.dumps(
            {
                "name": {"type": "Property", "value": "Phòng Lab AI"},
                "status": {"type": "Property", "value": "IN_USE"},
                "salary": {"type": "Property", "value": 50000000},
                "cccd": {"type": "Property", "value": "001200012345"},
                "hasAsset": {"type": "Relationship", "object": asset_urn},
            }
        ),
        json.dumps({"type": "Point", "coordinates": [105.8065, 21.5851]}),
        datetime.now(UTC),
    )
    empty_cursor = MagicMock()
    empty_cursor.fetchone.return_value = None

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db_readonly] = lambda: mock_db

    try:
        with patch(
            "app.entrypoints.routers.context.set_session_tenant",
            new_callable=AsyncMock,
        ) as mock_set_tenant:
            transport = ASGITransport(app=app, client=("198.51.100.88", 12345))
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # 1. Real DB entity: strips PII, parses ST_AsGeoJSON, includes relationships
                mock_db.execute.return_value = db_row_cursor
                r_real = await client.get(f"/api/v1/context/entities/{entity_urn}")
                assert r_real.status_code == 200
                data = r_real.json()
                assert data["source"] == "entity_state"
                assert data["coordinates"] == [105.8065, 21.5851]
                assert data["status_indicator"] == "busy"
                assert "salary" not in data["payload"]
                assert "cccd" not in data["payload"]
                assert any(rel["target"] == asset_urn for rel in data["relationships"])
                mock_set_tenant.assert_awaited_with(mock_db, str(tid))
                sql_str = str(mock_db.execute.call_args.args[0])
                assert "ST_AsGeoJSON(location::geometry)" in sql_str

                # 2. Campus preview seed fallback when DB has no row
                mock_db.execute.return_value = empty_cursor
                seed_urn = f"urn:ngsi-ld:Building:{tid}:ictu-c1"
                r_seed = await client.get(f"/api/v1/context/entities/{seed_urn}")
                assert r_seed.status_code == 200
                seed_body = r_seed.json()
                assert seed_body["source"] == "campus_seed_preview"
                assert seed_body["entity_id"] == seed_urn
                assert seed_body["coordinates"] == [105.8064, 21.5850]

                # 3. Unknown entity still returns 404
                r_missing = await client.get(
                    f"/api/v1/context/entities/urn:ngsi-ld:Building:{tid}:unknown-999"
                )
                assert r_missing.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_881_delete_subscription_404_check_and_502_on_orion_failure():
    """DELETE /subscriptions/{id} returns 404 if missing and 502 on Orion 5xx without DB update."""
    tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["tenant_admin"])
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["context.manage"]

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Case 1: Subscription does not exist for tenant -> 404 before calling Orion
            mock_sess_missing = AsyncMock()
            missing_cursor = MagicMock()
            missing_cursor.fetchone.return_value = None
            mock_sess_missing.execute.return_value = missing_cursor

            with (
                patch(
                    "app.entrypoints.routers.context.AsyncSessionLocal"
                ) as mock_sess_cls,
                patch(
                    "app.entrypoints.routers.context.set_session_tenant",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.adapters.external.orion_adapter.OrionAdapter.delete_subscription",
                    new_callable=AsyncMock,
                ) as mock_orion_del,
            ):
                mock_sess_cls.return_value.__aenter__.return_value = mock_sess_missing
                r_404 = await client.delete(
                    "/api/v1/context/subscriptions/sub-not-found"
                )
                assert r_404.status_code == 404
                mock_orion_del.assert_not_awaited()

            # Case 2: Orion raises 503 -> 502 Bad Gateway and DB commit NOT called
            mock_sess_502 = AsyncMock()
            found_cursor = MagicMock()
            found_cursor.fetchone.return_value = ("sub-live-1",)
            mock_sess_502.execute.return_value = found_cursor

            with (
                patch(
                    "app.entrypoints.routers.context.AsyncSessionLocal"
                ) as mock_sess_cls,
                patch(
                    "app.entrypoints.routers.context.set_session_tenant",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.adapters.external.orion_adapter.OrionAdapter.delete_subscription",
                    new_callable=AsyncMock,
                    side_effect=OrionAdapterError(
                        "Orion 503 Unavailable", status_code=503
                    ),
                ),
            ):
                mock_sess_cls.return_value.__aenter__.return_value = mock_sess_502
                r_502 = await client.delete("/api/v1/context/subscriptions/sub-live-1")
                assert r_502.status_code == 502
                mock_sess_502.commit.assert_not_awaited()

            # Case 3: Orion raises 404 -> treated as idempotent success, DB marked DELETED
            mock_sess_ok = AsyncMock()
            mock_sess_ok.execute.return_value = found_cursor

            with (
                patch(
                    "app.entrypoints.routers.context.AsyncSessionLocal"
                ) as mock_sess_cls,
                patch(
                    "app.entrypoints.routers.context.set_session_tenant",
                    new_callable=AsyncMock,
                ),
                patch(
                    "app.adapters.external.orion_adapter.OrionAdapter.delete_subscription",
                    new_callable=AsyncMock,
                    side_effect=OrionAdapterError("404 Not Found", status_code=404),
                ),
            ):
                mock_sess_cls.return_value.__aenter__.return_value = mock_sess_ok
                r_ok = await client.delete("/api/v1/context/subscriptions/sub-live-1")
                assert r_ok.status_code == 200
                mock_sess_ok.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ISSUES #884, #885, #887: DevOps, SDK Escaping & Unified PII Gatekeeper, CI
# ─────────────────────────────────────────────────────────────────────────────


def test_issues_884_885_887_dockerfile_compose_and_ci_configs():
    """Verify Dockerfile workers=1, Hasura/MFE env vars, and GitHub Actions CI configs."""
    dockerfile = (REPO_ROOT / "core-engine" / "Dockerfile").read_text(encoding="utf-8")
    assert '"--workers", "1"' in dockerfile
    assert '"--workers", "2"' not in dockerfile
    assert "ARG NEXT_PUBLIC_HASURA_WS_URL=" in dockerfile
    assert "ENV NEXT_PUBLIC_HASURA_WS_URL=$NEXT_PUBLIC_HASURA_WS_URL" in dockerfile

    compose = yaml.safe_load(
        (REPO_ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    )
    backend_mfe = compose["services"]["backend"]["environment"]["PLUGINS_MFE_URL"]
    assert "/plugins-mfe" in backend_mfe
    fe_args = compose["services"]["frontend"]["build"]["args"]
    fe_env = compose["services"]["frontend"]["environment"]
    assert "/plugins-mfe" in fe_args["NEXT_PUBLIC_PLUGINS_MFE_URL"]
    assert "NEXT_PUBLIC_HASURA_WS_URL" in fe_args
    assert "/plugins-mfe" in fe_env["NEXT_PUBLIC_PLUGINS_MFE_URL"]
    assert "NEXT_PUBLIC_HASURA_WS_URL" in fe_env

    fe_ci = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "frontend-ci.yml").read_text(
            encoding="utf-8"
        )
    )
    upload_step = next(
        s
        for s in fe_ci["jobs"]["build"]["steps"]
        if str(s.get("uses", "")).startswith("actions/upload-artifact")
    )
    assert upload_step["with"]["include-hidden-files"] is True

    be_ci_raw = (REPO_ROOT / ".github" / "workflows" / "backend-ci.yml").read_text(
        encoding="utf-8"
    )
    assert "'sdk/**'" in be_ci_raw
    assert "::error::Model drift detected!" in be_ci_raw

    lint_ci_raw = (
        REPO_ROOT / ".github" / "workflows" / "plugin-manifest-lint.yml"
    ).read_text(encoding="utf-8")
    assert "'plugins/**'" in lint_ci_raw
    assert "'scripts/verify_plugin_contracts.py'" in lint_ci_raw


def test_issue_887_sdk_escapes_special_chars_and_unifies_pii_gatekeeper(
    tmp_path: Path,
):
    """SDK escapes quotes/colons/apostrophes in display_name and unifies PII Gatekeeper."""
    assert PROHIBITED_NGSI_COLUMNS == SDK_PROHIBITED_NGSI_COLUMNS
    for required_pii in (
        "cccd",
        "cmnd",
        "citizen_id",
        "national_id",
        "salary",
        "base_salary",
        "net_salary",
        "gross_salary",
        "bonus",
        "allowance",
        "deduction",
        "tax",
        "tax_code",
        "bank_account",
        "bank_name",
        "password",
        "password_hash",
        "secret",
        "token",
        "api_key",
        "ssn",
        "dob",
        "date_of_birth",
        "phone",
        "personal_email",
        "address_detail",
        "medical_record",
        "fingerprint",
        "biometric",
        "id_card_number",
        "credit_card_info",
        "access_pin_code",
    ):
        assert required_pii in PROHIBITED_NGSI_COLUMNS

    tricky_name = 'Phân hệ "O\'Reilly": Quản lý & Kiểm định #1'
    rc, _ = init_plugin(
        code_name="oreilly-lab-module",
        output_dir=tmp_path,
        display_name=tricky_name,
    )
    assert rc == 0

    plugin_dir = tmp_path / "oreilly-lab-module"
    val_rc, errs = validate_plugin(plugin_dir)
    assert val_rc == 0, f"Unexpected SDK errors: {errs}"

    manifest_text = (plugin_dir / "manifest.yaml").read_text(encoding="utf-8")
    manifest_entity = ManifestValidator().validate_yaml_string(manifest_text)
    assert manifest_entity.display_name == tricky_name

    seed_sql = (plugin_dir / "db" / "seed_data.sql").read_text(encoding="utf-8")
    assert "O''Reilly" in seed_sql

    # Test PII blocked in attributes.target and relationships.column on BOTH validators
    manifest_dict = yaml.safe_load(manifest_text)
    manifest_dict["ngsi"]["entities"][0]["attributes"].append(
        {"column": "custom_col", "target": "personal_email", "type": "Property"}
    )
    manifest_dict["ngsi"]["entities"][0]["relationships"].append(
        {
            "column": "citizen_id",
            "target": "identifiedBy",
            "entity_type": "Citizen",
        }
    )
    (plugin_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest_dict, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    bad_rc, bad_errs = validate_plugin(plugin_dir)
    assert bad_rc == 1
    assert any("personal_email" in e for e in bad_errs)
    assert any("citizen_id" in e for e in bad_errs)

    with pytest.raises(DSLInvalidParametersError) as exc_info:
        ManifestValidator().validate(manifest_dict)
    assert "personal_email" in str(exc_info.value)
    assert "citizen_id" in str(exc_info.value)
