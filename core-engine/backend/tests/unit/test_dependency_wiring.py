import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.domain.entities import PluginStatus
from app.core.use_cases.ai_chat import AIChatUseCase
from app.core.use_cases.ai_command import AICommandUseCase
from app.core.use_cases.plugin_toggle import PluginToggleUseCase
from app.core.use_cases.plugin_upgrade import PluginUpgradeUseCase
from app.entrypoints import dependencies


def _mock_kwargs(factory) -> dict:
    """Build mock cho mọi tham số `Depends(...)` của factory."""
    return {name: MagicMock() for name in inspect.signature(factory).parameters}


async def test_get_ai_command_use_case_resolves_without_type_error():
    """Factory không được truyền tham số mà AICommandUseCase không khai báo."""
    use_case = await dependencies.get_ai_command_use_case(
        **_mock_kwargs(dependencies.get_ai_command_use_case)
    )
    assert isinstance(use_case, AICommandUseCase)


async def test_get_ai_chat_use_case_resolves_without_type_error():
    use_case = await dependencies.get_ai_chat_use_case(
        **_mock_kwargs(dependencies.get_ai_chat_use_case)
    )
    assert isinstance(use_case, AIChatUseCase)


def test_ai_command_factory_params_are_subset_of_constructor():
    """Mọi kwarg factory dùng phải tồn tại trong __init__ của use case."""
    ctor_params = set(inspect.signature(AICommandUseCase.__init__).parameters)
    factory_source = inspect.getsource(dependencies.get_ai_command_use_case)
    assert "conversation_repo=" not in factory_source
    assert "plugin_repo" in ctor_params


@pytest.mark.asyncio
async def test_plugin_toggle_use_case_shares_transactional_session():
    """PluginToggleUseCase và plugin_repo phải dùng chung cùng session (#726)."""
    mock_db = MagicMock()
    mock_n8n = MagicMock()
    use_case = await dependencies.get_plugin_toggle_use_case(
        n8n_adapter=mock_n8n,
        db=mock_db,
    )
    assert isinstance(use_case, PluginToggleUseCase)
    assert use_case.session is mock_db
    assert use_case.plugin_repo._session is mock_db


@pytest.mark.asyncio
async def test_plugin_upgrade_run_upgrade_preserves_was_disabled():
    """run_upgrade tôn trọng tham số was_disabled và giữ status DISABLED (#726)."""
    mock_repo = AsyncMock()
    mock_manifest_parser = MagicMock()
    mock_manifest = MagicMock()
    mock_manifest.version = "1.2.0"
    mock_manifest.display_name = "Test Module"
    mock_manifest_parser.parse.return_value = mock_manifest

    plugin = MagicMock()
    plugin.id = uuid.uuid4()
    plugin.code_name = "test-module"
    mock_repo.get_by_code_name.return_value = plugin
    mock_repo.get_installed_version.return_value = "1.1.0"
    mock_repo.get_installation_status.return_value = PluginStatus.UPGRADING
    mock_repo.get_config.return_value = {}

    use_case = PluginUpgradeUseCase(
        plugin_repo=mock_repo,
        manifest_parser=mock_manifest_parser,
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=AsyncMock(),
    )
    use_case._snapshot = AsyncMock(return_value={})
    use_case._step_db_migrations = AsyncMock(return_value=0)
    use_case._step_n8n_update = AsyncMock(return_value=[])
    use_case._step_metabase_replace = AsyncMock(return_value=[])
    use_case._step_appsmith_replace = AsyncMock(return_value=[])
    use_case._step_keycloak_roles = AsyncMock()

    ctx = MagicMock()
    ctx.tenant_id = uuid.uuid4()

    await use_case.run_upgrade(
        context=ctx,
        plugin_code_name="test-module",
        task_id=uuid.uuid4(),
        was_disabled=True,
    )

    # Status cuối cùng phải là DISABLED, không phải ACTIVE
    mock_repo.upsert_installation.assert_called_with(
        tenant_id=ctx.tenant_id,
        plugin_id=plugin.id,
        status=PluginStatus.DISABLED,
        installed_version="1.2.0",
    )
