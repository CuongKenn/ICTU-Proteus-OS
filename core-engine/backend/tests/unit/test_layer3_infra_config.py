# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Layer 3 infrastructure configuration and worker skeleton."""

import pytest
import yaml
from pathlib import Path

from app.infrastructure.config import Settings
from app.workers.context_sync_worker import ContextSyncWorker


def test_layer3_settings_defaults():
    settings = Settings()
    assert settings.LAYER3_ENABLED is False
    assert settings.ORION_URL == "http://localhost:1026"
    assert settings.MONGO_URL == "mongodb://localhost:27017"
    assert settings.HASURA_GRAPHQL_URL == "http://localhost:8080/v1/graphql"
    assert settings.CONTEXT_SYNC_BATCH_SIZE == 100
    assert settings.CONTEXT_SYNC_POLL_INTERVAL == 1.0
    assert settings.CONTEXT_SYNC_MAX_RETRIES == 5
    assert settings.CONTEXT_SYNC_STREAM_NAME == "stream:context:events"
    assert settings.CONTEXT_SYNC_STREAM_KEY == "stream:context:events"


def test_layer3_docker_compose_services():
    compose_path = Path(__file__).parents[4] / "deploy" / "docker-compose.yml"
    assert compose_path.exists()

    with open(compose_path, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})

    # Check postgres image uses postgis
    assert "postgres" in services
    assert services["postgres"]["image"] == "postgis/postgis:16-3.4"

    # Check mongo service
    assert "mongo" in services
    assert "layer3" in services["mongo"].get("profiles", [])
    assert services["mongo"]["image"] == "mongo:6.0"

    # Check orion-ld service
    assert "orion-ld" in services
    assert "layer3" in services["orion-ld"].get("profiles", [])
    assert "mongo" in services["orion-ld"].get("depends_on", {})
    assert services["orion-ld"]["image"] == "fiware/orion-ld:1.6.0"

    # Check hasura service
    assert "hasura" in services
    assert "layer3" in services["hasura"].get("profiles", [])
    assert "postgres" in services["hasura"].get("depends_on", {})

    # Check context-sync-worker service
    assert "context-sync-worker" in services
    assert "layer3" in services["context-sync-worker"].get("profiles", [])
    depends = services["context-sync-worker"].get("depends_on", {})
    assert "postgres" in depends
    assert "redis" in depends
    assert "orion-ld" in depends

    # Check volume
    volumes = compose.get("volumes", {})
    assert "mongo-data" in volumes


@pytest.mark.asyncio
async def test_context_sync_worker_skeleton():
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock

    mock_session = AsyncMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_session.execute.return_value = mock_cursor

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    worker = ContextSyncWorker(session_factory=mock_session_factory)
    assert worker.batch_size == 100
    assert worker.poll_interval == 1.0
    assert worker.is_running is False

    batch_processed = await worker.process_batch()
    assert batch_processed == 0

    await worker.stop()
    assert worker.is_running is False
