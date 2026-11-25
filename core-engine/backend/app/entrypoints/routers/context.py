# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Context Broker & Realtime Notifications Router (Layer 3).

Cung cấp:
- Endpoint nhận webhook notification từ Orion-LD (`/api/v1/context/notifications`).
- Chống vòng lặp đồng bộ (Anti-sync loop) Outbox -> Orion -> Notification -> Outbox.
- Cập nhật trực tiếp `context.entity_state` và phát realtime event vào Redis Streams.
- Đăng ký và quản lý subscriptions.
Tham chiếu: Issue #846 [L3-601], #847 [L3-602], #848 [L3-603].
"""

import hmac
import ipaddress
import json
import logging
import socket
import uuid
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import SQLAlchemyOutboxRepository
from app.core.domain.geo_utils import parse_ngsi_ld_geoproperty
from app.core.use_cases.manifest_validator import _PROHIBITED_NGSI_COLUMNS
from app.entrypoints.dependencies import get_current_tenant_context, require_permission
from app.infrastructure.config import settings
from app.infrastructure.database import (
    AsyncSessionLocal,
    get_db_readonly,
    set_session_tenant,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["Context & Realtime"])


class NGSINotificationPayload(BaseModel):
    subscriptionId: str = Field(  # noqa: N815
        ..., description="ID của Subscription bên Orion-LD"
    )
    data: list[dict[str, Any]] = Field(
        default_factory=list, description="Danh sách thực thể thay đổi"
    )


def parse_urn_parts(urn: str) -> tuple[str, str, str]:
    """Parse URN: urn:ngsi-ld:{Type}:{tenant_id}:{entity_id}."""
    parts = urn.split(":")
    if len(parts) >= 5 and parts[0] == "urn" and parts[1] == "ngsi-ld":
        entity_type = parts[2]
        tenant_id = parts[3]
        entity_id = ":".join(parts[4:])
        return entity_type, tenant_id, entity_id
    raise ValueError(f"Invalid NGSI-LD URN format: {urn}")


def _is_disallowed_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Kiểm tra IP có thuộc dải loopback, private, link-local hay không public."""
    check_ip = (
        ip_obj.ipv4_mapped
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped
        else ip_obj
    )
    return (
        check_ip.is_loopback
        or check_ip.is_private
        or check_ip.is_link_local
        or check_ip.is_multicast
        or check_ip.is_reserved
        or check_ip.is_unspecified
        or not check_ip.is_global
    )


def validate_subscription_callback_url(callback_url: str | None) -> str:
    """Kiểm tra chống SSRF cho callback_url khi đăng ký Orion subscription (#861)."""
    default_internal_url = (
        f"{settings.BACKEND_URL.rstrip('/')}/api/v1/context/notifications"
    )
    if callback_url is None or not callback_url.strip():
        return default_internal_url

    cleaned_url = callback_url.strip()
    if cleaned_url == default_internal_url:
        return default_internal_url

    parsed = urlparse(cleaned_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid callback_url: must use http or https scheme.",
        )

    hostname = parsed.hostname.strip().lower()
    if (
        "." not in hostname
        or hostname
        in (
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
            "host.docker.internal",
            "gateway.docker.internal",
            "metadata.google.internal",
        )
        or hostname.endswith((".local", ".internal", ".localhost"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSRF protection: internal or local callback_url is forbidden.",
        )

    # Nếu hostname là IP trực tiếp -> kiểm tra không cần DNS
    try:
        ip_literal = ipaddress.ip_address(hostname)
    except ValueError:
        ip_literal = None

    if ip_literal is not None:
        if _is_disallowed_ip(ip_literal):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "SSRF protection: private, loopback, or link-local IP "
                    "is forbidden."
                ),
            )
        return cleaned_url

    # Phân giải DNS cho public domain để chặn DNS rebinding trỏ về IP nội bộ
    try:
        infos = socket.getaddrinfo(
            hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resolve callback_url hostname '{hostname}'.",
        ) from exc

    for info in infos:
        ip_str = info[4][0].split("%")[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid resolved IP address: {ip_str}",
            ) from exc
        if _is_disallowed_ip(resolved_ip):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSRF protection: callback_url resolves to non-public IP.",
            )

    return cleaned_url


@router.post("/notifications", status_code=status.HTTP_200_OK)
async def receive_orion_notification(
    payload: NGSINotificationPayload,
    request: Request,
    x_orion_webhook_secret: str | None = Header(
        default=None, alias="X-Orion-Webhook-Secret"
    ),
):
    """Endpoint nhận notification webhook từ Orion-LD khi có thực thể thay đổi.

    Triển khai cơ chế xác thực webhook (#861) và chống vòng lặp đồng bộ (#848):
    Chỉ cập nhật vào `context.entity_state` và phát ra Redis Streams, TUYỆT ĐỐI KHÔNG
    ghi lại vào `context.context_outbox` để ngắt đệ quy vô hạn.
    """
    configured_secret = (settings.ORION_WEBHOOK_SECRET or "").strip()
    if configured_secret or settings.ENVIRONMENT == "production":
        provided_secret = x_orion_webhook_secret or ""
        if (
            not configured_secret
            or not provided_secret
            or not hmac.compare_digest(
                provided_secret.encode("utf-8"),
                configured_secret.encode("utf-8"),
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid X-Orion-Webhook-Secret header.",
            )

    if not payload.data:
        return {"status": "ignored", "reason": "empty_data"}

    redis_client = getattr(request.app.state, "redis_client", None)
    owns_redis = False
    if redis_client is None:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        owns_redis = True

    try:
        async with AsyncSessionLocal() as session:
            repo = SQLAlchemyOutboxRepository(session)
            updated_count = 0

            for entity in payload.data:
                entity_id = entity.get("id")
                if not entity_id:
                    continue

                try:
                    parsed_type, tenant_str, _raw_id = parse_urn_parts(entity_id)
                    t_id = uuid.UUID(tenant_str)
                except Exception:
                    logger.warning(
                        "Notification entity %s does not match expected URN format",
                        entity_id,
                    )
                    continue

                await set_session_tenant(session, t_id)

                lon: float | None = None
                lat: float | None = None
                if "location" in entity:
                    parsed_coords = parse_ngsi_ld_geoproperty(entity["location"])
                    if parsed_coords is not None:
                        lon, lat = parsed_coords

                sanitized_entity = {
                    k: v
                    for k, v in entity.items()
                    if k.lower() not in _PROHIBITED_NGSI_COLUMNS
                }

                # 1. Cập nhật trực tiếp entity_state (không ghi outbox -> chống lặp)
                await repo.upsert_entity_state(
                    tenant_id=t_id,
                    entity_id=entity_id,
                    entity_type=parsed_type,
                    payload=sanitized_entity,
                    longitude=lon,
                    latitude=lat,
                )

                # 2. Phát sự kiện sang Redis Streams cho consumer realtime (maxlen)
                event_data = {
                    "event_type": "context.notification.received",
                    "subscription_id": payload.subscriptionId,
                    "tenant_id": str(t_id),
                    "entity_id": entity_id,
                    "entity_type": parsed_type,
                    "payload": json.dumps(sanitized_entity),
                }
                await redis_client.xadd(
                    settings.CONTEXT_SYNC_STREAM_NAME,
                    event_data,
                    maxlen=10000,
                    approximate=True,
                )
                updated_count += 1

            await session.commit()
    finally:
        if owns_redis and redis_client is not None:
            await redis_client.aclose()

    return {"status": "success", "processed_entities": updated_count}


@router.get("/entities/{entity_id:path}")
async def get_context_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db_readonly),
    tenant_context=Depends(get_current_tenant_context),
):
    """Lấy trạng thái thực thể (Digital Twin) theo ID và cô lập theo tenant (#861)."""
    query = text("""
        SELECT tenant_id, entity_id, type, payload, location, updated_at
        FROM context.entity_state
        WHERE entity_id = :id AND tenant_id = :tenant_id;
        """)
    res = await db.execute(
        query, {"id": entity_id, "tenant_id": tenant_context.tenant_id}
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_id} not found in entity_state",
        )

    payload = row[3]
    if isinstance(payload, str):
        payload = json.loads(payload)

    return {
        "tenant_id": str(row[0]),
        "entity_id": row[1],
        "type": row[2],
        "payload": payload,
        "updated_at": row[5].isoformat() if row[5] else None,
    }


class CreateSubscriptionRequest(BaseModel):
    entity_type: str = Field(
        ..., description="Loại thực thể cần theo dõi (VD: Room, Employee)"
    )
    callback_url: str | None = Field(
        None, description="URL callback (nếu None dùng backend notification URL)"
    )


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_orion_subscription(
    req: CreateSubscriptionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_readonly),
    tenant_context=Depends(require_permission("context.manage")),
):
    """Đăng ký Orion subscription theo dõi entity type (Issue #846, #861)."""
    tenant_id = str(tenant_context.tenant_id)
    callback = validate_subscription_callback_url(req.callback_url)

    endpoint_cfg: dict[str, Any] = {
        "uri": callback,
        "accept": "application/json",
    }
    if settings.ORION_WEBHOOK_SECRET:
        endpoint_cfg["receiverInfo"] = [
            {
                "key": "X-Orion-Webhook-Secret",
                "value": settings.ORION_WEBHOOK_SECRET,
            }
        ]

    sub_payload = {
        "type": "Subscription",
        "entities": [{"type": req.entity_type}],
        "notification": {
            "endpoint": endpoint_cfg,
        },
    }

    http_client = getattr(request.app.state, "http_client", None)
    adapter = OrionAdapter(client=http_client)
    try:
        sub_id = await adapter.create_subscription(sub_payload, tenant_id=tenant_id)
    except Exception as e:
        logger.error("Failed to register subscription on Orion-LD: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Context Broker subscription error: {e}",
        ) from e
    finally:
        await adapter.aclose()

    # Lưu thông tin subscription vào context.subscriptions
    async with AsyncSessionLocal() as session:
        await set_session_tenant(session, tenant_context.tenant_id)
        query = text("""
            INSERT INTO context.subscriptions (
                subscription_id, tenant_id, entity_type, endpoint, status, created_at
            )
            VALUES (:sub_id, :tenant_id, :type, :endpoint, 'ACTIVE', clock_timestamp())
            ON CONFLICT (subscription_id) DO NOTHING;
            """)
        await session.execute(
            query,
            {
                "sub_id": sub_id,
                "tenant_id": uuid.UUID(tenant_id),
                "type": req.entity_type,
                "endpoint": callback,
            },
        )
        await session.commit()

    return {
        "subscription_id": sub_id,
        "tenant_id": tenant_id,
        "entity_type": req.entity_type,
        "endpoint": callback,
        "status": "ACTIVE",
    }


@router.get("/subscriptions", status_code=status.HTTP_200_OK)
async def list_orion_subscriptions(
    tenant_context=Depends(get_current_tenant_context),
):
    """Lấy danh sách subscriptions đang hoạt động của tenant (Issue #846)."""
    tenant_id = str(tenant_context.tenant_id)
    async with AsyncSessionLocal() as session:
        await set_session_tenant(session, tenant_context.tenant_id)
        query = text("""
            SELECT subscription_id, entity_type, endpoint, status, created_at
            FROM context.subscriptions
            WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
            ORDER BY created_at DESC;
            """)
        result = await session.execute(query, {"tenant_id": uuid.UUID(tenant_id)})
        rows = result.fetchall()

    return [
        {
            "subscription_id": r[0],
            "entity_type": r[1],
            "endpoint": r[2],
            "status": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_200_OK)
async def delete_orion_subscription(
    subscription_id: str,
    request: Request,
    tenant_context=Depends(require_permission("context.manage")),
):
    """Hủy đăng ký subscription trên Orion-LD và cập nhật CSDL (#846, #848, #861)."""
    tenant_id = str(tenant_context.tenant_id)
    http_client = getattr(request.app.state, "http_client", None)
    adapter = OrionAdapter(client=http_client)
    try:
        await adapter.delete_subscription(subscription_id, tenant_id=tenant_id)
    except Exception as e:
        logger.warning("Could not delete subscription on Orion: %s", e)
    finally:
        await adapter.aclose()

    async with AsyncSessionLocal() as session:
        await set_session_tenant(session, tenant_context.tenant_id)
        query = text("""
            UPDATE context.subscriptions
            SET status = 'DELETED'
            WHERE subscription_id = :sub_id AND tenant_id = :tenant_id;
            """)
        await session.execute(
            query,
            {"sub_id": subscription_id, "tenant_id": uuid.UUID(tenant_id)},
        )
        await session.commit()

    return {
        "status": "success",
        "subscription_id": subscription_id,
        "message": "Subscription cancelled.",
    }


@router.post("/outbox/replay-dlq", status_code=status.HTTP_200_OK)
async def replay_outbox_dlq(
    limit: int = Query(default=100, ge=1, le=1000),
    tenant_context=Depends(require_permission("context.manage")),
):
    """Tái xử lý các bản ghi outbox lỗi trong Dead Letter Queue (#836, #861)."""
    tenant_id = str(tenant_context.tenant_id)
    async with AsyncSessionLocal() as session:
        await set_session_tenant(session, tenant_context.tenant_id)
        repo = SQLAlchemyOutboxRepository(session)
        replayed_count = await repo.replay_dlq(tenant_id, max_records=limit)
        await session.commit()

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "replayed_count": replayed_count,
        "message": f"Successfully re-queued {replayed_count} DLQ records.",
    }
