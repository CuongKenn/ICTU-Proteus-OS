# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Orion-LD Context Broker Adapter.

Giao tiếp với FIWARE Orion-LD Context Broker theo chuẩn ETSI NGSI-LD v1.6+.
Tham chiếu: ADR-003, Issue #831 [L3-304], ETSI GS CIM 009.
"""

import logging
from typing import Any

import httpx

from app.core.domain.ports import IContextBrokerPort
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"


class OrionAdapterError(Exception):
    """Exception class cho các lỗi giao tiếp với Orion Context Broker."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OrionAdapter(IContextBrokerPort):
    """Adapter hiện thực hoá IContextBrokerPort cho FIWARE Orion-LD."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or settings.ORION_URL).rstrip("/")
        self._client = client
        self._timeout = timeout

    async def aclose(self) -> None:
        """Đóng httpx client nếu do adapter tự tạo."""
        if self._client is not None:
            await self._client.aclose()

    def _get_headers(self, tenant_id: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/ld+json",
            "Accept": "application/ld+json",
        }
        if tenant_id:
            # FIWARE standard multi-tenancy header
            headers["NGSILD-Tenant"] = str(tenant_id)
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: Any = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            if self._client is not None:
                resp = await self._client.request(
                    method, url, headers=headers, json=json_data, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.request(
                        method,
                        url,
                        headers=headers,
                        json=json_data,
                        timeout=self._timeout,
                    )
            return resp
        except httpx.RequestError as exc:
            logger.error(
                "HTTP request to Orion-LD failed: %s %s - %s", method, url, exc
            )
            raise OrionAdapterError(
                f"Network error communicating with Orion-LD: {exc}"
            ) from exc

    async def upsert_entity(
        self,
        entity_id: str,
        entity_type: str,
        payload: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> bool:
        """Upsert thực thể NGSI-LD (idempotent)."""
        headers = self._get_headers(tenant_id)

        # Chuẩn hoá payload NGSI-LD
        ngsi_payload = dict(payload)
        ngsi_payload["id"] = entity_id
        ngsi_payload["type"] = entity_type
        if "@context" not in ngsi_payload:
            ngsi_payload["@context"] = DEFAULT_CONTEXT

        # 1. Thử tạo mới qua POST /ngsi-ld/v1/entities
        resp = await self._request(
            "POST", "/ngsi-ld/v1/entities", headers=headers, json_data=ngsi_payload
        )

        if resp.status_code in (201, 204):
            logger.debug("Created NGSI-LD entity %s successfully", entity_id)
            return True

        if resp.status_code == 409:
            # Thực thể đã tồn tại -> cập nhật thuộc tính qua PATCH /attrs
            # Loại bỏ 'id', 'type', '@context' khi update attrs
            attrs_to_update = {
                k: v
                for k, v in ngsi_payload.items()
                if k not in ("id", "type", "@context")
            }
            if not attrs_to_update:
                return True

            patch_headers = dict(headers)
            # Thêm Link header cho context nếu dùng PATCH application/json
            patch_resp = await self._request(
                "POST",
                f"/ngsi-ld/v1/entities/{entity_id}/attrs",
                headers=patch_headers,
                json_data=attrs_to_update,
            )
            if patch_resp.status_code in (200, 204):
                logger.debug(
                    "Updated NGSI-LD entity %s attributes successfully", entity_id
                )
                return True

            logger.warning(
                "Failed to update attributes for %s, status=%d, body=%s",
                entity_id,
                patch_resp.status_code,
                patch_resp.text,
            )
            raise OrionAdapterError(
                f"Failed to update entity attributes: {patch_resp.text}",
                status_code=patch_resp.status_code,
            )

        logger.error(
            "Failed to upsert entity %s, status=%d, body=%s",
            entity_id,
            resp.status_code,
            resp.text,
        )
        raise OrionAdapterError(
            f"Failed to create entity: {resp.text}", status_code=resp.status_code
        )

    async def get_entity(
        self,
        entity_id: str,
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Lấy thông tin thực thể theo ID."""
        headers = self._get_headers(tenant_id)
        resp = await self._request(
            "GET", f"/ngsi-ld/v1/entities/{entity_id}", headers=headers
        )

        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            return resp.json()

        raise OrionAdapterError(
            f"Failed to get entity {entity_id}: {resp.text}",
            status_code=resp.status_code,
        )

    async def delete_entity(
        self,
        entity_id: str,
        *,
        tenant_id: str | None = None,
    ) -> bool:
        """Xoá một thực thể NGSI-LD (idempotent)."""
        headers = self._get_headers(tenant_id)
        resp = await self._request(
            "DELETE", f"/ngsi-ld/v1/entities/{entity_id}", headers=headers
        )

        if resp.status_code in (204, 404):
            return True

        raise OrionAdapterError(
            f"Failed to delete entity {entity_id}: {resp.text}",
            status_code=resp.status_code,
        )

    async def create_subscription(
        self,
        subscription_payload: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> str:
        """Đăng ký subscription theo dõi thay đổi thực thể."""
        headers = self._get_headers(tenant_id)
        payload = dict(subscription_payload)
        if "@context" not in payload:
            payload["@context"] = DEFAULT_CONTEXT

        resp = await self._request(
            "POST", "/ngsi-ld/v1/subscriptions", headers=headers, json_data=payload
        )

        if resp.status_code == 201:
            loc = resp.headers.get("Location")
            if loc:
                return loc.rstrip("/").split("/")[-1]
            return payload.get("id", "sub-created")

        raise OrionAdapterError(
            f"Failed to create subscription: {resp.text}",
            status_code=resp.status_code,
        )

    async def delete_subscription(
        self,
        subscription_id: str,
        *,
        tenant_id: str | None = None,
    ) -> bool:
        """Huỷ subscription theo ID (idempotent)."""
        headers = self._get_headers(tenant_id)
        resp = await self._request(
            "DELETE", f"/ngsi-ld/v1/subscriptions/{subscription_id}", headers=headers
        )

        if resp.status_code in (204, 404):
            return True

        raise OrionAdapterError(
            f"Failed to delete subscription {subscription_id}: {resp.text}",
            status_code=resp.status_code,
        )
