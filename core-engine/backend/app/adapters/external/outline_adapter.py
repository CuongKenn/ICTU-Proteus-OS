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


PARA_SPACE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "key": "projects",
        "name": "1. Projects",
        "description": "Dự án & mục tiêu ngắn hạn đang triển khai",
    },
    {
        "key": "areas",
        "name": "2. Areas",
        "description": "Quy trình chuẩn & trách nhiệm phòng ban thường trực",
    },
    {
        "key": "resources",
        "name": "3. Resources",
        "description": "Tài liệu tham khảo, biểu mẫu & cẩm nang",
    },
    {
        "key": "archives",
        "name": "4. Archives",
        "description": "Hồ sơ dự án & quy định cũ lưu trữ",
    },
)


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

    async def create_collection(
        self, name: str, description: str = ""
    ) -> dict[str, Any]:
        """Tạo một collection mới trên Outline Wiki (`POST /api/collections.create`)."""
        if not self.api_key:
            raise OutlineAdapterError("OUTLINE_API_KEY chưa cấu hình.")
        clean_name = (name or "").strip()
        if not clean_name:
            raise OutlineAdapterError("Tên collection không được để trống.")
        payload: dict[str, Any] = {"name": clean_name}
        if description:
            payload["description"] = description
        data = (await self._post("/api/collections.create", payload)).get("data") or {}
        raw_url = data.get("url", "")
        full_url = (
            raw_url
            if raw_url.startswith("http")
            else (f"{self.public_base_url}{raw_url}" if raw_url else "")
        )
        return {
            "id": data.get("id"),
            "name": data.get("name", clean_name),
            "description": data.get("description", description),
            "url": full_url,
        }

    def _build_local_para_spaces(
        self, tenant_id: str, tenant_name: str = ""
    ) -> list[dict[str, Any]]:
        """Trả danh sách 4 không gian P.A.R.A cục bộ khi Outline chưa cấu hình."""
        tid = str(tenant_id).strip()
        org_suffix = (
            f" ({tenant_name.strip()})" if tenant_name and tenant_name.strip() else ""
        )
        return [
            {
                "key": spec["key"],
                "name": spec["name"],
                "description": f"{spec['description']}{org_suffix}",
                "collection_id": f"{tid}:para:{spec['key']}",
                "tenant_id": tid,
                "mode": "local_para",
                "url": "",
            }
            for spec in PARA_SPACE_DEFINITIONS
        ]

    @staticmethod
    def _match_tenant_para_collection(
        collections: list[dict[str, Any]],
        *,
        tenant_id: str,
        space_name: str,
    ) -> dict[str, Any] | None:
        tenant_tag = f"[tenant:{tenant_id}]"
        # Ưu tiên khớp chính xác tag tenant trong description
        for coll in collections:
            desc = str(coll.get("description") or "")
            cname = str(coll.get("name") or "").strip()
            if tenant_tag in desc and cname.startswith(space_name):
                return coll
        # Nếu collection không mang tag của tenant khác và trùng tên chuẩn P.A.R.A
        for coll in collections:
            desc = str(coll.get("description") or "")
            cname = str(coll.get("name") or "").strip()
            if "[tenant:" not in desc and cname == space_name:
                return coll
        return None

    async def get_para_spaces(
        self, tenant_id: str, tenant_name: str = ""
    ) -> list[dict[str, Any]]:
        """Lấy trạng thái 4 không gian P.A.R.A hiện tại của tenant."""
        tid = str(tenant_id).strip()
        if not self.api_key:
            return self._build_local_para_spaces(tid, tenant_name)
        try:
            existing = await self.list_collections()
        except Exception as exc:
            logger.warning(
                "Outline unavailable when listing P.A.R.A spaces for tenant %s: %s",
                tid,
                exc,
            )
            return self._build_local_para_spaces(tid, tenant_name)

        matched_spaces: list[dict[str, Any]] = []
        for spec in PARA_SPACE_DEFINITIONS:
            found = self._match_tenant_para_collection(
                existing, tenant_id=tid, space_name=spec["name"]
            )
            if not found or not found.get("id"):
                return self._build_local_para_spaces(tid, tenant_name)
            raw_url = str(found.get("url") or "")
            full_url = (
                raw_url
                if raw_url.startswith("http")
                else (f"{self.public_base_url}{raw_url}" if raw_url else "")
            )
            matched_spaces.append(
                {
                    "key": spec["key"],
                    "name": spec["name"],
                    "description": spec["description"],
                    "collection_id": str(found["id"]),
                    "tenant_id": tid,
                    "mode": "outline",
                    "url": full_url,
                }
            )
        return matched_spaces

    async def bootstrap_para_collections(
        self, tenant_id: str, tenant_name: str = ""
    ) -> list[dict[str, Any]]:
        """Khởi tạo idempotent 4 không gian chuẩn P.A.R.A riêng cho tenant (#875).

        Nếu chưa cấu hình OUTLINE_API_KEY hoặc Outline không phản hồi, trả fallback
        `local_para` (`collection_id = "{tenant_id}:para:{key}"`) an toàn 100%.
        """
        tid = str(tenant_id).strip()
        if not self.api_key:
            return self._build_local_para_spaces(tid, tenant_name)

        try:
            existing = await self.list_collections()
            org_label = (
                f" — {tenant_name.strip()}"
                if tenant_name and tenant_name.strip()
                else ""
            )
            tenant_tag = f"[tenant:{tid}]"
            results: list[dict[str, Any]] = []

            for spec in PARA_SPACE_DEFINITIONS:
                found = self._match_tenant_para_collection(
                    existing, tenant_id=tid, space_name=spec["name"]
                )
                if found and found.get("id"):
                    coll_id = str(found["id"])
                    raw_url = str(found.get("url") or "")
                    full_url = (
                        raw_url
                        if raw_url.startswith("http")
                        else (f"{self.public_base_url}{raw_url}" if raw_url else "")
                    )
                else:
                    coll_name = (
                        f"{spec['name']} ({tenant_name.strip()})"
                        if tenant_name and tenant_name.strip()
                        else spec["name"]
                    )
                    coll_desc = f"{spec['description']}{org_label} {tenant_tag}"
                    created = await self.create_collection(
                        name=coll_name,
                        description=coll_desc,
                    )
                    coll_id = str(created.get("id") or f"{tid}:para:{spec['key']}")
                    full_url = str(created.get("url") or "")

                results.append(
                    {
                        "key": spec["key"],
                        "name": spec["name"],
                        "description": spec["description"],
                        "collection_id": coll_id,
                        "tenant_id": tid,
                        "mode": "outline",
                        "url": full_url,
                    }
                )
            return results
        except Exception as exc:
            logger.warning(
                "Outline P.A.R.A bootstrap fallback to local_para for tenant %s: %s",
                tid,
                exc,
            )
            return self._build_local_para_spaces(tid, tenant_name)

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

        coll = (collection_id or "").strip()
        if not coll:
            raise OutlineAdapterError(
                "collection_id là bắt buộc để đảm bảo cô lập dữ liệu giữa các tổ chức."
            )

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
                        f"{self.public_base_url}/doc/{url_id}" if url_id else ""
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
                        f"{self.public_base_url}/doc/{url_id}" if url_id else ""
                    )
                return data
            except httpx.HTTPError as e:
                logger.error("Outline API error: %s", e)
                raise OutlineAdapterError(f"Failed to fetch documents: {str(e)}") from e
