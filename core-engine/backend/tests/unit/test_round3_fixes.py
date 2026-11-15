# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.external.knowledge_connectors import (
    ConnectorError,
    HttpFeedConnector,
)
from app.entrypoints.routers.embed import _verify_tenant_dashboard_ownership


@pytest.mark.asyncio
async def test_http_feed_connector_blocks_ssrf_private_and_loopback():
    connector = HttpFeedConnector()
    with pytest.raises(ConnectorError, match="SSRF|nội bộ|riêng tư"):
        await connector.fetch_documents(config={"url": "http://127.0.0.1:8000/secret"})

    with pytest.raises(ConnectorError, match="SSRF|nội bộ|riêng tư"):
        await connector.fetch_documents(
            config={"url": "http://169.254.169.254/latest/meta-data/"}
        )

    with pytest.raises(ConnectorError, match="http/https"):
        await connector.fetch_documents(config={"url": "file:///etc/passwd"})


@pytest.mark.asyncio
async def test_embed_ownership_fails_closed_on_empty_or_error():
    tenant_id = uuid.uuid4()

    empty_db = AsyncMock()
    empty_res = MagicMock()
    empty_res.scalars.return_value.all.return_value = []
    empty_db.execute.return_value = empty_res
    assert await _verify_tenant_dashboard_ownership(empty_db, tenant_id, 42) is False

    err_db = AsyncMock()
    err_db.execute.side_effect = RuntimeError("db down")
    assert await _verify_tenant_dashboard_ownership(err_db, tenant_id, 42) is False

