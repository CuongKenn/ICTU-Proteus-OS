# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.domain.entities import (
    PluginEntity,
    PluginStatus,
    TenantContext,
    UserEntity,
)
from app.core.domain.exceptions import DSLPluginNotActiveError
from app.core.use_cases.plugin_records import PluginRecordsUseCase
from app.entrypoints.dependencies import get_current_tenant_context
from app.entrypoints.routers.users import deactivate_user


@pytest.mark.asyncio
async def test_get_current_tenant_context_inactive_user_raises_401():
    """Người dùng bị vô hiệu hóa (is_active=False) bị từ chối với HTTP 401 (#743)."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_keycloak = AsyncMock()
    mock_keycloak.verify_and_decode_token.return_value = {
        "tenant_id": str(tenant_id),
        "sub": str(user_id),
        "realm_access": {"roles": ["tenant_user"]},
        "email": "inactive@example.com",
    }

    mock_db = MagicMock()
    inactive_user = MagicMock()
    inactive_user.is_active = False

    with patch(
        "app.entrypoints.dependencies.SQLAlchemyUserRepository.get_by_keycloak_id",
        new=AsyncMock(return_value=inactive_user),
    ):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dummy")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant_context(
                credentials=creds,
                keycloak_adapter=mock_keycloak,
                db=mock_db,
            )
        assert exc_info.value.status_code == 401
        assert "vô hiệu hóa" in exc_info.value.detail


@pytest.mark.asyncio
async def test_deactivate_user_calls_keycloak_logout():
    """Deactivate user gọi cả disable_user và logout_user trên Keycloak (#743)."""
    tenant_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    target_keycloak_id = uuid.uuid4()

    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=caller_id,
        roles=["tenant_admin"],
        email="admin@test.com",
        full_name="Admin",
    )

    target_user = UserEntity(
        id=target_id,
        tenant_id=tenant_id,
        keycloak_id=target_keycloak_id,
        email="target@test.com",
        full_name="Target User",
        roles=["staff"],
        is_active=True,
    )

    mock_keycloak = AsyncMock()
    mock_db = AsyncMock()

    with patch("app.entrypoints.routers.users.SQLAlchemyUserRepository") as MockRepo:
        repo_inst = AsyncMock()
        repo_inst.get.return_value = target_user
        repo_inst.deactivate.return_value = None
        MockRepo.return_value = repo_inst

        await deactivate_user(
            user_id=target_id,
            context=ctx,
            keycloak=mock_keycloak,
            db=mock_db,
        )

        mock_keycloak.disable_user.assert_awaited_once_with(
            realm="proteus", user_id=str(target_keycloak_id)
        )
        mock_keycloak.logout_user.assert_awaited_once_with(
            realm="proteus", user_id=str(target_keycloak_id)
        )
        repo_inst.deactivate.assert_awaited_once_with(user_id=target_id)
        mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_plugin_records_passes_tenant_id_to_get_user_permissions():
    """PluginRecordsUseCase truyền ctx.tenant_id vào get_user_permissions (#743)."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=["employee"],
        email="user@test.com",
        full_name="User",
    )

    plugin_repo = AsyncMock()
    plugin_repo.get_by_code_name.return_value = PluginEntity(
        id=uuid.uuid4(),
        code_name="hr-module",
        display_name="HR",
        version="1.0.0",
        description="",
        author="",
        status=PluginStatus.ACTIVE,
    )
    plugin_repo.get_installation_status.return_value = PluginStatus.ACTIVE

    manifest_parser = MagicMock()
    manifest_parser.parse.return_value = MagicMock(
        database=MagicMock(tables=["hr_employees"])
    )

    role_repo = AsyncMock()
    role_repo.get_user_permissions.return_value = {"hr:employees:read", "hr:read"}

    mock_session = AsyncMock()
    # Mock table columns and count/select
    mock_cols_res = MagicMock()
    mock_cols_res.all.return_value = [("id", "uuid"), ("name", "varchar")]
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 0
    mock_rows_res = MagicMock()
    mock_rows_res.mappings.return_value.all.return_value = []
    mock_session.execute.side_effect = [mock_cols_res, mock_count_res, mock_rows_res]

    use_case = PluginRecordsUseCase(
        plugin_repo=plugin_repo,
        manifest_parser=manifest_parser,
        role_repo=role_repo,
        session=mock_session,
    )

    await use_case.list_records(ctx, "hr-module", "hr_employees")

    role_repo.get_user_permissions.assert_awaited_once_with(
        user_id, tenant_id=tenant_id
    )


@pytest.mark.asyncio
async def test_plugin_records_disabled_plugin_rejected():
    """Plugin chưa ACTIVE bị từ chối bởi DSLPluginNotActiveError (#743)."""
    tenant_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
        email="admin@test.com",
        full_name="Admin",
    )

    plugin_repo = AsyncMock()
    plugin_repo.get_by_code_name.return_value = PluginEntity(
        id=uuid.uuid4(),
        code_name="hr-module",
        display_name="HR",
        version="1.0.0",
        description="",
        author="",
        status=PluginStatus.ACTIVE,
    )
    plugin_repo.get_installation_status.return_value = PluginStatus.DISABLED

    manifest_parser = MagicMock()
    manifest_parser.parse.return_value = MagicMock(
        database=MagicMock(tables=["hr_employees"])
    )

    role_repo = AsyncMock()
    mock_session = AsyncMock()

    use_case = PluginRecordsUseCase(
        plugin_repo=plugin_repo,
        manifest_parser=manifest_parser,
        role_repo=role_repo,
        session=mock_session,
    )

    with pytest.raises(DSLPluginNotActiveError, match="chưa ACTIVE"):
        await use_case.list_records(ctx, "hr-module", "hr_employees")
