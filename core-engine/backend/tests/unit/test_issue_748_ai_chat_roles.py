# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.external.local_manifest_parser import ManifestParserError
from app.adapters.repositories.role_repo import RoleRepository
from app.core.domain.exceptions import ProteusBaseException
from app.core.use_cases.ai_chat import AIChatUseCase
from app.infrastructure.models import RoleModel, UserRoleModel


def test_manifest_parser_error_subclasses_proteus_base_exception():
    assert issubclass(ManifestParserError, ProteusBaseException)


@pytest.mark.asyncio
async def test_ai_chat_build_messages_loads_conversation_history():
    mock_llm = MagicMock()
    mock_command_use_case = MagicMock()
    mock_plugin_repo = MagicMock()
    mock_manifest_parser = MagicMock()
    mock_conversation_repo = AsyncMock()

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    mock_conversation_repo.list_messages.return_value = [
        {"role": "user", "content": "Tin nhắn 1"},
        {"role": "assistant", "content": "Phản hồi 1"},
    ]

    use_case = AIChatUseCase(
        llm_port=mock_llm,
        ai_command_use_case=mock_command_use_case,
        conversation_repo=mock_conversation_repo,
        plugin_repo=mock_plugin_repo,
        manifest_parser=mock_manifest_parser,
    )

    ctx = {"tenant_id": tenant_id, "user_id": user_id}
    messages = await use_case._build_messages(ctx, "Tin nhắn 2 mới", session_id)

    mock_conversation_repo.list_messages.assert_awaited_once_with(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        limit=10,
    )

    # First message is system prompt
    assert messages[0]["role"] == "system"
    # Followed by history
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Tin nhắn 1"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Phản hồi 1"
    # Last message is the current user text
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "Tin nhắn 2 mới"


@pytest.mark.asyncio
async def test_ai_chat_build_messages_without_session_id():
    mock_llm = MagicMock()
    mock_command_use_case = MagicMock()
    mock_plugin_repo = MagicMock()
    mock_manifest_parser = MagicMock()
    mock_conversation_repo = AsyncMock()

    use_case = AIChatUseCase(
        llm_port=mock_llm,
        ai_command_use_case=mock_command_use_case,
        conversation_repo=mock_conversation_repo,
        plugin_repo=mock_plugin_repo,
        manifest_parser=mock_manifest_parser,
    )

    ctx = {"tenant_id": uuid.uuid4(), "user_id": uuid.uuid4()}
    messages = await use_case._build_messages(ctx, "Tin nhắn đơn lẻ", None)

    mock_conversation_repo.list_messages.assert_not_called()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Tin nhắn đơn lẻ"


@pytest.mark.asyncio
async def test_role_repo_delete_role_cleans_user_roles():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    repo = RoleRepository(session=mock_session)
    role_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    await repo.delete_role(role_id, tenant_id)

    # Session.execute should be called twice: 1 for UserRoleModel, 1 for RoleModel
    assert mock_session.execute.call_count == 2
    await mock_session.flush()
