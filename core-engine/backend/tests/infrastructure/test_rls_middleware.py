# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest
from sqlalchemy import text
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.database import AsyncSessionLocal, current_tenant_id
from main import TenantIDMiddleware


@pytest.mark.asyncio
async def test_tenant_id_middleware_resets_tenant_id():
    """
    Theo bản vá bảo mật C6: TenantIDMiddleware luôn reset current_tenant_id về ''
    chứ không trust header X-Tenant-ID từ client để chống spoofing RLS.
    Tenant ID thực tế chỉ được gán trong get_current_tenant_context sau JWT verify.
    """
    valid_uuid = "12345678-1234-5678-1234-567812345678"
    token = current_tenant_id.set(valid_uuid)

    middleware = TenantIDMiddleware(app=None)
    captured_tenant_id = None

    async def fake_call_next(request):
        nonlocal captured_tenant_id
        captured_tenant_id = current_tenant_id.get()
        return Response(status_code=200)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [(b"x-tenant-id", b"malicious-tenant-id")],
    }
    request = Request(scope)

    try:
        response = await middleware.dispatch(request, fake_call_next)
        assert response.status_code == 200
        assert captured_tenant_id == "", f"Expected '', got '{captured_tenant_id}'"
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_rls_session_sets_tenant_id():
    """
    Test kiểm tra xem RLS event listener có tự động
    SET LOCAL app.current_tenant_id theo context_var hay không.
    Có skip guard nếu database local chưa chạy.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Local database not available: {exc}")

    valid_uuid = "12345678-1234-5678-1234-567812345678"
    token = current_tenant_id.set(valid_uuid)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            tenant_id = result.scalar()
            assert tenant_id == valid_uuid, f"Expected '{valid_uuid}', got '{tenant_id}'"
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_rls_session_empty_tenant_id():
    """
    Trường hợp không có tenant_id (như background jobs hoặc middleware reset),
    session sẽ được set empty string.
    Có skip guard nếu database local chưa chạy.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Local database not available: {exc}")

    token = current_tenant_id.set(None)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            tenant_id = result.scalar()
            assert tenant_id == "", f"Expected empty string, got '{tenant_id}'"
    finally:
        current_tenant_id.reset(token)
