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
import math
import re
import socket
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.external.orion_adapter import OrionAdapter
from app.adapters.repositories.outbox_repository import SQLAlchemyOutboxRepository
from app.core.domain.entities import TenantContext
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


ICTU_CAMPUS_CENTER: list[float] = [105.8064, 21.5850]

ETSI_NGSI_LD_CONTEXT: list[str] = [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "https://uri.etsi.org/ngsi-ld/v1.6/ngsi-ld-core-context-v1.6.jsonld",
]

_FK_ENTITY_TYPE_MAP: dict[str, str] = {
    "room": "Room",
    "organizer": "Employee",
    "employee": "Employee",
    "assignee": "Employee",
    "requester": "Employee",
    "user": "Employee",
    "manager": "Employee",
    "issuer": "Employee",
    "department": "Department",
    "dept": "Department",
    "asset": "Asset",
    "project": "Project",
    "customer": "Customer",
    "vendor": "Supplier",
    "supplier": "Supplier",
    "category": "Category",
    "building": "Building",
    "facility": "Building",
    "booking": "MeetingBooking",
    "ticket": "Ticket",
}

_WKT_POINT_RE = re.compile(
    r"POINT\s*\(\s*([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)


def _parse_bbox_param(bbox: str) -> tuple[float, float, float, float]:
    """Validate và parse tham số bbox='min_lon,min_lat,max_lon,max_lat'."""
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bbox format. Expected 'min_lon,min_lat,max_lon,max_lat'.",
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bbox coordinates: all 4 values must be valid numbers.",
        ) from exc

    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bbox coordinates: values must be finite numbers.",
        )
    if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bbox longitude: must be within [-180, 180].",
        )
    if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bbox latitude: must be within [-90, 90].",
        )
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid bbox bounds: min_lon <= max_lon "
                "and min_lat <= max_lat required."
            ),
        )
    return min_lon, min_lat, max_lon, max_lat


def _extract_scalar_value(val: Any) -> Any:
    if isinstance(val, dict) and "value" in val:
        return val.get("value")
    return val


def _extract_coordinates(
    payload: dict[str, Any], location_raw: Any = None
) -> list[float] | None:
    """Trích xuất tọa độ [lon, lat] từ payload.location hoặc cột PostGIS location."""
    loc_prop = payload.get("location")
    if isinstance(loc_prop, dict):
        parsed = parse_ngsi_ld_geoproperty(loc_prop)
        if parsed is not None:
            return [parsed[0], parsed[1]]
        if loc_prop.get("type") == "Point":
            parsed_direct = parse_ngsi_ld_geoproperty(
                {"type": "GeoProperty", "value": loc_prop}
            )
            if parsed_direct is not None:
                return [parsed_direct[0], parsed_direct[1]]

    if location_raw:
        if isinstance(location_raw, dict):
            parsed_raw = parse_ngsi_ld_geoproperty(
                {"type": "GeoProperty", "value": location_raw}
            )
            if parsed_raw is not None:
                return [parsed_raw[0], parsed_raw[1]]
        elif isinstance(location_raw, str):
            raw_str = location_raw.strip()
            if raw_str.startswith("{"):
                try:
                    geo_obj = json.loads(raw_str)
                    parsed_json = parse_ngsi_ld_geoproperty(
                        {"type": "GeoProperty", "value": geo_obj}
                    )
                    if parsed_json is not None:
                        return [parsed_json[0], parsed_json[1]]
                except Exception:
                    pass
            wkt_match = _WKT_POINT_RE.search(raw_str)
            if wkt_match:
                lon, lat = float(wkt_match.group(1)), float(wkt_match.group(2))
                if -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0:
                    return [lon, lat]
    return None


def _extract_relationships(
    payload: dict[str, Any], tenant_id: str
) -> list[dict[str, str]]:
    """Trích xuất danh sách quan hệ NGSI-LD (cô lập cùng tenant_id)."""
    rels: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add_rel(rel_name: str, target_urn: str, fallback_type: str = "Entity") -> None:
        if target_urn.startswith("urn:ngsi-ld:"):
            try:
                urn_type, urn_tenant, _ = parse_urn_parts(target_urn)
                if urn_tenant != tenant_id:
                    return
                target_type = urn_type
            except ValueError:
                target_type = fallback_type
        else:
            target_type = fallback_type
            target_urn = f"urn:ngsi-ld:{target_type}:{tenant_id}:{target_urn}"

        dedupe_key = (rel_name, target_urn)
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        rels.append(
            {
                "name": rel_name,
                "object": target_urn,
                "target": target_urn,
                "target_type": target_type,
            }
        )

    for key, val in payload.items():
        if key in ("id", "type", "@context", "tenant_id", "entity_id"):
            continue
        if isinstance(val, dict) and val.get("type") == "Relationship":
            raw_obj = val.get("object")
            if isinstance(raw_obj, str) and raw_obj.strip():
                _add_rel(key, raw_obj.strip())
            elif isinstance(raw_obj, list):
                for item in raw_obj:
                    if isinstance(item, str) and item.strip():
                        _add_rel(key, item.strip())
        elif key.lower().endswith("_id"):
            scalar = _extract_scalar_value(val)
            if scalar is not None and str(scalar).strip():
                prefix = key[:-3].lower()
                inferred_type = _FK_ENTITY_TYPE_MAP.get(
                    prefix,
                    "".join(part.capitalize() for part in prefix.split("_") if part)
                    or "Entity",
                )
                _add_rel(key, str(scalar).strip(), fallback_type=inferred_type)

    return rels


def _compute_status_indicator(payload: dict[str, Any]) -> str:
    """Tính trạng thái Digital Twin: normal | busy | warning | critical."""
    raw_status = _extract_scalar_value(
        payload.get("status")
        or payload.get("employmentStatus")
        or payload.get("stage")
        or ""
    )
    status_upper = str(raw_status or "").strip().upper()

    raw_priority = _extract_scalar_value(payload.get("priority") or "")
    priority_upper = str(raw_priority or "").strip().upper()

    escalated = _extract_scalar_value(payload.get("escalated"))
    is_active = _extract_scalar_value(payload.get("isActive"))

    if (
        escalated is True
        or priority_upper in ("P1", "CRITICAL", "URGENT")
        or status_upper
        in (
            "CRITICAL",
            "OVERDUE",
            "FAILED",
            "ERROR",
            "DOWN",
            "OUT_OF_SERVICE",
            "SLA_VIOLATED",
        )
    ):
        return "critical"

    if (
        is_active is False
        or priority_upper in ("P2", "HIGH")
        or status_upper
        in (
            "WARNING",
            "MAINTENANCE",
            "PENDING",
            "OPEN",
            "WAITING_ON_USER",
            "ON_HOLD",
            "DEGRADED",
        )
    ):
        return "warning"

    if status_upper in (
        "BUSY",
        "IN_USE",
        "OCCUPIED",
        "IN_PROGRESS",
        "BOOKED",
        "ASSIGNED",
        "RUNNING",
    ):
        return "busy"

    return "normal"


def _extract_display_name(
    entity_id: str, entity_type: str, payload: dict[str, Any]
) -> str:
    for candidate_key in (
        "name",
        "title",
        "fullName",
        "companyName",
        "invoiceNumber",
        "assetCode",
        "roomCode",
        "projectCode",
        "docCode",
    ):
        if candidate_key in payload:
            val = _extract_scalar_value(payload[candidate_key])
            if val is not None and str(val).strip():
                return str(val).strip()
    try:
        _, _, short_id = parse_urn_parts(entity_id)
        return f"{entity_type} ({short_id})"
    except ValueError:
        return entity_id


def _serialize_entity_record(
    *,
    tenant_id: str,
    entity_id: str,
    entity_type: str,
    payload: dict[str, Any],
    location_raw: Any = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    sanitized_payload = {
        k: v
        for k, v in (payload or {}).items()
        if k.lower() not in _PROHIBITED_NGSI_COLUMNS
    }
    sanitized_payload.setdefault("id", entity_id)
    sanitized_payload.setdefault("type", entity_type)
    sanitized_payload.setdefault("@context", list(ETSI_NGSI_LD_CONTEXT))

    coords = _extract_coordinates(sanitized_payload, location_raw=location_raw)
    if coords is not None and "location" not in sanitized_payload:
        sanitized_payload["location"] = {
            "type": "GeoProperty",
            "value": {"type": "Point", "coordinates": coords},
        }

    relationships = _extract_relationships(sanitized_payload, tenant_id=tenant_id)
    status_indicator = _compute_status_indicator(sanitized_payload)
    display_name = _extract_display_name(entity_id, entity_type, sanitized_payload)

    return {
        "id": entity_id,
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "type": entity_type,
        "name": display_name,
        "coordinates": coords,
        "longitude": coords[0] if coords else None,
        "latitude": coords[1] if coords else None,
        "status_indicator": status_indicator,
        "relationships": relationships,
        "payload": sanitized_payload,
        "updated_at": updated_at,
    }


def _build_ictu_campus_demo_entities(tenant_id: str) -> list[dict[str, Any]]:
    """Bộ thực thể mẫu Khuôn viên Đại học Số ICTU gắn đúng tenant_id hiện tại."""
    now_iso = datetime.now(UTC).isoformat()

    def _urn(etype: str, slug: str) -> str:
        return f"urn:ngsi-ld:{etype}:{tenant_id}:{slug}"

    def _prop(val: Any) -> dict[str, Any]:
        return {"type": "Property", "value": val}

    def _rel(target_urn: str) -> dict[str, Any]:
        return {"type": "Relationship", "object": target_urn}

    def _geo(lon: float, lat: float) -> dict[str, Any]:
        return {
            "type": "GeoProperty",
            "value": {"type": "Point", "coordinates": [lon, lat]},
        }

    raw_specs: list[tuple[str, str, dict[str, Any]]] = [
        (
            _urn("Building", "ictu-c1"),
            "Building",
            {
                "name": _prop("Tòa nhà Điều hành C1"),
                "buildingCode": _prop("ICTU-C1"),
                "floors": _prop(7),
                "status": _prop("ACTIVE"),
                "address": _prop("Đường Z115, Quyết Thắng, TP. Thái Nguyên"),
                "location": _geo(105.8064, 21.5850),
            },
        ),
        (
            _urn("Building", "ictu-c2"),
            "Building",
            {
                "name": _prop("Giảng đường Đa năng C2"),
                "buildingCode": _prop("ICTU-C2"),
                "floors": _prop(5),
                "status": _prop("IN_USE"),
                "occupancyPct": _prop(82),
                "partOfCampus": _rel(_urn("Building", "ictu-c1")),
                "location": _geo(105.8071, 21.5854),
            },
        ),
        (
            _urn("Building", "ictu-c6"),
            "Building",
            {
                "name": _prop("Tòa nhà Lab AI & IoT C6"),
                "buildingCode": _prop("ICTU-C6"),
                "floors": _prop(6),
                "status": _prop("ACTIVE"),
                "partOfCampus": _rel(_urn("Building", "ictu-c1")),
                "location": _geo(105.8057, 21.5846),
            },
        ),
        (
            _urn("Building", "ictu-library"),
            "Building",
            {
                "name": _prop("Trung tâm Số & Thư viện"),
                "buildingCode": _prop("ICTU-LIB"),
                "floors": _prop(4),
                "status": _prop("ACTIVE"),
                "partOfCampus": _rel(_urn("Building", "ictu-c1")),
                "location": _geo(105.8069, 21.5843),
            },
        ),
        (
            _urn("Room", "room-c1-202"),
            "Room",
            {
                "name": _prop("Phòng họp C1-202"),
                "roomCode": _prop("C1-202"),
                "capacity": _prop(40),
                "floor": _prop("Tầng 2"),
                "status": _prop("IN_USE"),
                "belongsToBuilding": _rel(_urn("Building", "ictu-c1")),
                "location": _geo(105.8065, 21.5851),
            },
        ),
        (
            _urn("Asset", "srv-gpu-c6-301"),
            "Asset",
            {
                "name": _prop("Server GPU Lab C6-301"),
                "assetCode": _prop("ICTU-GPU-A100-01"),
                "category": _prop("AI Compute Cluster"),
                "status": _prop("MAINTENANCE"),
                "locatedAt": _rel(_urn("Building", "ictu-c6")),
                "location": _geo(105.8058, 21.5847),
            },
        ),
        (
            _urn("Asset", "maxhub-c1-202"),
            "Asset",
            {
                "name": _prop("Máy chiếu tương tác Maxhub 86 inch"),
                "assetCode": _prop("ICTU-AV-MX86"),
                "category": _prop("Smart Conferencing"),
                "status": _prop("IN_USE"),
                "locatedInRoom": _rel(_urn("Room", "room-c1-202")),
                "locatedAt": _rel(_urn("Building", "ictu-c1")),
                "location": _geo(105.8065, 21.5850),
            },
        ),
        (
            _urn("Ticket", "it-inc-gpu-301"),
            "Ticket",
            {
                "title": _prop(
                    "Ticket bảo trì IT Helpdesk: Cảnh báo nhiệt cụm GPU C6-301"
                ),
                "priority": _prop("P1"),
                "status": _prop("OPEN"),
                "escalated": _prop(True),
                "relatedAsset": _rel(_urn("Asset", "srv-gpu-c6-301")),
                "locatedAt": _rel(_urn("Building", "ictu-c6")),
                "location": _geo(105.8059, 21.5848),
            },
        ),
        (
            _urn("MeetingBooking", "meet-hdkh-2026"),
            "MeetingBooking",
            {
                "title": _prop("Cuộc họp Hội đồng Khoa học & Chuyển đổi số ICTU"),
                "startTime": _prop("2026-11-25T08:30:00Z"),
                "endTime": _prop("2026-11-25T11:30:00Z"),
                "status": _prop("IN_PROGRESS"),
                "heldInRoom": _rel(_urn("Room", "room-c1-202")),
                "usesAsset": _rel(_urn("Asset", "maxhub-c1-202")),
                "location": _geo(105.8066, 21.5851),
            },
        ),
    ]

    return [
        _serialize_entity_record(
            tenant_id=tenant_id,
            entity_id=eid,
            entity_type=etype,
            payload={
                "id": eid,
                "type": etype,
                **body,
                "@context": list(ETSI_NGSI_LD_CONTEXT),
            },
            updated_at=now_iso,
        )
        for eid, etype, body in raw_specs
    ]


_build_campus_seed_entities = _build_ictu_campus_demo_entities


@router.get("/entities", status_code=status.HTTP_200_OK)
async def list_context_entities(
    type: str | None = Query(
        default=None, description="Lọc theo NGSI-LD Entity Type (VD: Room, Asset)"
    ),
    q: str | None = Query(
        default=None, description="Từ khóa tìm kiếm theo tên, mã hoặc URN"
    ),
    bbox: str | None = Query(
        default=None,
        description="Khung bản đồ dạng 'min_lon,min_lat,max_lon,max_lat' (WGS84)",
    ),
    include_demo_fallback: bool = Query(
        default=True,
        description="Hiển thị dữ liệu mẫu Khuôn viên số ICTU khi chưa có dữ liệu thực",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_readonly),
    tenant_context: TenantContext = Depends(get_current_tenant_context),
):
    """Truy vấn danh sách thực thể không gian Digital Twin cô lập theo tenant (#871)."""
    tenant_id_str = str(tenant_context.tenant_id)
    await set_session_tenant(session, tenant_id_str)

    parsed_bbox: tuple[float, float, float, float] | None = None
    if bbox is not None and bbox.strip():
        parsed_bbox = _parse_bbox_param(bbox.strip())

    clean_type = type.strip() if type and type.strip() else None
    clean_q = q.strip() if q and q.strip() else None

    where_clauses = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {
        "tenant_id": tenant_context.tenant_id,
        "limit": limit,
    }
    if clean_type:
        where_clauses.append("type = :entity_type")
        params["entity_type"] = clean_type
    if clean_q:
        where_clauses.append(
            "(entity_id ILIKE :q_like OR type ILIKE :q_like "
            "OR payload::text ILIKE :q_like)"
        )
        params["q_like"] = f"%{clean_q}%"
    if parsed_bbox is not None:
        min_lon, min_lat, max_lon, max_lat = parsed_bbox
        where_clauses.append(
            "location IS NOT NULL AND ST_Intersects("
            "location::geometry, "
            "ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)"
            ")"
        )
        params.update(
            {
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat,
            }
        )

    where_sql = " AND ".join(where_clauses)
    sql = text(f"""
        SELECT
            tenant_id,
            entity_id,
            type,
            payload,
            CASE
                WHEN location IS NOT NULL THEN ST_AsGeoJSON(location::geometry)
                ELSE NULL
            END AS location,
            updated_at
        FROM context.entity_state
        WHERE {where_sql}
        ORDER BY updated_at DESC
        LIMIT :limit;
    """)

    rows: list[Any] = []
    db_unavailable = False
    try:
        res = await session.execute(sql, params)
        rows = list(res.fetchall() or [])
    except Exception as exc:
        logger.warning(
            "Spatial query on context.entity_state unavailable (fallback=%s): %s",
            include_demo_fallback,
            exc,
        )
        db_unavailable = True

    if rows:
        entities = []
        for row in rows:
            raw_payload = row[3]
            if isinstance(raw_payload, str):
                raw_payload = json.loads(raw_payload)
            updated_val = row[5]
            updated_iso = (
                updated_val.isoformat()
                if hasattr(updated_val, "isoformat")
                else (str(updated_val) if updated_val else None)
            )
            entities.append(
                _serialize_entity_record(
                    tenant_id=str(row[0]),
                    entity_id=str(row[1]),
                    entity_type=str(row[2]),
                    payload=raw_payload if isinstance(raw_payload, dict) else {},
                    location_raw=row[4],
                    updated_at=updated_iso,
                )
            )
        return {
            "tenant_id": tenant_id_str,
            "source": "entity_state",
            "center": ICTU_CAMPUS_CENTER,
            "total": len(entities),
            "entities": entities,
        }

    # Kiểm tra xem tenant đã có dữ liệu thật trong entity_state chưa khi có bộ lọc
    tenant_has_existing_data = False
    if not db_unavailable and (clean_type or clean_q or parsed_bbox is not None):
        try:
            exists_res = await session.execute(
                text(
                    "SELECT entity_id FROM context.entity_state "
                    "WHERE tenant_id = :tenant_id LIMIT 1;"
                ),
                {"tenant_id": tenant_context.tenant_id},
            )
            tenant_has_existing_data = len(exists_res.fetchall() or []) > 0
        except Exception:
            tenant_has_existing_data = False

    if not include_demo_fallback or tenant_has_existing_data:
        return {
            "tenant_id": tenant_id_str,
            "source": "entity_state",
            "center": ICTU_CAMPUS_CENTER,
            "total": 0,
            "entities": [],
        }

    demo_entities = _build_ictu_campus_demo_entities(tenant_id_str)
    if clean_type:
        demo_entities = [e for e in demo_entities if e["type"] == clean_type]
    if clean_q:
        q_lower = clean_q.lower()
        demo_entities = [
            e
            for e in demo_entities
            if q_lower in e["name"].lower()
            or q_lower in e["entity_id"].lower()
            or q_lower in e["type"].lower()
            or q_lower in json.dumps(e["payload"], ensure_ascii=False).lower()
        ]
    if parsed_bbox is not None:
        min_lon, min_lat, max_lon, max_lat = parsed_bbox
        demo_entities = [
            e
            for e in demo_entities
            if e["coordinates"] is not None
            and min_lon <= e["coordinates"][0] <= max_lon
            and min_lat <= e["coordinates"][1] <= max_lat
        ]
    demo_entities = demo_entities[:limit]

    return {
        "tenant_id": tenant_id_str,
        "source": "campus_seed_preview",
        "center": ICTU_CAMPUS_CENTER,
        "total": len(demo_entities),
        "entities": demo_entities,
    }


@router.get("/entities/{entity_id:path}")
async def get_context_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_db_readonly),
    tenant_context=Depends(get_current_tenant_context),
):
    """Lấy trạng thái thực thể (Digital Twin) theo ID và cô lập theo tenant (#861, #881)."""
    tenant_id_str = str(tenant_context.tenant_id)
    await set_session_tenant(db, tenant_id_str)

    query = text("""
        SELECT
            tenant_id,
            entity_id,
            type,
            payload,
            CASE
                WHEN location IS NOT NULL THEN ST_AsGeoJSON(location::geometry)
                ELSE NULL
            END AS geojson,
            updated_at
        FROM context.entity_state
        WHERE entity_id = :id AND tenant_id = :tenant_id;
        """)
    row = None
    try:
        res = await db.execute(
            query, {"id": entity_id, "tenant_id": tenant_context.tenant_id}
        )
        row = res.fetchone()
    except Exception as exc:
        logger.warning(
            "Spatial query on context.entity_state unavailable for %s: %s",
            entity_id,
            exc,
        )

    if not row:
        for seed_entity in _build_campus_seed_entities(tenant_id_str):
            if seed_entity["entity_id"] == entity_id:
                return {**seed_entity, "source": "campus_seed_preview"}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity {entity_id} not found in entity_state",
        )

    raw_payload = row[3]
    if isinstance(raw_payload, str):
        raw_payload = json.loads(raw_payload)
    updated_val = row[5]
    updated_iso = (
        updated_val.isoformat()
        if hasattr(updated_val, "isoformat")
        else (str(updated_val) if updated_val else None)
    )
    serialized = _serialize_entity_record(
        tenant_id=str(row[0]),
        entity_id=str(row[1]),
        entity_type=str(row[2]),
        payload=raw_payload if isinstance(raw_payload, dict) else {},
        location_raw=row[4],
        updated_at=updated_iso,
    )
    return {**serialized, "source": "entity_state"}


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
    """Hủy đăng ký subscription trên Orion-LD và cập nhật CSDL (#846, #848, #861, #881)."""
    tenant_id = str(tenant_context.tenant_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with AsyncSessionLocal() as session:
        await set_session_tenant(session, tenant_id)
        exists_res = await session.execute(
            text("""
                SELECT subscription_id
                FROM context.subscriptions
                WHERE subscription_id = :sub_id
                  AND tenant_id = :tenant_id
                  AND status != 'DELETED';
                """),
            {"sub_id": subscription_id, "tenant_id": tenant_uuid},
        )
        if not exists_res.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription {subscription_id} not found for this tenant.",
            )

        http_client = getattr(request.app.state, "http_client", None)
        adapter = OrionAdapter(client=http_client)
        try:
            await adapter.delete_subscription(subscription_id, tenant_id=tenant_id)
        except Exception as e:
            err_status = getattr(e, "status_code", None)
            if err_status == 404 or "404" in str(e) or "not found" in str(e).lower():
                logger.info(
                    "Subscription %s already absent on Orion-LD (404); marking DELETED.",
                    subscription_id,
                )
            else:
                logger.error("Could not delete subscription on Orion: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Context Broker subscription deletion error: {e}",
                ) from e
        finally:
            await adapter.aclose()

        query = text("""
            UPDATE context.subscriptions
            SET status = 'DELETED'
            WHERE subscription_id = :sub_id AND tenant_id = :tenant_id;
            """)
        await session.execute(
            query,
            {"sub_id": subscription_id, "tenant_id": tenant_uuid},
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
