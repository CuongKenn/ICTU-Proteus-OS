# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""create context schema and tables

Revision ID: n8i9j0k1l2m3
Revises: m7h8i9j0k1l2
Create Date: 2026-11-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n8i9j0k1l2m3"
down_revision: str | None = "m7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tạo schema context
    op.execute("CREATE SCHEMA IF NOT EXISTS context;")

    # Cấp quyền cho app_user nếu role tồn tại
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT USAGE ON SCHEMA context TO app_user;
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA context TO app_user;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA context TO app_user;
            ALTER DEFAULT PRIVILEGES IN SCHEMA context GRANT ALL ON TABLES TO app_user;
            ALTER DEFAULT PRIVILEGES IN SCHEMA context GRANT ALL ON SEQUENCES TO app_user;
          END IF;
        END $$;
        """)

    # 2. Tạo bảng context.context_outbox
    op.execute("""
        CREATE TABLE IF NOT EXISTS context.context_outbox (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            entity_type VARCHAR(128) NOT NULL,
            entity_id VARCHAR(255) NOT NULL,
            op VARCHAR(32) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
            retry_count INT NOT NULL DEFAULT 0,
            idempotency_key VARCHAR(255) UNIQUE,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
        );
        """)

    # Indexes cho context_outbox
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_worker 
        ON context.context_outbox (status, created_at) 
        WHERE status = 'PENDING';
        """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_tenant_entity 
        ON context.context_outbox (tenant_id, entity_type, entity_id);
        """)

    # 3. Tạo bảng context.entity_state
    op.execute("""
        CREATE TABLE IF NOT EXISTS context.entity_state (
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            entity_id VARCHAR(255) NOT NULL,
            type VARCHAR(128) NOT NULL,
            payload JSONB NOT NULL,
            location geography(Point, 4326),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (tenant_id, entity_id)
        );
        """)

    # Indexes cho entity_state
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_state_location 
        ON context.entity_state USING GIST (location);
        """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_state_type 
        ON context.entity_state (tenant_id, type);
        """)

    # 4. Tạo bảng context.sync_cursor
    op.execute("""
        CREATE TABLE IF NOT EXISTS context.sync_cursor (
            consumer_id VARCHAR(128) NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            last_event_id VARCHAR(255) NOT NULL,
            last_synced_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (consumer_id, tenant_id)
        );
        """)

    # 5. Tạo bảng context.subscriptions
    op.execute("""
        CREATE TABLE IF NOT EXISTS context.subscriptions (
            subscription_id VARCHAR(255) PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            entity_type VARCHAR(128) NOT NULL,
            endpoint VARCHAR(512) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
        );
        """)

    # 6. Thiết lập Row-Level Security (RLS) bảo vệ phân tách đa tenant (#826)
    tables = ["context_outbox", "entity_state", "sync_cursor", "subscriptions"]
    for tbl in tables:
        op.execute(f"ALTER TABLE context.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE context.{tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies 
                WHERE schemaname = 'context' 
                  AND tablename = '{tbl}' 
                  AND policyname = 'tenant_isolation_policy_{tbl}'
              ) THEN
                CREATE POLICY tenant_isolation_policy_{tbl} ON context.{tbl}
                  FOR ALL TO PUBLIC USING (
                    current_setting('app.current_tenant_id', true) = '__system__'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                    OR tenant_id = NULLIF(current_setting('hasura.user', true)::jsonb ->> 'x-hasura-tenant-id', '')::uuid
                  )
                  WITH CHECK (
                    current_setting('app.current_tenant_id', true) = '__system__'
                    OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
                    OR tenant_id = NULLIF(current_setting('hasura.user', true)::jsonb ->> 'x-hasura-tenant-id', '')::uuid
                  );
              END IF;
            END $$;
            """)


def downgrade() -> None:
    tables = ["subscriptions", "sync_cursor", "entity_state", "context_outbox"]
    for tbl in tables:
        op.execute(f"DROP TABLE IF EXISTS context.{tbl} CASCADE;")
    op.execute("DROP SCHEMA IF EXISTS context CASCADE;")
