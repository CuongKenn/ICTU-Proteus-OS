# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Core Use Case — Generic Plugin Records CRUD
#
# Đọc/ghi trực tiếp các bảng dữ liệu của plugin qua MỘT nhóm endpoint duy nhất:
#   GET/POST /api/v1/plugins/{code}/records/{table}
#   PATCH/DELETE /api/v1/plugins/{code}/records/{table}/{id}
# Core không biết gì về asset hay CRM: tên bảng phải nằm trong
# manifest.yaml `database.tables` (allowlist), tên cột lấy từ
# information_schema (DB truth) nên không thể SQL-injection qua key.
#
# Phân vai rõ với dispatcher (plugin_action.py):
# - Quy trình có orchestration (duyệt → gán → nhắn tin) → n8n webhook.
# - CRUD hàng đơn lẻ không có workflow → endpoint này.
# Tenant isolation: mỗi tenant có schema riêng (tenant_<uuid>, do install tạo).
# Mọi query qualify "schema"."bảng" — KHÔNG dùng cột tenant_id (schema đã cách ly).
# Công thức schema phải khớp _step_1_database trong plugin_install.py.

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.repositories.base import AbstractPluginRepository
from app.adapters.repositories.role_repo import RoleRepository
from app.core.domain.entities import PluginStatus, TenantContext
from app.core.domain.exceptions import (
    DSLInvalidActionError,
    DSLInvalidParametersError,
    DSLPluginNotActiveError,
    InsufficientPermissionsError,
    PluginNotFoundError,
)
from app.core.domain.permissions import has_admin_role, has_wildcard_permission
from app.core.domain.ports import AbstractManifestParserPort

logger = logging.getLogger(__name__)

_CODE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_SCHEMA_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")
_MAX_LIMIT = 100
_UNSET = object()

# Cột server-owned: client không được set qua create/update (#697).
SERVER_OWNED_COLUMNS = frozenset(
    {
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
    }
)


def _jsonable(value: Any) -> Any:
    """Chuẩn hóa row DB thành JSON-serializable (datetime/UUID/Decimal…)."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _expand_resource_variants(name: str) -> set[str]:
    """Sinh các biến thể số ít / số nhiều cơ bản cho tên tài nguyên."""
    variants: set[str] = set()
    if not name:
        return variants
    variants.add(name)
    stripped_s = name.rstrip("s")
    if stripped_s:
        variants.add(stripped_s)
    if name.endswith("ies") and len(name) > 3:
        variants.add(name[:-3] + "y")
    elif name.endswith("es") and len(name) > 2:
        variants.add(name[:-2])
    elif name.endswith("s") and len(name) > 1:
        variants.add(name[:-1])
    else:
        variants.add(f"{name}s")
        if name.endswith("y") and len(name) > 1:
            variants.add(name[:-1] + "ies")
        else:
            variants.add(f"{name}es")
    return variants


class PluginRecordsUseCase:
    """CRUD generic cho bảng dữ liệu plugin (allowlist từ manifest)."""

    def __init__(
        self,
        plugin_repo: AbstractPluginRepository,
        manifest_parser: AbstractManifestParserPort,
        role_repo: RoleRepository,
        session: AsyncSession,
    ) -> None:
        self.plugin_repo = plugin_repo
        self.manifest_parser = manifest_parser
        self.role_repo = role_repo
        self.session = session

    # ─── Guards ───────────────────────────────────────────────

    async def _resolve_table(self, plugin_code: str, table: str) -> None:
        if not _CODE_PATTERN.match(plugin_code):
            raise PluginNotFoundError(f"Plugin '{plugin_code}' không tồn tại.")
        if not _TABLE_PATTERN.match(table):
            raise DSLInvalidActionError(f"Bảng '{table}' không hợp lệ.")
        from app.adapters.external.local_manifest_parser import ManifestParserError

        try:
            manifest = self.manifest_parser.parse(plugin_code)
        except ManifestParserError as exc:
            raise PluginNotFoundError(f"Plugin '{plugin_code}' không tồn tại.") from exc
        allowed = manifest.database.tables if manifest.database else []
        if table not in allowed:
            raise DSLInvalidActionError(
                f"Bảng '{table}' không thuộc plugin '{plugin_code}'."
            )

    async def _require_active(self, ctx: TenantContext, plugin_code: str) -> None:
        plugin = await self.plugin_repo.get_by_code_name(plugin_code)
        if not plugin:
            raise PluginNotFoundError(f"Plugin '{plugin_code}' không tồn tại.")
        status = await self.plugin_repo.get_installation_status(
            ctx.tenant_id, plugin.id
        )
        if status != PluginStatus.ACTIVE:
            raise DSLPluginNotActiveError(
                f"Plugin '{plugin_code}' chưa ACTIVE (hiện tại: {status})."
            )

    async def _require_table_permission(
        self, ctx: TenantContext, plugin_code: str, table: str, action: str = "read"
    ) -> None:
        if has_admin_role(ctx.roles):
            return
        perms = await self.role_repo.get_user_permissions(
            ctx.user_id, tenant_id=ctx.tenant_id
        )
        if has_wildcard_permission(perms):
            return

        prefix = plugin_code.split("-")[0]
        prefix_colon = f"{prefix}:"
        user_plugin_perms = [p for p in perms if p.startswith(prefix_colon)]
        if not user_plugin_perms:
            raise InsufficientPermissionsError(
                f"Cần quyền nhóm '{prefix}:*' để truy cập dữ liệu plugin."
            )

        # Trích xuất full_resource từ tên bảng (VD: hr_leave_requests -> leave_requests)
        full_resource = (
            table[len(prefix) + 1 :] if table.startswith(f"{prefix}_") else table
        )
        base_resources = {full_resource, table}
        if "_" in full_resource:
            parts = [seg for seg in full_resource.split("_") if seg]
            if parts:
                base_resources.add(parts[0])
            if len(parts) >= 2:
                acronym = "".join(seg[0] for seg in parts)
                if len(acronym) >= 2:
                    base_resources.add(acronym)

        candidates: set[str] = set()
        for base in base_resources:
            candidates.update(_expand_resource_variants(base))

        # Wildcard cấp plugin
        plugin_wildcards = {
            f"{prefix}:*",
            f"{prefix}:*:*",
            f"{prefix}:*:manage",
            f"{prefix}:*:{action}",
        }
        if action == "read":
            plugin_wildcards.update(
                {
                    f"{prefix}:*:read",
                    f"{prefix}:*:read_all",
                    f"{prefix}:*:write",
                    f"{prefix}:*:approve",
                }
            )
        elif action in ("write", "create", "update"):
            plugin_wildcards.update({f"{prefix}:*:write", f"{prefix}:*:approve"})
        elif action == "delete":
            plugin_wildcards.update({f"{prefix}:*:delete", f"{prefix}:*:write"})

        if any(p in user_plugin_perms for p in plugin_wildcards):
            return

        for r in candidates:
            if action == "read":
                if any(
                    p in user_plugin_perms
                    for p in (
                        f"{prefix}:{r}:read",
                        f"{prefix}:{r}:read_all",
                        f"{prefix}:{r}:write",
                        f"{prefix}:{r}:approve",
                        f"{prefix}:{r}:manage",
                        f"{prefix}:{r}:*",
                    )
                ):
                    return
            elif action in ("write", "create", "update"):
                allowed_write = {
                    f"{prefix}:{r}:write",
                    f"{prefix}:{r}:approve",
                    f"{prefix}:{r}:manage",
                    f"{prefix}:{r}:*",
                }
                if action in ("create", "update"):
                    allowed_write.add(f"{prefix}:{r}:{action}")
                if any(p in user_plugin_perms for p in allowed_write):
                    return
            elif action == "delete":
                if any(
                    p in user_plugin_perms
                    for p in (
                        f"{prefix}:{r}:delete",
                        f"{prefix}:{r}:write",
                        f"{prefix}:{r}:manage",
                        f"{prefix}:{r}:*",
                    )
                ):
                    return

        raise InsufficientPermissionsError(
            f"Cần quyền '{prefix}:{full_resource}:{action}' "
            f"để thao tác trên bảng '{table}'."
        )

    async def _require_prefix_perm(self, ctx: TenantContext, plugin_code: str) -> None:
        if has_admin_role(ctx.roles):
            return
        prefix = plugin_code.split("-")[0] + ":"
        perms = await self.role_repo.get_user_permissions(
            ctx.user_id, tenant_id=ctx.tenant_id
        )
        if has_wildcard_permission(perms):
            return
        if not any(p.startswith(prefix) for p in perms):
            raise InsufficientPermissionsError(
                f"Cần quyền nhóm '{prefix}*' để truy cập dữ liệu plugin."
            )

    async def _columns(self, schema: str, table: str) -> dict[str, str]:
        """Map cột → data_type (dùng để coerce kiểu cho asyncpg)."""
        res = await self.session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": table},
        )
        cols = {r[0]: r[1] for r in res.all()}
        if not cols:
            # Manifest cho phép nhưng bảng chưa tồn tại trong schema tenant
            # (install chưa chạy xong hoặc seed thiếu CREATE TABLE).
            raise PluginNotFoundError(
                f"Bảng '{table}' chưa tồn tại — plugin có thể chưa cài xong."
            )
        return cols

    @staticmethod
    def _coerce(col_type: str, col: str, value: Any) -> Any:
        """Ép kiểu Python cho asyncpg. Sai định dạng → 400 rõ ràng thay vì 500."""
        if value is None:
            return None
        if (
            isinstance(value, str)
            and not value.strip()
            and col_type
            in (
                "uuid",
                "date",
                "timestamp with time zone",
                "timestamp without time zone",
                "numeric",
                "decimal",
                "real",
                "double precision",
                "integer",
                "bigint",
                "smallint",
            )
        ):
            return None

        if col_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("true", "1", "yes"):
                    return True
                if lowered in ("false", "0", "no"):
                    return False
            raise DSLInvalidParametersError(
                f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
            )

        if col_type in (
            "integer",
            "bigint",
            "smallint",
            "numeric",
            "decimal",
            "real",
            "double precision",
        ):
            if isinstance(value, bool):
                raise DSLInvalidParametersError(
                    f"Giá trị cột '{col}' không đúng định dạng ({col_type}): "
                    "không chấp nhận boolean."
                )

        try:
            if col_type == "date" and isinstance(value, str):
                return date.fromisoformat(value.strip()[:10])
            if col_type in (
                "timestamp with time zone",
                "timestamp without time zone",
            ):
                if isinstance(value, str):
                    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                return value
            if col_type == "uuid" and isinstance(value, str):
                return uuid.UUID(value.strip())
            if col_type in ("numeric", "decimal"):
                if isinstance(value, Decimal):
                    return value
                if isinstance(value, int | float):
                    return Decimal(str(value))
                if isinstance(value, str):
                    return Decimal(value.strip())
                raise DSLInvalidParametersError(
                    f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
                )
            if col_type in ("real", "double precision"):
                if isinstance(value, int | float):
                    return float(value)
                if isinstance(value, str):
                    return float(value.strip())
                raise DSLInvalidParametersError(
                    f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
                )
            if col_type in ("integer", "bigint", "smallint"):
                if isinstance(value, int):
                    return value
                if isinstance(value, float):
                    if value.is_integer():
                        return int(value)
                    raise DSLInvalidParametersError(
                        f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
                    )
                if isinstance(value, str):
                    return int(value.strip())
                raise DSLInvalidParametersError(
                    f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
                )
            if col_type in ("json", "jsonb"):
                if isinstance(value, dict | list):
                    return json.dumps(value, ensure_ascii=False)
                if isinstance(value, str):
                    try:
                        json.loads(value)
                        return value
                    except Exception:
                        return json.dumps(value, ensure_ascii=False)
        except (ValueError, InvalidOperation) as exc:
            raise DSLInvalidParametersError(
                f"Giá trị cột '{col}' không đúng định dạng ({col_type})."
            ) from exc
        return value

    def _coerce_params(
        self, col_types: dict[str, str], data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            c: self._coerce(col_types[c], c, data[c]) for c in data if c in col_types
        }

    @staticmethod
    def _schema(ctx: TenantContext) -> str:
        schema = f"tenant_{ctx.tenant_id}".replace("-", "_")
        if not _SCHEMA_PATTERN.match(schema):
            raise DSLInvalidParametersError("Tenant schema không hợp lệ.")
        return schema

    @staticmethod
    def _qt(schema: str, table: str) -> str:
        """Qualified table — cả 2 đều đã qua allowlist/regex nên an toàn."""
        return f'"{schema}"."{table}"'

    # ─── Public API ───────────────────────────────────────────

    async def list_records(
        self,
        ctx: TenantContext,
        plugin_code: str,
        table: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await self._resolve_table(plugin_code, table)
        await self._require_active(ctx, plugin_code)
        await self._require_table_permission(ctx, plugin_code, table, "read")
        limit = max(1, min(limit, _MAX_LIMIT))
        offset = max(0, offset)
        schema = self._schema(ctx)
        qt = self._qt(schema, table)
        cols = await self._columns(schema, table)  # validate bảng tồn tại
        order = "ORDER BY created_at DESC " if "created_at" in cols else ""
        total_res = await self.session.execute(
            text(f"SELECT COUNT(*) FROM {qt}"),
        )
        total = total_res.scalar() or 0
        rows_res = await self.session.execute(
            text(f"SELECT * FROM {qt} {order}LIMIT :lim OFFSET :off"),
            {"lim": limit, "off": offset},
        )
        rows = [_jsonable(dict(r)) for r in rows_res.mappings().all()]
        return {"rows": rows, "total": total}

    async def create_record(
        self,
        ctx: TenantContext,
        plugin_code: str,
        table: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        await self._resolve_table(plugin_code, table)
        await self._require_active(ctx, plugin_code)
        await self._require_table_permission(ctx, plugin_code, table, "write")
        if not isinstance(data, dict) or not data:
            raise DSLInvalidParametersError("Body phải là JSON object không rỗng.")
        col_types = await self._columns(self._schema(ctx), table)
        # Cột do server sở hữu (id, tenant_id, audit) KHÔNG nhận từ client (#697).
        body = {c: v for c, v in data.items() if c not in SERVER_OWNED_COLUMNS}
        params = self._coerce_params(col_types, body)
        # Một số plugin đời đầu (VD hr-module) vẫn giữ cột tenant_id NOT NULL —
        # luôn lấy tenant_id từ context (JWT), ghi đè mọi giá trị client gửi.
        if "tenant_id" in col_types:
            params["tenant_id"] = self._coerce(
                col_types["tenant_id"], "tenant_id", str(ctx.tenant_id)
            )
        if not params:
            raise DSLInvalidParametersError("Không có cột nào hợp lệ để ghi.")
        col_sql = ", ".join(params)
        val_sql = ", ".join(f":{c}" for c in params)
        qt = self._qt(self._schema(ctx), table)
        res = await self.session.execute(
            text(f"INSERT INTO {qt} ({col_sql}) VALUES ({val_sql}) RETURNING *"),
            params,
        )
        row = res.mappings().first()
        return _jsonable(dict(row)) if row else {}

    async def update_record(
        self,
        ctx: TenantContext,
        plugin_code: str,
        table: str,
        record_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        await self._resolve_table(plugin_code, table)
        await self._require_active(ctx, plugin_code)
        await self._require_table_permission(ctx, plugin_code, table, "write")
        try:
            uuid.UUID(str(record_id))
        except ValueError as exc:
            raise DSLInvalidParametersError("record id phải là UUID.") from exc
        if not isinstance(data, dict) or not data:
            raise DSLInvalidParametersError("Body phải là JSON object không rỗng.")
        col_types = await self._columns(self._schema(ctx), table)
        body = {c: v for c, v in data.items() if c not in SERVER_OWNED_COLUMNS}
        coerced = self._coerce_params(col_types, body)
        allowed = list(coerced)
        if not allowed:
            raise DSLInvalidParametersError("Không có cột nào hợp lệ để cập nhật.")
        set_sql = ", ".join(f"{c} = :{c}" for c in allowed)
        params: dict[str, Any] = {c: coerced[c] for c in allowed}
        params["rid"] = self._coerce("uuid", "id", record_id)
        qt = self._qt(self._schema(ctx), table)
        res = await self.session.execute(
            text(f"UPDATE {qt} SET {set_sql} WHERE id = :rid RETURNING *"),
            params,
        )
        row = res.mappings().first()
        if row is None:
            raise PluginNotFoundError(
                f"Bản ghi '{record_id}' không tồn tại trong '{table}'."
            )
        return _jsonable(dict(row))

    async def delete_record(
        self,
        ctx: TenantContext,
        plugin_code: str,
        table: str,
        record_id: str,
    ) -> None:
        await self._resolve_table(plugin_code, table)
        await self._require_active(ctx, plugin_code)
        await self._require_table_permission(ctx, plugin_code, table, "delete")
        try:
            uuid.UUID(str(record_id))
        except ValueError as exc:
            raise DSLInvalidParametersError("record id phải là UUID.") from exc
        await self._columns(self._schema(ctx), table)  # probe bảng tồn tại
        try:
            rid = uuid.UUID(str(record_id))
        except ValueError as exc:
            raise DSLInvalidParametersError("record id phải là UUID.") from exc
        params: dict[str, Any] = {"rid": rid}
        qt = self._qt(self._schema(ctx), table)
        res = await self.session.execute(
            text(f"DELETE FROM {qt} WHERE id = :rid"),
            params,
        )
        if (res.rowcount or 0) == 0:
            raise PluginNotFoundError(
                f"Bản ghi '{record_id}' không tồn tại trong '{table}'."
            )
