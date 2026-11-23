# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for Transactional Outbox, ContextSyncWorker, Redis Streams, Idempotency, and DLQ.

Tham chiếu: Issue #834, #835, #836, #837, #839.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import (
    OutboxRecord,
    SQLAlchemyOutboxRepository,
)
from app.workers.context_sync_worker import (
    ContextSyncWorker,
    format_ngsi_ld_entity_id,
    transform_to_ngsi_ld,
)


def test_format_ngsi_ld_entity_id():
    tid = uuid.uuid4()
    # If raw uuid
    ngsi_id = format_ngsi_ld_entity_id("Room", tid, "room-101")
    assert ngsi_id == f"urn:ngsi-ld:Room:{tid}:room-101"

    # If already formatted
    existing = "urn:ngsi-ld:Room:tenant:123"
    assert format_ngsi_ld_entity_id("Room", tid, existing) == existing


def test_transform_to_ngsi_ld_properties_and_location():
    raw_payload = {
        "id": "abc",
        "tenant_id": "def",
        "name": "Hội trường 1",
        "capacity": 100,
        "organizer_id": "emp-001",
        "latitude": 21.028511,
        "longitude": 105.804817,
    }
    ngsi_attrs, lon, lat = transform_to_ngsi_ld(raw_payload)

    assert lon == 105.804817
    assert lat == 21.028511
    assert ngsi_attrs["name"] == {"type": "Property", "value": "Hội trường 1"}
    assert ngsi_attrs["capacity"] == {"type": "Property", "value": 100}
    assert ngsi_attrs["organizer_id"]["type"] == "Relationship"
    assert "location" in ngsi_attrs
    assert ngsi_attrs["location"]["type"] == "GeoProperty"
    assert ngsi_attrs["location"]["value"]["coordinates"] == [105.804817, 21.028511]


@pytest.mark.asyncio
async def test_outbox_worker_process_batch_success():
    tid = uuid.uuid4()
    record1 = OutboxRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        entity_type="Room",
        entity_id="room-101",
        op="UPSERT",
        payload={"name": "Phòng họp A", "capacity": 20},
        status="PENDING",
        retry_count=0,
        idempotency_key="key-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    record2 = OutboxRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        entity_type="Room",
        entity_id="room-102",
        op="DELETE",
        payload={"name": "Phòng họp B"},
        status="PENDING",
        retry_count=0,
        idempotency_key="key-2",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_orion = AsyncMock(spec=OrionAdapter)
    mock_redis = AsyncMock()

    # Mock execute returns for fetch_pending_batch
    rows = [
        (
            record1.id,
            record1.tenant_id,
            record1.entity_type,
            record1.entity_id,
            record1.op,
            record1.payload,
            record1.status,
            record1.retry_count,
            record1.idempotency_key,
            record1.created_at,
            record1.updated_at,
        ),
        (
            record2.id,
            record2.tenant_id,
            record2.entity_type,
            record2.entity_id,
            record2.op,
            record2.payload,
            record2.status,
            record2.retry_count,
            record2.idempotency_key,
            record2.created_at,
            record2.updated_at,
        ),
    ]
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_session.execute.return_value = mock_cursor

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    worker = ContextSyncWorker(
        session_factory=mock_session_factory,
        orion_adapter=mock_orion,
        redis_client=mock_redis,
    )

    count = await worker.process_batch()
    assert count == 2

    # Check Orion calls
    mock_orion.upsert_entity.assert_called_once()
    mock_orion.delete_entity.assert_called_once()

    # Check Redis stream publish
    assert mock_redis.xadd.call_count == 2
    stream_calls = mock_redis.xadd.call_args_list
    assert stream_calls[0][0][0] == "stream:context:events"
    assert stream_calls[0][0][1]["event_type"] == "context.entity.updated"
    assert stream_calls[1][0][1]["event_type"] == "context.entity.deleted"

    # Verify session commit occurred
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_worker_crash_and_dlq_on_repeated_failures():
    """Verify that if processing fails, retry_count is incremented and marked DLQ on threshold."""
    tid = uuid.uuid4()
    bad_record = OutboxRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        entity_type="Room",
        entity_id="broken-room",
        op="UPSERT",
        payload={"name": "Broken Room"},
        status="PENDING",
        retry_count=4,  # Next failure hits max_retries = 5 -> DLQ
        idempotency_key="key-bad",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_orion = AsyncMock(spec=OrionAdapter)
    mock_orion.upsert_entity.side_effect = RuntimeError(
        "Orion down or rejected payload"
    )
    mock_redis = AsyncMock()

    rows = [
        (
            bad_record.id,
            bad_record.tenant_id,
            bad_record.entity_type,
            bad_record.entity_id,
            bad_record.op,
            bad_record.payload,
            bad_record.status,
            bad_record.retry_count,
            bad_record.idempotency_key,
            bad_record.created_at,
            bad_record.updated_at,
        ),
    ]
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_session.execute.return_value = mock_cursor

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    worker = ContextSyncWorker(
        session_factory=mock_session_factory,
        orion_adapter=mock_orion,
        redis_client=mock_redis,
    )

    count = await worker.process_batch()
    # 0 processed successfully
    assert count == 0

    # Verify session committed the error / retry update to DB
    mock_session.commit.assert_called_once()
    # Redis should NOT have received a published event
    mock_redis.xadd.assert_not_called()
