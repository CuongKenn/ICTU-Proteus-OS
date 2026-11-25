# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression unit tests for Issues #882, #883, #884, and #885 (Backend)."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.adapters.external.local_manifest_parser import LocalManifestParser
from app.adapters.external.outline_adapter import OutlineAdapter
from app.adapters.repositories.ai_command_repo import SQLAlchemyAICommandRepository
from app.adapters.repositories.conversation_repo import ConversationRepository
from app.adapters.repositories.hr_leave_repo import SQLAlchemyHRLeaveRepository
from app.core.domain.entities import AICommandStatus, PluginStatus, TenantContext
from app.core.use_cases.action_catalog import (
    resolve_workflow_webhook_url,
    split_plugin_action,
)
from app.core.use_cases.ai_chat import AIChatDTO, AIChatUseCase
from app.core.use_cases.ai_command import AICommandDTO, AICommandUseCase
from app.core.use_cases.dsl_validator import DSLInvalidParametersError, DSLValidator
from app.core.use_cases.event_subscriber_worker import EventSubscriberWorker
from app.core.use_cases.plugin_action import PluginActionUseCase
from app.core.use_cases.plugin_install import (
    PluginInstallError,
    PluginInstallUseCase,
    _split_seed_statements_safe,
    _validate_seed_statement,
)
from app.core.use_cases.rag_ingestion import RAGIngestionUseCase
from app.entrypoints import dependencies
from app.entrypoints.dependencies import (
    get_ai_command_use_case,
    get_audit_log_repo,
    get_conversation_use_case,
    get_current_tenant_context,
    get_qdrant_adapter,
    get_rag_ingestion_use_case,
    get_role_repo,
)
from app.infrastructure.config import settings
from app.infrastructure.database import get_db_transactional
from main import app

# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #882: AI Command Approval Completion, core.*, core.knowledge.save & Z3
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_882_ai_command_repo_update_execution_result():
    session = AsyncMock()
    session.add = MagicMock()
    repo = SQLAlchemyAICommandRepository(session=session)
    cmd_id = uuid.uuid4()

    await repo.update_execution_result(
        cmd_id,
        {"saved": True, "title": "SOP"},
        status=AICommandStatus.COMPLETED,
    )

    session.execute.assert_awaited_once()
    stmt, bind = session.execute.await_args.args
    sql = str(stmt)
    assert "execution_result = :res" in sql
    assert "status = :status" in sql
    assert "executed_at = NOW()" in sql
    assert bind["status"] == "COMPLETED"
    assert bind["cmd_id"] == cmd_id
    assert json.loads(bind["res"]) == {"saved": True, "title": "SOP"}


@pytest.mark.asyncio
async def test_issue_882_process_approval_completes_core_knowledge_save_and_n8n():
    tenant_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    approver_id = uuid.uuid4()
    cmd_id = uuid.uuid4()

    ai_cmd_repo = AsyncMock()
    n8n_adapter = AsyncMock()
    n8n_adapter.trigger_webhook.return_value = {"ticket_id": "T-100"}
    qdrant_adapter = AsyncMock()
    user_repo = AsyncMock()
    user_repo.get_by_email.return_value = None
    user_repo.get.return_value = SimpleNamespace(
        id=approver_id,
        tenant_id=tenant_id,
        roles=["tenant_admin"],
        is_active=True,
    )
    mm_adapter = AsyncMock()
    mm_adapter.get_user_by_id.return_value = None

    uc = AICommandUseCase(
        plugin_repo=AsyncMock(),
        ai_command_repo=ai_cmd_repo,
        dsl_dry_run_repo=AsyncMock(),
        role_repo=AsyncMock(),
        mattermost_adapter=mm_adapter,
        n8n_adapter=n8n_adapter,
        qdrant_adapter=qdrant_adapter,
        user_repo=user_repo,
    )

    # 1) core.knowledge.save approval -> COMPLETED + Qdrant indexed
    ai_cmd_repo.get_command_by_id.return_value = {
        "id": cmd_id,
        "tenant_id": tenant_id,
        "issued_by_user_id": requester_id,
        "status": "PENDING_APPROVAL",
        "effect": "write",
        "action": "core.knowledge.save",
        "parameters": {
            "title": "Quy trình vận hành Lab AI",
            "content": "Bước 1: Kiểm tra GPU.\n\nBước 2: Bật Docker.",
            "para_space": "areas",
        },
        "approved_by_user_id": None,
    }
    with patch("app.adapters.external.outline_adapter.settings") as mock_out_settings:
        mock_out_settings.OUTLINE_URL = "http://outline.local"
        mock_out_settings.OUTLINE_API_KEY = ""
        outcome = await uc.process_approval(str(cmd_id), str(approver_id), "approve")

    assert outcome == "approved"
    ai_cmd_repo.update_execution_result.assert_awaited_once()
    exec_args = ai_cmd_repo.update_execution_result.await_args
    assert exec_args.kwargs["status"] == AICommandStatus.COMPLETED
    assert exec_args.args[1]["saved"] is True
    assert exec_args.args[1]["para_space"] == "areas"
    qdrant_adapter.upsert_vectors.assert_awaited_once()

    # 2) n8n plugin action approval -> transitions to COMPLETED with webhook response
    ai_cmd_repo.reset_mock()
    cmd_id_2 = uuid.uuid4()
    ai_cmd_repo.get_command_by_id.return_value = {
        "id": cmd_id_2,
        "tenant_id": tenant_id,
        "issued_by_user_id": requester_id,
        "status": "PENDING_APPROVAL",
        "effect": "write",
        "action": "hr.leave_requests.approve",
        "parameters": {"request_id": "req-1"},
        "approved_by_user_id": None,
    }
    n8n_adapter.build_webhook_url = MagicMock(
        return_value="http://n8n:5678/webhook/hr-leave-approve"
    )
    outcome_n8n = await uc.process_approval(str(cmd_id_2), str(approver_id), "approve")
    assert outcome_n8n == "approved"
    ai_cmd_repo.update_execution_result.assert_awaited_once_with(
        cmd_id_2, {"ticket_id": "T-100"}, status=AICommandStatus.COMPLETED
    )
    ai_cmd_repo.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_issue_882_dsl_validator_catches_domain_z3_invalid_params_in_both_paths(
    tmp_path,
):
    plugin_repo = AsyncMock()
    plugin_repo.get_tenant_plugin_status_by_code.return_value = PluginStatus.ACTIVE
    role_repo = AsyncMock()
    role_repo.get_user_permissions.return_value = ["hr:leave:write", "meeting:*"]

    # 1) 3-part action with invalid Z3 parameter type (start_time="not-a-date")
    validator_3p = DSLValidator(
        plugin_repo=plugin_repo,
        role_repo=role_repo,
        tenant_id="t-882",
        user_id=str(uuid.uuid4()),
    )
    with pytest.raises(DSLInvalidParametersError, match="start_time"):
        await validator_3p.validate(
            {
                "dsl_version": "1.0",
                "action": "meeting.bookings.create",
                "effect": "write",
                "parameters": {"start_time": "invalid-date", "end_time": "10:00"},
            }
        )

    # 2) 2-part plugin workflow action with invalid Z3 parameter type (days="abc")
    parser = MagicMock()
    parser.plugins_dir = tmp_path
    (tmp_path / "hr-module").mkdir()
    parser.parse.return_value = SimpleNamespace(
        name="hr-module",
        workflows=[
            SimpleNamespace(
                id="wf_leave_create",
                file="workflows/leave.json",
                trigger="webhook",
            )
        ],
    )
    validator_2p = DSLValidator(
        plugin_repo=plugin_repo,
        role_repo=role_repo,
        tenant_id="t-882",
        user_id=str(uuid.uuid4()),
        manifest_parser=parser,
    )
    with pytest.raises(DSLInvalidParametersError, match="days"):
        await validator_2p.validate(
            {
                "dsl_version": "1.0",
                "action": "hr.wf_leave_create",
                "effect": "write",
                "parameters": {"days": "ba-ngay"},
            }
        )

    # 3) AIChatUseCase._run_react handles Z3 parameter type error gracefully
    cmd_uc = AICommandUseCase(
        plugin_repo=plugin_repo,
        ai_command_repo=AsyncMock(),
        dsl_dry_run_repo=AsyncMock(),
        role_repo=role_repo,
        mattermost_adapter=AsyncMock(),
        n8n_adapter=AsyncMock(),
        manifest_parser=parser,
    )
    llm = MagicMock()
    llm.ainvoke_json = AsyncMock(
        return_value=SimpleNamespace(content='{"thought": "dừng", "finish": true}')
    )
    chat_uc = AIChatUseCase(llm_port=llm, ai_command_use_case=cmd_uc)
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    dto = AIChatDTO(session_id=uuid.uuid4(), natural_language_input="nghỉ ba ngày")
    bad_step = AICommandDTO(
        command_id=uuid.uuid4(),
        session_id=dto.session_id,
        dsl_version="1.0",
        action="hr.wf_leave_create",
        effect="write",
        parameters={"days": "ba-ngay"},
    )
    st, msg, _ = await chat_uc._run_react([bad_step], dto, ctx)
    assert st == AICommandStatus.FAILED
    assert "days" in msg


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #883: P.A.R.A Knowledge Isolation, Upload/Ingest/Sync & Session PK
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_883_outline_para_collection_does_not_leak_untagged_other_tenant():
    tid_a = "aaaaaaaa-1111-2222-3333-444444444444"
    tid_b = "bbbbbbbb-1111-2222-3333-444444444444"
    collections = [
        {"id": "untagged-1", "name": "1. Projects", "description": "Generic projects"},
        {
            "id": "tagged-a",
            "name": "1. Projects (Tenant A)",
            "description": f"Dự án [tenant:{tid_a}]",
        },
    ]

    # Tenant B must NOT match untagged "1. Projects" or Tenant A's collection
    assert (
        OutlineAdapter._match_tenant_para_collection(
            collections, tenant_id=tid_b, space_name="1. Projects"
        )
        is None
    )
    # Tenant A matches its own tagged collection
    matched_a = OutlineAdapter._match_tenant_para_collection(
        collections, tenant_id=tid_a, space_name="1. Projects"
    )
    assert matched_a is not None and matched_a["id"] == "tagged-a"


@pytest.mark.asyncio
async def test_issue_883_para_bootstrap_rbac_upload_ingest_sync_and_qdrant_local():
    tid = uuid.uuid4()
    unpriv_ctx = TenantContext(
        tenant_id=tid,
        user_id=uuid.uuid4(),
        roles=["staff"],
        email="staff@ictu.edu.vn",
    )
    admin_ctx = TenantContext(
        tenant_id=tid,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
        email="admin@ictu.edu.vn",
    )
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = []
    mock_qdrant = AsyncMock()
    mock_ingest_uc = AsyncMock()
    mock_ingest_uc.execute.return_value = {
        "status": "success",
        "processed_documents": 2,
        "upserted_chunks": 3,
    }

    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.dependency_overrides[get_qdrant_adapter] = lambda: mock_qdrant
    app.dependency_overrides[get_rag_ingestion_use_case] = lambda: mock_ingest_uc
    app.state.http_client = AsyncMock(spec=httpx.AsyncClient)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) Unprivileged user blocked from POST /knowledge/para/bootstrap (403)
            app.dependency_overrides[get_current_tenant_context] = lambda: unpriv_ctx
            r_boot_403 = await client.post("/api/v1/ai/knowledge/para/bootstrap")
            assert r_boot_403.status_code == 403

            # 2) Local upload indexes extracted chunks into Qdrant
            app.dependency_overrides[get_current_tenant_context] = lambda: admin_ctx
            with patch("app.adapters.external.outline_adapter.settings") as m_set:
                m_set.OUTLINE_URL = "http://outline.local"
                m_set.OUTLINE_API_KEY = ""
                r_local_up = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    data={"para_space": "projects"},
                    files={
                        "file": (
                            "sprint-plan.md",
                            b"# Sprint 1\nNoi dung ke hoach du an.",
                            "text/markdown",
                        )
                    },
                )
            assert r_local_up.status_code == 201
            assert r_local_up.json()["mode"] == "local_para"
            assert r_local_up.json()["upserted_chunks"] >= 1
            mock_qdrant.upsert_vectors.assert_awaited_once()
            q_kwargs = mock_qdrant.upsert_vectors.await_args.kwargs
            assert q_kwargs["tenant_id"] == str(tid)
            assert q_kwargs["metadatas"][0]["para_space"] == "projects"
            assert q_kwargs["metadatas"][0]["title"] == "sprint-plan"

            # 3) Online upload auto-bootstraps P.A.R.A space when empty collection_id,
            #    and maps OutlineAdapterError -> 502 Bad Gateway
            para_spaces_online = [
                {
                    "key": "projects",
                    "name": "1. Projects",
                    "collection_id": "out-proj-1",
                    "mode": "outline",
                },
                {
                    "key": "areas",
                    "name": "2. Areas",
                    "collection_id": "out-area-2",
                    "mode": "outline",
                },
                {
                    "key": "resources",
                    "name": "3. Resources",
                    "collection_id": "out-res-3",
                    "mode": "outline",
                },
                {
                    "key": "archives",
                    "name": "4. Archives",
                    "collection_id": "out-arch-4",
                    "mode": "outline",
                },
            ]
            with (
                patch("app.adapters.external.outline_adapter.settings") as m_set,
                patch.object(
                    OutlineAdapter,
                    "get_para_spaces",
                    new=AsyncMock(
                        side_effect=[
                            [{"key": "projects", "mode": "local_para"}],
                            para_spaces_online,
                            para_spaces_online,
                        ]
                    ),
                ),
                patch.object(
                    OutlineAdapter,
                    "ensure_para_spaces",
                    new=AsyncMock(return_value=para_spaces_online),
                ) as mock_ensure,
                patch.object(
                    OutlineAdapter,
                    "publish_document",
                    new=AsyncMock(
                        return_value={"id": "doc-out-1", "url": "http://wiki/doc/1"}
                    ),
                ) as mock_pub,
            ):
                m_set.OUTLINE_URL = "http://outline.local"
                m_set.OUTLINE_API_KEY = "real-outline-key"

                r_online_up = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    data={"para_space": "projects"},
                    files={"file": ("roadmap.md", b"# Roadmap", "text/markdown")},
                )
                assert r_online_up.status_code == 201
                assert r_online_up.json()["collection_id"] == "out-proj-1"
                mock_ensure.assert_awaited_once()
                assert mock_pub.await_args.kwargs["collection_id"] == "out-proj-1"

                # Ingest with P.A.R.A collection_id allowed (not false 403)
                r_ingest_single = await client.post(
                    "/api/v1/ai/knowledge/ingest?collection_id=out-area-2"
                )
                assert r_ingest_single.status_code == 200

                # Ingest without collection_id passes all tenant P.A.R.A collection_ids
                mock_ingest_uc.execute.reset_mock()
                r_ingest_all = await client.post("/api/v1/ai/knowledge/ingest")
                assert r_ingest_all.status_code == 200
                ingest_kwargs = mock_ingest_uc.execute.await_args.kwargs
                assert set(ingest_kwargs["collection_ids"]) >= {
                    str(tid),
                    "out-proj-1",
                    "out-area-2",
                    "out-res-3",
                    "out-arch-4",
                }

            # Outline error when OUTLINE_API_KEY is set -> 502 Bad Gateway
            from app.adapters.external.outline_adapter import OutlineAdapterError

            with (
                patch("app.adapters.external.outline_adapter.settings") as m_set,
                patch.object(
                    OutlineAdapter,
                    "get_para_spaces",
                    new=AsyncMock(return_value=para_spaces_online),
                ),
                patch.object(
                    OutlineAdapter,
                    "publish_document",
                    new=AsyncMock(
                        side_effect=OutlineAdapterError("Outline upstream 500")
                    ),
                ),
            ):
                m_set.OUTLINE_URL = "http://outline.local"
                m_set.OUTLINE_API_KEY = "real-outline-key"
                r_502 = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    data={"para_space": "areas"},
                    files={"file": ("sop.md", b"# SOP", "text/markdown")},
                )
                assert r_502.status_code == 502
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_issue_883_rag_ingestion_preserves_vectors_on_empty_and_single_space():
    source = MagicMock()
    source.list_documents = AsyncMock(return_value=[])
    vec = MagicMock()
    vec.replace_tenant_vectors = AsyncMock()
    vec.upsert_vectors = AsyncMock()

    uc = RAGIngestionUseCase(source, vec)

    # 1) Empty documents -> NEVER wipe tenant vectors
    res_empty = await uc.execute("tenant-1", collection_ids=["tenant-1", "c-proj"])
    assert res_empty["status"] == "success"
    assert res_empty["upserted_chunks"] == 0
    vec.replace_tenant_vectors.assert_not_awaited()
    vec.upsert_vectors.assert_not_awaited()

    # 2) Single collection_id -> upsert_vectors (preserving other 3 P.A.R.A spaces)
    source.list_documents = AsyncMock(
        return_value=[
            {
                "id": "d-1",
                "title": "Ghi chú",
                "text": "Nội dung dự án X.",
                "collectionId": "c-proj",
            }
        ]
    )
    res_single = await uc.execute(
        "tenant-1", collection_id="c-proj", para_space="projects"
    )
    assert res_single["upserted_chunks"] == 1
    vec.upsert_vectors.assert_awaited_once()
    vec.replace_tenant_vectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_issue_883_conversation_repo_pk_collision_maps_to_403():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    colliding_session_id = uuid.uuid4()

    session = AsyncMock()
    session.add = MagicMock()
    user_lookup_res = MagicMock()
    user_lookup_res.scalar.return_value = user_id
    empty_select_res = MagicMock()
    empty_select_res.scalar_one_or_none.return_value = None
    session.execute.side_effect = [
        user_lookup_res,
        empty_select_res,
        empty_select_res,
        user_lookup_res,
        empty_select_res,
    ]

    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = nested_cm
    nested_cm.__aexit__.return_value = False
    session.begin_nested = MagicMock(return_value=nested_cm)
    session.flush.side_effect = IntegrityError(
        "INSERT INTO ai_sessions", {}, Exception("duplicate key")
    )

    repo = ConversationRepository(session)
    with pytest.raises(PermissionError, match="Session belongs to another tenant"):
        await repo.ensure_session(tenant_id, user_id, colliding_session_id)

    with pytest.raises(PermissionError, match="Session belongs to another tenant"):
        await repo.assert_session_owned(tenant_id, user_id, colliding_session_id)

    # Verify router maps PermissionError -> 403 Forbidden
    mock_conv_uc = AsyncMock()
    mock_conv_uc.ensure_session.side_effect = PermissionError(
        "Session belongs to another tenant"
    )
    ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, roles=["staff"])
    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_conversation_use_case] = lambda: mock_conv_uc
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ai/sessions",
                json={"session_id": str(colliding_session_id)},
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #884: RLS in Webhooks/Jobs, HR Leave SQL, Event Worker & Multi-word Plugin
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_884_keycloak_and_mattermost_reject_set_rls_and_main_jobs(
    monkeypatch,
):
    # 1) get_keycloak_webhook_use_case sets __system__ on transactional session
    mock_db = AsyncMock()
    mock_mm = AsyncMock()
    with patch(
        "app.infrastructure.database.set_session_tenant", new_callable=AsyncMock
    ) as mock_set_tenant:
        kc_uc = await dependencies.get_keycloak_webhook_use_case(
            db=mock_db, mattermost_adapter=mock_mm
        )
        mock_set_tenant.assert_awaited_once_with(mock_db, "__system__")
        assert kc_uc.session is mock_db

    # 2) Mattermost reject branch sets __system__ then cmd["tenant_id"]
    monkeypatch.setattr(settings, "MATTERMOST_WEBHOOK_SECRET", "mm-secret-884")
    cmd_id = str(uuid.uuid4())
    cmd_tenant = str(uuid.uuid4())
    body = json.dumps(
        {
            "user_id": "mm-approver",
            "context": {"action_id": cmd_id, "action": "reject"},
        }
    ).encode("utf-8")
    sig = hmac.new(b"mm-secret-884", body, hashlib.sha256).hexdigest()

    db = AsyncMock()
    ai_uc = AsyncMock()
    ai_uc.ai_command_repo = AsyncMock()
    ai_uc.ai_command_repo._session = db
    ai_uc.ai_command_repo.get_command_by_id.return_value = {
        "id": cmd_id,
        "tenant_id": cmd_tenant,
        "status": "PENDING_APPROVAL",
    }
    ai_uc.process_approval.return_value = "rejected"

    app.dependency_overrides[get_db_transactional] = lambda: db
    app.dependency_overrides[get_ai_command_use_case] = lambda: ai_uc
    app.dependency_overrides[get_audit_log_repo] = lambda: AsyncMock()
    try:
        tenant_calls: list[str] = []

        async def _record_tenant(_sess, tid):
            tenant_calls.append(str(tid))

        with patch(
            "app.infrastructure.database.set_session_tenant",
            side_effect=_record_tenant,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/api/v1/webhooks/mattermost/callback",
                    content=body,
                    headers={"Mattermost-Signature": sig},
                )
        assert resp.status_code == 200
        assert tenant_calls[:2] == ["__system__", cmd_tenant]
    finally:
        app.dependency_overrides.clear()

    # 3) Verify main.py background jobs set __system__
    main_src = (Path(__file__).resolve().parents[2] / "main.py").read_text(
        encoding="utf-8"
    )
    for fn_name in (
        "async def run_plugin_cleanup()",
        "async def run_proactive_monitor_scan()",
        "async def run_proactive_monitor_morning()",
    ):
        idx = main_src.index(fn_name)
        snippet = main_src[idx : idx + 350]
        assert 'await set_session_tenant(session, "__system__")' in snippet


@pytest.mark.asyncio
async def test_issue_884_hr_leave_repo_duration_days_status_and_savepoint():
    session = AsyncMock()
    session.add = MagicMock()
    nested_cm = AsyncMock()
    nested_cm.__aenter__.return_value = nested_cm
    nested_cm.__aexit__.return_value = False
    session.begin_nested = MagicMock(return_value=nested_cm)

    schemas_res = MagicMock()
    schemas_res.scalars.return_value.all.return_value = ["tenant_broken", "tenant_ok"]

    ok_res = MagicMock()
    ok_res.mappings.return_value.all.return_value = [
        {"employee_id": "emp-1", "days_count": 3, "status": "PENDING_APPROVAL"}
    ]

    executed_sqls: list[str] = []

    async def _exec(stmt, params=None):
        sql = str(stmt)
        executed_sqls.append(sql)
        if "information_schema.tables" in sql:
            return schemas_res
        if '"tenant_broken"' in sql:
            raise RuntimeError("schema column mismatch")
        return ok_res

    session.execute.side_effect = _exec
    repo = SQLAlchemyHRLeaveRepository(session=session)
    leaves = await repo.get_pending_leaves_older_than(2)

    assert leaves is not None and len(leaves) == 1
    assert leaves[0]["days_count"] == 3
    assert session.begin_nested.call_count == 2
    assert any("COALESCE(duration_days, 1) AS days_count" in s for s in executed_sqls)
    assert any(
        "UPPER(status) IN ('PENDING', 'PENDING_APPROVAL')" in s for s in executed_sqls
    )


def test_issue_884_event_subscriber_tenant_webhook_and_multiword_plugins(tmp_path):
    # 1) EventSubscriberWorker optional tenant_id prefixing
    parser = LocalManifestParser()
    n8n = MagicMock()
    worker = EventSubscriberWorker(manifest_parser=parser, n8n_adapter=n8n)
    tid = uuid.UUID("abcdef12-3456-7890-abcd-ef1234567890")

    url_no_tid = worker._resolve_handler_webhook_url(
        "document-module", "workflows/reassign_document.json"
    )
    assert url_no_tid.endswith("/webhook/document/reassign")

    url_with_tid = worker._resolve_handler_webhook_url(
        "document-module", "workflows/reassign_document.json", tenant_id=tid
    )
    assert url_with_tid.endswith("/webhook/t_abcdef12_document/reassign")

    # 2) Real it-helpdesk-module action resolution: it.wf_ticket_create
    assert split_plugin_action("it.wf_ticket_create") == (
        "it-helpdesk-module",
        "wf_ticket_create",
    )
    it_url = resolve_workflow_webhook_url(
        parser, "it-helpdesk-module", "wf_ticket_create", tenant_id=tid
    )
    assert it_url.endswith("/webhook/t_abcdef12_helpdesk/ticket/create")

    # 3) Synthesized multi-word plugin: lab-asset-module -> lab.wf_lab_items_sync
    lab_dir = tmp_path / "lab-asset-module" / "workflows"
    lab_dir.mkdir(parents=True)
    (tmp_path / "lab-asset-module" / "manifest.yaml").write_text(
        'name: "lab-asset-module"\nversion: "1.0.0"\n', encoding="utf-8"
    )
    (lab_dir / "lab_items_sync.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "type": "n8n-nodes-base.webhook",
                        "parameters": {"path": "lab/items/sync"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    mock_parser = MagicMock()
    mock_parser.plugins_dir = tmp_path
    mock_parser.parse.return_value = SimpleNamespace(
        name="lab-asset-module",
        workflows=[
            SimpleNamespace(
                id="wf_lab_items_sync",
                file="workflows/lab_items_sync.json",
                name="Lab Sync",
                description="Sync lab items",
                trigger="webhook",
            )
        ],
    )
    assert split_plugin_action(
        "lab.wf_lab_items_sync", manifest_parser=mock_parser
    ) == ("lab-asset-module", "wf_lab_items_sync")

    cmd_uc = AICommandUseCase(
        plugin_repo=AsyncMock(),
        ai_command_repo=AsyncMock(),
        dsl_dry_run_repo=AsyncMock(),
        role_repo=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        n8n_adapter=AsyncMock(),
        manifest_parser=mock_parser,
    )
    lab_url = cmd_uc._resolve_action_url("lab.wf_lab_items_sync", tenant_id=tid)
    assert lab_url.endswith("/webhook/t_abcdef12_lab/items/sync")


@pytest.mark.asyncio
async def test_issue_884_plugin_action_use_case_resolves_short_prefix_for_multiword():
    parser = LocalManifestParser()
    repo = AsyncMock()
    repo.get_by_code_name.return_value = SimpleNamespace(id=uuid.uuid4())
    repo.get_installation_status.return_value = PluginStatus.ACTIVE
    role_repo = AsyncMock()
    role_repo.get_user_permissions.return_value = ["it:tickets:write"]
    n8n = AsyncMock()
    n8n.trigger_webhook.return_value = {"success": True}

    uc = PluginActionUseCase(
        plugin_repo=repo,
        manifest_parser=parser,
        n8n_adapter=n8n,
        role_repo=role_repo,
    )
    ctx = TenantContext(
        tenant_id=uuid.UUID("12345678-1111-2222-3333-444444444444"),
        user_id=uuid.uuid4(),
        roles=["it_staff"],
    )
    res = await uc.execute(
        ctx, "it-helpdesk-module", "wf_ticket_create", {"title": "Wifi hỏng"}
    )
    assert res["action"] == "wf_ticket_create"
    webhook_url = n8n.trigger_webhook.await_args.args[0]
    assert webhook_url.endswith("/webhook/t_12345678_helpdesk/ticket/create")


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE #885: Seed Validator String Literal Handling & Dynamic Plugin RLS NULLIF
# ─────────────────────────────────────────────────────────────────────────────


def test_issue_885_validate_seed_allows_keywords_in_literals_and_blocks_real_sql():
    # Real it-helpdesk-module seed_data.sql (contains 'reset mật khẩu' inside literal)
    it_seed_path = (
        Path(__file__).resolve().parents[4]
        / "plugins"
        / "it-helpdesk-module"
        / "db"
        / "seed_data.sql"
    )
    stmts = _split_seed_statements_safe(it_seed_path.read_text(encoding="utf-8"))
    assert len(stmts) >= 5
    for stmt in stmts:
        _validate_seed_statement(stmt)

    # Escaped single quotes containing multiple forbidden keywords inside string literal
    tricky_ok = (
        "INSERT INTO it_categories (id, name, description) VALUES "
        "('11111111-1111-1111-1111-111111111111', 'It''s reset & update', "
        "'Hướng dẫn drop cache, set role, copy file, public.users') "
        "ON CONFLICT (id) DO NOTHING;"
    )
    _validate_seed_statement(tricky_ok)

    # Actual forbidden SQL outside string literals MUST still be rejected
    for forbidden in (
        "RESET ALL;",
        "SET role TO postgres;",
        "DROP TABLE it_tickets;",
        "COPY it_tickets FROM '/tmp/pwn.csv';",
        "INSERT INTO public.users (id) VALUES ('1');",
        "SELECT * FROM public.users;",
    ):
        with pytest.raises(PluginInstallError):
            _validate_seed_statement(forbidden)


@pytest.mark.asyncio
async def test_issue_885_plugin_install_rls_policy_uses_nullif_and_system_bypass(
    tmp_path,
):
    plugin_dir = tmp_path / "hr-module"
    plugin_dir.mkdir()
    (plugin_dir / "seed.sql").write_text(
        "CREATE TABLE hr_test (id UUID PRIMARY KEY, tenant_id UUID NOT NULL);",
        encoding="utf-8",
    )
    parser = MagicMock()
    parser.plugins_dir = tmp_path

    session = AsyncMock()
    session.add = MagicMock()
    cols_res = MagicMock()
    cols_res.fetchall.return_value = [("hr_test",)]
    default_res = MagicMock()
    default_res.fetchall.return_value = []

    executed_sqls: list[str] = []

    async def _exec(stmt, params=None):
        s = str(stmt)
        executed_sqls.append(s)
        if "information_schema.columns" in s:
            return cols_res
        return default_res

    session.execute.side_effect = _exec

    uc = PluginInstallUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=parser,
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    from app.core.domain.plugin_manifest import PluginManifest

    manifest = PluginManifest(
        name="hr-module",
        display_name="HR",
        version="1.0.0",
        description="HR",
        author="ICTU",
        license="AGPL-3.0",
        compatibility={"proteus_os_min_version": "1.0.0"},
        database={"tables": ["hr_test"], "seed_file": "seed.sql"},
    )
    ctx = TenantContext(
        tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["tenant_admin"]
    )
    await uc._step_1_database(ctx, "hr-module", manifest)

    policy_stmts = [
        s for s in executed_sqls if "CREATE POLICY tenant_isolation_policy" in s
    ]
    assert len(policy_stmts) == 1
    assert (
        "current_setting('app.current_tenant_id', true) = '__system__'"
        in policy_stmts[0]
    )
    assert (
        "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
        in policy_stmts[0]
    )
