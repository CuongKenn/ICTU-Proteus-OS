# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.domain.entities import TenantContext
from app.entrypoints.dependencies import (
    get_current_tenant_context,
    get_db_readonly,
    get_role_repo,
)
from app.infrastructure.config import settings
from main import app


@pytest.fixture
def mock_tenant_context():
    return TenantContext(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        roles=["staff"],
        email="staff@example.com",
    )


@pytest.fixture
def mock_admin_context():
    return TenantContext(
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        roles=["superadmin"],
        email="admin@example.com",
    )


@pytest.mark.asyncio
async def test_embed_metabase_success(mock_tenant_context, monkeypatch):
    monkeypatch.setattr(settings, "METABASE_SECRET_KEY", "supersecretkey")
    monkeypatch.setattr(settings, "METABASE_SITE_URL", "http://metabase.local")
    monkeypatch.setattr(settings, "METABASE_PUBLIC_URL", "http://metabase-public.local")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        json.dumps({"metabase": ["42", "43"]})
    ]
    mock_db.execute.return_value = mock_result

    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["analytics.view"]

    app.dependency_overrides[get_current_tenant_context] = lambda: mock_tenant_context
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_db_readonly] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/embed/metabase/42",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert res.status_code == 200
        data = res.json()
        assert "url" in data
        assert "http://metabase-public.local/embed/dashboard/" in data["url"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_embed_metabase_foreign_dashboard_forbidden(
    mock_tenant_context, monkeypatch
):
    monkeypatch.setattr(settings, "METABASE_SECRET_KEY", "supersecretkey")
    monkeypatch.setattr(settings, "METABASE_SITE_URL", "http://metabase.local")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    # Tenant only owns dashboard 42
    mock_result.scalars.return_value.all.return_value = [
        json.dumps({"metabase": ["42"]})
    ]
    mock_db.execute.return_value = mock_result

    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["analytics.view"]

    app.dependency_overrides[get_current_tenant_context] = lambda: mock_tenant_context
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
        data = res.json()
        assert "không thuộc quyền sở hữu" in data["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_embed_metabase_admin_bypass_ownership(mock_admin_context, monkeypatch):
    monkeypatch.setattr(settings, "METABASE_SECRET_KEY", "supersecretkey")
    monkeypatch.setattr(settings, "METABASE_SITE_URL", "http://metabase.local")

    mock_db = AsyncMock()
    mock_role_repo = AsyncMock()

    app.dependency_overrides[get_current_tenant_context] = lambda: mock_admin_context
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_db_readonly] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/embed/metabase/999",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert res.status_code == 200
        data = res.json()
        assert "http://metabase.local/embed/dashboard/" in data["url"]
    finally:
        app.dependency_overrides.clear()
