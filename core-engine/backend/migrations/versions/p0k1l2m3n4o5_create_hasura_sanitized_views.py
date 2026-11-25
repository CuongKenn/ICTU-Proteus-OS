# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""create sanitized views for hasura filtering sensitive columns

Revision ID: p0k1l2m3n4o5
Revises: o9j0k1l2m3n4
Create Date: 2026-11-23

"""

from collections.abc import Sequence

from alembic import op

revision: str = "p0k1l2m3n4o5"
down_revision: str | None = "o9j0k1l2m3n4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tạo view sanitized trong schema context loại bỏ các cột lương/tài chính/PII
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'hr_employees'
          ) THEN
            CREATE OR REPLACE VIEW context.v_hr_employees_sanitized
            WITH (security_invoker = true, security_barrier = true) AS
            SELECT
              id,
              tenant_id,
              employee_code,
              full_name,
              email,
              department_id,
              position,
              hire_date,
              status,
              created_at,
              updated_at
            FROM public.hr_employees;
          END IF;
        END $$;
        """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS context.v_hr_employees_sanitized CASCADE;")
