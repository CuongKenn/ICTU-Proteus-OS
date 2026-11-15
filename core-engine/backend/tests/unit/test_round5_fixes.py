# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression unit tests cho các bug Round 5 (#796)."""

import hashlib
import hmac
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.domain.entities import PluginStatus, TenantContext
from app.core.use_cases.ai_command import AICommandUseCase
from app.core.use_cases.plugin_uninstall import PluginUninstallUseCase
from app.entrypoints.dependencies import (
    get_ai_command_use_case,
    get_audit_log_repo,
    get_current_tenant_context,
    get_db_readonly,
    get_role_repo,
)
from app.infrastructure.config import settings
from app.infrastructure.database import get_db_transactional
from main import app


@pytest.mark.asyncio
async def test_mattermost_plugin_cleanup_uses_deleted_status_and_reports_error(
    monkeypatch,
):
    monkeypatch.setattr(settings, "MATTERMOST_WEBHOOK_SECRET", "test-secret")
    tenant_id = str(uuid.uuid4())
    plugin_id = str(uuid.uuid4())
    body = json.dumps(
        {
            "user_id": "mm-admin",
            "context": {
                "action_type": "plugin_cleanup",
                "action": "approve",
                "action_id": plugin_id,
                "tenant_id": tenant_id,
            },
        }
    ).encode("utf-8")
    sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()

    db = AsyncMock()
    mock_repo = AsyncMock()
    app.dependency_overrides[get_db_transactional] = lambda: db
    app.dependency_overrides[get_ai_command_use_case] = lambda: AsyncMock()
    app.dependency_overrides[get_audit_log_repo] = lambda: AsyncMock()

    try:
        with (
            patch(
                "app.adapters.repositories.plugin_repo.SQLAlchemyPluginRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.infrastructure.database.set_session_tenant",
                new_callable=AsyncMock,
            ) as mock_set_tenant,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/webhooks/mattermost/callback",
                    content=body,
                    headers={"Mattermost-Signature": sig},
                )
        assert resp.status_code == 200
        res = resp.json()
        mock_set_tenant.assert_awaited_once_with(db, tenant_id)
        mock_repo.update_status.assert_awaited_once_with(
            tenant_id=uuid.UUID(tenant_id),
            plugin_id=uuid.UUID(plugin_id),
            status=PluginStatus.DELETED,
        )
        db.commit.assert_awaited_once()
        assert "✅" in res["update"]["message"]

        # Khi update_status lỗi, không được trả thông báo thành công
        db_err = AsyncMock()
        mock_repo_err = AsyncMock()
        mock_repo_err.update_status.side_effect = RuntimeError("db down")
        app.dependency_overrides[get_db_transactional] = lambda: db_err
        with (
            patch(
                "app.adapters.repositories.plugin_repo.SQLAlchemyPluginRepository",
                return_value=mock_repo_err,
            ),
            patch(
                "app.infrastructure.database.set_session_tenant",
                new_callable=AsyncMock,
            ),
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp_err = await ac.post(
                    "/api/v1/webhooks/mattermost/callback",
                    content=body,
                    headers={"Mattermost-Signature": sig},
                )
        res_err = resp_err.json()
        db_err.rollback.assert_awaited_once()
        assert "update" not in res_err
        assert "❌" in res_err["ephemeral_text"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_embed_metabase_tenant_admin_cannot_bypass_ownership(monkeypatch):
    monkeypatch.setattr(settings, "METABASE_SECRET_KEY", "supersecretkey")
    monkeypatch.setattr(settings, "METABASE_SITE_URL", "http://metabase.local")
    monkeypatch.setattr(settings, "METABASE_PUBLIC_URL", "http://metabase-public.local")

    tenant_admin_ctx = TenantContext(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        roles=["tenant_admin"],
        email="tadmin@example.com",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        json.dumps({"metabase": ["42"]})
    ]
    mock_db.execute.return_value = mock_result

    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["analytics.view"]

    app.dependency_overrides[get_current_tenant_context] = lambda: tenant_admin_ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_db_readonly] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/embed/metabase/999",
                headers={"Authorization": "Bearer fake-token"},
            )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_command_approver_allowed_handles_none_approver_tenant():
    role_repo = AsyncMock()
    role_repo.get_user_permissions.return_value = ["hr:*"]
    uc = AICommandUseCase(
        plugin_repo=AsyncMock(),
        ai_command_repo=AsyncMock(),
        dsl_dry_run_repo=AsyncMock(),
        role_repo=role_repo,
        mattermost_adapter=AsyncMock(),
        n8n_adapter=AsyncMock(),
    )
    tenant_id = uuid.uuid4()
    approver = SimpleNamespace(id=uuid.uuid4(), roles=["staff"], tenant_id=None)
    cmd = {"action": "hr.list", "tenant_id": tenant_id}

    allowed, reason = await uc._approver_allowed(cmd, approver)
    assert allowed is True
    assert reason == ""
    role_repo.get_user_permissions.assert_awaited_once_with(
        approver.id, tenant_id=tenant_id
    )


@pytest.mark.asyncio
async def test_plugin_uninstall_drop_tables_uses_set_local_search_path():
    session = AsyncMock()
    session.execute.side_effect = [None, RuntimeError("drop failed")]
    uc = PluginUninstallUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    ctx = TenantContext(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    manifest = SimpleNamespace(database=SimpleNamespace(tables=["hr_employees"]))

    with pytest.raises(RuntimeError, match="drop failed"):
        await uc._step_6_database(ctx, "hr-module", manifest)

    executed_sql = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("SET LOCAL search_path TO" in s for s in executed_sql)
    assert not any("SET search_path TO public" in s for s in executed_sql)
