# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
from typing import Any

import httpx

from app.core.domain.ports import AbstractDocumentSourcePort
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)


class OutlineAdapterError(Exception):
    pass


class OutlineAdapter(AbstractDocumentSourcePort):
    """
    Adapter để tương tác với Outline API.
    Sử dụng để lấy danh sách tài liệu cho RAG Ingestion Pipeline và publish tài liệu.
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self.base_url = settings.OUTLINE_URL.rstrip("/")
        self.public_base_url = getattr(settings, "outline_public_base", self.base_url)
        self.api_key = settings.OUTLINE_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST tới Outline API, trả JSON gốc (đã raise nếu lỗi)."""
        url = f"{self.base_url}{path}"
        try:
            if self._client is not None:
                response = await self._client.post(
                    url, headers=self.headers, json=payload, timeout=15.0
                )
                response.raise_for_status()
                return response.json()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=15.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("Outline API error (%s): %s", path, e)
            raise OutlineAdapterError(f"Failed to call {path}: {str(e)}") from e

    async def list_collections(self) -> list[dict[str, Any]]:
        """Lấy danh sách collections (để chọn nơi publish tài liệu)."""
        if not self.api_key:
            return []
        data = await self._post("/api/collections.list", {"limit": 100})
        return data.get("data") or []

    async def publish_document(
        self,
        title: str,
        text: str,
        *,
        collection_id: str | None = None,
        parent_document_id: str | None = None,
        publish: bool = True,
    ) -> dict[str, Any]:
        """Tạo document mới trên Outline (documents.create)."""
        if not self.api_key:
            raise OutlineAdapterError("OUTLINE_API_KEY chưa cấu hình.")

        coll = collection_id
        if not coll:
            colls = await self._post("/api/collections.list", {"limit": 1})
            data = colls.get("data") or []
            if not data:
                raise OutlineAdapterError(
                    "Outline chưa có collection nào — tạo collection trước khi publish."
                )
            coll = data[0].get("id")

        payload: dict[str, Any] = {
            "title": title,
            "text": text,
            "collectionId": coll,
            "publish": publish,
        }
        if parent_document_id:
            payload["parentDocumentId"] = parent_document_id

        data = (await self._post("/api/documents.create", payload)).get("data") or {}
        url_id = data.get("urlId", "")
        return {
            "id": data.get("id"),
            "url": f"{self.public_base_url}/doc/{url_id}" if url_id else "",
            "title": data.get("title", title),
        }

    async def list_documents(
        self, collection_id: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Lấy danh sách documents từ Outline.
        """
        if not self.api_key:
            logger.warning("OUTLINE_API_KEY is not set. Skipping document fetch.")
            return []

        url = f"{self.base_url}/api/documents.list"
        payload = {"offset": offset, "limit": limit}
        if collection_id:
            payload["collectionId"] = collection_id

        if self._client is not None:
            try:
                response = await self._client.post(
                    url, headers=self.headers, json=payload, timeout=10.0
                )
                response.raise_for_status()
                data = response.json().get("data", [])
                for doc in data:
                    url_id = doc.get("urlId", "")
                    doc["source_url"] = (
                        f"{self.base_url}/doc/{url_id}" if url_id else ""
                    )
                return data
            except httpx.HTTPError as e:
                logger.error("Outline API error: %s", e)
                raise OutlineAdapterError(f"Failed to fetch documents: {str(e)}") from e

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=10.0
                )
                response.raise_for_status()
                data = response.json().get("data", [])
                for doc in data:
                    url_id = doc.get("urlId", "")
                    doc["source_url"] = (
                        f"{self.base_url}/doc/{url_id}" if url_id else ""
                    )
                return data
            except httpx.HTTPError as e:
                logger.error("Outline API error: %s", e)
                raise OutlineAdapterError(f"Failed to fetch documents: {str(e)}") from e
