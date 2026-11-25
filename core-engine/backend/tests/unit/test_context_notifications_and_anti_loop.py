# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Context notifications endpoint and anti-sync loop protection.

Tham chiếu: Issue #847 [L3-602], Issue #848 [L3-603], Issue #850 [L3-605].
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.entrypoints.routers.context import parse_urn_parts
from main import app


def test_parse_urn_parts():
    urn = "urn:ngsi-ld:Room:4a8b7e23-1122-3344-5566-778899aabbcc:room-101"
    etype, tenant, raw_id = parse_urn_parts(urn)
    assert etype == "Room"
    assert tenant == "4a8b7e23-1122-3344-5566-778899aabbcc"
    assert raw_id == "room-101"

    with pytest.raises(ValueError, match="Invalid NGSI-LD URN format"):
        parse_urn_parts("invalid:urn:format")


@pytest.mark.asyncio
async def test_notifications_endpoint_anti_loop_and_redis_stream():
    """Verify that when a notification arrives from Orion:
    1. It updates context.entity_state directly.
    2. It publishes to Redis Stream.
    3. It NEVER calls context_outbox.enqueue (anti-loop protection).
    """
    tid = uuid.uuid4()
    notification_payload = {
        "subscriptionId": "sub-test-123",
        "data": [
            {
                "id": f"urn:ngsi-ld:Room:{tid}:room-alpha",
                "type": "Room",
                "name": {"type": "Property", "value": "Phòng Alpha"},
                "capacity": {"type": "Property", "value": 50},
                "location": {
                    "type": "GeoProperty",
                    "value": {
                        "type": "Point",
                        "coordinates": [105.804817, 21.028511],
                    },
                },
            }
        ],
    }

    mock_session = AsyncMock()
    mock_redis = AsyncMock()

    with (
        patch("app.entrypoints.routers.context.AsyncSessionLocal") as mock_sess_cls,
        patch(
            "app.adapters.repositories.outbox_repository.SQLAlchemyOutboxRepository.upsert_entity_state"
        ) as mock_upsert,
        patch(
            "app.adapters.repositories.outbox_repository.SQLAlchemyOutboxRepository.enqueue"
        ) as mock_enqueue,
    ):
        mock_sess_cls.return_value.__aenter__.return_value = mock_session

        app.state.redis_client = mock_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/context/notifications",
                json=notification_payload,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["processed_entities"] == 1

        # 1. Verify entity_state was updated directly with spatial coordinates
        mock_upsert.assert_called_once()
        u_args, u_kwargs = mock_upsert.call_args
        assert u_kwargs["tenant_id"] == tid
        assert u_kwargs["entity_id"] == f"urn:ngsi-ld:Room:{tid}:room-alpha"
        assert u_kwargs["longitude"] == 105.804817
        assert u_kwargs["latitude"] == 21.028511

        # 2. ANTI-LOOP CRITICAL: Verify outbox enqueue was NOT called
        mock_enqueue.assert_not_called()

        # 3. Verify published to Redis Stream
        mock_redis.xadd.assert_called_once()
        s_args, s_kwargs = mock_redis.xadd.call_args
        assert s_args[0] == "stream:context:events"
        assert s_args[1]["event_type"] == "context.notification.received"


@pytest.mark.asyncio
async def test_subscriptions_crud_endpoints():
    """Kiểm thử API đăng ký, lấy danh sách và hủy Orion subscription (#846, #848)."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from app.core.domain.entities import TenantContext
    from app.entrypoints.dependencies import get_current_tenant_context

    tid = uuid.uuid4()
    ctx = TenantContext(tenant_id=tid, user_id=uuid.uuid4(), roles=["tenant_admin"])
    app.dependency_overrides[get_current_tenant_context] = lambda: ctx

    mock_session = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (
            "sub-abc-123",
            "Meeting",
            "http://test/cb",
            "ACTIVE",
            datetime.now(UTC),
        )
    ]
    mock_session.execute.return_value = mock_cursor

    try:
        with (
            patch("app.entrypoints.routers.context.AsyncSessionLocal") as mock_sess_cls,
            patch(
                "app.adapters.external.orion_adapter.OrionAdapter.delete_subscription"
            ) as mock_del_sub,
        ):
            mock_sess_cls.return_value.__aenter__.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # GET subscriptions
                get_resp = await client.get("/api/v1/context/subscriptions")
                assert get_resp.status_code == 200
                subs = get_resp.json()
                assert len(subs) == 1
                assert subs[0]["subscription_id"] == "sub-abc-123"

                # DELETE subscription
                del_resp = await client.delete(
                    "/api/v1/context/subscriptions/sub-abc-123"
                )
                assert del_resp.status_code == 200
                del_data = del_resp.json()
                assert del_data["status"] == "success"
                mock_del_sub.assert_called_once()
    finally:
        app.dependency_overrides.clear()
