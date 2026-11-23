# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Context Sync Worker Service (Layer 3).

Chịu trách nhiệm quét bảng context.context_outbox (Transactional Outbox Pattern),
chuyển đổi sự kiện sang định dạng NGSI-LD chuẩn, đồng bộ sang Context Broker (Orion-LD),
cập nhật bảng context.entity_state, và phát sự kiện vào Redis Streams cho consumer realtime.
Tham chiếu: ADR-005, Issue #835 [L3-403], Issue #836 [L3-404], Issue #837 [L3-405].
"""

import asyncio
import json
import logging
import signal
import sys
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import (
    OutboxRecord,
    SQLAlchemyOutboxRepository,
)
from app.core.domain.geo_utils import to_ngsi_ld_geoproperty
from app.infrastructure.config import settings
from app.infrastructure.database import AsyncSessionLocal

logger = logging.getLogger("context_sync_worker")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)


def format_ngsi_ld_entity_id(
    entity_type: str, tenant_id: uuid.UUID | str, entity_id: str
) -> str:
    """Quy chuẩn URN Entity ID: urn:ngsi-ld:{Type}:{tenant}:{uuid}."""
    clean_id = str(entity_id).strip()
    if clean_id.startswith("urn:ngsi-ld:"):
        return clean_id
    return f"urn:ngsi-ld:{entity_type}:{tenant_id}:{clean_id}"


def transform_to_ngsi_ld(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], float | None, float | None]:
    """Chuyển đổi raw record payload sang định dạng thuộc tính NGSI-LD.

    Trả về (ngsi_payload, longitude, latitude).
    """
    ngsi_attrs: dict[str, Any] = {}
    lon: float | None = None
    lat: float | None = None

    for k, v in payload.items():
        if k in ("id", "tenant_id", "created_at", "updated_at"):
            continue

        # Kiểm tra toạ độ không gian
        if k.lower() in ("latitude", "lat") and isinstance(v, (int, float)):
            lat = float(v)
            continue
        if k.lower() in ("longitude", "lon", "lng") and isinstance(v, (int, float)):
            lon = float(v)
            continue

        # Quan hệ (Relationship)
        if k.endswith("_id") and v:
            target_type = k[:-3].capitalize()
            ngsi_attrs[k] = {
                "type": "Relationship",
                "object": (
                    str(v)
                    if str(v).startswith("urn:ngsi-ld:")
                    else f"urn:ngsi-ld:{target_type}:{v}"
                ),
            }
        else:
            ngsi_attrs[k] = {
                "type": "Property",
                "value": v,
            }

    if lat is not None and lon is not None:
        ngsi_attrs["location"] = to_ngsi_ld_geoproperty(lon, lat)

    return ngsi_attrs, lon, lat


class ContextSyncWorker:
    """Worker xử lý vòng lặp outbox đồng bộ ngữ cảnh (Transactional Outbox Pattern)."""

    def __init__(
        self,
        session_factory=None,
        orion_adapter=None,
        redis_client=None,
    ) -> None:
        self.is_running = False
        self.batch_size = settings.CONTEXT_SYNC_BATCH_SIZE
        self.poll_interval = settings.CONTEXT_SYNC_POLL_INTERVAL
        self.max_retries = settings.CONTEXT_SYNC_MAX_RETRIES
        self.stream_name = settings.CONTEXT_SYNC_STREAM_NAME

        self.session_factory = session_factory or AsyncSessionLocal
        self.orion = orion_adapter or OrionAdapter()
        self._redis = redis_client

    async def get_redis(self):
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def start(self) -> None:
        """Khởi động worker loop và xử lý tín hiệu ngắt."""
        self.is_running = True
        logger.info(
            "Starting Context Sync Worker: Orion=%s, BatchSize=%d, Stream=%s",
            settings.ORION_URL,
            self.batch_size,
            self.stream_name,
        )

        while self.is_running:
            try:
                processed_count = await self.process_batch()
                if processed_count == 0:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Worker cancelled, exiting loop.")
                break
            except Exception as e:
                logger.error("Error in outbox processing loop: %s", e, exc_info=True)
                await asyncio.sleep(min(self.poll_interval * 2, 10.0))

        await self.close()
        logger.info("Context Sync Worker shutdown complete.")

    async def stop(self) -> None:
        """Dừng worker êm dịu (graceful shutdown)."""
        logger.info("Stopping Context Sync Worker...")
        self.is_running = False

    async def close(self) -> None:
        """Dọn dẹp tài nguyên."""
        await self.orion.aclose()
        if self._redis is not None:
            await self._redis.aclose()

    async def process_batch(self) -> int:
        """Quét và xử lý một batch các bản ghi PENDING từ context_outbox."""
        async with self.session_factory() as session:
            repo = SQLAlchemyOutboxRepository(session)
            records = await repo.fetch_pending_batch(batch_size=self.batch_size)
            if not records:
                return 0

            redis_client = await self.get_redis()
            processed_ids: list[uuid.UUID] = []

            for record in records:
                ngsi_id = format_ngsi_ld_entity_id(
                    record.entity_type, record.tenant_id, record.entity_id
                )
                try:
                    if record.op == "DELETE":
                        # Xoá bên Orion-LD và entity_state
                        await self.orion.delete_entity(
                            ngsi_id, tenant_id=str(record.tenant_id)
                        )
                        await repo.delete_entity_state(record.tenant_id, ngsi_id)

                        # Phát sự kiện sang Redis Streams
                        event_data = {
                            "event_type": "context.entity.deleted",
                            "tenant_id": str(record.tenant_id),
                            "entity_id": ngsi_id,
                            "entity_type": record.entity_type,
                            "op": "DELETE",
                            "timestamp": record.created_at.isoformat(),
                        }
                        await redis_client.xadd(self.stream_name, event_data)
                    else:
                        # UPSERT: Chuyển đổi sang NGSI-LD
                        ngsi_attrs, lon, lat = transform_to_ngsi_ld(record.payload)
                        await self.orion.upsert_entity(
                            ngsi_id,
                            record.entity_type,
                            ngsi_attrs,
                            tenant_id=str(record.tenant_id),
                        )
                        await repo.upsert_entity_state(
                            record.tenant_id,
                            ngsi_id,
                            record.entity_type,
                            ngsi_attrs,
                            longitude=lon,
                            latitude=lat,
                        )

                        # Phát sự kiện sang Redis Streams
                        event_data = {
                            "event_type": "context.entity.updated",
                            "tenant_id": str(record.tenant_id),
                            "entity_id": ngsi_id,
                            "entity_type": record.entity_type,
                            "op": record.op,
                            "payload": json.dumps(ngsi_attrs),
                            "timestamp": record.created_at.isoformat(),
                        }
                        await redis_client.xadd(self.stream_name, event_data)

                    processed_ids.append(record.id)
                except Exception as exc:
                    logger.warning(
                        "Failed to process outbox record %s (entity %s): %s",
                        record.id,
                        ngsi_id,
                        exc,
                    )
                    await repo.mark_failed(
                        record.id, str(exc), max_retries=self.max_retries
                    )

            if processed_ids:
                await repo.mark_processed(processed_ids)

            await session.commit()
            return len(processed_ids)


async def main() -> None:
    """Entrypoint chính của worker process."""
    worker = ContextSyncWorker()

    loop = asyncio.get_running_loop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))
    else:

        def _win_handler(signum: int, frame: Any) -> None:
            asyncio.create_task(worker.stop())

        signal.signal(signal.SIGINT, _win_handler)
        signal.signal(signal.SIGTERM, _win_handler)

    try:
        await worker.start()
    except Exception as e:
        logger.critical("Fatal error in Context Sync Worker: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
