# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.database import current_tenant_id, set_session_tenant


def test_init_sql_forces_rls_and_enables_app_user_login():
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    init_sql_path = repo_root / "deploy" / "postgres" / "init.sql"
    assert init_sql_path.exists(), "deploy/postgres/init.sql must exist"

    content = init_sql_path.read_text(encoding="utf-8")

    # 1. Verify app_user is configured with LOGIN
    assert "CREATE ROLE app_user WITH LOGIN" in content
    assert "GRANT USAGE ON SCHEMA public TO app_user" in content

    # 2. Verify all core tables with tenant_id have FORCE ROW LEVEL SECURITY
    core_tables = [
        "users",
        "tenant_plugins",
        "roles",
        "audit_logs",
        "ai_commands",
        "tenant_integrations",
    ]

    for table in core_tables:
        assert (
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in content
        ), f"Missing ENABLE RLS for {table}"
        assert (
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in content
        ), f"Missing FORCE RLS for {table}"


def test_init_sql_policies_use_nullif_and_support_system():
    """Verify RLS policies in init.sql wrap in NULLIF to avoid UUID syntax errors (#728)."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    init_sql_path = repo_root / "deploy" / "postgres" / "init.sql"
    content = init_sql_path.read_text(encoding="utf-8")

    core_tables = [
        "users",
        "tenant_plugins",
        "roles",
        "audit_logs",
        "ai_commands",
        "tenant_integrations",
    ]

    for table in core_tables:
        assert f"tenant_isolation_policy_{table}" in content
        assert (
            "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
            in content
        )
        assert "__system__" in content


def test_plugin_install_forces_rls_on_plugin_tables():
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    install_path = (
        repo_root
        / "core-engine"
        / "backend"
        / "app"
        / "core"
        / "use_cases"
        / "plugin_install.py"
    )
    assert install_path.exists(), "plugin_install.py must exist"

    content = install_path.read_text(encoding="utf-8")
    assert 'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY' in content
    assert "FOR ALL TO public" in content


@pytest.mark.asyncio
async def test_set_session_tenant_config():
    """Verify set_session_tenant sets contextvar and executes config sql (#728)."""
    mock_session = AsyncMock()
    tid = uuid.uuid4()

    await set_session_tenant(mock_session, tid)
    assert current_tenant_id.get() == str(tid)
    mock_session.execute.assert_called_once()

    # System context
    mock_session.reset_mock()
    await set_session_tenant(mock_session, "__system__")
    assert current_tenant_id.get() == "__system__"
    mock_session.execute.assert_called_once()

    # Empty context
    mock_session.reset_mock()
    await set_session_tenant(mock_session, None)
    assert current_tenant_id.get() == ""
    mock_session.execute.assert_called_once()
