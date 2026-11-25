# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Entrypoint Router — AI Orchestrator (DX-DSL)
# Tham chiếu: docs/api-swagger.yaml POST /ai/command, docs/dsl-spec.md

import logging
import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from app.adapters.external.qdrant_adapter import QdrantAdapter
from app.core.domain.entities import AICommandStatus, TenantContext
from app.core.use_cases.ai_chat import AIChatDTO, AIChatUseCase
from app.core.use_cases.ai_command import AICommandDTO, AICommandUseCase
from app.core.use_cases.conversation import ConversationUseCase
from app.core.use_cases.rag_ingestion import (
    VALID_PARA_SPACES,
    RAGIngestionUseCase,
    infer_para_space,
)
from app.entrypoints.dependencies import (
    get_ai_chat_use_case,
    get_ai_command_use_case,
    get_conversation_use_case,
    get_current_tenant_context,
    get_plugin_repo,
    get_qdrant_adapter,
    get_rag_ingestion_use_case,
    get_role_repo,
    require_permission,
)
from app.entrypoints.schemas.ai_command import (
    AIChatRequest,
    AICommandRequest,
    AICommandResponse,
)
from app.entrypoints.schemas.conversation import (
    ChatMessageResponse,
    MessageAppendRequest,
    SessionEnsureRequest,
    SessionInfoResponse,
    SessionResponse,
)
from app.infrastructure.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai")


@router.post(
    "/chat",
    response_model=AICommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gửi câu lệnh ngôn ngữ tự nhiên để LLM phân tích",
)
@limiter.limit("5/minute")
async def submit_ai_chat(
    request: Request,
    body: AIChatRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: AIChatUseCase = Depends(get_ai_chat_use_case),
) -> AICommandResponse:
    logger.info(
        "AI chat received",
        extra={"session_id": str(body.session_id), "tenant_id": str(ctx.tenant_id)},
    )
    dto = AIChatDTO(
        session_id=body.session_id, natural_language_input=body.natural_language_input
    )
    try:
        status_code, message, result = await use_case.execute(dto, ctx)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    # Trả đúng command_id từ execution kết quả hoặc dsl_preview (#731)
    preview, real_command_id = _extract_chat_preview_and_command_id(result)

    return AICommandResponse(
        command_id=real_command_id or uuid.uuid4(),
        status=status_code,
        message=message,
        result=result if status_code == AICommandStatus.COMPLETED else None,
        dsl_preview=preview,
    )


def _extract_chat_preview_and_command_id(
    result: Any,
) -> tuple[dict | None, uuid.UUID | None]:
    """Trích xuất dsl_preview và command_id thật từ kết quả AIChatUseCase."""
    if not isinstance(result, dict):
        return None, None
    preview = result.get("dsl_preview")
    real_command_id: uuid.UUID | None = None
    if result.get("command_id"):
        try:
            real_command_id = uuid.UUID(str(result["command_id"]))
        except (ValueError, TypeError):
            pass
    if not real_command_id and isinstance(preview, dict) and preview.get("command_id"):
        try:
            real_command_id = uuid.UUID(str(preview["command_id"]))
        except (ValueError, TypeError):
            pass
    if (
        not real_command_id
        and isinstance(result.get("steps"), list)
        and result["steps"]
    ):
        last_step = result["steps"][-1]
        if isinstance(last_step, dict) and last_step.get("command_id"):
            try:
                real_command_id = uuid.UUID(str(last_step["command_id"]))
            except (ValueError, TypeError):
                pass
    return preview, real_command_id


@router.post(
    "/command",
    response_model=AICommandResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gửi DX-DSL Command đến AI Orchestrator",
)
@limiter.limit("10/minute")
async def submit_ai_command(
    request: Request,
    body: AICommandRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: AICommandUseCase = Depends(get_ai_command_use_case),
    chat_use_case: AIChatUseCase = Depends(get_ai_chat_use_case),
) -> AICommandResponse:
    """
    Nhận DX-DSL command từ AI Layer, validate và xử lý.
    Nếu client gửi natural_language_input mà không có action/effect,
    tự động forward sang chat_use_case.

    - Nếu effect = read: thực thi ngay, trả về kết quả.
    - Nếu effect = write/critical: gửi xin phê duyệt qua Mattermost,
      trả về PENDING_APPROVAL (Human-in-the-loop).

    Tham chiếu: docs/dsl-spec.md §4 (Effect Levels & Approval Rules)
    """
    if body.natural_language_input and not body.action:
        chat_dto = AIChatDTO(
            session_id=body.session_id,
            natural_language_input=body.natural_language_input,
        )
        try:
            status_code, message, result = await chat_use_case.execute(chat_dto, ctx)
        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        preview, extracted_id = _extract_chat_preview_and_command_id(result)
        real_command_id = extracted_id or body.command_id
        return AICommandResponse(
            command_id=real_command_id,
            status=status_code,
            message=message,
            result=result if status_code == AICommandStatus.COMPLETED else None,
            dsl_preview=preview,
        )

    if not body.action or not body.effect:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Các trường 'action' và 'effect' là bắt buộc đối với DX-DSL Command",
        )

    logger.info(
        "AI command received",
        extra={
            "action": body.action,
            "effect": body.effect,
            "tenant_id": str(ctx.tenant_id),
            "user_id": str(ctx.user_id),
        },
    )

    dto = AICommandDTO(
        command_id=body.command_id,
        session_id=body.session_id,
        dsl_version=body.dsl_version,
        action=body.action,
        effect=body.effect,
        parameters=body.parameters,
        approval_message=body.approval_message,
    )
    try:
        status_code, message, result = await use_case.execute(dto, ctx)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    preview = None
    if status_code == AICommandStatus.PENDING_APPROVAL:
        preview = {
            "command_id": str(body.command_id),
            "action": body.action,
            "effect": body.effect,
            "parameters": body.parameters,
            "dry_run": result,
        }
    elif isinstance(result, dict) and "dsl_preview" in result:
        preview = result.get("dsl_preview")

    return AICommandResponse(
        command_id=body.command_id,
        status=status_code,
        message=message,
        result=result if status_code != AICommandStatus.PENDING_APPROVAL else None,
        dsl_preview=preview,
    )


@router.post(
    "/knowledge/ingest",
    status_code=status.HTTP_200_OK,
    summary="Manual Trigger: RAG Document Ingestion",
    dependencies=[Depends(require_permission("ai.knowledge.ingest"))],
)
@limiter.limit("5/minute")
async def trigger_rag_ingestion(
    request: Request,
    collection_id: str | None = None,
    body: dict[str, Any] | None = Body(default=None),
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: RAGIngestionUseCase = Depends(get_rag_ingestion_use_case),
):
    """
    Kích hoạt thủ công quá trình Ingestion tài liệu từ Outline vào Qdrant
    cho tenant hiện tại. Bắt buộc giới hạn theo collection của tenant (#734, #883).
    """
    from app.adapters.external.outline_adapter import OutlineAdapter

    raw_coll = (
        collection_id
        if collection_id is not None
        else (body or {}).get("collection_id")
    )
    req_collection_id = (
        str(raw_coll).strip()
        if raw_coll is not None and str(raw_coll).strip()
        else None
    )
    tenant_collection = getattr(ctx, "outline_collection_id", None) or str(
        ctx.tenant_id
    )
    local_para_prefix = f"{ctx.tenant_id}:para:"

    doc_source = (
        use_case.document_source_port
        if isinstance(use_case, RAGIngestionUseCase)
        and hasattr(use_case.document_source_port, "get_para_spaces")
        else OutlineAdapter(client=getattr(request.app.state, "http_client", None))
    )
    para_spaces = await doc_source.get_para_spaces(tenant_id=tenant_collection)
    allowed_para_ids = {
        str(s.get("collection_id"))
        for s in (para_spaces or [])
        if s.get("collection_id")
    }
    para_map = {
        str(s["collection_id"]): str(s["key"])
        for s in (para_spaces or [])
        if s.get("collection_id") and s.get("key") in VALID_PARA_SPACES
    }

    if (
        req_collection_id
        and req_collection_id != tenant_collection
        and not req_collection_id.startswith(local_para_prefix)
        and req_collection_id not in allowed_para_ids
        and "superadmin" not in (ctx.roles or [])
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền ingest collection của tổ chức khác.",
        )

    if req_collection_id:
        matched_space = para_map.get(req_collection_id)
        if matched_space:
            try:
                return await use_case.execute(
                    str(ctx.tenant_id),
                    collection_id=req_collection_id,
                    para_space=matched_space,
                )
            except TypeError:
                pass
        return await use_case.execute(
            str(ctx.tenant_id), collection_id=req_collection_id
        )

    all_collection_ids = list(
        dict.fromkeys([tenant_collection, *sorted(allowed_para_ids)])
    )
    try:
        return await use_case.execute(
            str(ctx.tenant_id),
            collection_ids=all_collection_ids,
            collection_para_map=para_map,
        )
    except TypeError:
        return await use_case.execute(
            str(ctx.tenant_id), collection_id=tenant_collection
        )


@router.post(
    "/ipc/transmit",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="POC: Kích hoạt truyền tải KV-Cache qua Event Bus",
)
async def transmit_kv_cache_ipc(
    body: dict,  # tạm dùng dict thay vì schema nếu chưa import
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
):
    """
    Kích hoạt giao tiếp IPC giữa 2 AI Agents, sử dụng State Pointer (UUID)
    thay vì gửi toàn bộ Context Text qua Event Bus.
    """
    from pydantic import ValidationError

    from app.adapters.external.qdrant_adapter import QdrantAdapter
    from app.adapters.external.redis_event_bus import RedisEventBusPublisher
    from app.ai.kv_cache_ipc import KVCacheIPCManager
    from app.entrypoints.schemas.ai_ipc import (
        KVCacheTransmitRequest,
        KVCacheTransmitResponse,
    )

    try:
        req = KVCacheTransmitRequest(**(body or {}))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e

    redis_publisher = getattr(request.app.state, "redis_event_bus", None)
    if redis_publisher is None:
        redis_publisher = RedisEventBusPublisher()

    state_qdrant_client = getattr(request.app.state, "qdrant_client", None)
    qdrant_adapter = getattr(request.app.state, "qdrant_adapter", None)
    if qdrant_adapter is None or (
        state_qdrant_client is not None
        and getattr(qdrant_adapter, "client", None) is not state_qdrant_client
    ):
        qdrant_adapter = QdrantAdapter(qdrant_client=state_qdrant_client)
        request.app.state.qdrant_adapter = qdrant_adapter

    manager = KVCacheIPCManager(
        qdrant_adapter=qdrant_adapter,
        redis_publisher=redis_publisher,
    )

    pointer_uuid, latency_ms = await manager.transmit_context(
        tenant_id=str(ctx.tenant_id),
        source_agent=req.source_agent,
        target_agent=req.target_agent,
        context_text=req.context_data,
    )

    return KVCacheTransmitResponse(
        pointer_uuid=pointer_uuid,
        latency_ms=latency_ms,
        message="Đã truyền tải Context Pointer thành công",
    )


@router.get(
    "/commands/{command_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Trạng thái 1 lệnh (để chat widget poll khi chờ duyệt)",
)
@limiter.limit("30/minute")
async def get_ai_command_status(
    command_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: AICommandUseCase = Depends(get_ai_command_use_case),
):
    """Trả về status/action/effect/deadline của lệnh cùng tenant.

    Cùng tenant được xem (người duyệt cần theo dõi). 404 khi không tồn tại
    hoặc khác tenant (không lộ thông tin).
    """
    cmd = await use_case.ai_command_repo.get_command_by_id(command_id)
    if not cmd or str(cmd.get("tenant_id")) != str(ctx.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lệnh."
        )
    dl = cmd.get("approval_deadline")
    return {
        "command_id": str(cmd.get("id") or command_id),
        "status": cmd.get("status"),
        "action": cmd.get("action"),
        "effect": cmd.get("effect"),
        "approval_deadline": dl.isoformat() if hasattr(dl, "isoformat") else dl,
    }


@router.post(
    "/commands/{command_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Người ra lệnh tự hủy lệnh đang chờ duyệt",
)
@limiter.limit("30/minute")
async def cancel_ai_command(
    command_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: AICommandUseCase = Depends(get_ai_command_use_case),
):
    outcome = await use_case.cancel_own_command(str(command_id), str(ctx.user_id))
    if outcome == "invalid":
        return {"cancelled": False, "reason": "Lệnh không còn ở trạng thái chờ duyệt."}
    if outcome == "denied":
        return {"cancelled": False, "reason": "Bạn không có quyền hủy lệnh này."}
    return {"cancelled": True}


# ─── Conversation Memory (server-side, per user+tenant) ─────────────────────


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ensure AI chat session của user",
)
@limiter.limit("30/minute")
async def ensure_ai_session(
    request: Request,
    body: SessionEnsureRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: ConversationUseCase = Depends(get_conversation_use_case),
):
    try:
        session_id = await use_case.ensure_session(
            ctx.tenant_id, ctx.user_id, body.session_id
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    await use_case.conversation_repo.commit()
    return SessionResponse(session_id=session_id)


@router.get(
    "/sessions",
    response_model=list[SessionInfoResponse],
    summary="Liệt kê AI chat sessions của user",
)
@limiter.limit("30/minute")
async def list_ai_sessions(
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: ConversationUseCase = Depends(get_conversation_use_case),
):
    try:
        return await use_case.sessions(ctx.tenant_id, ctx.user_id)
    except ValueError:
        return []


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    summary="Lịch sử 1 AI chat session",
)
@limiter.limit("60/minute")
async def list_ai_messages(
    session_id: uuid.UUID,
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: ConversationUseCase = Depends(get_conversation_use_case),
):
    try:
        return await use_case.history(ctx.tenant_id, ctx.user_id, session_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lưu 1 turn chat vào session",
)
@limiter.limit("60/minute")
async def append_ai_message(
    session_id: uuid.UUID,
    body: MessageAppendRequest,
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: ConversationUseCase = Depends(get_conversation_use_case),
):
    try:
        real_session = await use_case.ensure_session(
            ctx.tenant_id, ctx.user_id, session_id
        )
        msg_id = await use_case.save_turn(
            ctx.tenant_id,
            ctx.user_id,
            real_session,
            body.role,
            body.content,
            body.command_id,
            body.citations,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    await use_case.conversation_repo.commit()
    return ChatMessageResponse(
        id=msg_id,
        role=body.role,
        content=body.content,
        command_id=body.command_id,
        citations=body.citations,
    )


# ─── Dynamic Action Catalog ─────────────────────────────────────────────────


@router.get(
    "/actions",
    summary="Danh sách actions AI được phép gọi (catalog động theo plugin đã cài)",
)
@limiter.limit("30/minute")
async def list_ai_actions(
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    plugin_repo=Depends(get_plugin_repo),
):
    from app.adapters.external.local_manifest_parser import LocalManifestParser
    from app.core.use_cases.action_catalog import build_catalog_for_tenant

    catalog = await build_catalog_for_tenant(
        plugin_repo, LocalManifestParser(), ctx.tenant_id
    )
    return {
        "actions": [
            {
                "action": a.action,
                "effect_hint": a.effect_hint,
                "description": a.description,
            }
            for a in catalog
        ]
    }


# ─── Knowledge Search (RAG citations) ───────────────────────────────────────


@router.post(
    "/knowledge/search",
    status_code=status.HTTP_200_OK,
    summary="Tìm kiếm tri thức nội bộ (hybrid, cô lập theo tenant)",
)
@limiter.limit("20/minute")
async def search_knowledge(
    body: dict,
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
    qdrant: QdrantAdapter = Depends(get_qdrant_adapter),
):
    query = str((body or {}).get("query", "")).strip()
    if not query:
        return {"query": "", "citations": []}
    try:
        limit = int((body or {}).get("limit", 5) or 5)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit phải là số nguyên hợp lệ.",
        ) from e
    limit = max(1, min(limit, 20))
    raw_para_filter = (body or {}).get("para_space")
    para_filter: str | None = None
    if raw_para_filter is not None and str(raw_para_filter).strip():
        norm_filter = str(raw_para_filter).strip().lower()
        if norm_filter not in VALID_PARA_SPACES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"para_space '{raw_para_filter}' không hợp lệ. "
                    f"Chỉ hỗ trợ: {', '.join(VALID_PARA_SPACES)}."
                ),
            )
        para_filter = norm_filter

    try:
        if para_filter:
            hits = await qdrant.search(
                tenant_id=str(ctx.tenant_id),
                query=query,
                limit=limit,
                filters={"para_space": para_filter},
            )
        else:
            hits = await qdrant.search(
                tenant_id=str(ctx.tenant_id), query=query, limit=limit
            )
    except Exception as e:
        logger.warning("Knowledge search thất bại: %s", e)
        return {"query": query, "citations": [], "warning": f"RAG chưa khả dụng: {e}"}
    return {
        "query": query,
        "citations": [
            {
                "document": h.get("document"),
                "score": h.get("score"),
                "doc_title": (h.get("metadata") or {}).get("doc_title"),
                "source_url": (h.get("metadata") or {}).get("source_url"),
                "para_space": (h.get("metadata") or {}).get("para_space"),
            }
            for h in hits
        ],
    }


@router.get(
    "/knowledge/para/spaces",
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách 4 không gian tri thức P.A.R.A của tổ chức hiện tại",
)
async def list_para_knowledge_spaces(
    request: Request,
    ctx: TenantContext = Depends(get_current_tenant_context),
):
    from app.adapters.external.outline_adapter import OutlineAdapter

    http_client = getattr(request.app.state, "http_client", None)
    source = OutlineAdapter(client=http_client)
    spaces = await source.get_para_spaces(tenant_id=str(ctx.tenant_id))
    mode = (
        "outline"
        if spaces and all(s.get("mode") == "outline" for s in spaces)
        else "local_para"
    )
    return {
        "status": "ready",
        "tenant_id": str(ctx.tenant_id),
        "mode": mode,
        "spaces": spaces,
    }


async def _require_knowledge_bootstrap_permission(
    context: TenantContext = Depends(get_current_tenant_context),
    role_repo=Depends(get_role_repo),
) -> TenantContext:
    """RBAC cho P.A.R.A bootstrap: cho phép admin hoặc quyền knowledge (#883)."""
    from app.core.domain.exceptions import InsufficientPermissionsError
    from app.core.domain.permissions import has_admin_role, has_wildcard_permission

    if has_admin_role(context.roles):
        return context
    user_permissions = (
        await role_repo.get_user_permissions(
            context.user_id, tenant_id=context.tenant_id
        )
        if role_repo is not None
        else []
    )
    if has_wildcard_permission(user_permissions):
        return context
    normalized: set[str] = set()
    for p in user_permissions or []:
        s = str(p)
        normalized.add(s)
        normalized.add(s.replace(":", "."))
        normalized.add(s.replace(".", ":"))
    allowed = {
        "ai.knowledge.ingest",
        "ai:knowledge:ingest",
        "ai.knowledge.write",
        "ai:knowledge:write",
        "plugins.install",
        "plugins:install",
    }
    if not (normalized & allowed):
        raise InsufficientPermissionsError(
            "Cần quyền 'ai.knowledge.ingest' hoặc 'plugins:install' "
            "để khởi tạo không gian tri thức."
        )
    return context


@router.post(
    "/knowledge/para/bootstrap",
    status_code=status.HTTP_200_OK,
    summary="Khởi tạo tự động 4 không gian tri thức P.A.R.A trên Outline / Local",
)
@limiter.limit("10/minute")
async def bootstrap_para_knowledge_spaces(
    request: Request,
    body: dict[str, Any] | None = Body(default=None),
    ctx: TenantContext = Depends(_require_knowledge_bootstrap_permission),
):
    from app.adapters.external.outline_adapter import OutlineAdapter

    tenant_name = str((body or {}).get("tenant_name") or "").strip()
    http_client = getattr(request.app.state, "http_client", None)
    source = OutlineAdapter(client=http_client)
    spaces = await source.bootstrap_para_collections(
        tenant_id=str(ctx.tenant_id), tenant_name=tenant_name
    )
    mode = (
        "outline"
        if spaces and all(s.get("mode") == "outline" for s in spaces)
        else "local_para"
    )
    return {
        "status": "ready",
        "tenant_id": str(ctx.tenant_id),
        "mode": mode,
        "spaces": spaces,
    }


@router.get(
    "/knowledge/connectors",
    status_code=status.HTTP_200_OK,
    summary="Liệt kê connector đồng bộ tri thức khả dụng",
)
async def list_knowledge_connectors(
    ctx: TenantContext = Depends(get_current_tenant_context),
):
    from app.adapters.external.knowledge_connectors import list_connectors

    return {"connectors": list_connectors()}


@router.post(
    "/knowledge/sync",
    status_code=status.HTTP_200_OK,
    summary="Đồng bộ tri thức từ nguồn ngoài vào Outline (connector framework)",
)
@limiter.limit("5/minute")
async def sync_knowledge(
    body: dict,
    request: Request,
    ctx: TenantContext = Depends(require_permission("plugins:install")),
):
    """Kéo tài liệu từ connector ngoài → publish vào Outline Wiki.

    Body: {"connector": "http_feed", "config": {"url": "..."},
           "collection_id": null}
    """
    from app.adapters.external.knowledge_connectors import get_connector
    from app.adapters.external.outline_adapter import OutlineAdapter
    from app.core.use_cases.knowledge_sync import KnowledgeSyncUseCase

    payload = body or {}
    raw_coll = payload.get("collection_id")
    req_collection_id = (
        str(raw_coll).strip()
        if raw_coll is not None and str(raw_coll).strip()
        else None
    )
    tenant_collection = getattr(ctx, "outline_collection_id", None) or str(
        ctx.tenant_id
    )
    local_para_prefix = f"{ctx.tenant_id}:para:"
    source = OutlineAdapter(client=getattr(request.app.state, "http_client", None))
    if (
        req_collection_id
        and req_collection_id != tenant_collection
        and not req_collection_id.startswith(local_para_prefix)
        and "superadmin" not in (ctx.roles or [])
    ):
        allowed_para_ids = {
            str(s.get("collection_id"))
            for s in await source.get_para_spaces(tenant_id=tenant_collection)
            if s.get("collection_id")
        }
        if req_collection_id not in allowed_para_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền thao tác trên collection của tổ chức khác.",
            )
    target_collection = req_collection_id or tenant_collection

    connector_name = str(payload.get("connector") or "http_feed")
    connector_cls = get_connector(connector_name)
    if connector_cls is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector '{connector_name}' không tồn tại.",
        )
    connector = connector_cls()
    use_case = KnowledgeSyncUseCase(connector=connector, document_source=source)
    result = await use_case.execute(
        config=payload.get("config") or {},
        collection_id=target_collection,
        publish=bool(payload.get("publish", True)),
    )
    return result


@router.post(
    "/knowledge/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Tải file PDF/DOCX/TXT/MD lên, trích chữ và đăng vào Outline",
)
@limiter.limit("10/minute")
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(..., description="File PDF/DOCX/TXT/MD (tối đa 10MB)"),
    collection_id: str | None = Form(None),
    para_space: str | None = Form(default=None),
    ctx: TenantContext = Depends(require_permission("plugins:install")),
    qdrant: QdrantAdapter = Depends(get_qdrant_adapter),
):
    """Nhận 1 file upload → trích văn bản → publish tài liệu Wiki kèm nhãn P.A.R.A.

    Mỗi file = 1 tài liệu (tiêu đề = tên file). File .doc đời cũ,
    PDF scan toàn ảnh hoặc file quá 10MB bị từ chối với lỗi rõ ràng.
    """
    from app.adapters.external.outline_adapter import (
        OutlineAdapter,
        OutlineAdapterError,
    )
    from app.core.use_cases.knowledge_upload import (
        MAX_UPLOAD_BYTES,
        KnowledgeUploadUseCase,
        UnsupportedFileError,
        extract_text,
        title_from_filename,
    )

    raw_para = (
        para_space if para_space is not None else request.query_params.get("para_space")
    )
    explicit_para: str | None = None
    if raw_para is not None and str(raw_para).strip():
        norm_para = str(raw_para).strip().lower()
        if norm_para not in VALID_PARA_SPACES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"para_space '{raw_para}' không hợp lệ. "
                    f"Chỉ chấp nhận: {', '.join(VALID_PARA_SPACES)}."
                ),
            )
        explicit_para = norm_para

    http_client = getattr(request.app.state, "http_client", None)
    source = OutlineAdapter(client=http_client)

    req_collection_id = (
        collection_id.strip() if collection_id and collection_id.strip() else None
    )
    tenant_collection = getattr(ctx, "outline_collection_id", None) or str(
        ctx.tenant_id
    )
    local_para_prefix = f"{ctx.tenant_id}:para:"
    if (
        req_collection_id
        and req_collection_id != tenant_collection
        and not req_collection_id.startswith(local_para_prefix)
        and "superadmin" not in (ctx.roles or [])
    ):
        allowed_para_ids = {
            str(s.get("collection_id"))
            for s in await source.get_para_spaces(tenant_id=tenant_collection)
            if s.get("collection_id")
        }
        if req_collection_id not in allowed_para_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền thao tác trên collection của tổ chức khác.",
            )

    resolved_para_space = infer_para_space(
        title=file.filename or "",
        collection_id=req_collection_id or tenant_collection,
        explicit_para_space=explicit_para,
    )
    target_collection = req_collection_id or tenant_collection
    if (
        not req_collection_id or req_collection_id.startswith(local_para_prefix)
    ) and source.api_key:
        spaces = await source.get_para_spaces(tenant_id=tenant_collection)
        matched = next(
            (
                s
                for s in (spaces or [])
                if s.get("key") == resolved_para_space
                and s.get("mode") == "outline"
                and s.get("collection_id")
            ),
            None,
        )
        if matched is None:
            spaces = await source.ensure_para_spaces(tenant_id=tenant_collection)
            matched = next(
                (
                    s
                    for s in (spaces or [])
                    if s.get("key") == resolved_para_space
                    and s.get("mode") == "outline"
                    and s.get("collection_id")
                ),
                None,
            )
        if matched is not None:
            target_collection = str(matched["collection_id"])

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File vượt quá giới hạn {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
        )

    use_case = KnowledgeUploadUseCase(document_source=source)
    try:
        upload_res = await use_case.execute(
            filename=file.filename or "tai-lieu",
            content=content,
            collection_id=target_collection,
        )
        return {
            **upload_res,
            "para_space": resolved_para_space,
            "collection_id": target_collection,
        }
    except UnsupportedFileError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except OutlineAdapterError as e:
        if source.api_key:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
            ) from e
        # Fallback an toàn khi môi trường local chưa cấu hình OUTLINE_API_KEY (#883)
        try:
            extracted = extract_text(file.filename or "tai-lieu.txt", content)
        except UnsupportedFileError as parse_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(parse_err)
            ) from parse_err
        doc_title = title_from_filename(file.filename or "tai-lieu")
        local_coll = (
            req_collection_id
            if req_collection_id and req_collection_id.startswith(local_para_prefix)
            else f"{ctx.tenant_id}:para:{resolved_para_space}"
        )
        upserted_chunks = 0
        try:
            chunker = RAGIngestionUseCase(
                document_source_port=source, vector_db_port=qdrant
            )
            chunks = chunker._chunk_text(extracted)
            if chunks:
                doc_id = f"local:{local_coll}:{doc_title}"
                metadatas = [
                    {
                        "doc_title": doc_title,
                        "title": doc_title,
                        "source_url": "",
                        "document_id": doc_id,
                        "chunk_index": idx,
                        "para_space": resolved_para_space,
                        "collection_id": local_coll,
                    }
                    for idx, _ in enumerate(chunks)
                ]
                await qdrant.upsert_vectors(
                    tenant_id=str(ctx.tenant_id),
                    chunks=chunks,
                    metadatas=metadatas,
                )
                upserted_chunks = len(chunks)
        except Exception as q_err:
            logger.warning(
                "Local P.A.R.A upload không thể index vào Qdrant (best-effort): %s",
                q_err,
            )
        return {
            "status": "success",
            "mode": "local_para",
            "filename": file.filename or "tai-lieu",
            "title": doc_title,
            "url": "",
            "chars": len(extracted),
            "upserted_chunks": upserted_chunks,
            "para_space": resolved_para_space,
            "collection_id": local_coll,
        }


# ─── Chat Streaming (SSE pipeline events) ───────────────────────────────────


@router.post(
    "/chat/stream",
    summary="Chat với Proteus AI, stream SSE (started/token/dsl/result)",
)
@limiter.limit("5/minute")
async def stream_ai_chat(
    request: Request,
    body: AIChatRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    use_case: AIChatUseCase = Depends(get_ai_chat_use_case),
):
    import json as _json

    from fastapi.responses import StreamingResponse

    dto = AIChatDTO(
        session_id=body.session_id, natural_language_input=body.natural_language_input
    )
    # M1: chặn IDOR session trước khi stream (đồng bộ, để trả 403 ngay).
    if use_case.conversation_repo is not None:
        try:
            await use_case.conversation_repo.assert_session_owned(
                ctx.tenant_id, ctx.user_id, body.session_id
            )
        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e

    async def event_gen():
        async for payload in use_case.execute_stream(dto, ctx):
            event = payload.pop("event", "message")
            yield f"event: {event}\ndata: {_json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
