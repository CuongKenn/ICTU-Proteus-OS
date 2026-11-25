# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression tests for Layer 3 security, outbox, adapter, and DevOps (#861-#864)."""

import json
import math
import re
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import yaml
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.adapters.external.orion_adapter import (
    OrionAdapter,
    _sanitize_ngsi_tenant,
)
from app.adapters.repositories.outbox_repository import OutboxRecord
from app.core.domain.entities import TenantContext
from app.core.domain.geo_utils import parse_ngsi_ld_geoproperty
from app.entrypoints.dependencies import (
    get_current_tenant_context,
    get_db_readonly,
    get_role_repo,
)
from app.entrypoints.routers.context import validate_subscription_callback_url
from app.infrastructure.config import settings
from app.workers.context_sync_worker import ContextSyncWorker
from main import app

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #861: Webhook Auth, RBAC, SSRF, DLQ Limit, Cross-Tenant IDOR, RLS Session
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_861_webhook_secret_enforcement(monkeypatch):
    """When ORION_WEBHOOK_SECRET is configured, missing/wrong secret returns 401."""
    monkeypatch.setattr(settings, "ORION_WEBHOOK_SECRET", "super-secret-orion-key")
    tid = uuid.uuid4()
    payload = {
        "subscriptionId": "sub-861",
        "data": [
            {
                "id": f"urn:ngsi-ld:Room:{tid}:room-1",
                "type": "Room",
                "name": {"type": "Property", "value": "Room 1"},
                "salary": {"type": "Property", "value": 99999999},
            }
        ],
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing header -> 401
        resp_missing = await client.post("/api/v1/context/notifications", json=payload)
        assert resp_missing.status_code == 401

        # 2. Wrong header -> 401
        resp_wrong = await client.post(
            "/api/v1/context/notifications",
            json=payload,
            headers={"X-Orion-Webhook-Secret": "wrong-secret"},
        )
        assert resp_wrong.status_code == 401

        # 3. Correct header -> 200 + fallback redis closed + prohibited col stripped
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        if hasattr(app.state, "redis_client"):
            delattr(app.state, "redis_client")

        with (
            patch("app.entrypoints.routers.context.AsyncSessionLocal") as mock_sess_cls,
            patch(
                "app.entrypoints.routers.context.aioredis.from_url",
                return_value=mock_redis,
            ),
            patch(
                "app.entrypoints.routers.context.set_session_tenant",
                new_callable=AsyncMock,
            ) as mock_set_tenant,
            patch(
                "app.adapters.repositories.outbox_repository.SQLAlchemyOutboxRepository.upsert_entity_state",
                new_callable=AsyncMock,
            ) as mock_upsert,
        ):
            mock_sess_cls.return_value.__aenter__.return_value = mock_session

            resp_ok = await client.post(
                "/api/v1/context/notifications",
                json=payload,
                headers={"X-Orion-Webhook-Secret": "super-secret-orion-key"},
            )
            assert resp_ok.status_code == 200
            mock_set_tenant.assert_awaited_once_with(mock_session, tid)
            mock_upsert.assert_awaited_once()
            saved_payload = mock_upsert.call_args.kwargs["payload"]
            assert "salary" not in saved_payload

            # Verify stream trim & fallback redis aclose (#863)
            mock_redis.xadd.assert_awaited_once()
            assert mock_redis.xadd.call_args.kwargs["maxlen"] == 10000
            assert mock_redis.xadd.call_args.kwargs["approximate"] is True
            mock_redis.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_issue_861_production_requires_webhook_secret(monkeypatch):
    """In production environment, empty ORION_WEBHOOK_SECRET fails closed with 401."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ORION_WEBHOOK_SECRET", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/context/notifications",
            json={"subscriptionId": "sub-prod", "data": []},
        )
        assert resp.status_code == 401


def test_issue_861_ssrf_callback_url_validation(monkeypatch):
    """Verify SSRF helper blocks loopback, private, link-local, and internal hosts."""
    monkeypatch.setattr(settings, "BACKEND_URL", "http://backend:8000")

    # Allowed: None or exact internal notification URL
    assert (
        validate_subscription_callback_url(None)
        == "http://backend:8000/api/v1/context/notifications"
    )
    assert (
        validate_subscription_callback_url(
            "http://backend:8000/api/v1/context/notifications"
        )
        == "http://backend:8000/api/v1/context/notifications"
    )

    # Allowed: public IP over http/https
    assert (
        validate_subscription_callback_url("https://93.184.216.34/ngsi/callback")
        == "https://93.184.216.34/ngsi/callback"
    )

    # Blocked SSRF targets
    blocked_urls = [
        "ftp://93.184.216.34/notify",
        "http://localhost:8000/secret",
        "http://127.0.0.1:8080/v1/metadata",
        "http://10.0.0.15:9000/internal",
        "http://172.16.5.4:5432/db",
        "http://172.31.255.1/admin",
        "http://192.168.1.10/router",
        "http://169.254.169.254/latest/meta-data/",
        "http://hasura:8080/v1/graphql",
        "http://keycloak.internal/admin",
        "http://[::1]:8000/test",
    ]
    for bad_url in blocked_urls:
        with pytest.raises(HTTPException) as exc_info:
            validate_subscription_callback_url(bad_url)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_issue_861_rbac_and_subscription_webhook_secret_header(monkeypatch):
    """Non-admin without context.manage gets 403; authorized user gets receiverInfo."""
    monkeypatch.setattr(settings, "ORION_WEBHOOK_SECRET", "wh-secret-999")
    tid = uuid.uuid4()
    regular_user = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["user"])
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["plugins.read"]

    app.dependency_overrides[get_current_tenant_context] = lambda: regular_user
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.post(
                "/api/v1/context/subscriptions", json={"entity_type": "Room"}
            )
            assert r1.status_code == 403

            r2 = await client.delete("/api/v1/context/subscriptions/sub-1")
            assert r2.status_code == 403

            r3 = await client.post("/api/v1/context/outbox/replay-dlq")
            assert r3.status_code == 403

            # Grant context.manage -> allowed + receiverInfo + limit bounds
            mock_role_repo.get_user_permissions.return_value = ["context.manage"]

            r_bad_limit = await client.post(
                "/api/v1/context/outbox/replay-dlq?limit=5000"
            )
            assert r_bad_limit.status_code == 422

            mock_session = AsyncMock()
            with (
                patch(
                    "app.entrypoints.routers.context.AsyncSessionLocal"
                ) as mock_sess_cls,
                patch(
                    "app.adapters.external.orion_adapter.OrionAdapter.create_subscription",
                    new_callable=AsyncMock,
                    return_value="sub-created-861",
                ) as mock_create_sub,
            ):
                mock_sess_cls.return_value.__aenter__.return_value = mock_session
                r_create = await client.post(
                    "/api/v1/context/subscriptions", json={"entity_type": "Room"}
                )
                assert r_create.status_code == 201
                sent_sub = mock_create_sub.call_args.args[0]
                receiver_info = sent_sub["notification"]["endpoint"]["receiverInfo"]
                assert receiver_info == [
                    {"key": "X-Orion-Webhook-Secret", "value": "wh-secret-999"}
                ]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_861_get_entity_enforces_tenant_id_in_sql():
    """GET /api/v1/context/entities/{id} binds tenant_id in SQL WHERE against IDOR."""
    tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["user"])
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchone.return_value = None
    mock_db.execute.return_value = mock_res

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_db_readonly] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/context/entities/urn:ngsi-ld:Room:other-tenant:1"
            )
            assert resp.status_code == 404

        sql_stmt, bind_params = mock_db.execute.call_args.args
        assert "tenant_id = :tenant_id" in str(sql_stmt)
        assert bind_params["tenant_id"] == tid
    finally:
        app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #862: Trigger Safe Tenant Resolution + Sensitive Stripping + 5-Part URN
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_862_trigger_sql_safe_uuid_and_sensitive_stripping():
    """Verify migration o9j0k1l2m3n4 and init.sql catch UUID errors and strip PII."""
    repo_root = Path(__file__).parents[4]
    mig_path = (
        Path(__file__).parents[2]
        / "migrations"
        / "versions"
        / "o9j0k1l2m3n4_add_outbox_triggers.py"
    )
    init_sql_path = repo_root / "deploy" / "postgres" / "init.sql"

    for path in (mig_path, init_sql_path):
        content = path.read_text(encoding="utf-8")
        assert "(v_payload->>'tenant_id')::uuid" in content
        assert "TG_TABLE_SCHEMA LIKE 'tenant_%'" in content
        assert "replace(substr(TG_TABLE_SCHEMA, 8), '_', '-')::uuid" in content
        assert "v_payload := v_payload - ARRAY[" in content
        for col in (
            "password",
            "hashed_password",
            "salary",
            "base_salary",
            "ssn",
            "cccd",
            "bank_account",
            "credit_card",
        ):
            assert f"'{col}'" in content


def test_issue_862_transform_to_ngsi_ld_5part_urn_and_prohibited_columns():
    """Verify transform_to_ngsi_ld strips prohibited cols and builds 5-part URN."""
    tid = uuid.uuid4()
    raw = {
        "id": "emp-1",
        "full_name": "Nguyen Van B",
        "department_id": "dept-it",
        "salary": 25000000,
        "base_salary": 20000000,
        "password": "plain",
        "hashed_password": "hash",
        "bank_account": "123456789",
        "ssn": "001099000111",
        "cccd": "001099000111",
        "api_key": "sk-secret",
    }
    attrs, lon, lat = ContextSyncWorker.transform_to_ngsi_ld(raw, tenant_id=tid)
    assert lon is None and lat is None
    assert attrs["full_name"] == {"type": "Property", "value": "Nguyen Van B"}
    assert attrs["department_id"] == {
        "type": "Relationship",
        "object": f"urn:ngsi-ld:Department:{tid}:dept-it",
    }
    for forbidden in (
        "salary",
        "base_salary",
        "password",
        "hashed_password",
        "bank_account",
        "ssn",
        "cccd",
        "api_key",
    ):
        assert forbidden not in attrs


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #863: Tenant Header, URL Quoting, SAVEPOINT Isolation, Geo Validation
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_863_sanitize_ngsi_tenant():
    """Verify _sanitize_ngsi_tenant produces Orion-LD compliant ^[a-z0-9_]+$."""
    pattern = re.compile(r"^[a-z0-9_]+$")

    t_digit = _sanitize_ngsi_tenant("11111111-2222-3333-4444-555555555555")
    assert t_digit == "t_11111111_2222_3333_4444_555555555555"
    assert pattern.match(t_digit)
    assert _sanitize_ngsi_tenant(t_digit) == t_digit

    t_alpha = _sanitize_ngsi_tenant("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert t_alpha == "a1b2c3d4_e5f6_7890_abcd_ef1234567890"
    assert pattern.match(t_alpha)


@pytest.mark.asyncio
async def test_issue_863_orion_url_quoting_and_shared_client():
    """Verify OrionAdapter quotes path-traversal chars and preserves shared client."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.side_effect = [
        httpx.Response(200, json={"id": "x"}),
        httpx.Response(204),
    ]

    adapter = OrionAdapter(base_url="http://orion:1026", client=mock_client)
    await adapter.get_entity("urn:ngsi-ld:Room:1/../../admin?x=1")
    get_url = mock_client.request.call_args_list[0].args[1]
    assert "/../../" not in get_url
    assert "%2F..%2F..%2Fadmin%3Fx%3D1" in get_url

    await adapter.delete_subscription("sub/../../evil")
    del_url = mock_client.request.call_args_list[1].args[1]
    assert "sub%2F..%2F..%2Fevil" in del_url

    # Shared client must NOT be closed by adapter.aclose()
    await adapter.aclose()
    mock_client.aclose.assert_not_called()


@pytest.mark.asyncio
async def test_issue_863_worker_savepoint_isolates_failed_record():
    """Verify SAVEPOINT rolls back only the failing record without aborting batch."""
    tid = uuid.uuid4()
    bad_rec = OutboxRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        entity_type="Room",
        entity_id="room-bad",
        op="UPSERT",
        payload={"name": "Bad Room", "salary": 5000},
        status="PENDING",
        retry_count=0,
        idempotency_key="k1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    good_rec = OutboxRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        entity_type="Room",
        entity_id="room-good",
        op="UPSERT",
        payload={"name": "Good Room", "department_id": "dept-1"},
        status="PENDING",
        retry_count=0,
        idempotency_key="k2",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    savepoint_events: list[str] = []

    class FakeNestedCM:
        async def __aenter__(self):
            savepoint_events.append("enter")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            savepoint_events.append("rollback" if exc_type else "release")
            return False

    mock_session = AsyncMock()
    mock_session.begin_nested = MagicMock(side_effect=lambda: FakeNestedCM())
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (
            r.id,
            r.tenant_id,
            r.entity_type,
            r.entity_id,
            r.op,
            r.payload,
            r.status,
            r.retry_count,
            r.idempotency_key,
            r.created_at,
            r.updated_at,
        )
        for r in (bad_rec, good_rec)
    ]
    mock_session.execute.return_value = mock_cursor

    mock_orion = AsyncMock(spec=OrionAdapter)
    mock_orion.upsert_entity.side_effect = [RuntimeError("Orion 500"), True]
    mock_redis = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield mock_session

    worker = ContextSyncWorker(
        session_factory=session_factory,
        orion_adapter=mock_orion,
        redis_client=mock_redis,
    )
    processed = await worker.process_batch()
    assert processed == 1
    assert "rollback" in savepoint_events
    assert "release" in savepoint_events
    mock_session.commit.assert_awaited_once()


def test_issue_863_geo_utils_strict_validation():
    """Verify parse_ngsi_ld_geoproperty rejects bool, NaN/Inf, and invalid bounds."""
    assert parse_ngsi_ld_geoproperty(None) is None
    assert parse_ngsi_ld_geoproperty({"type": "GeoProperty", "value": "bad"}) is None
    assert (
        parse_ngsi_ld_geoproperty(
            {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [True, False]},
            }
        )
        is None
    )
    assert (
        parse_ngsi_ld_geoproperty(
            {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [math.nan, 21.0]},
            }
        )
        is None
    )
    assert (
        parse_ngsi_ld_geoproperty(
            {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [math.inf, 21.0]},
            }
        )
        is None
    )
    assert (
        parse_ngsi_ld_geoproperty(
            {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [181.0, 21.0]},
            }
        )
        is None
    )
    assert (
        parse_ngsi_ld_geoproperty(
            {
                "type": "GeoProperty",
                "value": {"type": "Point", "coordinates": [105.8, -91.0]},
            }
        )
        is None
    )
    assert parse_ngsi_ld_geoproperty(
        {
            "type": "GeoProperty",
            "value": {"type": "Point", "coordinates": [105.8, 21.0]},
        }
    ) == (105.8, 21.0)


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #864: Docker Compose, Hasura Metadata, Keycloak Realm, Views, Mongo Backup
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_864_docker_compose_and_prod_labels():
    deploy_dir = Path(__file__).parents[4] / "deploy"

    prod = yaml.safe_load(
        (deploy_dir / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )
    mfe_labels = prod["services"]["plugins-mfe"]["labels"]
    hasura_labels = prod["services"]["hasura"]["labels"]

    assert len(mfe_labels) == 6
    assert all("plugins-mfe" in lbl for lbl in mfe_labels)
    assert len(hasura_labels) == 3
    assert all("routers.hasura" in lbl for lbl in hasura_labels)

    base = yaml.safe_load(
        (deploy_dir / "docker-compose.yml").read_text(encoding="utf-8")
    )
    worker_build = base["services"]["context-sync-worker"]["build"]
    assert worker_build["context"] == "../core-engine"
    assert worker_build["dockerfile"] == "Dockerfile"
    assert worker_build["target"] == "backend"

    hasura_jwt = json.loads(
        base["services"]["hasura"]["environment"]["HASURA_GRAPHQL_JWT_SECRET"]
    )
    assert "claims_format" not in hasura_jwt
    assert hasura_jwt["claims_namespace_path"] == "$"

    backend_env = base["services"]["backend"]["environment"]
    assert backend_env["ORION_URL"] == "http://orion-ld:1026"
    assert backend_env["BACKEND_URL"] == "http://backend:8000"
    assert "LAYER3_ENABLED" in backend_env
    assert "ORION_WEBHOOK_SECRET" in backend_env


def test_issue_864_keycloak_admin_uuid_sanitized_view_and_mongo_scripts():
    repo_root = Path(__file__).parents[4]
    deploy_dir = repo_root / "deploy"

    # 1. Keycloak admin user has valid UUID tenant_id
    realm = json.loads(
        (deploy_dir / "keycloak" / "realm-import.json").read_text(encoding="utf-8")
    )
    admin_user = next(u for u in realm["users"] if u["username"] == "admin")
    admin_tid = admin_user["attributes"]["tenant_id"][0]
    assert uuid.UUID(admin_tid) == uuid.UUID("00000000-0000-0000-0000-000000000001")

    # 2. Sanitized view checks table_schema = 'public' and security_invoker = true
    view_mig = (
        Path(__file__).parents[2]
        / "migrations"
        / "versions"
        / "p0k1l2m3n4o5_create_hasura_sanitized_views.py"
    ).read_text(encoding="utf-8")
    assert "table_schema = 'public'" in view_mig
    assert "security_invoker = true" in view_mig
    assert "security_barrier = true" in view_mig

    # 3. Mongo backup & restore support passwordless default and all multi-tenant DBs
    backup_sh = (deploy_dir / "scripts" / "backup_mongo.sh").read_text(encoding="utf-8")
    restore_sh = (deploy_dir / "scripts" / "restore_mongo.sh").read_text(
        encoding="utf-8"
    )
    assert "--db=" not in backup_sh
    assert 'if [ -n "${MONGO_USER}" ]' in backup_sh
    assert "--nsInclude=" not in restore_sh
    assert 'if [ -n "${MONGO_USER}" ]' in restore_sh

    # 4. apply_metadata.sh supports HASURA_GRAPHQL_ADMIN_SECRET fallback
    apply_sh = (deploy_dir / "hasura" / "scripts" / "apply_metadata.sh").read_text(
        encoding="utf-8"
    )
    assert "HASURA_GRAPHQL_ADMIN_SECRET" in apply_sh
