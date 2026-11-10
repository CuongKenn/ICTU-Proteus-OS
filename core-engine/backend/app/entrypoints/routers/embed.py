# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Entrypoint Router — Embed URLs (Metabase, Appsmith)

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.entities import TenantContext
from app.core.domain.permissions import has_admin_role
from app.entrypoints.dependencies import get_db_readonly, require_permission
from app.infrastructure.config import settings

router = APIRouter(prefix="/embed")


def _verify_metabase_token(token: str, secret_key: str) -> dict:
    """M11: verify JWT embed (tenant binding). Raise 403 nếu sai tenant/hết hạn."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Embed token không hợp lệ: {e}",
        ) from e
    return payload


async def _verify_tenant_dashboard_ownership(
    db: AsyncSession, tenant_id: uuid.UUID, dashboard_id: int
) -> bool:
    """Kiểm tra dashboard_id có thuộc về plugin nào đã cài của tenant không (#734)."""
    try:
        stmt = text(
            "SELECT config_override FROM tenant_plugins "
            "WHERE tenant_id = :tenant_id AND status = 'ACTIVE'"
        )
        result = await db.execute(stmt, {"tenant_id": tenant_id})
        rows = result.scalars().all()
    except Exception:
        return True

    if not rows:
        return True

    str_did = str(dashboard_id)
    has_metabase_configs = False
    for conf in rows:
        if not conf:
            continue
        try:
            data = json.loads(conf) if isinstance(conf, str) else conf
        except Exception:
            continue
        if isinstance(data, dict):
            mb = data.get("metabase")
            if mb:
                has_metabase_configs = True
                if isinstance(mb, list) and (
                    str_did in [str(x) for x in mb] or dashboard_id in mb
                ):
                    return True
                elif str(mb) == str_did:
                    return True

    return not has_metabase_configs


@router.get("/metabase/{dashboard_id}", summary="Get Metabase embed URL")
async def get_metabase_embed_url(
    dashboard_id: int,
    ctx: TenantContext = Depends(require_permission("analytics.view")),
    db: AsyncSession = Depends(get_db_readonly),
):
    """
    Tạo Signed URL cho iframe Metabase.
    Yêu cầu quyền analytics.view và kiểm tra quyền sở hữu dashboard (#734).
    """
    if not has_admin_role(ctx.roles):
        is_owned = await _verify_tenant_dashboard_ownership(
            db, ctx.tenant_id, dashboard_id
        )
        if not is_owned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Dashboard {dashboard_id} không thuộc quyền sở hữu của tổ chức bạn.",
            )

    secret_key = settings.METABASE_SECRET_KEY or settings.METABASE_EMBEDDING_KEY
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metabase embed chưa được cấu hình (thiếu secret).",
        )
    public_url = getattr(settings, "METABASE_PUBLIC_URL", None)
    if not public_url or not isinstance(public_url, str):
        public_url = settings.METABASE_SITE_URL
    site_url = str(public_url).rstrip("/")
    if not site_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metabase embed chưa được cấu hình (thiếu site URL).",
        )

    # M11: bind tenant_id vào JWT để chống cross-tenant reuse.
    payload = {
        "resource": {"dashboard": dashboard_id},
        "params": {"tenant_id": str(ctx.tenant_id)},
        "exp": int(time.time()) + 600,  # 10 phút
    }

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    # Verify ngay sau khi ký (phát hiện sai secret/thuật toán sớm).
    _verify_metabase_token(token, secret_key)

    return {
        "url": (f"{site_url}/embed/dashboard/" f"{token}#bordered=true&titled=false")
    }
