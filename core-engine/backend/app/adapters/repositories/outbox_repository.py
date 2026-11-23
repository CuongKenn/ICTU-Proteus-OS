# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Repository cho Transactional Outbox (Layer 3 — Context Sync).

Tham chiếu: ADR-005, Issue #833 [L3-401], Issue #834 [L3-402], Issue #836 [L3-404].
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class OutboxRecord:
    id: uuid.UUID
    tenant_id: uuid.UUID
    entity_type: str
    entity_id: str
    op: str
    payload: dict[str, Any]
    status: str
    retry_count: int
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class SQLAlchemyOutboxRepository:
    """Repository quản lý bảng context.context_outbox và context.entity_state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        tenant_id: uuid.UUID | str,
        entity_type: str,
        entity_id: str,
        op: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> uuid.UUID:
        """Thêm một bản ghi vào context.context_outbox trong transaction hiện tại."""
        t_id = uuid.UUID(str(tenant_id))
        outbox_id = uuid.uuid4()
        query = text("""
            INSERT INTO context.context_outbox (
                id, tenant_id, entity_type, entity_id, op, payload, status, retry_count, idempotency_key, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :entity_type, :entity_id, :op, :payload, 'PENDING', 0, :idempotency_key, clock_timestamp(), clock_timestamp()
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id;
            """)
        res = await self.session.execute(
            query,
            {
                "id": outbox_id,
                "tenant_id": t_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "op": op,
                "payload": json.dumps(payload),
                "idempotency_key": idempotency_key,
            },
        )
        row = res.fetchone()
        return row[0] if row else outbox_id

    async def fetch_pending_batch(self, batch_size: int = 100) -> list[OutboxRecord]:
        """Lấy một batch bản ghi PENDING sử dụng SELECT ... FOR UPDATE SKIP LOCKED."""
        query = text("""
            SELECT id, tenant_id, entity_type, entity_id, op, payload, status, retry_count, idempotency_key, created_at, updated_at
            FROM context.context_outbox
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT :limit
            FOR UPDATE SKIP LOCKED;
            """)
        res = await self.session.execute(query, {"limit": batch_size})
        rows = res.fetchall()
        records: list[OutboxRecord] = []
        for r in rows:
            payload = r[5]
            if isinstance(payload, str):
                payload = json.loads(payload)
            records.append(
                OutboxRecord(
                    id=r[0],
                    tenant_id=r[1],
                    entity_type=r[2],
                    entity_id=r[3],
                    op=r[4],
                    payload=payload,
                    status=r[6],
                    retry_count=r[7],
                    idempotency_key=r[8],
                    created_at=r[9],
                    updated_at=r[10],
                )
            )
        return records

    async def mark_processed(self, outbox_ids: list[uuid.UUID]) -> None:
        """Đánh dấu danh sách bản ghi outbox là PROCESSED."""
        if not outbox_ids:
            return
        query = text("""
            UPDATE context.context_outbox
            SET status = 'PROCESSED', updated_at = clock_timestamp()
            WHERE id = ANY(:ids);
            """)
        await self.session.execute(query, {"ids": outbox_ids})

    async def mark_failed(
        self, outbox_id: uuid.UUID, error_message: str, max_retries: int = 5
    ) -> None:
        """Tăng retry_count; nếu vượt quá max_retries thì chuyển sang trạng thái DLQ."""
        query = text("""
            UPDATE context.context_outbox
            SET retry_count = retry_count + 1,
                error_message = :error,
                status = CASE WHEN retry_count + 1 >= :max_retries THEN 'DLQ' ELSE 'PENDING' END,
                updated_at = clock_timestamp()
            WHERE id = :id;
            """)
        await self.session.execute(
            query,
            {
                "id": outbox_id,
                "error": error_message[:1000],
                "max_retries": max_retries,
            },
        )

    async def upsert_entity_state(
        self,
        tenant_id: uuid.UUID | str,
        entity_id: str,
        entity_type: str,
        payload: dict[str, Any],
        longitude: float | None = None,
        latitude: float | None = None,
    ) -> None:
        """Cập nhật bản ghi trạng thái trong context.entity_state cùng PostGIS location nếu có."""
        t_id = uuid.UUID(str(tenant_id))
        loc_clause = "NULL"
        params: dict[str, Any] = {
            "tenant_id": t_id,
            "entity_id": entity_id,
            "type": entity_type,
            "payload": json.dumps(payload),
        }

        if longitude is not None and latitude is not None:
            loc_clause = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography"
            params["lon"] = float(longitude)
            params["lat"] = float(latitude)

        query = text(f"""
            INSERT INTO context.entity_state (tenant_id, entity_id, type, payload, location, updated_at)
            VALUES (:tenant_id, :entity_id, :type, :payload, {loc_clause}, clock_timestamp())
            ON CONFLICT (tenant_id, entity_id) DO UPDATE
            SET type = EXCLUDED.type,
                payload = EXCLUDED.payload,
                location = EXCLUDED.location,
                updated_at = clock_timestamp();
            """)
        await self.session.execute(query, params)

    async def delete_entity_state(
        self, tenant_id: uuid.UUID | str, entity_id: str
    ) -> None:
        """Xoá bản ghi trạng thái trong context.entity_state."""
        t_id = uuid.UUID(str(tenant_id))
        query = text("""
            DELETE FROM context.entity_state
            WHERE tenant_id = :tenant_id AND entity_id = :entity_id;
            """)
        await self.session.execute(query, {"tenant_id": t_id, "entity_id": entity_id})
