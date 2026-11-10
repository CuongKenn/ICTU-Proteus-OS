# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPError, Request, Response

from app.adapters.external.keycloak_adapter import KeycloakAdapter, KeycloakAdapterError
from app.adapters.external.local_manifest_parser import LocalManifestParser
from app.adapters.external.qdrant_adapter import QdrantAdapter
from app.adapters.external.redis_event_bus import RedisEventBusPublisher
from app.adapters.repositories.plugin_repo import SQLAlchemyPluginRepository
from app.ai.plugin_synthesizer import PluginSynthesizer
from app.core.use_cases.dsl_dry_run import DSLDryRunEngine


@pytest.mark.asyncio
async def test_keycloak_force_refresh_cooldown():
    """Verify that _force_refresh_jwks enforces cooldown."""
    mock_client = AsyncMock()
    mock_client.get.return_value = Response(
        200, json={"keys": [{"kid": "test-kid"}]}, request=Request("GET", "http://test")
    )

    adapter = KeycloakAdapter(client=mock_client)
    res1 = await adapter._force_refresh_jwks()
    assert res1 == {"keys": [{"kid": "test-kid"}]}
    assert mock_client.get.call_count == 1

    # Immediate second call should hit cooldown and not call client.get again
    res2 = await adapter._force_refresh_jwks()
    assert res2 == {"keys": [{"kid": "test-kid"}]}
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_keycloak_refresh_jwks_http_error():
    """Verify that _get_jwks raises KeycloakAdapterError on httpx.HTTPError when cache is empty."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = HTTPError("Connection refused")

    adapter = KeycloakAdapter(client=mock_client)
    with pytest.raises(KeycloakAdapterError, match="Cannot reach Keycloak to fetch JWKS"):
        await adapter._get_jwks()


@pytest.mark.asyncio
async def test_qdrant_does_not_recreate_existing_collection():
    """Verify that _ensure_collection_exists does not recreate collection if it already exists."""
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    adapter = QdrantAdapter(qdrant_client=mock_client)
    await adapter._ensure_collection_exists()

    mock_client.collection_exists.assert_called_once_with("knowledge_base")
    mock_client.recreate_collection.assert_not_called()
    assert adapter._collection_ensured is True


@pytest.mark.asyncio
async def test_plugin_repo_list_marketplace_with_category():
    """Verify that list_marketplace applies category filter in SQL query."""
    mock_session = AsyncMock()
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1
    mock_rows_res = MagicMock()
    mock_rows_res.mappings.return_value = []

    mock_session.execute.side_effect = [mock_count_res, mock_rows_res]

    repo = SQLAlchemyPluginRepository(session=mock_session)
    plugins, total = await repo.list_marketplace(limit=10, offset=0, category="HR")

    assert mock_session.execute.call_count == 2
    # Verify both queries included category parameter
    for call in mock_session.execute.call_args_list:
        params = call[0][1]
        assert params.get("category") == "HR"


@pytest.mark.asyncio
@patch("app.ai.plugin_synthesizer.settings.LLM_BASE_URL", new="")
async def test_plugin_synthesizer_has_mandatory_fields(tmp_path):
    """Verify that synthesized manifest contains display_name, author, license, compatibility."""
    import yaml

    synthesizer = PluginSynthesizer()
    synthesizer._plugins_dir = tmp_path

    plugin_name = await synthesizer.synthesize("tạo plugin bệnh viện")
    manifest_file = tmp_path / plugin_name / "manifest.yaml"
    assert manifest_file.exists()

    manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    assert "display_name" in manifest_data
    assert "author" in manifest_data
    assert "license" in manifest_data
    assert "compatibility" in manifest_data
    assert "database" in manifest_data


def test_local_manifest_parser_module_fallback():
    """Verify that parser finds 'hr-module' when given 'hr'."""
    parser = LocalManifestParser()
    manifest = parser.parse("hr")
    assert manifest.name == "hr-module"
