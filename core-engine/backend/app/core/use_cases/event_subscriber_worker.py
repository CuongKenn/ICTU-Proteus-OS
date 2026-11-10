# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import uuid
from typing import Any

from app.adapters.external.local_manifest_parser import ManifestParserError
from app.adapters.external.n8n_adapter import N8nAdapter
from app.adapters.repositories.plugin_repo import SQLAlchemyPluginRepository
from app.core.domain.ports import AbstractManifestParserPort
from app.infrastructure.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EventSubscriberWorker:
    """
    Worker lắng nghe Event Bus và tự động kích hoạt n8n webhooks
    của các Plugins đã subscribe event tương ứng.
    """

    def __init__(
        self,
        manifest_parser: AbstractManifestParserPort,
        n8n_adapter: N8nAdapter,
    ):
        self.manifest_parser = manifest_parser
        self.n8n_adapter = n8n_adapter

    def _resolve_handler_webhook_url(
        self, plugin_code: str, handler_workflow: str
    ) -> str:
        """Resolve webhook URL cho handler_workflow của event subscription (#729)."""
        import json
        from pathlib import Path

        from app.infrastructure.config import settings

        # Nếu là action name (vd plugin.resource.method), n8n_adapter.build_webhook_url xử lý được
        if not (
            "/" in handler_workflow
            or "\\" in handler_workflow
            or handler_workflow.endswith(".json")
        ):
            return self.n8n_adapter.build_webhook_url(handler_workflow)

        # Chặn path traversal
        if ".." in handler_workflow or handler_workflow.startswith("/"):
            raise ValueError(f"Invalid handler_workflow path: {handler_workflow}")

        plugins_dir_attr = getattr(self.manifest_parser, "plugins_dir", "plugins")
        if callable(plugins_dir_attr):
            plugins_dir = Path(plugins_dir_attr()).resolve()
        else:
            plugins_dir = Path(plugins_dir_attr).resolve()
        if not plugins_dir.is_dir():
            candidate = (Path(__file__).resolve().parents[5] / "plugins").resolve()
            if candidate.is_dir():
                plugins_dir = candidate
        wf_path = (plugins_dir / plugin_code / handler_workflow).resolve()
        if not wf_path.is_relative_to(plugins_dir) or not wf_path.is_file():
            raise ValueError(
                f"Workflow file '{handler_workflow}' not found in plugin '{plugin_code}'"
            )

        with open(wf_path, encoding="utf-8-sig") as f:
            wf_json = json.load(f)

        webhook_path = None
        for node in wf_json.get("nodes", []):
            if node.get("type") == "n8n-nodes-base.webhook":
                webhook_path = (node.get("parameters", {}) or {}).get("path")
                if webhook_path:
                    break

        if not webhook_path:
            stem = wf_path.stem.replace("_", "-")
            prefix = plugin_code.replace("-module", "")
            webhook_path = f"{prefix}/{stem}"

        base_url = settings.N8N_URL.rstrip("/")
        return f"{base_url}/webhook/{str(webhook_path).lstrip('/')}"

    async def handle_event(self, envelope: dict[str, Any]) -> None:
        """Hàm xử lý một event đến từ Redis."""
        tenant_id_str = envelope.get("tenant_id")
        event_type = envelope.get("event_type")
        plugin_source = envelope.get("plugin_source")
        payload = envelope.get("payload", {})
        event_id = envelope.get("event_id")

        if not tenant_id_str or not event_type or not plugin_source:
            logger.warning(
                "Event envelope thiếu thông tin bắt buộc, bỏ qua.",
                extra={"envelope": envelope},
            )
            return

        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except ValueError:
            logger.warning(f"Invalid tenant_id format: {tenant_id_str}")
            return

        logger.debug(
            f"Received event {event_type} from {plugin_source}",
            extra={"event_id": event_id},
        )

        # Mở session mới cho mỗi event để không giữ connection quá lâu
        async with AsyncSessionLocal() as session:
            from app.infrastructure.database import set_session_tenant

            await set_session_tenant(session, tenant_id)
            plugin_repo = SQLAlchemyPluginRepository(session=session)
            plugins, _ = await plugin_repo.list_installed(tenant_id)

            # Quét manifest của các plugin đang active
            for p in plugins:
                try:
                    manifest = self.manifest_parser.parse(p.code_name)
                    # Tìm xem có subscription nào khớp không
                    for sub in manifest.event_subscriptions:
                        if (
                            sub.source_plugin == plugin_source
                            and event_type in sub.event_types
                        ):
                            # TÌM THẤY MATCH! Trigger workflow.
                            try:
                                webhook_url = self._resolve_handler_webhook_url(
                                    p.code_name, sub.handler_workflow
                                )

                                # Đẩy thêm metadata vào payload để n8n biết source
                                enriched_payload = {
                                    **payload,
                                    "_event_metadata": {
                                        "event_id": event_id,
                                        "event_type": event_type,
                                        "source_plugin": plugin_source,
                                        "tenant_id": tenant_id_str,
                                    },
                                }

                                await self.n8n_adapter.trigger_webhook(
                                    webhook_url=webhook_url, payload=enriched_payload
                                )
                                logger.info(
                                    "Cross-plugin workflow triggered",
                                    extra={
                                        "triggering_event": event_type,
                                        "source_plugin": plugin_source,
                                        "target_plugin": p.code_name,
                                        "workflow": sub.handler_workflow,
                                    },
                                )
                            except Exception as trigger_err:
                                logger.error(
                                    f"Failed to trigger subscriber workflow {sub.handler_workflow}: {trigger_err}",
                                    exc_info=True,
                                )

                except ManifestParserError:
                    logger.warning(
                        f"Failed to parse manifest for active plugin {p.code_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error checking subscriptions for {p.code_name}", exc_info=True
                    )
