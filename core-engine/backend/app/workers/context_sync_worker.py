# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Context Sync Worker Service (Layer 3).

Chịu trách nhiệm quét bảng context.context_outbox (Transactional Outbox Pattern),
chuyển đổi sự kiện sang định dạng NGSI-LD chuẩn, đồng bộ sang Context Broker (Orion-LD),
cập nhật bảng context.entity_state và phát sự kiện vào Redis Streams realtime.
Tham chiếu: ADR-005, Issue #835 [L3-403], Issue #836 [L3-404], Issue #837 [L3-405].
"""

import asyncio
import inspect
import json
import logging
import math
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import SQLAlchemyOutboxRepository
from app.core.domain.geo_utils import to_ngsi_ld_geoproperty
from app.core.use_cases.manifest_validator import _PROHIBITED_NGSI_COLUMNS
from app.infrastructure.config import settings
from app.infrastructure.database import AsyncSessionLocal, set_session_tenant

logger = logging.getLogger("context_sync_worker")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)

_SENSITIVE_NGSI_COLUMNS: frozenset[str] = _PROHIBITED_NGSI_COLUMNS | frozenset(
    {
        "password_hash",
        "cccd",
        "cmnd",
        "national_id",
        "net_salary",
        "gross_salary",
        "bonus",
        "allowance",
        "bank_number",
        "iban",
        "credit_card",
    }
)


@asynccontextmanager
async def _record_savepoint(session: Any):
    """Bao bọc thao tác DB của từng bản ghi trong SAVEPOINT để cô lập lỗi SQL."""
    if isinstance(session, AsyncSession):
        async with session.begin_nested():
            yield
        return

    nested = session.begin_nested() if hasattr(session, "begin_nested") else None
    if nested is not None and hasattr(nested, "__aenter__"):
        async with nested:
            yield
    else:
        if inspect.isawaitable(nested):
            nested.close()
        yield


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
    tenant_id: uuid.UUID | str | None = None,
) -> tuple[dict[str, Any], float | None, float | None]:
    """Chuyển đổi raw record payload sang định dạng thuộc tính NGSI-LD.

    Loại bỏ toàn bộ các cột nhạy cảm thuộc `_PROHIBITED_NGSI_COLUMNS` và tạo
    URN 5 phần cho thuộc tính Relationship khi biết `tenant_id`.
    Trả về (ngsi_payload, longitude, latitude).
    """
    ngsi_attrs: dict[str, Any] = {}
    lon: float | None = None
    lat: float | None = None

    effective_tenant: str | None = None
    if tenant_id is not None and str(tenant_id).strip():
        effective_tenant = str(tenant_id).strip()
    elif payload.get("tenant_id") and str(payload["tenant_id"]).strip():
        effective_tenant = str(payload["tenant_id"]).strip()

    for k, v in payload.items():
        if k in ("id", "tenant_id", "created_at", "updated_at"):
            continue
        if k.lower() in _SENSITIVE_NGSI_COLUMNS:
            continue

        # Kiểm tra toạ độ không gian
        if (
            k.lower() in ("latitude", "lat")
            and not isinstance(v, bool)
            and isinstance(v, int | float)
            and math.isfinite(float(v))
        ):
            lat = float(v)
            continue
        if (
            k.lower() in ("longitude", "lon", "lng")
            and not isinstance(v, bool)
            and isinstance(v, int | float)
            and math.isfinite(float(v))
        ):
            lon = float(v)
            continue

        # Quan hệ (Relationship)
        if k.endswith("_id") and v:
            target_type = k[:-3].capitalize()
            str_v = str(v).strip()
            if str_v.startswith("urn:ngsi-ld:"):
                rel_object = str_v
            elif effective_tenant:
                rel_object = f"urn:ngsi-ld:{target_type}:{effective_tenant}:{str_v}"
            else:
                rel_object = f"urn:ngsi-ld:{target_type}:{str_v}"
            ngsi_attrs[k] = {
                "type": "Relationship",
                "object": rel_object,
            }
        else:
            ngsi_attrs[k] = {
                "type": "Property",
                "value": v,
            }

    if (
        lat is not None
        and lon is not None
        and -180.0 <= lon <= 180.0
        and -90.0 <= lat <= 90.0
    ):
        ngsi_attrs["location"] = to_ngsi_ld_geoproperty(lon, lat)
    else:
        lon, lat = None, None

    return ngsi_attrs, lon, lat


class ContextSyncWorker:
    """Worker xử lý vòng lặp outbox đồng bộ ngữ cảnh (Transactional Outbox Pattern)."""

    transform_to_ngsi_ld = staticmethod(transform_to_ngsi_ld)

    def __init__(
        self,
        session_factory=None,
        orion_adapter=None,
        redis_client=None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.is_running = False
        self.batch_size = settings.CONTEXT_SYNC_BATCH_SIZE
        self.poll_interval = settings.CONTEXT_SYNC_POLL_INTERVAL
        self.max_retries = settings.CONTEXT_SYNC_MAX_RETRIES
        self.stream_name = settings.CONTEXT_SYNC_STREAM_NAME

        self._owns_http_client = False
        if http_client is None and orion_adapter is None:
            http_client = httpx.AsyncClient(timeout=10.0)
            self._owns_http_client = True
        self._http_client = http_client

        self.session_factory = session_factory or AsyncSessionLocal
        self.orion = orion_adapter or OrionAdapter(client=self._http_client)
        self._owns_redis = redis_client is None
        self._redis = redis_client

    async def get_redis(self):
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            self._owns_redis = True
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
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        if self._redis is not None and self._owns_redis:
            await self._redis.aclose()
            self._redis = None

    async def process_batch(self) -> int:
        """Quét và xử lý một batch các bản ghi PENDING từ context_outbox."""
        async with self.session_factory() as session:
            await set_session_tenant(session, "__system__")
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
                    async with _record_savepoint(session):
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
                            await redis_client.xadd(
                                self.stream_name,
                                event_data,
                                maxlen=10000,
                                approximate=True,
                            )
                        else:
                            # UPSERT: Chuyển đổi sang NGSI-LD (lọc cột nhạy cảm)
                            clean_payload = {
                                k: v
                                for k, v in record.payload.items()
                                if k.lower() not in _SENSITIVE_NGSI_COLUMNS
                            }
                            ngsi_attrs, lon, lat = transform_to_ngsi_ld(
                                clean_payload, tenant_id=record.tenant_id
                            )
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
                            await redis_client.xadd(
                                self.stream_name,
                                event_data,
                                maxlen=10000,
                                approximate=True,
                            )

                    processed_ids.append(record.id)
                except Exception as exc:
                    logger.warning(
                        "Failed to process outbox record %s (entity %s): %s",
                        record.id,
                        ngsi_id,
                        exc,
                    )
                    try:
                        async with _record_savepoint(session):
                            await repo.mark_failed(
                                record.id, str(exc), max_retries=self.max_retries
                            )
                    except Exception as mark_exc:
                        logger.error(
                            "Could not mark outbox record %s failed: %s",
                            record.id,
                            mark_exc,
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
