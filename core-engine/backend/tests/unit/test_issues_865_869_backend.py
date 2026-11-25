# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit & router tests cho chuỗi bản vá Backend Issues #862, #865, #868, #869."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.external.outline_adapter import OutlineAdapter, OutlineAdapterError
from app.core.domain.entities import (
    AICommandStatus,
    TenantContext,
    TenantIntegrationEntity,
)
from app.core.domain.exceptions import (
    DSLInvalidParametersError,
    InsufficientPermissionsError,
)
from app.core.domain.plugin_manifest import (
    ManifestCompatibility,
    ManifestDatabase,
    ManifestNGSI,
    ManifestNGSIEntity,
    PluginManifest,
)
from app.core.use_cases.ai_command import AICommandDTO, AICommandUseCase
from app.core.use_cases.plugin_install import PluginInstallError, PluginInstallUseCase
from app.core.use_cases.plugin_records import PluginRecordsUseCase
from app.core.use_cases.plugin_uninstall import PluginUninstallUseCase
from app.core.use_cases.plugin_upgrade import PluginUpgradeError, PluginUpgradeUseCase
from app.core.use_cases.tenant_onboarding import TenantOnboardingUseCase
from app.entrypoints.dependencies import (
    get_current_tenant_context,
    get_db_transactional,
    get_keycloak_adapter,
    get_role_repo,
)
from app.entrypoints.routers.roles import get_role_use_case
from main import app

# ─── 1. Issue #862: Outbox Trigger trong Install & Upgrade ────────────────────


@pytest.mark.asyncio
async def test_issue_862_install_attaches_outbox_trigger():
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    session = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    session.execute.return_value = res

    uc = PluginInstallUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    manifest = PluginManifest(
        name="asset-module",
        display_name="Asset",
        version="1.0.0",
        description="d",
        author="a",
        license="MIT",
        compatibility=ManifestCompatibility(proteus_os_min_version="1.0.0"),
        database=ManifestDatabase(tables=["asset_items"]),
        ngsi=ManifestNGSI(
            entities=[ManifestNGSIEntity(table="asset_items", type="Asset")]
        ),
    )

    await uc._step_1_database(ctx, "asset-module", manifest)

    schema_name = f"tenant_{ctx.tenant_id}".replace("-", "_")
    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    expected_drop = (
        f'DROP TRIGGER IF EXISTS "trg_outbox_asset_items" '
        f'ON "{schema_name}"."asset_items";'
    )
    expected_create = (
        f'CREATE TRIGGER "trg_outbox_asset_items" '
        f"AFTER INSERT OR UPDATE OR DELETE "
        f'ON "{schema_name}"."asset_items" '
        f"FOR EACH ROW EXECUTE FUNCTION context.fn_generic_outbox_notify('Asset');"
    )
    assert any(
        "fn_generic_outbox_notify" in s and expected_drop in s and expected_create in s
        for s in sqls
    )


@pytest.mark.asyncio
async def test_issue_862_install_rejects_unsafe_ngsi_identifier():
    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    session = AsyncMock()
    res = MagicMock()
    res.fetchall.return_value = []
    session.execute.return_value = res

    uc = PluginInstallUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    manifest = PluginManifest(
        name="asset-module",
        display_name="Asset",
        version="1.0.0",
        description="d",
        author="a",
        license="MIT",
        compatibility=ManifestCompatibility(proteus_os_min_version="1.0.0"),
        database=ManifestDatabase(tables=["asset_items"]),
        ngsi=ManifestNGSI(
            entities=[ManifestNGSIEntity(table="asset_items", type="Asset'); DROP--")]
        ),
    )

    with pytest.raises(PluginInstallError, match="Invalid NGSI entity"):
        await uc._step_1_database(ctx, "asset-module", manifest)


@pytest.mark.asyncio
async def test_issue_862_upgrade_attaches_outbox_trigger():
    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    plugin_repo = AsyncMock()
    plugin_repo.list_applied_migrations.return_value = {}
    session = AsyncMock()
    uc = PluginUpgradeUseCase(
        plugin_repo=plugin_repo,
        manifest_parser=MagicMock(),
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    manifest = PluginManifest(
        name="meeting-module",
        display_name="Meeting",
        version="1.1.0",
        description="d",
        author="a",
        license="MIT",
        compatibility=ManifestCompatibility(proteus_os_min_version="1.0.0"),
        database=ManifestDatabase(tables=["meeting_rooms"]),
        ngsi=ManifestNGSI(
            entities=[ManifestNGSIEntity(table="meeting_rooms", type="Room")]
        ),
    )

    with patch.object(uc, "_discover_migrations", return_value=[]):
        applied = await uc._step_db_migrations(
            ctx, uuid.uuid4(), "meeting-module", manifest, "1.0.0"
        )

    assert applied == 0
    schema_name = f"tenant_{ctx.tenant_id}".replace("-", "_")
    sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    expected_room_trg = (
        f'CREATE TRIGGER "trg_outbox_meeting_rooms" '
        f"AFTER INSERT OR UPDATE OR DELETE "
        f'ON "{schema_name}"."meeting_rooms" '
        f"FOR EACH ROW EXECUTE FUNCTION context.fn_generic_outbox_notify('Room');"
    )
    assert any(expected_room_trg in s for s in sqls)

    bad_manifest = manifest.model_copy(
        update={
            "ngsi": ManifestNGSI(
                entities=[ManifestNGSIEntity(table="bad-table!", type="Room")]
            )
        }
    )
    with (
        patch.object(uc, "_discover_migrations", return_value=[]),
        pytest.raises(PluginUpgradeError, match="Invalid NGSI entity"),
    ):
        await uc._step_db_migrations(
            ctx, uuid.uuid4(), "meeting-module", bad_manifest, "1.0.0"
        )


# ─── 2. Issue #865.1: Cô lập Collection Outline ở Knowledge Sync & Upload ─────


@pytest.mark.asyncio
async def test_issue_865_1_outline_publish_requires_collection_id(monkeypatch):
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "OUTLINE_API_KEY", "test-outline-key")
    mock_client = AsyncMock()
    adapter = OutlineAdapter(client=mock_client)

    with pytest.raises(OutlineAdapterError, match="collection_id là bắt buộc"):
        await adapter.publish_document("Tiêu đề", "Nội dung", collection_id=None)

    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_issue_865_1_knowledge_sync_and_upload_block_cross_tenant():
    tenant_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    ctx = TenantContext(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: AsyncMock()
    app.state.http_client = AsyncMock()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) sync_knowledge truyền collection_id tenant khác -> 403
            r_sync_403 = await client.post(
                "/api/v1/ai/knowledge/sync",
                json={
                    "connector": "http_feed",
                    "config": {},
                    "collection_id": "other-tenant-collection",
                },
                headers={"Authorization": "Bearer fake"},
            )
            assert r_sync_403.status_code == 403

            # 2) upload_knowledge truyền collection_id tenant khác -> 403
            r_up_403 = await client.post(
                "/api/v1/ai/knowledge/upload",
                data={"collection_id": "other-tenant-collection"},
                files={"file": ("test.txt", b"hello world", "text/plain")},
                headers={"Authorization": "Bearer fake"},
            )
            assert r_up_403.status_code == 403

            # 3) upload_knowledge thiếu collection_id -> tự ép về str(ctx.tenant_id)
            with patch(
                "app.core.use_cases.knowledge_upload.KnowledgeUploadUseCase.execute",
                new_callable=AsyncMock,
            ) as mock_exec:
                mock_exec.return_value = {"status": "success", "id": "doc-1"}
                r_up_ok = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    files={"file": ("test.txt", b"hello world", "text/plain")},
                    headers={"Authorization": "Bearer fake"},
                )
                assert r_up_ok.status_code == 201
                assert mock_exec.await_args.kwargs["collection_id"] == str(tenant_id)
    finally:
        app.dependency_overrides.clear()


# ─── 3. Issue #865.2: Multi-Realm Keycloak resolution ở users.py & roles.py ──


@pytest.mark.asyncio
async def test_issue_865_2_users_and_roles_resolve_tenant_realm():
    tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    admin_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    staff_kc_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    staff_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    role_id = uuid.UUID("55555555-5555-5555-5555-555555555555")

    ctx = TenantContext(tenant_id=tenant_id, user_id=admin_id, roles=["tenant_admin"])
    kc = AsyncMock()
    kc.get_user.return_value = {"emailVerified": False}
    db_mock = AsyncMock()

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: AsyncMock()
    app.dependency_overrides[get_db_transactional] = lambda: db_mock
    app.dependency_overrides[get_keycloak_adapter] = lambda: kc

    pending_user = SimpleNamespace(
        id=staff_id,
        tenant_id=tenant_id,
        keycloak_id=staff_kc_id,
        email="staff@acme.vn",
        full_name="Staff",
        roles=[],
        is_active=False,
        last_login_at=None,
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with (
                patch(
                    "app.entrypoints.routers.users.SQLAlchemyTenantRepository"
                ) as u_tenant_cls,
                patch(
                    "app.entrypoints.routers.users.SQLAlchemyUserRepository"
                ) as u_user_cls,
            ):
                u_tenant_cls.return_value.get_by_id = AsyncMock(
                    return_value=SimpleNamespace(keycloak_realm="acme-realm")
                )
                u_user_cls.return_value.list_by_tenant = AsyncMock(
                    return_value=[pending_user]
                )
                u_user_cls.return_value.get = AsyncMock(return_value=pending_user)
                u_user_cls.return_value.deactivate = AsyncMock()

                # list_users
                r1 = await client.get(
                    "/api/v1/users", headers={"Authorization": "Bearer x"}
                )
                assert r1.status_code == 200
                kc.get_user.assert_awaited_once_with("acme-realm", str(staff_kc_id))

                # resend_invite
                r2 = await client.post(
                    f"/api/v1/users/{staff_id}/resend-invite",
                    headers={"Authorization": "Bearer x", "host": "localhost:3000"},
                )
                assert r2.status_code == 200
                assert kc.send_invite_email.await_args.kwargs["realm"] == "acme-realm"

                # deactivate_user
                r3 = await client.patch(
                    f"/api/v1/users/{staff_id}/deactivate",
                    headers={"Authorization": "Bearer x"},
                )
                assert r3.status_code == 204
                assert kc.disable_user.await_args.kwargs["realm"] == "acme-realm"
                assert kc.logout_user.await_args.kwargs["realm"] == "acme-realm"

            # roles assign & revoke
            mock_role_uc = AsyncMock()
            mock_role_uc.role_repo = SimpleNamespace(session=db_mock)
            mock_role_uc.user_repo.get = AsyncMock(return_value=pending_user)
            mock_role_uc.get_role = AsyncMock(
                return_value=SimpleNamespace(
                    id=role_id,
                    name="hr_manager",
                    display_name="HR Manager",
                    plugin_code_name="hr-module",
                )
            )
            app.dependency_overrides[get_role_use_case] = lambda: mock_role_uc

            with (
                patch(
                    "app.entrypoints.routers.roles.SQLAlchemyTenantRepository"
                ) as r_tenant_cls,
                patch(
                    "app.entrypoints.routers.roles._sync_position_on_assign",
                    new=AsyncMock(),
                ),
            ):
                r_tenant_cls.return_value.get_by_id = AsyncMock(
                    return_value=SimpleNamespace(keycloak_realm="acme-realm")
                )

                r4 = await client.post(
                    f"/api/v1/roles/{role_id}/assign",
                    json={"user_id": str(staff_id)},
                    headers={"Authorization": "Bearer x"},
                )
                assert r4.status_code == 200
                assert kc.assign_role_to_user.await_args.kwargs["realm"] == "acme-realm"

                r5 = await client.post(
                    f"/api/v1/roles/{role_id}/revoke",
                    json={"user_id": str(staff_id)},
                    headers={"Authorization": "Bearer x"},
                )
                assert r5.status_code == 200
                assert (
                    kc.revoke_role_from_user.await_args.kwargs["realm"] == "acme-realm"
                )
    finally:
        app.dependency_overrides.clear()


# ─── 4. Issue #865.3: Truyền đủ parameters vào DSLDryRunEngine ────────────────


@pytest.mark.asyncio
async def test_issue_865_3_ai_command_passes_parameters_to_dry_run(monkeypatch):
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "MATTERMOST_SYSTEM_CHANNEL_ID", "ch-test")
    dry_run_repo = AsyncMock()
    dry_run_repo.execute_dry_run.return_value = {"affected_count": 2, "preview": []}
    mm = AsyncMock()
    mm.send_interactive_message.return_value = "msg-1"

    uc = AICommandUseCase(
        plugin_repo=AsyncMock(),
        ai_command_repo=AsyncMock(),
        dsl_dry_run_repo=dry_run_repo,
        mattermost_adapter=mm,
        n8n_adapter=AsyncMock(),
        role_repo=AsyncMock(),
    )
    uc.dry_run_engine.execute_dry_run = AsyncMock(
        return_value={"affected_count": 2, "preview": []}
    )
    ctx = TenantContext(
        tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["tenant_admin"]
    )
    dto = AICommandDTO(
        command_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        dsl_version="1.0",
        action="hr.leave_requests.approve",
        effect="write",
        parameters={"request_id": "req-999", "reason": "Approved"},
    )

    with patch(
        "app.core.use_cases.ai_command.DSLValidator.validate",
        new_callable=AsyncMock,
        return_value=True,
    ):
        status_out, _, _ = await uc.execute(dto, ctx)

    assert status_out == AICommandStatus.PENDING_APPROVAL
    call_kwargs = uc.dry_run_engine.execute_dry_run.await_args.kwargs
    assert call_kwargs["dsl_payload"] == {
        "action": "hr.leave_requests.approve",
        "effect": "write",
        "parameters": {"request_id": "req-999", "reason": "Approved"},
    }


# ─── 5. Issue #865.4: Uninstall Orion-LD cleanup & PluginManifest events ──────


def test_issue_865_4_plugin_manifest_converts_events_block():
    manifest = PluginManifest(
        name="asset-module",
        display_name="Asset",
        version="1.0.0",
        description="d",
        author="a",
        license="MIT",
        compatibility={"proteus_os_min_version": "1.0.0"},
        workflows=[
            {
                "id": "wf_asset_request",
                "name": "Asset Request",
                "trigger": "webhook",
                "file": "workflows/asset_request.json",
            }
        ],
        events={
            "consumes": [
                "hr.employee.deactivated",
                "finance.expense_request.approved",
            ],
            "produces": [
                "asset.assignment.created",
                "asset.maintenance.due",
            ],
        },
    )

    assert len(manifest.event_subscriptions) == 2
    by_src = {s.source_plugin: s for s in manifest.event_subscriptions}
    assert by_src["hr-module"].event_types == ["hr.employee.deactivated"]
    assert by_src["finance-module"].event_types == ["finance.expense_request.approved"]
    assert by_src["hr-module"].handler_workflow == "workflows/asset_request.json"
    assert [p.event_type for p in manifest.event_publications] == [
        "asset.assignment.created",
        "asset.maintenance.due",
    ]


@pytest.mark.asyncio
async def test_issue_865_4_uninstall_cleans_orion_subscriptions_and_context_tables():
    ctx = TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), roles=["admin"])
    session = AsyncMock()

    select_res = MagicMock()
    select_res.fetchall.return_value = [("urn:ngsi-ld:Subscription:sub-1",)]

    def _exec_side_effect(stmt, *args, **kwargs):
        if "SELECT subscription_id" in str(stmt):
            return select_res
        return MagicMock()

    session.execute.side_effect = _exec_side_effect

    uc = PluginUninstallUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        n8n_adapter=AsyncMock(),
        metabase_adapter=AsyncMock(),
        appsmith_adapter=AsyncMock(),
        keycloak_adapter=AsyncMock(),
        mattermost_adapter=AsyncMock(),
        session=session,
    )
    manifest = PluginManifest(
        name="asset-module",
        display_name="Asset",
        version="1.0.0",
        description="d",
        author="a",
        license="MIT",
        compatibility={"proteus_os_min_version": "1.0.0"},
        ngsi=ManifestNGSI(
            entities=[ManifestNGSIEntity(table="asset_items", type="Asset")]
        ),
    )

    with patch("app.adapters.external.orion_adapter.OrionAdapter") as mock_orion_cls:
        orion_inst = AsyncMock()
        mock_orion_cls.return_value = orion_inst

        await uc._step_1_events(ctx, "asset-module", manifest, [])

        orion_inst.delete_subscription.assert_awaited_once_with(
            "urn:ngsi-ld:Subscription:sub-1", tenant_id=str(ctx.tenant_id)
        )

    executed_sqls = [str(c.args[0]) for c in session.execute.call_args_list]
    assert any("DELETE FROM context.subscriptions" in s for s in executed_sqls)
    assert any("DELETE FROM context.entity_state" in s for s in executed_sqls)
    assert any("DELETE FROM context.context_outbox" in s for s in executed_sqls)


# ─── 6. Issue #865.5 & #869: LF line endings, _coerce bool, RBAC ──────────────


def test_issue_865_5_plugin_records_has_no_orphan_cr():
    records_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "use_cases"
        / "plugin_records.py"
    )
    raw = records_path.read_bytes()
    assert b"\r" not in raw


def test_issue_865_5_coerce_boolean_and_rejects_bool_for_numeric():
    coerce = PluginRecordsUseCase._coerce

    # boolean column coercion
    assert coerce("boolean", "is_active", True) is True
    assert coerce("boolean", "is_active", False) is False
    for truthy in ("true", "TRUE", "1", "yes", " Yes "):
        assert coerce("boolean", "is_active", truthy) is True
    for falsy in ("false", "FALSE", "0", "no", " No "):
        assert coerce("boolean", "is_active", falsy) is False
    for invalid in ("maybe", "", "2", 123):
        with pytest.raises(DSLInvalidParametersError):
            coerce("boolean", "is_active", invalid)

    # bool rejected on numeric/integer columns
    for num_type in (
        "integer",
        "bigint",
        "smallint",
        "numeric",
        "decimal",
        "real",
        "double precision",
    ):
        with pytest.raises(DSLInvalidParametersError):
            coerce(num_type, "amount", True)
        with pytest.raises(DSLInvalidParametersError):
            coerce(num_type, "amount", False)

    # valid numbers still pass
    assert coerce("integer", "qty", 5) == 5
    assert coerce("numeric", "price", "12.50") == Decimal("12.50")
    assert coerce("double precision", "ratio", "0.75") == 0.75


@pytest.mark.asyncio
async def test_issue_869_plugin_records_rbac_approve_manage_and_plural():
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["leave_approver"],
    )
    role_repo = AsyncMock()
    uc = PluginRecordsUseCase(
        plugin_repo=AsyncMock(),
        manifest_parser=MagicMock(),
        role_repo=role_repo,
        session=AsyncMock(),
    )

    # 1) Quyền :approve cho phép read & write trên hr_leave_requests, cấm delete
    role_repo.get_user_permissions.return_value = ["hr:leave_requests:approve"]
    await uc._require_table_permission(ctx, "hr-module", "hr_leave_requests", "read")
    await uc._require_table_permission(ctx, "hr-module", "hr_leave_requests", "write")
    with pytest.raises(InsufficientPermissionsError):
        await uc._require_table_permission(
            ctx, "hr-module", "hr_leave_requests", "delete"
        )

    # 2) Quyền :manage cho phép read/write/delete + singular/plural (ticket -> tickets)
    role_repo.get_user_permissions.return_value = ["it:ticket:manage"]
    await uc._require_table_permission(
        ctx, "it-helpdesk-module", "it_ticket_updates", "write"
    )
    await uc._require_table_permission(
        ctx, "it-helpdesk-module", "it_ticket_updates", "delete"
    )

    # 3) Quyền procurement:po:approve khớp bảng procurement_purchase_orders
    role_repo.get_user_permissions.return_value = ["procurement:po:approve"]
    await uc._require_table_permission(
        ctx, "procurement-module", "procurement_purchase_orders", "write"
    )

    # 4) Quyền :read tuyệt đối KHÔNG được ghi hay xóa
    role_repo.get_user_permissions.return_value = ["finance:expense_requests:read"]
    await uc._require_table_permission(
        ctx, "finance-module", "finance_expense_requests", "read"
    )
    with pytest.raises(InsufficientPermissionsError):
        await uc._require_table_permission(
            ctx, "finance-module", "finance_expense_requests", "write"
        )


# ─── 7. Issue #868: Mask secret trong Tenant Integrations API ─────────────────


@pytest.mark.asyncio
async def test_issue_868_tenant_integrations_masks_secrets_without_mutating_db():
    tenant_id = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tenant_id, user_id=uuid.uuid4(), roles=["tenant_admin"]
    )
    stored_records: list[TenantIntegrationEntity] = []

    tenant_repo = AsyncMock()

    async def _fake_add(entity: TenantIntegrationEntity) -> TenantIntegrationEntity:
        # Lưu bản chụp như DB thật
        stored_records.append(entity.model_copy(deep=True))
        return entity

    tenant_repo.add_integration.side_effect = _fake_add
    tenant_repo.get_integrations.side_effect = lambda _tid: list(stored_records)

    uc = TenantOnboardingUseCase(
        tenant_repo=tenant_repo,
        keycloak_adapter=AsyncMock(),
        session=AsyncMock(),
    )

    raw_cfg = {
        "base_url": "https://smtp.acme.vn",
        "api_key": "sk-live-1234567890abcd",
        "webhook_secret": "short",
        "bot_token": "xoxb-9999998888",
        "smtp_password": "super-secret-password-xyz9",
        "private_key": "-----BEGIN KEY-----9876",
    }
    added = await uc.add_integration(ctx, "custom_smtp", raw_cfg)

    # Giá trị trả về cho UI đã được mask
    assert added.config["base_url"] == "https://smtp.acme.vn"
    assert added.config["api_key"] == "••••••••abcd"
    assert added.config["webhook_secret"] == "••••••••"
    assert added.config["bot_token"] == "••••••••8888"
    assert added.config["smtp_password"] == "••••••••xyz9"
    assert added.config["private_key"] == "••••••••9876"

    # Giá trị thật lưu trong DB KHÔNG bị sửa thành chuỗi mask
    assert stored_records[0].config["api_key"] == "sk-live-1234567890abcd"
    assert stored_records[0].config["webhook_secret"] == "short"
    assert stored_records[0].config["smtp_password"] == "super-secret-password-xyz9"

    # get_integrations cũng trả bản đã mask
    with patch("httpx.AsyncClient") as mock_http_cls:
        http_inst = AsyncMock()
        mock_http_cls.return_value.__aenter__.return_value = http_inst
        listed = await uc.get_integrations(ctx)

    custom = next(i for i in listed if i.provider == "custom_smtp")
    assert custom.config["api_key"] == "••••••••abcd"
    assert stored_records[0].config["api_key"] == "sk-live-1234567890abcd"
