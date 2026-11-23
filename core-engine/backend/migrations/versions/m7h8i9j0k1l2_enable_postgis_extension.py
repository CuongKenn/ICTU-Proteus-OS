# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""enable postgis extension

Revision ID: m7h8i9j0k1l2
Revises: l6g7h8i9j0k1
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7h8i9j0k1l2"
down_revision: str | None = "l6g7h8i9j0k1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Bật extension postgis một cách an toàn và idempotent
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")


def downgrade() -> None:
    # Downgrade an toàn: chỉ drop extension nếu không có bảng/cột nào đang phụ thuộc
    conn = op.get_bind()
    # Kiểm tra xem có cột geography/geometry nào đang tồn tại không
    res = conn.execute(sa.text("""
            SELECT count(*) 
            FROM information_schema.columns 
            WHERE udt_name IN ('geometry', 'geography') 
              AND table_schema NOT IN ('information_schema', 'pg_catalog');
            """)).scalar()
    if res == 0:
        op.execute("DROP EXTENSION IF EXISTS postgis CASCADE;")
