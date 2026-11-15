# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.domain.entities import TenantContext
from app.core.use_cases.ai_chat import AIChatUseCase
from app.core.use_cases.plugin_install import PluginInstallError, PluginInstallUseCase
from app.core.use_cases.plugin_upgrade import _split_sql_statements


def test_split_sql_statements_respects_double_quoted_identifiers():
    sql = 'CREATE TABLE "my;table" (id int); INSERT INTO "my;table" VALUES (1);'
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2
    assert '"my;table"' in stmts[0]
    assert '"my;table"' in stmts[1]


@pytest.mark.asyncio
async def test_plugin_install_marks_failed_dirty_when_manifest_parse_raises():
    session = AsyncMock()
    plugin_repo = AsyncMock()
    plugin = MagicMock()
    plugin.id = uuid.uuid4()
    plugin.version = "1.0.0"
    plugin_repo.get_by_code_name.return_value = plugin
    plugin_repo.get_tenant_plugin_status.return_value = None

    manifest_parser = MagicMock()
    manifest_parser.parse.side_effect = ValueError("bad manifest")

    uc = PluginInstallUseCase(
        session=session,
        plugin_repo=plugin_repo,
        manifest_parser=manifest_parser,
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
    )
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
        email="admin@example.com",
    )

    with pytest.raises(PluginInstallError, match="bad manifest"):
        await uc.execute(ctx, "hr-module")

    plugin_repo.update_status.assert_awaited()
    assert plugin_repo.update_status.await_args.kwargs["status"].value == "FAILED_DIRTY"


def test_ai_chat_summarize_keeps_truncation_note_with_data_parts():
    uc = AIChatUseCase(llm_port=MagicMock(), ai_command_use_case=MagicMock())
    outcomes = [
        {
            "index": 1,
            "action": "hr.employees.list",
            "status": "COMPLETED",
            "result": {"count": 2, "items": [{"name": "A"}, {"name": "B"}]},
        }
    ]
    overall, summary, _ = uc._summarize(
        outcomes=outcomes,
        total_hint=4,
        thoughts=["step 1"],
        end_reason="iters",
    )
    assert overall.value == "COMPLETED"
    assert "dừng sau giới hạn vòng lặp" in summary
