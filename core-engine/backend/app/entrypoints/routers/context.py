# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Context Broker & Realtime Notifications Router (Layer 3).

Cung cấp:
- Endpoint nhận webhook notification từ Orion-LD (`/api/v1/context/notifications`).
- Chống vòng lặp đồng bộ (Anti-sync loop) giữa Outbox -> Orion -> Notification -> Outbox.
- Cập nhật trực tiếp `context.entity_state` và phát realtime event vào Redis Streams.
- Đăng ký và quản lý subscriptions.
Tham chiếu: Issue #846 [L3-601], #847 [L3-602], #848 [L3-603].
"""

import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import SQLAlchemyOutboxRepository
from app.core.domain.geo_utils import parse_ngsi_ld_geoproperty
from app.entrypoints.dependencies import get_current_tenant_context
from app.infrastructure.config import settings
from app.infrastructure.database import AsyncSessionLocal, get_db_readonly

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["Context & Realtime"])


class NGSINotificationPayload(BaseModel):
    subscriptionId: str = Field(..., description="ID của Subscription bên Orion-LD")
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


@router.post("/notifications", status_code=status.HTTP_200_OK)
async def receive_orion_notification(
    payload: NGSINotificationPayload,
    request: Request,
):
    """Endpoint nhận notification webhook từ Orion-LD khi có thực thể thay đổi.

    Triển khai cơ chế chống vòng lặp đồng bộ (#848):
    Chỉ cập nhật vào `context.entity_state` và phát ra Redis Streams, TUYỆT ĐỐI KHÔNG
    ghi lại vào `context.context_outbox` để ngắt đệ quy vô hạn.
    """
    if not payload.data:
        return {"status": "ignored", "reason": "empty_data"}

    async with AsyncSessionLocal() as session:
        repo = SQLAlchemyOutboxRepository(session)
        updated_count = 0

        # Lấy redis client từ app.state nếu có, hoặc tạo kết nối
        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is None:
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        for entity in payload.data:
            entity_id = entity.get("id")
            entity_type = entity.get("type", "Unknown")
            if not entity_id:
                continue

            try:
                parsed_type, tenant_str, raw_id = parse_urn_parts(entity_id)
                t_id = uuid.UUID(tenant_str)
            except Exception:
                # Nếu không khớp format chuẩn, fallback gán tenant rỗng/bỏ qua
                logger.warning(
                    "Notification entity %s does not match expected URN format",
                    entity_id,
                )
                continue

            # Kiểm tra location nếu có GeoProperty
            lon: float | None = None
            lat: float | None = None
            if "location" in entity:
                try:
                    lon, lat = parse_ngsi_ld_geoproperty(entity["location"])
                except Exception as e:
                    logger.debug(
                        "Could not parse location in entity %s: %s", entity_id, e
                    )

            # 1. Cập nhật trực tiếp vào entity_state (không ghi outbox -> chống vòng lặp)
            await repo.upsert_entity_state(
                tenant_id=t_id,
                entity_id=entity_id,
                entity_type=parsed_type,
                payload=entity,
                longitude=lon,
                latitude=lat,
            )

            # 2. Phát sự kiện vào Redis Streams cho consumer realtime
            event_data = {
                "event_type": "context.notification.received",
                "subscription_id": payload.subscriptionId,
                "tenant_id": str(t_id),
                "entity_id": entity_id,
                "entity_type": parsed_type,
                "payload": json.dumps(entity),
            }
            await redis_client.xadd(settings.CONTEXT_SYNC_STREAM_NAME, event_data)
            updated_count += 1

        await session.commit()

    return {"status": "success", "processed_entities": updated_count}


@router.get("/entities/{entity_id:path}")
async def get_context_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db_readonly),
    tenant_context=Depends(get_current_tenant_context),
):
    """Lấy trạng thái thực thể (Digital Twin) theo ID."""
    query = text("""
        SELECT tenant_id, entity_id, type, payload, location, updated_at
        FROM context.entity_state
        WHERE entity_id = :id;
        """)
    res = await db.execute(query, {"id": entity_id})
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
    db: AsyncSession = Depends(get_db_readonly),
    tenant_context=Depends(get_current_tenant_context),
):
    """Đăng ký Orion subscription theo dõi entity type (Issue #846)."""
    tenant_id = str(tenant_context.tenant_id)
    callback = (
        req.callback_url or f"{settings.BACKEND_URL}/api/v1/context/notifications"
    )

    sub_payload = {
        "type": "Subscription",
        "entities": [{"type": req.entity_type}],
        "notification": {
            "endpoint": {
                "uri": callback,
                "accept": "application/json",
            }
        },
    }

    adapter = OrionAdapter()
    try:
        sub_id = await adapter.create_subscription(sub_payload, tenant_id=tenant_id)
    except Exception as e:
        logger.error("Failed to register subscription on Orion-LD: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Context Broker subscription error: {e}",
        )

    # Lưu thông tin subscription vào context.subscriptions
    async with AsyncSessionLocal() as session:
        query = text("""
            INSERT INTO context.subscriptions (subscription_id, tenant_id, entity_type, endpoint, status, created_at)
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
    tenant_context=Depends(get_current_tenant_context),
):
    """Hủy đăng ký subscription trên Orion-LD và cập nhật CSDL (Issue #846, #848)."""
    tenant_id = str(tenant_context.tenant_id)
    adapter = OrionAdapter()
    try:
        await adapter.delete_subscription(subscription_id, tenant_id=tenant_id)
    except Exception as e:
        logger.warning("Could not delete subscription on Orion: %s", e)

    async with AsyncSessionLocal() as session:
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
    limit: int = 100,
    tenant_context=Depends(get_current_tenant_context),
):
    """Tái xử lý các bản ghi outbox lỗi trong Dead Letter Queue (DLQ) cho tenant (Issue #836)."""
    tenant_id = str(tenant_context.tenant_id)
    async with AsyncSessionLocal() as session:
        repo = SQLAlchemyOutboxRepository(session)
        replayed_count = await repo.replay_dlq(tenant_id, max_records=limit)
        await session.commit()

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "replayed_count": replayed_count,
        "message": f"Successfully re-queued {replayed_count} DLQ records.",
    }
