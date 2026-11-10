# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Core Domain — Configure Plugin Credentials Use Case

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from app.adapters.repositories.base import AbstractPluginRepository
from app.core.domain.entities import TenantContext
from app.core.domain.ports import AbstractWorkflowEnginePort
from app.entrypoints.schemas.plugin import PluginCredentialPayload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConfigurePluginCredentialsUseCase:
    """
    Quản lý luồng cấu hình Credentials cho Plugin.
    Chuyển tiếp credentials an toàn tới n8n, đồng thời cập nhật credential_ids
    vào tenant_plugins và gán credential vào các workflow n8n liên quan.
    """

    def __init__(
        self,
        n8n_adapter: AbstractWorkflowEnginePort,
        plugin_repo: AbstractPluginRepository | None = None,
        session: AsyncSession | None = None,
    ):
        self.n8n_adapter = n8n_adapter
        self.plugin_repo = plugin_repo
        self.session = session

    async def execute(
        self, plugin_id: str, payload: PluginCredentialPayload, ctx: TenantContext
    ) -> dict[str, Any]:
        """Thực thi cấu hình credentials."""
        logger.info(
            "Configuring credentials for plugin %s in tenant %s",
            plugin_id,
            ctx.tenant_id,
        )

        # RLS Prefix: tenant_{tenant_id}_{plugin_id}_{payload.credential_name}
        safe_name = f"tenant_{ctx.tenant_id}_{payload.credential_name}"

        result = await self.n8n_adapter.create_credential(
            credential_type=payload.credential_type,
            credential_name=safe_name,
            data=payload.data,
        )
        cred_id = str(result.get("id", ""))

        if self.plugin_repo and cred_id:
            try:
                pid = uuid.UUID(str(plugin_id))
                existing_creds = await self.plugin_repo.get_credential_ids(
                    ctx.tenant_id, pid
                )
                new_entry = {
                    "id": cred_id,
                    "name": safe_name,
                    "type": payload.credential_type,
                }
                updated_creds = [
                    c
                    for c in existing_creds
                    if (c.get("type") if isinstance(c, dict) else None)
                    != payload.credential_type
                ]
                updated_creds.append(new_entry)
                await self.plugin_repo.update_credential_ids(
                    ctx.tenant_id, pid, updated_creds
                )

                # Cập nhật workflow n8n nếu có
                config = await self.plugin_repo.get_config(ctx.tenant_id, pid)
                workflow_ids = config.get("n8n", []) if isinstance(config, dict) else []
                for wfid in workflow_ids:
                    try:
                        wf = await self.n8n_adapter.get_workflow(str(wfid))
                        if wf and isinstance(wf, dict):
                            modified = False
                            for node in wf.get("nodes", []):
                                ncreds = node.setdefault("credentials", {})
                                if (
                                    payload.credential_type in ncreds
                                    or payload.credential_type
                                    == (node.get("type") or "").split(".")[-1]
                                    or payload.credential_type
                                    in str(node.get("type", ""))
                                ):
                                    ncreds[payload.credential_type] = {
                                        "id": cred_id,
                                        "name": safe_name,
                                    }
                                    modified = True
                            if modified:
                                await self.n8n_adapter.update_workflow(str(wfid), wf)
                    except Exception as wf_err:
                        logger.warning(
                            "Không thể cập nhật credential cho workflow %s: %s",
                            wfid,
                            wf_err,
                        )

                if self.session:
                    await self.session.commit()
            except Exception as ex:
                logger.warning(
                    "Lỗi cập nhật credential_ids vào DB hoặc workflows: %s", ex
                )

        return {
            "message": "Credential tạo thành công",
            "credential_id": cred_id,
            "safe_name": safe_name,
        }
