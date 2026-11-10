# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""add mattermost_user_id to users

Revision ID: l6g7h8i9j0k1
Revises: k5f6g7h8i9j0
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l6g7h8i9j0k1"
down_revision: str | None = "k5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_cols = [c["name"] for c in inspector.get_columns("users")]
    if "mattermost_user_id" not in user_cols:
        op.add_column(
            "users",
            sa.Column("mattermost_user_id", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("users", "mattermost_user_id")
