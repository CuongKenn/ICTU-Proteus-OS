# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from app.adapters.external.keycloak_adapter import (
    KeycloakAdapter,
    mattermost_numeric_id,
)
from app.adapters.repositories.base import (
    AbstractTenantRepository,
    AbstractUserRepository,
)
from app.core.domain.entities import TenantEntity, UserEntity

logger = logging.getLogger(__name__)


@dataclass
class OnboardingRequest:
    company_name: str
    admin_full_name: str
    admin_email: str
    admin_password: str


class OnboardingUseCase:
    """
    Use Case xử lý luồng đăng ký trực tuyến (SaaS Onboarding).
    """

    def __init__(
        self,
        tenant_repo: AbstractTenantRepository,
        user_repo: AbstractUserRepository,
        keycloak_adapter: KeycloakAdapter,
        mattermost_adapter: Any = None,
    ) -> None:
        self.tenant_repo = tenant_repo
        self.user_repo = user_repo
        self.keycloak_adapter = keycloak_adapter
        self.mattermost_adapter = mattermost_adapter

    def _generate_slug(self, name: str) -> str:
        """Tạo slug đơn giản từ tên công ty."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        if not slug:
            slug = f"tenant-{uuid.uuid4().hex[:8]}"
        return slug

    async def execute(self, req: OnboardingRequest) -> dict[str, str]:
        logger.info(
            "Bắt đầu xử lý đăng ký Tenant mới",
            extra={"email": req.admin_email, "company": req.company_name},
        )

        # 1. Tạo Tenant ID & Slug
        tenant_id = uuid.uuid4()
        base_slug = self._generate_slug(req.company_name)

        # Đảm bảo slug unique
        slug = base_slug
        counter = 1
        while await self.tenant_repo.get_by_slug(slug) is not None:
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Mặc định sử dụng realm "proteus" chung cho tất cả Tenant (Multi-tenant trong 1 realm)
        # Thuộc tính tenant_id trong JWT sẽ đảm nhiệm việc phân tách dữ liệu.
        keycloak_realm = "proteus"

        # 2. Tạo User trên Keycloak với tenant_id
        try:
            # Thuộc tính này sẽ được mapper map vào token dưới dạng claim "tenant_id"
            user_attributes = {"tenant_id": [str(tenant_id)]}

            # Username mặc định là email, có thể tách riêng tuỳ hệ thống
            keycloak_user_id = await self.keycloak_adapter.create_user(
                realm=keycloak_realm,
                username=req.admin_email,
                email=req.admin_email,
                first_name=req.admin_full_name.split(" ")[0],
                last_name=(
                    " ".join(req.admin_full_name.split(" ")[1:])
                    if " " in req.admin_full_name
                    else ""
                ),
                attributes=user_attributes,
            )
        except ValueError as e:
            # User already exists
            logger.warning(
                "Đăng ký thất bại: Email đã tồn tại", extra={"email": req.admin_email}
            )
            raise ValueError("Email đã được sử dụng") from e

        try:
            # 2.5 Gán mattermostId để Mattermost SSO hoạt động cho owner mới.
            try:
                await self.keycloak_adapter.set_user_attributes(
                    realm=keycloak_realm,
                    user_id=keycloak_user_id,
                    attributes={
                        "mattermostId": [str(mattermost_numeric_id(keycloak_user_id))]
                    },
                )
            except Exception:
                logger.warning(
                    "Không thể gán mattermostId cho owner mới",
                    extra={"user_id": keycloak_user_id},
                )

            # 3. Đặt mật khẩu cho User
            await self.keycloak_adapter.set_user_password(
                realm=keycloak_realm,
                user_id=keycloak_user_id,
                password=req.admin_password,
            )

            # 4. Gán role tenant_admin
            await self.keycloak_adapter.assign_role_to_user(
                realm=keycloak_realm, user_id=keycloak_user_id, role_name="tenant_admin"
            )

            # 5. Lưu Tenant vào Database
            # C10: chống race slug — DB có UNIQUE(slug), catch IntegrityError và
            # retry với suffix thay vì check-then-insert (TOCTOU).
            from sqlalchemy.exc import IntegrityError as _IntegrityError

            session = getattr(self.tenant_repo, "_session", None) or getattr(
                self.user_repo, "_session", None
            )

            _attempt = 0
            while True:
                tenant_entity = TenantEntity(
                    id=tenant_id,
                    name=req.company_name,
                    slug=slug,
                    keycloak_realm=keycloak_realm,
                    is_active=True,
                )
                try:
                    if session is not None and hasattr(session, "begin_nested"):
                        async with session.begin_nested():
                            await self.tenant_repo.create(tenant_entity)
                    else:
                        await self.tenant_repo.create(tenant_entity)
                    break
                except _IntegrityError:
                    if (
                        session is not None
                        and hasattr(session, "rollback")
                        and not hasattr(session, "begin_nested")
                    ):
                        await session.rollback()
                    _attempt += 1
                    if _attempt >= 3:
                        raise ValueError(
                            "Tên tổ chức vừa được đăng ký, vui lòng thử lại."
                        )
                    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

            # 5.5 Tạo Keycloak Group tenant_{slug} và gán user vào group
            try:
                if hasattr(self.keycloak_adapter, "create_tenant_group"):
                    group_name = f"tenant_{slug}"
                    await self.keycloak_adapter.create_tenant_group(
                        realm=keycloak_realm,
                        group_name=group_name,
                    )
                    if hasattr(self.keycloak_adapter, "get_group_by_name") and hasattr(
                        self.keycloak_adapter, "add_user_to_group"
                    ):
                        group_id = await self.keycloak_adapter.get_group_by_name(
                            realm=keycloak_realm,
                            group_name=group_name,
                        )
                        if group_id:
                            await self.keycloak_adapter.add_user_to_group(
                                realm=keycloak_realm,
                                user_id=keycloak_user_id,
                                group_id=group_id,
                            )
            except Exception as grp_err:
                logger.warning(
                    "Không thể tạo/gán Keycloak group tenant_%s: %s", slug, grp_err
                )

            # Thiết lập session tenant context để vượt qua RLS WITH CHECK (#728)
            from app.infrastructure.database import set_session_tenant

            _active_sess = getattr(self.user_repo, "_session", None) or getattr(
                self.tenant_repo, "_session", None
            )
            if _active_sess is not None:
                await set_session_tenant(_active_sess, tenant_id)
            else:
                from app.infrastructure.database import current_tenant_id as _tid_ctx

                _tid_ctx.set(str(tenant_id))

            # 6. Lưu User vào Database
            user_entity = UserEntity(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                keycloak_id=uuid.UUID(keycloak_user_id),
                email=req.admin_email,
                full_name=req.admin_full_name,
                is_active=True,
            )
            # user_repo dùng upsert method
            await self.user_repo.upsert(
                {
                    "id": user_entity.id,
                    "tenant_id": user_entity.tenant_id,
                    "keycloak_id": user_entity.keycloak_id,
                    "email": user_entity.email,
                    "full_name": user_entity.full_name,
                    "is_active": user_entity.is_active,
                }
            )

            await self.user_repo.commit()

            # 7. Tạo Mattermost team riêng cho tenant + đưa owner vào team.
            # Best-effort: chat lỗi/không cấu hình thì chỉ warning, KHÔNG chặn signup.
            if self.mattermost_adapter is not None:
                try:
                    from app.core.use_cases.tenant_onboarding import (
                        ensure_tenant_mattermost_team,
                    )

                    team_cfg = await ensure_tenant_mattermost_team(
                        self.tenant_repo, self.mattermost_adapter, tenant_id
                    )
                    # M17: sanitize username MM về ^[a-z0-9._-]+$.
                    username = (
                        re.sub(
                            r"[^a-z0-9._-]+",
                            "-",
                            req.admin_email.split("@")[0].lower(),
                        )
                        .strip(".-")[:64]
                        .strip(".-")
                        or f"user-{uuid.uuid4().hex[:8]}"
                    )
                    await self.mattermost_adapter.ensure_user_in_team_by_email(
                        team_id=team_cfg["team_id"],
                        email=req.admin_email,
                        username=username,
                        password=secrets.token_urlsafe(24),
                        auth_service="gitlab",
                        auth_data=str(mattermost_numeric_id(keycloak_user_id)),
                    )
                    logger.info(
                        "Đã tạo Mattermost team cho tenant mới",
                        extra={
                            "tenant_id": str(tenant_id),
                            "team": team_cfg["team_name"],
                        },
                    )
                except Exception as e:
                    logger.warning(
                        "Bỏ qua tạo Mattermost team cho tenant %s: %s", slug, e
                    )

            if hasattr(self.tenant_repo, "commit"):
                await self.tenant_repo.commit()
            elif hasattr(self.user_repo, "commit"):
                await self.user_repo.commit()

            logger.info(
                "Đăng ký Tenant thành công",
                extra={"tenant_id": str(tenant_id), "keycloak_id": keycloak_user_id},
            )

            return {
                "tenant_id": str(tenant_id),
                "slug": slug,
                "user_id": keycloak_user_id,
                "message": "Đăng ký thành công",
            }
        except Exception as e:
            if keycloak_user_id and hasattr(self.keycloak_adapter, "delete_user"):
                try:
                    await self.keycloak_adapter.delete_user(
                        realm=keycloak_realm, user_id=keycloak_user_id
                    )
                    logger.info(
                        "Rollback: Đã xóa user Keycloak %s sau lỗi onboarding",
                        keycloak_user_id,
                    )
                except Exception as del_err:
                    logger.warning("Không thể rollback xóa user Keycloak: %s", del_err)
            raise
