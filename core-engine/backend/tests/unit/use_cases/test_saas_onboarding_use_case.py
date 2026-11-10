# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.use_cases.tenants.onboarding_use_case import (
    OnboardingRequest,
    OnboardingUseCase,
)


@pytest.fixture
def mock_tenant_repo():
    repo = AsyncMock()
    repo.get_by_slug.return_value = None
    repo.create = AsyncMock()
    session = AsyncMock()
    # mock async context manager for begin_nested
    nested_cm = AsyncMock()
    nested_cm.__aenter__ = AsyncMock(return_value=nested_cm)
    nested_cm.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=nested_cm)
    repo._session = session
    return repo


@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    repo.upsert = AsyncMock()
    repo.commit = AsyncMock()
    repo._session = AsyncMock()
    return repo


@pytest.fixture
def mock_keycloak_adapter():
    adapter = AsyncMock()
    adapter.create_user.return_value = str(uuid.uuid4())
    adapter.set_user_attributes = AsyncMock()
    adapter.set_user_password = AsyncMock()
    adapter.assign_role_to_user = AsyncMock()
    adapter.create_tenant_group = AsyncMock(return_value="group-123")
    adapter.get_group_by_name = AsyncMock(return_value="group-123")
    adapter.add_user_to_group = AsyncMock()
    adapter.delete_user = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_onboarding_success_creates_group_and_adds_user(
    mock_tenant_repo, mock_user_repo, mock_keycloak_adapter
):
    use_case = OnboardingUseCase(
        tenant_repo=mock_tenant_repo,
        user_repo=mock_user_repo,
        keycloak_adapter=mock_keycloak_adapter,
        mattermost_adapter=None,
    )
    req = OnboardingRequest(
        company_name="Acme Corp",
        admin_full_name="Alice Wonderland",
        admin_email="alice@acme.com",
        admin_password="Password123!",
    )

    res = await use_case.execute(req)

    assert res["slug"] == "acme-corp"
    mock_keycloak_adapter.create_tenant_group.assert_called_once_with(
        realm="proteus", group_name="tenant_acme-corp"
    )
    mock_keycloak_adapter.add_user_to_group.assert_called_once()
    mock_user_repo.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_onboarding_slug_retry_with_begin_nested(
    mock_tenant_repo, mock_user_repo, mock_keycloak_adapter
):
    use_case = OnboardingUseCase(
        tenant_repo=mock_tenant_repo,
        user_repo=mock_user_repo,
        keycloak_adapter=mock_keycloak_adapter,
        mattermost_adapter=None,
    )
    req = OnboardingRequest(
        company_name="Acme Corp",
        admin_full_name="Alice Wonderland",
        admin_email="alice@acme.com",
        admin_password="Password123!",
    )

    # First attempt raises IntegrityError, second succeeds
    mock_tenant_repo.create.side_effect = [
        IntegrityError(
            "duplicate key", params=None, orig=Exception("unique constraint")
        ),
        None,
    ]

    res = await use_case.execute(req)

    assert "acme-corp-" in res["slug"]
    assert mock_tenant_repo.create.call_count == 2
    mock_tenant_repo._session.begin_nested.assert_called()


@pytest.mark.asyncio
async def test_onboarding_error_rolls_back_keycloak_user(
    mock_tenant_repo, mock_user_repo, mock_keycloak_adapter
):
    use_case = OnboardingUseCase(
        tenant_repo=mock_tenant_repo,
        user_repo=mock_user_repo,
        keycloak_adapter=mock_keycloak_adapter,
        mattermost_adapter=None,
    )
    req = OnboardingRequest(
        company_name="Acme Corp",
        admin_full_name="Alice Wonderland",
        admin_email="alice@acme.com",
        admin_password="Password123!",
    )

    # DB user upsert fails
    mock_user_repo.upsert.side_effect = RuntimeError("DB error")

    with pytest.raises(RuntimeError, match="DB error"):
        await use_case.execute(req)

    mock_keycloak_adapter.delete_user.assert_called_once()
