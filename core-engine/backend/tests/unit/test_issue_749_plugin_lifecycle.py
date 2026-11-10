# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.external.redis_event_bus import RedisEventBusPublisher
from app.core.domain.entities import PluginEntity, PluginStatus, TenantContext
from app.core.domain.plugin_manifest import PluginManifest
from app.core.use_cases.plugin_credentials import ConfigurePluginCredentialsUseCase
from app.core.use_cases.plugin_toggle import PluginToggleUseCase
from app.core.use_cases.plugin_uninstall import PluginUninstallUseCase
from app.core.use_cases.plugin_upgrade import _DANGEROUS_SQL, PluginUpgradeUseCase
from app.entrypoints.routers.plugins import (
    _mark_uninstall_failed_if_stuck,
    _mark_upgrade_failed_if_stuck,
)
from app.entrypoints.schemas.plugin import PluginCredentialPayload


@pytest.mark.asyncio
async def test_redis_event_bus_lifecycle_prefix_deduplication():
    bus = RedisEventBusPublisher()

    with patch.object(bus, "publish_critical", new_callable=AsyncMock) as mock_pub:
        # Pass action with 'plugin.' prefix
        await bus.publish_plugin_lifecycle(
            action="plugin.uninstalled",
            tenant_id="tenant-123",
            plugin_name="hr-module",
            plugin_version="1.0.0",
        )
        assert mock_pub.call_count == 1
        call_kwargs = mock_pub.call_args.kwargs
        assert call_kwargs["event_type"] == "plugin.uninstalled"

        # Pass action without prefix
        await bus.publish_plugin_lifecycle(
            action="installed",
            tenant_id="tenant-123",
            plugin_name="hr-module",
            plugin_version="1.0.0",
        )
        assert mock_pub.call_count == 2
        call_kwargs2 = mock_pub.call_args.kwargs
        assert call_kwargs2["event_type"] == "plugin.installed"


@pytest.mark.asyncio
async def test_plugin_toggle_emits_lifecycle_events():
    mock_repo = AsyncMock()
    mock_repo.get_by_id.return_value = PluginEntity(
        id=uuid.uuid4(),
        code_name="hr-module",
        display_name="HR",
        description="",
        version="1.0.0",
        author="ICTU",
        license="AGPL",
        icon_url="",
        manifest_url="",
    )
    mock_repo.get_installation_status.side_effect = [
        PluginStatus.ACTIVE,
        PluginStatus.DISABLED,
    ]
    mock_repo.get_config.return_value = {}

    mock_n8n = AsyncMock()
    mock_session = AsyncMock()
    mock_event_bus = AsyncMock()

    use_case = PluginToggleUseCase(
        plugin_repo=mock_repo,
        n8n_adapter=mock_n8n,
        session=mock_session,
        event_bus=mock_event_bus,
    )

    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    plugin_id = uuid.uuid4()

    # Disable
    await use_case.disable_plugin(ctx, plugin_id)
    mock_event_bus.publish_plugin_lifecycle.assert_called_with(
        action="disabled",
        tenant_id=str(ctx.tenant_id),
        plugin_name="hr-module",
        plugin_version="1.0.0",
    )

    # Enable
    await use_case.enable_plugin(ctx, plugin_id)
    mock_event_bus.publish_plugin_lifecycle.assert_called_with(
        action="enabled",
        tenant_id=str(ctx.tenant_id),
        plugin_name="hr-module",
        plugin_version="1.0.0",
    )


@pytest.mark.asyncio
async def test_plugin_uninstall_cleans_up_n8n_credentials_and_appsmith():
    mock_repo = AsyncMock()
    mock_repo.get_credential_ids.return_value = [
        {"id": "cred-1", "name": "t_cred1", "type": "gmailOAuth2"},
        "cred-2",
    ]
    mock_n8n = AsyncMock()
    mock_appsmith = AsyncMock()
    mock_session = AsyncMock()
    mock_manifest = MagicMock(spec=PluginManifest)

    use_case = PluginUninstallUseCase(
        plugin_repo=mock_repo,
        tenant_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        n8n_adapter=mock_n8n,
        metabase_adapter=AsyncMock(),
        appsmith_adapter=mock_appsmith,
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=mock_session,
    )

    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    pid = uuid.uuid4()

    # Test _step_5_n8n cleans workflows and credentials
    await use_case._step_5_n8n(
        context=ctx,
        plugin_code_name="hr-module",
        manifest=mock_manifest,
        asset_ids=["wf-100"],
        plugin_id=pid,
    )

    mock_n8n.delete_workflow.assert_called_once_with("wf-100")
    assert mock_n8n.delete_credential.call_count == 2
    mock_n8n.delete_credential.assert_any_call("cred-1")
    mock_n8n.delete_credential.assert_any_call("cred-2")

    # Test _step_3_appsmith
    await use_case._step_3_appsmith(
        context=ctx,
        plugin_code_name="hr-module",
        manifest=mock_manifest,
        asset_ids=["app-1", "app-2"],
    )
    assert mock_appsmith.delete_application.call_count == 2


def test_dangerous_sql_regex_blocks_forbidden_commands():
    assert _DANGEROUS_SQL.search("DELETE FROM hr_employees;") is not None
    assert _DANGEROUS_SQL.search("COPY hr_salaries TO '/tmp/data';") is not None
    assert (
        _DANGEROUS_SQL.search(
            "CREATE FUNCTION hack() RETURNS void AS $$ BEGIN END; $$ LANGUAGE plpgsql;"
        )
        is not None
    )
    assert (
        _DANGEROUS_SQL.search(
            "CREATE OR REPLACE FUNCTION hack() RETURNS void AS $$ $$ LANGUAGE plpgsql;"
        )
        is not None
    )
    assert _DANGEROUS_SQL.search("DROP TABLE hr_employees;") is not None
    assert _DANGEROUS_SQL.search("TRUNCATE hr_logs;") is not None

    # Safe SQL should not match
    assert (
        _DANGEROUS_SQL.search(
            "ALTER TABLE hr_employees ADD COLUMN department VARCHAR(50);"
        )
        is None
    )
    assert _DANGEROUS_SQL.search("CREATE TABLE hr_bonus (id UUID PRIMARY KEY);") is None


@pytest.mark.asyncio
async def test_configure_plugin_credentials_persists_to_repo():
    mock_n8n = AsyncMock()
    mock_n8n.create_credential.return_value = {"id": "new-cred-id"}
    mock_repo = AsyncMock()
    mock_repo.get_credential_ids.return_value = []
    mock_repo.get_config.return_value = {"n8n": ["wf-1"]}
    mock_session = AsyncMock()

    wf_mock = {
        "id": "wf-1",
        "nodes": [
            {
                "type": "n8n-nodes-base.gmail",
                "credentials": {"gmailOAuth2": {}},
            }
        ],
    }
    mock_n8n.get_workflow.return_value = wf_mock

    use_case = ConfigurePluginCredentialsUseCase(
        n8n_adapter=mock_n8n,
        plugin_repo=mock_repo,
        session=mock_session,
    )

    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    pid = uuid.uuid4()
    payload = PluginCredentialPayload(
        credential_type="gmailOAuth2",
        credential_name="company_gmail",
        data={"user": "test@company.com"},
    )

    res = await use_case.execute(str(pid), payload, ctx)
    assert res["credential_id"] == "new-cred-id"

    # Verify repo update
    mock_repo.update_credential_ids.assert_called_once()
    saved_creds = mock_repo.update_credential_ids.call_args[0][2]
    assert any(
        c.get("id") == "new-cred-id" and c.get("type") == "gmailOAuth2"
        for c in saved_creds
    )

    # Verify workflow update
    mock_n8n.update_workflow.assert_called_once()
    assert mock_session.commit.call_count == 1
