# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""add generic outbox trigger function

Revision ID: o9j0k1l2m3n4
Revises: n8i9j0k1l2m3
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o9j0k1l2m3n4"
down_revision: str | None = "n8i9j0k1l2m3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION context.fn_generic_outbox_notify()
        RETURNS TRIGGER AS $$
        DECLARE
          v_tenant_id uuid;
          v_entity_id varchar;
          v_payload jsonb;
          v_entity_type varchar;
          v_op varchar;
        BEGIN
          v_entity_type := TG_ARGV[0];
          IF (TG_OP = 'DELETE') THEN
            v_op := 'DELETE';
            v_entity_id := OLD.id::varchar;
            v_payload := to_jsonb(OLD);
            BEGIN
              v_tenant_id := OLD.tenant_id;
            EXCEPTION WHEN OTHERS THEN
              v_tenant_id := NULLIF(current_setting('app.current_tenant_id', true), '')::uuid;
            END;
          ELSE
            v_op := 'UPSERT';
            v_entity_id := NEW.id::varchar;
            v_payload := to_jsonb(NEW);
            BEGIN
              v_tenant_id := NEW.tenant_id;
            EXCEPTION WHEN OTHERS THEN
              v_tenant_id := NULLIF(current_setting('app.current_tenant_id', true), '')::uuid;
            END;
          END IF;

          IF v_tenant_id IS NOT NULL THEN
            INSERT INTO context.context_outbox (
              tenant_id, entity_type, entity_id, op, payload, status, created_at, updated_at
            ) VALUES (
              v_tenant_id, v_entity_type, v_entity_id, v_op, v_payload, 'PENDING', clock_timestamp(), clock_timestamp()
            );
          END IF;

          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS context.fn_generic_outbox_notify() CASCADE;")
