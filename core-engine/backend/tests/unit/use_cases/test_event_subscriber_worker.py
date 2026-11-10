# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.use_cases.event_subscriber_worker import EventSubscriberWorker


def get_plugins_dir():
    return Path(__file__).resolve().parents[5] / "plugins"


@pytest.fixture
def worker():
    manifest_parser = MagicMock()
    manifest_parser.plugins_dir = get_plugins_dir()
    n8n_adapter = MagicMock()
    n8n_adapter.trigger_webhook = AsyncMock()
    return EventSubscriberWorker(
        manifest_parser=manifest_parser, n8n_adapter=n8n_adapter
    )


def test_resolve_handler_webhook_url_from_file(worker):
    """EventSubscriberWorker trích xuất đúng path từ node webhook trong file workflow (#729)."""
    url = worker._resolve_handler_webhook_url(
        "document-module", "workflows/reassign_document.json"
    )
    assert url.endswith("/webhook/document/reassign")


def test_resolve_handler_webhook_url_action_format(worker):
    """Nếu handler_workflow là action 3-part thì gọi build_webhook_url (#729)."""
    worker.n8n_adapter.build_webhook_url.return_value = (
        "http://n8n:5678/webhook/hr-leave-approve"
    )
    url = worker._resolve_handler_webhook_url("hr-module", "hr.leave.approve")
    worker.n8n_adapter.build_webhook_url.assert_called_once_with("hr.leave.approve")
    assert url == "http://n8n:5678/webhook/hr-leave-approve"


@pytest.mark.asyncio
async def test_handle_event_triggers_subscriber_workflow(worker):
    """Xử lý event, tìm match trong event_subscriptions và trigger webhook (#729)."""
    tenant_id = uuid.uuid4()
    envelope = {
        "tenant_id": str(tenant_id),
        "event_type": "hr.employee.deactivated",
        "plugin_source": "hr-module",
        "event_id": str(uuid.uuid4()),
        "payload": {"employee_id": "emp_123"},
    }

    mock_plugin = MagicMock()
    mock_plugin.code_name = "document-module"

    sub = MagicMock()
    sub.source_plugin = "hr-module"
    sub.event_types = ["hr.employee.deactivated"]
    sub.handler_workflow = "workflows/reassign_document.json"

    manifest = MagicMock()
    manifest.event_subscriptions = [sub]
    worker.manifest_parser.parse.return_value = manifest

    with patch(
        "app.core.use_cases.event_subscriber_worker.AsyncSessionLocal"
    ) as mock_sess_cls:
        mock_sess = AsyncMock()
        mock_sess_cls.return_value.__aenter__.return_value = mock_sess
        with patch(
            "app.core.use_cases.event_subscriber_worker.SQLAlchemyPluginRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.list_installed.return_value = ([mock_plugin], 1)
            mock_repo_cls.return_value = mock_repo

            await worker.handle_event(envelope)

            worker.n8n_adapter.trigger_webhook.assert_called_once()
            call_kwargs = worker.n8n_adapter.trigger_webhook.call_args.kwargs
            assert call_kwargs["webhook_url"].endswith("/webhook/document/reassign")
            assert call_kwargs["payload"]["employee_id"] == "emp_123"
            assert (
                call_kwargs["payload"]["_event_metadata"]["event_type"]
                == "hr.employee.deactivated"
            )
