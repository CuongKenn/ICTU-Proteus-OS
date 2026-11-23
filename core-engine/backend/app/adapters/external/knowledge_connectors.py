# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Knowledge Connector Framework — đồng bộ tri thức từ nguồn ngoài vào Proteus.
# Connector chỉ CHỊU TRÁCH NHIỆM ĐỌC + chuẩn hoá dữ liệu; việc ghi vào nguồn
# đích (Outline) do use case/publisher lo. Đăng ký connector mới bằng
# `register_connector()` — framework mở rộng không cần sửa core.

import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.domain.ports import AbstractKnowledgeConnectorPort

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    pass


# ─── Registry ────────────────────────────────────────────────────────────

_CONNECTOR_REGISTRY: dict[str, type[AbstractKnowledgeConnectorPort]] = {}


def register_connector(cls: type[AbstractKnowledgeConnectorPort]) -> type:
    """Decorator đăng ký connector theo `name`."""
    name = getattr(cls, "name", None) or cls.__name__.lower()
    _CONNECTOR_REGISTRY[name] = cls
    return cls


def get_connector(name: str) -> type[AbstractKnowledgeConnectorPort] | None:
    return _CONNECTOR_REGISTRY.get(name)


def list_connectors() -> list[str]:
    return sorted(_CONNECTOR_REGISTRY.keys())


# ─── Connector mẫu: HTTP JSON Feed ───────────────────────────────────────
# Đọc 1 URL trả JSON dạng {"documents": [{"title","text","id","url"}]} hoặc
# list trực tiếp. Dùng cho nguồn nội bộ/đối tác đã expose API đơn giản.


def _validate_public_http_url(url: str) -> None:
    """Chặn SSRF: chỉ cho phép http/https tới IP/host công khai (#787)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ConnectorError("http_feed chỉ hỗ trợ URL http/https hợp lệ.")

    hostname = parsed.hostname.strip().lower()
    if hostname in ("localhost", "ip6-localhost"):
        raise ConnectorError("http_feed từ chối địa chỉ nội bộ (SSRF protection).")

    try:
        infos = socket.getaddrinfo(
            hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except socket.gaierror as e:
        raise ConnectorError(f"Không phân giải được hostname '{hostname}': {e}") from e

    for info in infos:
        ip_str = info[4][0].split("%")[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError as e:
            raise ConnectorError(f"Địa chỉ IP không hợp lệ: {ip_str}") from e
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            raise ConnectorError(
                f"http_feed từ chối IP nội bộ/riêng tư {ip_obj} (SSRF protection)."
            )


@register_connector
class HttpFeedConnector(AbstractKnowledgeConnectorPort):
    """Connector mẫu: kéo documents từ 1 HTTP JSON endpoint."""

    name = "http_feed"

    async def fetch_documents(self, *, config: dict[str, Any]) -> list[dict[str, Any]]:
        url = (config or {}).get("url")
        if not url or not isinstance(url, str):
            raise ConnectorError("http_feed cần config.url")
        _validate_public_http_url(url)

        headers = (config or {}).get("headers") or {}
        raw_timeout = (config or {}).get("timeout", 15.0)
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError) as e:
            raise ConnectorError("http_feed config.timeout không hợp lệ.") from e
        if not (1.0 <= timeout <= 30.0):
            timeout = min(max(timeout, 1.0), 30.0)

        async with httpx.AsyncClient(follow_redirects=False) as client:
            try:
                resp = await client.get(url, headers=headers, timeout=timeout)
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError as e:
                raise ConnectorError(f"http_feed fetch thất bại: {e}") from e
            except ValueError as e:
                raise ConnectorError(f"http_feed không trả JSON hợp lệ: {e}") from e

        raw_items = (
            payload.get("documents")
            if isinstance(payload, dict)
            else payload if isinstance(payload, list) else []
        )
        documents: list[dict[str, Any]] = []
        for item in raw_items or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            text = str(item.get("text") or item.get("content") or "").strip()
            if not title or not text:
                continue
            documents.append(
                {
                    "title": title,
                    "text": text,
                    "external_id": item.get("id") or item.get("external_id"),
                    "source_url": item.get("url") or item.get("source_url"),
                }
            )
        logger.info("http_feed: fetched %s documents", len(documents))
        return documents
