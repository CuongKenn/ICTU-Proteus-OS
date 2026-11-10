# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.repositories.base import AbstractHRLeaveRepository

# Định nghĩa cấu trúc động cho bảng hr_leave_requests (không đưa vào models.py để tránh Alembic)
dynamic_metadata = MetaData()
hr_leave_requests_table = Table(
    "hr_leave_requests",
    dynamic_metadata,
    Column("employee_id", String),
    Column("created_at", DateTime(timezone=True)),
    Column("days_count", Integer),
    Column("status", String),
)


class SQLAlchemyHRLeaveRepository(AbstractHRLeaveRepository):
    """Adapter: Implement HR Leave Repository dùng SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_leaves_older_than(self, days: int) -> list[dict] | None:
        # Quét các tenant schema chứa bảng hr_leave_requests (#735)
        check_table = await self._session.execute(
            text(
                "SELECT table_schema FROM information_schema.tables WHERE table_name = 'hr_leave_requests'"
            )
        )
        schemas = check_table.scalars().all()
        if not schemas:
            return None

        now = datetime.now(UTC)
        day_ago = now - timedelta(days=days)
        all_leaves: list[dict] = []

        for schema in schemas:
            safe_schema = "".join(c for c in str(schema) if c.isalnum() or c == "_")
            if not safe_schema:
                continue
            try:
                res_leaves = await self._session.execute(
                    text(
                        f'SELECT employee_id, created_at, days_count, status FROM "{safe_schema}".hr_leave_requests '
                        f"WHERE status = 'pending' AND created_at < :day_ago"
                    ),
                    {"day_ago": day_ago},
                )
                for row in res_leaves.mappings().all():
                    d = dict(row)
                    d["requested_by"] = d.get("employee_id") or d.get(
                        "issued_by_user_id"
                    )
                    d["issued_by_user_id"] = d["requested_by"]
                    all_leaves.append(d)
            except Exception:
                continue

        return all_leaves

    async def count_leaves_spike(self) -> dict | None:
        # Tính spike thống kê trên toàn bộ tenant schemas (#735)
        check_table = await self._session.execute(
            text(
                "SELECT table_schema FROM information_schema.tables WHERE table_name = 'hr_leave_requests'"
            )
        )
        schemas = check_table.scalars().all()
        if not schemas:
            return None
        now = datetime.now(UTC)
        recent_since = now - timedelta(days=7)
        base_since = now - timedelta(days=35)
        total_recent = 0
        total_base = 0

        for schema in schemas:
            safe_schema = "".join(c for c in str(schema) if c.isalnum() or c == "_")
            if not safe_schema:
                continue
            try:
                recent = (
                    await self._session.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{safe_schema}".hr_leave_requests '
                            f"WHERE created_at >= :since"
                        ),
                        {"since": recent_since},
                    )
                ).scalar() or 0
                base = (
                    await self._session.execute(
                        text(
                            f'SELECT COUNT(*) FROM "{safe_schema}".hr_leave_requests '
                            f"WHERE created_at >= :bstart AND created_at < :bend"
                        ),
                        {"bstart": base_since, "bend": recent_since},
                    )
                ).scalar() or 0
                total_recent += recent
                total_base += base
            except Exception:
                continue

        baseline_daily_avg = total_base / 28
        ratio = (
            (total_recent / 7 / baseline_daily_avg) if baseline_daily_avg > 0 else 0.0
        )
        return {
            "recent": int(total_recent),
            "baseline_daily_avg": round(baseline_daily_avg, 2),
            "ratio": round(ratio, 2),
        }
