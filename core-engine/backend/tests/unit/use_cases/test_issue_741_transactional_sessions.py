# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.repositories.role_repo import RoleRepository
from app.adapters.repositories.tenant_repo import SQLAlchemyTenantRepository
from app.core.domain.entities import TenantContext, TenantEntity
from app.core.use_cases.ai_command import AICommandDTO, AICommandUseCase
from app.core.use_cases.role_management import RoleManagementUseCase
from app.core.use_cases.tenant_onboarding import ensure_tenant_mattermost_team
from app.use_cases.tenants.onboarding_use_case import (
    OnboardingRequest,
    OnboardingUseCase,
)


@pytest.mark.asyncio
async def test_role_repo_and_management_use_case_commits():
    mock_session = AsyncMock()
    role_repo = RoleRepository(mock_session)
    mock_user_repo = AsyncMock()

    use_case = RoleManagementUseCase(role_repo, mock_user_repo)
    tenant_id = uuid.uuid4()

    # 1. create_role
    mock_session.commit.reset_mock()
    await use_case.create_role(
        tenant_id, {"name": "test_role", "permissions": ["users:read"]}
    )
    mock_session.commit.assert_called_once()

    # 2. update_role
    mock_session.commit.reset_mock()
    mock_role = MagicMock()
    mock_role.name = "test_role"
    role_repo.get_role = AsyncMock(return_value=mock_role)
    await use_case.update_role(uuid.uuid4(), tenant_id, {"name": "updated_role"})
    mock_session.commit.assert_called_once()

    # 3. delete_role
    mock_session.commit.reset_mock()
    role_repo.delete_role = AsyncMock()
    await use_case.delete_role(uuid.uuid4(), tenant_id)
    mock_session.commit.assert_called_once()

    # 4. assign_role_to_user
    mock_session.commit.reset_mock()
    mock_user = MagicMock()
    mock_user.tenant_id = tenant_id
    mock_user_repo.get = AsyncMock(return_value=mock_user)
    mock_user_repo.get_by_keycloak_id = AsyncMock(return_value=None)
    role_repo.assign_role = AsyncMock()
    await use_case.assign_role_to_user(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), tenant_id
    )
    mock_session.commit.assert_called_once()

    # 5. revoke_role_from_user
    mock_session.commit.reset_mock()
    role_repo.revoke_role = AsyncMock()
    await use_case.revoke_role_from_user(uuid.uuid4(), uuid.uuid4(), tenant_id)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_tenant_repo_commit_and_onboarding_mattermost_commit():
    mock_session = AsyncMock()
    tenant_repo = SQLAlchemyTenantRepository(mock_session)

    # Verify SQLAlchemyTenantRepository.commit
    await tenant_repo.commit()
    mock_session.commit.assert_called_once()

    # Verify ensure_tenant_mattermost_team calls commit
    tenant_id = uuid.uuid4()
    mock_tenant = TenantEntity(
        id=tenant_id,
        name="Acme Corp",
        slug="acme",
        keycloak_realm="proteus",
        plan="standard",
        is_active=True,
    )
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = mock_tenant
    mock_adapter = AsyncMock()
    mock_adapter.get_team_by_name.return_value = {"id": "team-123", "name": "acme"}
    mock_adapter.create_channel.return_value = {"id": "chan-123"}
    mock_adapter.get_bot_user_id.return_value = "bot-123"

    cfg = await ensure_tenant_mattermost_team(mock_repo, mock_adapter, tenant_id)
    assert cfg["team_id"] == "team-123"
    mock_repo.upsert_integration_config.assert_called_once()
    mock_repo.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ai_command_use_case_invites_user_and_commits():
    mock_user_repo = AsyncMock()
    mock_ai_cmd_repo = AsyncMock()
    mock_audit_repo = AsyncMock()
    mock_role_repo = AsyncMock()

    use_case = AICommandUseCase(
        plugin_repo=AsyncMock(),
        ai_command_repo=mock_ai_cmd_repo,
        dsl_dry_run_repo=AsyncMock(),
        role_repo=mock_role_repo,
        mattermost_adapter=AsyncMock(),
        n8n_adapter=AsyncMock(),
        audit_log_repo=mock_audit_repo,
        user_repo=mock_user_repo,
    )

    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
        token="mock_token",
    )

    body = AICommandDTO(
        command_id=uuid.uuid4(),
        dsl_version="1.0.0",
        action="core.users.invite",
        parameters={
            "email": "newuser@example.com",
            "name": "New User",
            "keycloak_id": str(uuid.uuid4()),
        },
        effect="write",
        approval_message="Invite user to tenant",
    )

    # Test core write execution for core.users.invite
    handled, res = await use_case._execute_core_write_action(
        body.action, ctx.tenant_id, ctx.user_id, body.parameters
    )
    assert handled is True
    assert res["status"] == "invited"
    mock_user_repo.upsert.assert_called_once()
    mock_user_repo.commit.assert_called_once()
