# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression unit tests cho Round 6 (#800)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose.exceptions import JWTClaimsError

from app.adapters.external.keycloak_adapter import KeycloakAdapter
from app.adapters.external.outline_adapter import OutlineAdapter
from app.infrastructure.config import settings


@pytest.mark.asyncio
async def test_keycloak_adapter_accepts_public_and_internal_issuers(monkeypatch):
    monkeypatch.setattr(settings, "KEYCLOAK_URL", "http://keycloak:8080")
    monkeypatch.setattr(settings, "KEYCLOAK_PUBLIC_URL", "https://auth.example.com")
    monkeypatch.setattr(settings, "KEYCLOAK_REALM", "proteus")
    monkeypatch.setattr(settings, "KEYCLOAK_CLIENT_ID", "proteus-bff")

    adapter = KeycloakAdapter()
    adapter._get_jwks = AsyncMock(return_value={"keys": [{"kid": "k1"}]})

    with (
        patch(
            "app.adapters.external.keycloak_adapter.jwt.get_unverified_header",
            return_value={"kid": "k1"},
        ),
        patch(
            "app.adapters.external.keycloak_adapter.jwt.decode",
            return_value={
                "iss": "https://auth.example.com/realms/proteus",
                "azp": "proteus-bff",
                "sub": "u-1",
            },
        ),
    ):
        payload = await adapter.verify_and_decode_token("fake.jwt.token")
    assert payload["sub"] == "u-1"

    with (
        patch(
            "app.adapters.external.keycloak_adapter.jwt.get_unverified_header",
            return_value={"kid": "k1"},
        ),
        patch(
            "app.adapters.external.keycloak_adapter.jwt.decode",
            return_value={
                "iss": "https://evil.example.com/realms/proteus",
                "azp": "proteus-bff",
                "sub": "u-1",
            },
        ),
    ):
        with pytest.raises(JWTClaimsError, match="Invalid issuer"):
            await adapter.verify_and_decode_token("fake.jwt.token")


@pytest.mark.asyncio
async def test_outline_adapter_list_documents_uses_public_base_url(monkeypatch):
    monkeypatch.setattr(settings, "OUTLINE_URL", "http://outline:3000")
    monkeypatch.setattr(settings, "OUTLINE_PUBLIC_URL", "https://wiki.example.com")
    monkeypatch.setattr(settings, "OUTLINE_API_KEY", "test-key")

    adapter = OutlineAdapter()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"id": "d1", "title": "Guide", "urlId": "guide-abc"}]
    }
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch(
        "app.adapters.external.outline_adapter.httpx.AsyncClient",
        return_value=mock_client,
    ):
        docs = await adapter.list_documents()

    assert docs[0]["source_url"] == "https://wiki.example.com/doc/guide-abc"
