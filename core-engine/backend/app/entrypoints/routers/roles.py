# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.external.keycloak_adapter import KeycloakAdapter
from app.adapters.repositories.role_repo import RoleRepository
from app.adapters.repositories.tenant_repo import SQLAlchemyTenantRepository
from app.core.domain.entities import TenantContext
from app.core.domain.exceptions import NotFoundError
from app.core.use_cases.role_management import RoleManagementUseCase
from app.entrypoints.dependencies import (
    get_current_tenant_context,
    get_db_transactional,
    get_keycloak_adapter,
    require_permission,
)
from app.entrypoints.schemas.role import (
    ApplyTemplateRequest,
    ApplyTemplateResponse,
    RoleAssign,
    RoleCreate,
    RoleResponse,
    RoleTemplateInfo,
    RoleUpdate,
)
from app.infrastructure.config import settings

# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later


router = APIRouter(prefix="/roles", tags=["Roles"])


async def _resolve_keycloak_realm(
    context: TenantContext, use_case: RoleManagementUseCase | None = None
) -> str:
    """Resolve đúng Keycloak realm cho tenant hiện tại (#865.2)."""
    ctx_realm = getattr(context, "keycloak_realm", None)
    if isinstance(ctx_realm, str) and ctx_realm.strip():
        return ctx_realm.strip()
    try:
        session = getattr(getattr(use_case, "role_repo", None), "session", None)
        if session is not None:
            tenant_repo = SQLAlchemyTenantRepository(session=session)
            tenant = await tenant_repo.get_by_id(context.tenant_id)
            t_realm = getattr(tenant, "keycloak_realm", None) if tenant else None
            if isinstance(t_realm, str) and t_realm.strip():
                return t_realm.strip()
    except Exception:  # noqa: BLE001
        pass
    return settings.KEYCLOAK_REALM


async def _sync_position_on_assign(
    session, tenant_id: uuid.UUID, email: str, display_name: str
) -> None:
    """Best-effort: gán role → điền chức vụ (hr_employees.position) khi còn trống.

    Đồng bộ 1 chiều Roles → HR để danh sách không lệch. Không bao giờ ghi đè
    chức vụ HR đã nhập tay (dữ liệu HR chi tiết hơn tên role). Không raise.
    """
    import inspect
    import logging
    import re as _re

    from sqlalchemy import text as _t

    try:
        if not display_name or not email:
            return
        schema = f"tenant_{str(tenant_id).replace('-', '_')}"
        if not _re.match(r"^[a-zA-Z0-9_]+$", schema):
            return
        exists = await session.execute(
            _t(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :s AND table_name = 'hr_employees'"
            ),
            {"s": schema},
        )
        row = exists.first()
        if inspect.isawaitable(row):
            row = await row
        if row is None:
            return
        async with session.begin_nested():
            await session.execute(
                _t(
                    f'UPDATE "{schema}"."hr_employees" SET position = :p '
                    "WHERE lower(email) = lower(:e) "
                    "AND (position IS NULL OR position = '')"
                ),
                {"p": display_name, "e": email},
            )
    except Exception as exc:
        logging.getLogger(__name__).warning("Sync chức vụ HR bỏ qua: %s", exc)


def get_role_use_case(
    session: AsyncSession = Depends(get_db_transactional),
) -> RoleManagementUseCase:
    from app.adapters.repositories.user_repo import SQLAlchemyUserRepository

    role_repo = RoleRepository(session)
    user_repo = SQLAlchemyUserRepository(session)
    return RoleManagementUseCase(role_repo, user_repo)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Tạo Role mới cho Tenant.
    """
    role = await use_case.create_role(tenant_context.tenant_id, data.model_dump())
    return role


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    tenant_context: TenantContext = Depends(require_permission("roles.read")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Liệt kê tất cả các roles của Tenant.
    """
    roles = await use_case.list_roles(tenant_context.tenant_id)
    return roles


@router.get("/templates", response_model=list[RoleTemplateInfo])
async def list_role_templates(
    tenant_context: TenantContext = Depends(get_current_tenant_context),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Liệt kê template role theo loại tổ chức (SME / trường học / hành chính).
    """
    return use_case.list_role_templates()


@router.post("/apply-template", response_model=ApplyTemplateResponse)
async def apply_role_template(
    data: ApplyTemplateRequest,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Áp 1 template: tạo các role còn thiếu (idempotent, trùng tên thì bỏ qua).
    """
    try:
        result = await use_case.apply_role_template(
            tenant_context.tenant_id, data.template_key
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApplyTemplateResponse(template_key=data.template_key, **result)


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: uuid.UUID,
    tenant_context: TenantContext = Depends(require_permission("roles.read")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Lấy chi tiết một Role theo ID.
    """
    role = await use_case.get_role(role_id, tenant_context.tenant_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    data: RoleUpdate,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Cập nhật thông tin Role hoặc phân quyền (permissions) cho Role.
    """
    try:
        role = await use_case.update_role(
            role_id, tenant_context.tenant_id, data.model_dump(exclude_unset=True)
        )
        return role
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
):
    """
    Xóa một Role.
    """
    try:
        await use_case.delete_role(role_id, tenant_context.tenant_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể xóa Role vì vẫn còn liên kết dữ liệu ràng buộc.",
        ) from e


@router.post("/{role_id}/assign")
async def assign_role_to_user(
    role_id: uuid.UUID,
    data: RoleAssign,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
    keycloak: KeycloakAdapter = Depends(get_keycloak_adapter),
):
    """
    Gán một Role cho một User.
    """
    try:
        # Get user to sync to Keycloak
        user = await use_case.user_repo.get(data.user_id)
        if not user or not user.keycloak_id:
            raise ValueError("User not found or missing keycloak_id")
        # C5: chặn cross-tenant — user phải cùng tenant với caller.
        if str(user.tenant_id) != str(tenant_context.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền gán role cho user thuộc tenant khác.",
            )

        role = await use_case.get_role(role_id, tenant_context.tenant_id)
        if not role:
            raise ValueError("Role not found")

        await use_case.assign_role_to_user(
            data.user_id, role_id, tenant_context.user_id, tenant_context.tenant_id
        )

        # Assign role in Keycloak
        kc_role_name = (
            f"{role.plugin_code_name}_{role.name}"
            if getattr(role, "plugin_code_name", None)
            else role.name
        )
        realm = await _resolve_keycloak_realm(tenant_context, use_case)
        try:
            await keycloak.assign_role_to_user(
                realm=realm,
                user_id=str(user.keycloak_id),
                role_name=kc_role_name,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Lỗi khi gán role cho Keycloak user", exc_info=exc
            )

        # Đồng bộ Roles → HR: điền chức vụ khi hồ sơ còn trống (best-effort).
        await _sync_position_on_assign(
            use_case.role_repo.session,
            tenant_context.tenant_id,
            user.email,
            getattr(role, "display_name", "") or role.name,
        )

        return {"detail": "Role assigned successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{role_id}/revoke")
async def revoke_role_from_user(
    role_id: uuid.UUID,
    data: RoleAssign,
    tenant_context: TenantContext = Depends(require_permission("roles:manage")),
    use_case: RoleManagementUseCase = Depends(get_role_use_case),
    keycloak: KeycloakAdapter = Depends(get_keycloak_adapter),
):
    """
    Thu hồi một Role từ một User.
    """
    try:
        # Get user to sync to Keycloak
        user = await use_case.user_repo.get(data.user_id)
        if not user or not user.keycloak_id:
            raise ValueError("User not found or missing keycloak_id")
        # C5: chặn cross-tenant — user phải cùng tenant với caller.
        if str(user.tenant_id) != str(tenant_context.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền thu hồi role của user thuộc tenant khác.",
            )

        role = await use_case.get_role(role_id, tenant_context.tenant_id)
        if not role:
            raise ValueError("Role not found")

        await use_case.revoke_role_from_user(
            data.user_id, role_id, tenant_context.tenant_id
        )

        # Revoke role in Keycloak
        kc_role_name = (
            f"{role.plugin_code_name}_{role.name}"
            if getattr(role, "plugin_code_name", None)
            else role.name
        )
        realm = await _resolve_keycloak_realm(tenant_context, use_case)
        try:
            await keycloak.revoke_role_from_user(
                realm=realm,
                user_id=str(user.keycloak_id),
                role_name=kc_role_name,
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Lỗi khi thu hồi role từ Keycloak user", exc_info=exc
            )

        return {"detail": "Role revoked successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
