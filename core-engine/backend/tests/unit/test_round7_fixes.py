# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression unit tests cho Round 7 (#805, #806)."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.domain.entities import AICommandStatus, PluginStatus, TenantContext
from app.core.use_cases.rag_ingestion import RAGIngestionUseCase
from app.entrypoints.dependencies import (
    get_ai_chat_use_case,
    get_ai_command_use_case,
    get_current_tenant_context,
    get_plugin_upgrade_use_case,
    get_rag_ingestion_use_case,
    get_role_repo,
)
from main import app


@pytest.mark.asyncio
async def test_get_current_tenant_context_sets_rls_before_is_active_check():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    call_order: list[str] = []

    async def _mock_set_tenant(_db, tid):
        call_order.append(f"set_tenant:{tid}")

    mock_user_repo = AsyncMock()

    async def _mock_get_user(uid):
        call_order.append(f"get_user:{uid}")
        return SimpleNamespace(is_active=False)

    mock_user_repo.get_by_keycloak_id.side_effect = _mock_get_user

    mock_kc = AsyncMock()
    mock_kc.verify_and_decode_token.return_value = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "realm_access": {"roles": ["staff"]},
        "name": "Tester",
    }

    from app.entrypoints.dependencies import get_current_tenant_context as _dep

    with (
        patch(
            "app.infrastructure.database.set_session_tenant",
            side_effect=_mock_set_tenant,
        ),
        patch(
            "app.entrypoints.dependencies.SQLAlchemyUserRepository",
            return_value=mock_user_repo,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _dep(
                credentials=SimpleNamespace(credentials="tok"),
                keycloak_adapter=mock_kc,
                db=AsyncMock(),
            )

    assert exc_info.value.status_code == 401
    assert call_order == [f"set_tenant:{tenant_id}", f"get_user:{user_id}"]


@pytest.mark.asyncio
async def test_rag_ingestion_rejects_foreign_collection_and_filters_strictly():
    tenant_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["ai.knowledge.ingest"]
    mock_uc = AsyncMock()

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_rag_ingestion_use_case] = lambda: mock_uc

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/ai/knowledge/ingest?collection_id=other-tenant-col",
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 403
        mock_uc.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()

    # Unit check RAGIngestionUseCase strict collectionId filter
    doc_port = AsyncMock()
    doc_port.list_documents.return_value = [
        {"id": "1", "collectionId": "other-col", "text": "secret", "title": "S"},
        {"id": "2", "collectionId": None, "text": "orphan", "title": "O"},
    ]
    vec_port = AsyncMock()
    rag = RAGIngestionUseCase(document_source_port=doc_port, vector_db_port=vec_port)
    res = await rag.execute(str(tenant_id), collection_id="my-col")
    assert res.get("processed_documents", res.get("documents_processed", 0)) == 0
    vec_port.upsert_vectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_upgrade_plugin_commits_use_case_session_before_task():
    tenant_id = uuid.uuid4()
    plugin_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["plugins.upgrade"]

    uc_session = AsyncMock()
    uc_repo = AsyncMock()
    uc_repo._session = uc_session
    uc_repo.get_installation_status.return_value = PluginStatus.ACTIVE
    mock_uc = AsyncMock()
    mock_uc.plugin_repo = uc_repo
    mock_uc.prepare_upgrade.return_value = (
        SimpleNamespace(code_name="hr-module"),
        "1.0.0",
        "1.1.0",
    )

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_plugin_upgrade_use_case] = lambda: mock_uc

    try:
        with patch(
            "app.entrypoints.routers.plugins._run_upgrade_plugin_background",
            new_callable=AsyncMock,
        ) as mock_bg:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    f"/api/v1/plugins/{plugin_id}/upgrade",
                    headers={"Authorization": "Bearer fake"},
                )
        assert resp.status_code == 202
        uc_session.commit.assert_awaited_once()
        mock_bg.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_submit_ai_command_nl_extracts_real_command_id():
    real_cmd_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["staff"],
    )
    mock_chat_uc = AsyncMock()
    mock_chat_uc.execute.return_value = (
        AICommandStatus.PENDING_APPROVAL,
        "Chờ duyệt",
        {"dsl_preview": {"command_id": str(real_cmd_id), "action": "hr.leave.create"}},
    )

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_ai_command_use_case] = lambda: AsyncMock()
    app.dependency_overrides[get_ai_chat_use_case] = lambda: mock_chat_uc

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/ai/command",
                json={
                    "session_id": str(uuid.uuid4()),
                    "natural_language_input": "xin nghỉ phép ngày mai",
                },
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 202
        assert resp.json()["command_id"] == str(real_cmd_id)
    finally:
        app.dependency_overrides.clear()
