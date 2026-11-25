# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests cho Issue #875 Backend — Cấu trúc P.A.R.A trên Outline & Qdrant."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.external.outline_adapter import OutlineAdapter
from app.core.domain.entities import TenantContext
from app.core.use_cases.rag_ingestion import RAGIngestionUseCase, infer_para_space
from app.core.use_cases.tenant_onboarding import TenantOnboardingUseCase
from app.entrypoints.dependencies import get_current_tenant_context, get_role_repo
from main import app


@pytest.mark.asyncio
async def test_outline_adapter_create_collection_and_bootstrap_para_online():
    """Khi Outline hoạt động: khởi tạo đủ 4 không gian P.A.R.A với mode='outline'."""
    tid = str(uuid.uuid4())
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    created_payloads: list[dict] = []

    async def _fake_post(url: str, *, headers=None, json=None, timeout=None):
        req = httpx.Request("POST", url)
        if url.endswith("/api/collections.list"):
            return httpx.Response(200, json={"data": []}, request=req)
        if url.endswith("/api/collections.create"):
            created_payloads.append(json)
            idx = len(created_payloads)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": f"outline-coll-{idx}",
                        "name": json["name"],
                        "description": json.get("description", ""),
                        "url": f"/collection/para-{idx}",
                    }
                },
                request=req,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    mock_client.post.side_effect = _fake_post

    with patch("app.adapters.external.outline_adapter.settings") as mock_settings:
        mock_settings.OUTLINE_URL = "http://outline.local"
        mock_settings.outline_public_base = "http://wiki.ictu.local"
        mock_settings.OUTLINE_API_KEY = "valid-outline-token"

        adapter = OutlineAdapter(client=mock_client)
        spaces = await adapter.bootstrap_para_collections(
            tenant_id=tid, tenant_name="ICTU"
        )

    assert len(spaces) == 4
    assert [s["key"] for s in spaces] == [
        "projects",
        "areas",
        "resources",
        "archives",
    ]
    assert [s["name"] for s in spaces] == [
        "1. Projects",
        "2. Areas",
        "3. Resources",
        "4. Archives",
    ]
    assert all(s["mode"] == "outline" for s in spaces)
    assert spaces[0]["collection_id"] == "outline-coll-1"
    assert spaces[0]["url"] == "http://wiki.ictu.local/collection/para-1"
    assert len(created_payloads) == 4


@pytest.mark.asyncio
async def test_outline_adapter_bootstrap_para_fallback_when_no_key_or_offline():
    """Khi thiếu OUTLINE_API_KEY hoặc lỗi mạng: trả fallback local_para an toàn."""
    tid = str(uuid.uuid4())

    # 1. Không có API key
    with patch("app.adapters.external.outline_adapter.settings") as mock_settings:
        mock_settings.OUTLINE_URL = "http://outline.local"
        mock_settings.OUTLINE_API_KEY = ""
        adapter_no_key = OutlineAdapter()
        local_spaces = await adapter_no_key.bootstrap_para_collections(tenant_id=tid)

    assert len(local_spaces) == 4
    assert all(s["mode"] == "local_para" for s in local_spaces)
    assert [s["collection_id"] for s in local_spaces] == [
        f"{tid}:para:projects",
        f"{tid}:para:areas",
        f"{tid}:para:resources",
        f"{tid}:para:archives",
    ]

    # 2. Có API key nhưng Outline không phản hồi (ConnectError)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.ConnectError("Outline connection refused")
    with patch("app.adapters.external.outline_adapter.settings") as mock_settings:
        mock_settings.OUTLINE_URL = "http://outline.local"
        mock_settings.OUTLINE_API_KEY = "secret-key"
        adapter_offline = OutlineAdapter(client=mock_client)
        fallback_spaces = await adapter_offline.bootstrap_para_collections(
            tenant_id=tid
        )

    assert len(fallback_spaces) == 4
    assert all(s["mode"] == "local_para" for s in fallback_spaces)
    assert fallback_spaces[2]["collection_id"] == f"{tid}:para:resources"


@pytest.mark.asyncio
async def test_tenant_onboarding_best_effort_para_never_fails_onboarding():
    """Khi tạo Tenant mới: gọi bootstrap P.A.R.A best-effort, không chặn onboarding."""
    superadmin_ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["superadmin"],
        email="root@ictu.edu.vn",
    )
    tenant_repo = AsyncMock()
    tenant_repo.get_by_slug.return_value = None
    tenant_repo.create.side_effect = lambda entity: entity

    keycloak_adapter = AsyncMock()
    failing_outline = MagicMock()
    failing_outline.bootstrap_para_collections = AsyncMock(
        side_effect=RuntimeError("Outline service crashed")
    )

    uc = TenantOnboardingUseCase(
        tenant_repo=tenant_repo,
        keycloak_adapter=keycloak_adapter,
        session=AsyncMock(),
        outline_adapter=failing_outline,
    )

    created = await uc.create_tenant(
        context=superadmin_ctx,
        name="Đại học CNTT & Truyền thông ICTU",
        slug="ictu-tnu",
        plan="enterprise",
    )
    assert created.slug == "ictu-tnu"
    failing_outline.bootstrap_para_collections.assert_awaited_once_with(
        tenant_id=str(created.id),
        tenant_name="Đại học CNTT & Truyền thông ICTU",
    )


@pytest.mark.asyncio
async def test_rag_ingestion_infers_para_space_into_qdrant_chunk_metadata():
    """RAGIngestionUseCase suy luận và gắn nhãn para_space cho từng chunk Qdrant."""
    assert infer_para_space(title="Kế hoạch Dự án Chuyển đổi số 2026") == "projects"
    assert infer_para_space(title="Quy trình vận hành SOP Phòng Đào tạo") == "areas"
    assert infer_para_space(title="Cẩm nang biểu mẫu hành chính") == "resources"
    assert infer_para_space(title="Lưu trữ hồ sơ cũ 2022") == "archives"
    assert infer_para_space(title="Ghi chú chung") == "resources"

    outline_source = MagicMock()
    outline_source.list_documents = AsyncMock(
        return_value=[
            {
                "id": "d-proj",
                "title": "Sprint 4 Milestone Dự án OLP",
                "source_url": "http://wiki/doc/1",
                "text": "Mục tiêu tuần này.",
                "collectionId": "t-1",
            },
            {
                "id": "d-area",
                "title": "Nội quy an toàn thông tin",
                "source_url": "http://wiki/doc/2",
                "text": "Mọi mật khẩu phải bật 2FA.",
                "collectionId": "t-1",
            },
            {
                "id": "d-arch",
                "title": "Quy định cũ hết hiệu lực 2020",
                "source_url": "http://wiki/doc/3",
                "text": "Tài liệu lưu trữ.",
                "collectionId": "t-1",
            },
            {
                "id": "d-default",
                "title": "Giới thiệu tổng quan",
                "source_url": "http://wiki/doc/4",
                "text": "Thông tin tham khảo.",
                "collectionId": "t-1",
            },
        ]
    )
    qdrant_port = MagicMock()
    qdrant_port.replace_tenant_vectors = AsyncMock(return_value=True)

    uc = RAGIngestionUseCase(outline_source, qdrant_port)
    res = await uc.execute("t-1")
    assert res["status"] == "success"
    assert res["processed_documents"] == 4

    metadatas = qdrant_port.replace_tenant_vectors.call_args.kwargs["metadatas"]
    assert [m["para_space"] for m in metadatas] == [
        "projects",
        "areas",
        "archives",
        "resources",
    ]


@pytest.mark.asyncio
async def test_ai_router_para_spaces_bootstrap_and_upload_with_para_space():
    """Kiểm thử API /api/v1/ai/knowledge/para/* và upload_knowledge gắn para_space."""
    tid = uuid.uuid4()
    ctx = TenantContext(
        tenant_id=tid,
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
        email="admin@ictu.edu.vn",
    )
    mock_role_repo = AsyncMock()
    mock_role_repo.get_user_permissions.return_value = ["plugins:install"]

    app.dependency_overrides[get_current_tenant_context] = lambda: ctx
    app.dependency_overrides[get_role_repo] = lambda: mock_role_repo
    app.state.http_client = AsyncMock(spec=httpx.AsyncClient)

    try:
        with patch("app.adapters.external.outline_adapter.settings") as mock_settings:
            mock_settings.OUTLINE_URL = "http://outline.local"
            mock_settings.OUTLINE_API_KEY = ""

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # 1. GET /api/v1/ai/knowledge/para/spaces
                spaces_resp = await client.get("/api/v1/ai/knowledge/para/spaces")
                assert spaces_resp.status_code == 200
                spaces_data = spaces_resp.json()
                assert spaces_data["status"] == "ready"
                assert spaces_data["mode"] == "local_para"
                assert len(spaces_data["spaces"]) == 4

                # 2. POST /api/v1/ai/knowledge/para/bootstrap
                boot_resp = await client.post(
                    "/api/v1/ai/knowledge/para/bootstrap",
                    json={"tenant_name": "ICTU Digital Campus"},
                )
                assert boot_resp.status_code == 200
                boot_data = boot_resp.json()
                assert boot_data["status"] == "ready"
                assert boot_data["mode"] == "local_para"
                assert [s["key"] for s in boot_data["spaces"]] == [
                    "projects",
                    "areas",
                    "resources",
                    "archives",
                ]

                # 3. Upload tài liệu gắn nhãn para_space="projects"
                up_resp = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    data={
                        "para_space": "projects",
                        "collection_id": f"{tid}:para:projects",
                    },
                    files={
                        "file": (
                            "ke-hoach.md",
                            "# Kế hoạch Phase 4\nHoàn thành Digital Twin.".encode(),
                            "text/markdown",
                        )
                    },
                )
                assert up_resp.status_code == 201
                up_data = up_resp.json()
                assert up_data["status"] == "success"
                assert up_data["para_space"] == "projects"

                # 4. Upload với para_space không hợp lệ -> 400
                bad_resp = await client.post(
                    "/api/v1/ai/knowledge/upload",
                    data={"para_space": "unknown_bucket"},
                    files={
                        "file": (
                            "note.txt",
                            "Nội dung thử nghiệm".encode(),
                            "text/plain",
                        )
                    },
                )
                assert bad_resp.status_code == 400
    finally:
        app.dependency_overrides.clear()
