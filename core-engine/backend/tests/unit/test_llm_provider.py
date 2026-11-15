# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests cho LocalLLMProvider (app/ai/llm_provider.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.ai.llm_provider import LocalLLMProvider


def _mock_async_client(post_side_effect=None, post_return=None, stream_lines=None):
    client = MagicMock()
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    elif post_return is not None:
        client.post = AsyncMock(return_value=post_return)

    if stream_lines is not None:
        stream_resp = MagicMock()
        stream_resp.raise_for_status = MagicMock()

        async def _aiter_lines():
            for line in stream_lines:
                yield line

        stream_resp.aiter_lines = _aiter_lines
        stream_ctx = AsyncMock()
        stream_ctx.__aenter__.return_value = stream_resp
        stream_ctx.__aexit__.return_value = False
        client.stream.return_value = stream_ctx

    client_ctx = AsyncMock()
    client_ctx.__aenter__.return_value = client
    client_ctx.__aexit__.return_value = False
    return client_ctx, client


@pytest.mark.asyncio
async def test_local_llm_provider_ainvoke_success():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": "xin chào"}}]}
    client_ctx, client = _mock_async_client(post_return=resp)

    provider = LocalLLMProvider("http://llm.local/v1/", "qwen3:8b", api_key="k")
    with patch("app.ai.llm_provider.httpx.AsyncClient", return_value=client_ctx):
        out = await provider.ainvoke([{"role": "user", "content": "hi"}])

    assert out.content == "xin chào"
    client.post.assert_awaited_once()
    assert client.post.call_args.args[0] == "http://llm.local/v1/chat/completions"


@pytest.mark.asyncio
async def test_local_llm_provider_ainvoke_json_fallback_on_400():
    req = httpx.Request("POST", "http://llm.local/v1/chat/completions")
    resp_400 = httpx.Response(400, request=req, text="unsupported response_format")
    err_400 = httpx.HTTPStatusError("400", request=req, response=resp_400)

    resp_ok = MagicMock()
    resp_ok.raise_for_status = MagicMock()
    resp_ok.json.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}

    client_ctx, client = _mock_async_client(post_side_effect=[err_400, resp_ok])
    provider = LocalLLMProvider("http://llm.local/v1", "qwen3:8b")

    with patch("app.ai.llm_provider.httpx.AsyncClient", return_value=client_ctx):
        out = await provider.ainvoke_json([{"role": "user", "content": "json"}])

    assert out.content == '{"ok": true}'
    assert client.post.await_count == 2
    assert "response_format" in client.post.call_args_list[0].kwargs["json"]
    assert "response_format" not in client.post.call_args_list[1].kwargs["json"]


@pytest.mark.asyncio
async def test_local_llm_provider_ainvoke_json_reraises_500():
    req = httpx.Request("POST", "http://llm.local/v1/chat/completions")
    resp_500 = httpx.Response(500, request=req, text="internal error")
    err_500 = httpx.HTTPStatusError("500", request=req, response=resp_500)
    client_ctx, _ = _mock_async_client(post_side_effect=err_500)

    provider = LocalLLMProvider("http://llm.local/v1", "qwen3:8b")
    with patch("app.ai.llm_provider.httpx.AsyncClient", return_value=client_ctx):
        with pytest.raises(httpx.HTTPStatusError):
            await provider.ainvoke_json([{"role": "user", "content": "json"}])


@pytest.mark.asyncio
async def test_local_llm_provider_astream_parses_sse_and_skips_bad_json():
    lines = [
        "",
        "event: ping",
        'data: {"choices": [{"delta": {"content": "Xin "}}]}',
        "data: {broken-json",
        'data: {"choices": [{"delta": {"content": "chào"}}]}',
        "data: [DONE]",
        'data: {"choices": [{"delta": {"content": "ignored"}}]}',
    ]
    client_ctx, _ = _mock_async_client(stream_lines=lines)
    provider = LocalLLMProvider("http://llm.local/v1", "qwen3:8b")

    with patch("app.ai.llm_provider.httpx.AsyncClient", return_value=client_ctx):
        chunks = [
            c async for c in provider.astream([{"role": "user", "content": "hi"}])
        ]

    assert chunks == ["Xin ", "chào"]

