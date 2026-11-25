# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
from typing import Any

from app.core.domain.ports import AbstractDocumentSourcePort, AbstractVectorDBPort

logger = logging.getLogger(__name__)

VALID_PARA_SPACES: tuple[str, ...] = ("projects", "areas", "resources", "archives")

_PARA_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "archives",
        (
            "4. archives",
            ":para:archives",
            "archives",
            "archive",
            "lưu trữ",
            "luu tru",
            "luu-tru",
            "hết hiệu lực",
            "deprecated",
            "hồ sơ cũ",
            "quy định cũ",
        ),
    ),
    (
        "projects",
        (
            "1. projects",
            ":para:projects",
            "projects",
            "project",
            "dự án",
            "du an",
            "du-an",
            "triển khai",
            "sprint",
            "milestone",
            "okr",
        ),
    ),
    (
        "areas",
        (
            "2. areas",
            ":para:areas",
            "areas",
            "area",
            "quy trình",
            "quy trinh",
            "quy-trinh",
            "quy chế",
            "quy định",
            "nội quy",
            "noi-quy",
            "chính sách",
            "sop",
            "sla",
            "phòng ban",
            "vận hành",
        ),
    ),
    (
        "resources",
        (
            "3. resources",
            ":para:resources",
            "resources",
            "resource",
            "tài liệu",
            "tai-lieu",
            "cẩm nang",
            "cam-nang",
            "biểu mẫu",
            "bieu-mau",
            "template",
            "hướng dẫn",
            "handbook",
            "tham khảo",
        ),
    ),
)


def infer_para_space(
    *,
    doc: dict[str, Any] | None = None,
    title: str = "",
    collection_id: str | None = None,
    collection_name: str = "",
    explicit_para_space: str | None = None,
) -> str:
    """Suy luận nhãn P.A.R.A ('projects' | 'areas' | 'resources' | 'archives').

    Ưu tiên: explicit -> metadata -> collection -> title -> mặc định 'resources'.
    """
    doc_dict = doc or {}
    meta_dict = (
        doc_dict.get("metadata") if isinstance(doc_dict.get("metadata"), dict) else {}
    )

    for candidate in (
        explicit_para_space,
        doc_dict.get("para_space"),
        meta_dict.get("para_space"),
    ):
        if candidate is not None:
            norm = str(candidate).strip().lower()
            if norm in VALID_PARA_SPACES:
                return norm

    coll_signals = " ".join(
        str(x).strip().lower()
        for x in (
            collection_name,
            doc_dict.get("collection_name"),
            doc_dict.get("collectionName"),
            collection_id,
            doc_dict.get("collectionId"),
        )
        if x
    )
    if coll_signals:
        for space, keywords in _PARA_KEYWORDS:
            if any(kw in coll_signals for kw in keywords):
                return space

    title_signal = str(title or doc_dict.get("title") or "").strip().lower()
    if title_signal:
        for space, keywords in _PARA_KEYWORDS:
            if any(kw in title_signal for kw in keywords):
                return space

    return "resources"


class RAGIngestionUseCase:
    """
    Use case cho RAG Document Ingestion.
    Luồng: Outline -> Chunking -> Embedding -> Qdrant.
    Cron: Chạy 2h sáng hàng đêm (được cấu hình ở scheduler/router).
    """

    def __init__(
        self,
        document_source_port: AbstractDocumentSourcePort,
        vector_db_port: AbstractVectorDBPort,
    ):
        self.document_source_port = document_source_port
        self.vector_db_port = vector_db_port
        self.max_chars_per_chunk = 2000  # Ước lượng ~512 tokens

    def _chunk_text(self, text: str) -> list[str]:
        """
        Chia text thành các chunks theo paragraph (\n\n) hoặc (\n).
        Đảm bảo max_chars_per_chunk.
        """
        if not text:
            return []

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for p in paragraphs:
            # Fallback split by \n if paragraph is still too long
            if len(p) > self.max_chars_per_chunk:
                lines = p.split("\n")
                for line in lines:
                    if (
                        len(current_chunk) + len(line) > self.max_chars_per_chunk
                        and current_chunk
                    ):
                        chunks.append(current_chunk.strip())
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line if current_chunk else line
            else:
                if (
                    len(current_chunk) + len(p) > self.max_chars_per_chunk
                    and current_chunk
                ):
                    chunks.append(current_chunk.strip())
                    current_chunk = p
                else:
                    current_chunk += "\n\n" + p if current_chunk else p

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _infer_para_space(
        self,
        *,
        doc: dict[str, Any] | None = None,
        collection_id: str | None = None,
        explicit_para_space: str | None = None,
    ) -> str:
        return infer_para_space(
            doc=doc,
            collection_id=collection_id,
            explicit_para_space=explicit_para_space,
        )

    async def execute(
        self,
        tenant_id: str,
        collection_id: str | None = None,
        para_space: str | None = None,
    ) -> dict[str, Any]:
        """
        Thực thi quy trình RAG Ingestion cho một tenant cụ thể.
        Bắt buộc lọc theo collection của tenant (#734) và gắn nhãn P.A.R.A (#875).
        """
        logger.info(
            "Starting RAG Ingestion for tenant: %s, collection: %s",
            tenant_id,
            collection_id,
        )

        try:
            # 1. Fetch documents từ Outline có filter collection (#734)
            target_collection = collection_id or tenant_id
            try:
                documents = await self.document_source_port.list_documents(
                    collection_id=target_collection
                )
            except TypeError:
                documents = await self.document_source_port.list_documents()

            if target_collection:
                documents = [
                    d
                    for d in documents
                    if str(d.get("collectionId")) == str(target_collection)
                ]

            total_docs = len(documents)
            all_chunks: list[str] = []
            all_metadatas: list[dict[str, Any]] = []

            # 2. Chunking & gắn nhãn P.A.R.A
            for doc in documents:
                title = doc.get("title", "Untitled")
                source_url = doc.get("source_url", "")
                text = doc.get("text", "")

                chunks = self._chunk_text(text)

                if not chunks:
                    continue

                doc_para_space = self._infer_para_space(
                    doc=doc,
                    collection_id=target_collection,
                    explicit_para_space=para_space,
                )

                metadatas = [
                    {
                        "doc_title": title,
                        "source_url": source_url,
                        "document_id": doc.get("id"),
                        "chunk_index": idx,
                        "para_space": doc_para_space,
                    }
                    for idx, _ in enumerate(chunks)
                ]
                all_chunks.extend(chunks)
                all_metadatas.extend(metadatas)

            total_chunks = len(all_chunks)

            # 3. Upsert / Replace Qdrant
            # QdrantAdapter sử dụng FastEmbed (Hybrid Search Dense+BM25) bên dưới,
            # thay thế cho việc gọi thẳng OpenAI API, tối ưu cho RRF.
            replace_fn = getattr(self.vector_db_port, "replace_tenant_vectors", None)
            if callable(replace_fn):
                await replace_fn(
                    tenant_id=tenant_id, chunks=all_chunks, metadatas=all_metadatas
                )
            elif all_chunks:
                await self.vector_db_port.upsert_vectors(
                    tenant_id=tenant_id, chunks=all_chunks, metadatas=all_metadatas
                )

            logger.info(
                "RAG Ingestion completed: %s docs, %s chunks.", total_docs, total_chunks
            )
            return {
                "status": "success",
                "processed_documents": total_docs,
                "upserted_chunks": total_chunks,
            }
        except Exception as e:
            logger.error("RAG Ingestion failed: %s", e)
            return {"status": "failed", "error": str(e)}
