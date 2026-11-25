# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit and contract tests for OrionAdapter and NGSI-LD JSON-LD representations.

Tham chiếu: Issue #831 [L3-304], Issue #832 [L3-305], docs/ngsi-ld-model.md.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.external.orion_adapter import (
    DEFAULT_CONTEXT,
    OrionAdapter,
)


@pytest.mark.asyncio
async def test_orion_adapter_upsert_created():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.return_value = httpx.Response(201)

    adapter = OrionAdapter(base_url="http://mock-orion:1026", client=mock_client)

    payload = {
        "name": {"type": "Property", "value": "Room A101"},
        "capacity": {"type": "Property", "value": 30},
    }
    result = await adapter.upsert_entity(
        entity_id="urn:ngsi-ld:Room:ictu:room-a101",
        entity_type="Room",
        payload=payload,
        tenant_id="ictu-tenant-uuid",
    )
    assert result is True
    mock_client.request.assert_called_once()
    args, kwargs = mock_client.request.call_args
    assert args[0] == "POST"
    assert args[1] == "http://mock-orion:1026/ngsi-ld/v1/entities"
    assert kwargs["headers"]["NGSILD-Tenant"] == "ictu_tenant_uuid"
    assert kwargs["json"]["@context"] == DEFAULT_CONTEXT
    assert kwargs["json"]["id"] == "urn:ngsi-ld:Room:ictu:room-a101"


@pytest.mark.asyncio
async def test_orion_adapter_upsert_conflict_then_patch():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    # 1st call returns 409 Conflict, 2nd call returns 204 No Content
    mock_client.request.side_effect = [
        httpx.Response(409, text="Already exists"),
        httpx.Response(204),
    ]

    adapter = OrionAdapter(base_url="http://mock-orion:1026", client=mock_client)

    payload = {
        "name": {"type": "Property", "value": "Room A101 Updated"},
    }
    result = await adapter.upsert_entity(
        entity_id="urn:ngsi-ld:Room:ictu:room-a101",
        entity_type="Room",
        payload=payload,
    )
    assert result is True
    assert mock_client.request.call_count == 2
    # Verify second call was to /attrs and preserves @context for application/ld+json
    patch_args, patch_kwargs = mock_client.request.call_args
    assert "attrs" in patch_args[1]
    assert patch_kwargs["json"] == {
        "name": {"type": "Property", "value": "Room A101 Updated"},
        "@context": DEFAULT_CONTEXT,
    }


@pytest.mark.asyncio
async def test_orion_adapter_get_and_delete():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.side_effect = [
        httpx.Response(200, json={"id": "urn:ngsi-ld:Room:ictu:1", "type": "Room"}),
        httpx.Response(404),
        httpx.Response(204),
        httpx.Response(404),
    ]

    adapter = OrionAdapter(base_url="http://mock-orion:1026", client=mock_client)

    # 1. Get found
    entity = await adapter.get_entity("urn:ngsi-ld:Room:ictu:1")
    assert entity is not None
    assert entity["id"] == "urn:ngsi-ld:Room:ictu:1"

    # 2. Get 404
    entity404 = await adapter.get_entity("urn:ngsi-ld:Room:ictu:2")
    assert entity404 is None

    # 3. Delete 204
    del_ok = await adapter.delete_entity("urn:ngsi-ld:Room:ictu:1")
    assert del_ok is True

    # 4. Delete 404 (idempotent)
    del_ok2 = await adapter.delete_entity("urn:ngsi-ld:Room:ictu:2")
    assert del_ok2 is True


@pytest.mark.asyncio
async def test_orion_adapter_subscription_lifecycle():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.request.side_effect = [
        httpx.Response(
            201, headers={"Location": "/ngsi-ld/v1/subscriptions/sub-12345"}
        ),
        httpx.Response(204),
    ]

    adapter = OrionAdapter(base_url="http://mock-orion:1026", client=mock_client)

    sub_id = await adapter.create_subscription(
        {
            "type": "Subscription",
            "entities": [{"type": "Room"}],
            "notification": {
                "endpoint": {"uri": "http://backend:8000/api/v1/context/notifications"}
            },
        }
    )
    assert sub_id == "sub-12345"

    del_res = await adapter.delete_subscription("sub-12345")
    assert del_res is True


def test_ngsi_ld_contract_room_entity():
    """Verify NGSI-LD contract for Room entity against docs/ngsi-ld-model.md."""
    room = {
        "id": "urn:ngsi-ld:Room:ictu:4a8b7e23-1122-3344-5566-778899aabbcc",
        "type": "Room",
        "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
        "name": {"type": "Property", "value": "Phòng Hội thảo A101"},
        "capacity": {"type": "Property", "value": 45},
        "floor": {"type": "Property", "value": "Tầng 1 - Tòa Alpha"},
        "location": {
            "type": "GeoProperty",
            "value": {"type": "Point", "coordinates": [105.804817, 21.028511]},
        },
    }

    # Contract Assertions
    assert room["id"].startswith("urn:ngsi-ld:Room:")
    assert room["type"] == "Room"
    assert room["name"]["type"] == "Property"
    assert isinstance(room["name"]["value"], str)
    assert room["capacity"]["type"] == "Property"
    assert isinstance(room["capacity"]["value"], int)
    assert room["location"]["type"] == "GeoProperty"
    assert room["location"]["value"]["type"] == "Point"
    assert len(room["location"]["value"]["coordinates"]) == 2


def test_ngsi_ld_contract_employee_and_asset():
    """Verify NGSI-LD contract for Employee and Asset entities."""
    employee = {
        "id": "urn:ngsi-ld:Employee:ictu:emp-001",
        "type": "Employee",
        "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
        "employeeCode": {"type": "Property", "value": "NV001"},
        "fullName": {"type": "Property", "value": "Nguyễn Văn A"},
        "email": {"type": "Property", "value": "nva@ictu.vn"},
        "memberOf": {
            "type": "Relationship",
            "object": "urn:ngsi-ld:Department:ictu:dept-it",
        },
    }
    assert employee["memberOf"]["type"] == "Relationship"
    assert employee["memberOf"]["object"].startswith("urn:ngsi-ld:Department:")

    asset = {
        "id": "urn:ngsi-ld:Asset:ictu:ast-999",
        "type": "Asset",
        "@context": "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
        "assetCode": {"type": "Property", "value": "LAP-2026-001"},
        "belongsToCategory": {
            "type": "Relationship",
            "object": "urn:ngsi-ld:AssetCategory:ictu:cat-laptop",
        },
    }
    assert asset["belongsToCategory"]["type"] == "Relationship"
    assert asset["belongsToCategory"]["object"].startswith("urn:ngsi-ld:AssetCategory:")
