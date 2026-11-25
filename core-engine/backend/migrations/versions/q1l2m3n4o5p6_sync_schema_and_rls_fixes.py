# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""sync schema drift, fix outbox trigger RLS, and harden ai_sessions/ai_messages RLS

Revision ID: q1l2m3n4o5p6
Revises: p0k1l2m3n4o5
Create Date: 2026-11-25

Fixes:
- Issue #879: Sync missing ORM columns (`ai_commands.raw_input`, `ai_commands.parsed_dsl`,
  `audit_logs.details`), indexes (`ai_sessions`, `ai_messages`, `plugin_schema_migrations`),
  nullability (`plugins.category`), and constraints (`tenants.uq_tenants_slug`,
  `users_tenant_id_email_key`, `user_roles_user_role_key`, `plugin_schema_migrations` FKs)
  so `alembic check` reports zero drift on PostgreSQL 16 + PostGIS.
- Issue #881: Harden `context.fn_generic_outbox_notify()` with `SECURITY DEFINER` and safe
  `set_config('app.current_tenant_id', v_tenant_id::text, true)` when session setting is
  unset so n8n / background writes never fail `FORCE ROW LEVEL SECURITY` on `context_outbox`.
- Issue #883: Use `NULLIF(current_setting('app.current_tenant_id', true), '')::uuid` and
  `__system__` support in RLS policies on `ai_sessions` and `ai_messages`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "q1l2m3n4o5p6"
down_revision: str | None = "p0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Missing columns on ai_commands & audit_logs (#879)
    op.execute("ALTER TABLE ai_commands ADD COLUMN IF NOT EXISTS raw_input TEXT;")
    op.execute("ALTER TABLE ai_commands ADD COLUMN IF NOT EXISTS parsed_dsl JSONB;")
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS details JSONB;")

    # 2. plugins.category NOT NULL alignment with PluginModel (#879)
    op.execute("UPDATE plugins SET category = 'Utilities' WHERE category IS NULL;")
    op.execute("ALTER TABLE plugins ALTER COLUMN category SET DEFAULT 'Utilities';")
    op.execute("ALTER TABLE plugins ALTER COLUMN category SET NOT NULL;")

    # 3. Align tenants slug uniqueness with TenantModel (ix_tenants_slug unique index)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_slug ON tenants (slug);")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS uq_tenants_slug;")

    # 4. Ensure UniqueConstraints on users & user_roles (#879)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'users_tenant_id_email_key'
            ) THEN
                ALTER TABLE users
                    ADD CONSTRAINT users_tenant_id_email_key UNIQUE (tenant_id, email);
            END IF;
        END $$;
        """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'user_roles_user_role_key'
            ) THEN
                ALTER TABLE user_roles
                    ADD CONSTRAINT user_roles_user_role_key UNIQUE (user_id, role_id);
            END IF;
        END $$;
        """)

    # 5. Missing BaseModel / SoftDeleteMixin indexes on ai_sessions & ai_messages (#879)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_sessions_id ON ai_sessions (id);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_sessions_deleted_at ON ai_sessions (deleted_at);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_messages_id ON ai_messages (id);")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_messages_deleted_at ON ai_messages (deleted_at);"
    )

    # 6. Align plugin_schema_migrations indexes & ForeignKeys (#879)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_plugin_schema_migrations_tenant_plugin "
        "ON plugin_schema_migrations (tenant_id, plugin_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_plugin_schema_migrations_tenant_id "
        "ON plugin_schema_migrations (tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_plugin_schema_migrations_plugin_id "
        "ON plugin_schema_migrations (plugin_id);"
    )
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'plugin_schema_migrations'
                  AND c.contype = 'f'
                  AND c.conname = 'plugin_schema_migrations_tenant_id_fkey'
            ) THEN
                ALTER TABLE plugin_schema_migrations
                    ADD CONSTRAINT plugin_schema_migrations_tenant_id_fkey
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'plugin_schema_migrations'
                  AND c.contype = 'f'
                  AND c.conname = 'plugin_schema_migrations_plugin_id_fkey'
            ) THEN
                ALTER TABLE plugin_schema_migrations
                    ADD CONSTRAINT plugin_schema_migrations_plugin_id_fkey
                    FOREIGN KEY (plugin_id) REFERENCES plugins(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """)

    # 7. Fix RLS policies on ai_sessions & ai_messages against empty string UUID cast (#883)
    op.execute("ALTER TABLE ai_sessions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ai_sessions FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON ai_sessions;")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ai_sessions ON ai_sessions;"
    )
    op.execute("""
        CREATE POLICY tenant_isolation_policy_ai_sessions ON ai_sessions
            FOR ALL TO PUBLIC
            USING (
                current_setting('app.current_tenant_id', true) = '__system__'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.current_tenant_id', true) = '__system__'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
        """)

    op.execute("ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE ai_messages FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON ai_messages;")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ai_messages ON ai_messages;"
    )
    op.execute("""
        CREATE POLICY tenant_isolation_policy_ai_messages ON ai_messages
            FOR ALL TO PUBLIC
            USING (
                current_setting('app.current_tenant_id', true) = '__system__'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
                current_setting('app.current_tenant_id', true) = '__system__'
                OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
        """)

    # 8. Fix context.fn_generic_outbox_notify() for FORCE RLS compatibility (#881)
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
  ELSE
    v_op := 'UPSERT';
    v_entity_id := NEW.id::varchar;
    v_payload := to_jsonb(NEW);
  END IF;

  BEGIN
    v_tenant_id := (v_payload->>'tenant_id')::uuid;
  EXCEPTION WHEN OTHERS THEN
    v_tenant_id := NULL;
  END;

  IF v_tenant_id IS NULL THEN
    BEGIN
      v_tenant_id := NULLIF(current_setting('app.current_tenant_id', true), '')::uuid;
    EXCEPTION WHEN OTHERS THEN
      v_tenant_id := NULL;
    END;
  END IF;

  IF v_tenant_id IS NULL AND TG_TABLE_SCHEMA LIKE 'tenant_%' THEN
    BEGIN
      v_tenant_id := replace(substr(TG_TABLE_SCHEMA, 8), '_', '-')::uuid;
    EXCEPTION WHEN OTHERS THEN
      v_tenant_id := NULL;
    END;
  END IF;

  v_payload := v_payload - ARRAY[
    'password','password_hash','hashed_password','secret','api_key','token',
    'ssn','cccd','cmnd','national_id','identity_card','tax_id',
    'salary','base_salary','net_salary','gross_salary','bonus','allowance',
    'bank_account','bank_number','iban','credit_card'
  ];

  IF v_tenant_id IS NOT NULL THEN
    IF NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL THEN
      PERFORM set_config('app.current_tenant_id', v_tenant_id::text, true);
    END IF;
    INSERT INTO context.context_outbox (
      tenant_id, entity_type, entity_id, op, payload, status,
      created_at, updated_at
    ) VALUES (
      v_tenant_id, v_entity_type, v_entity_id, v_op, v_payload, 'PENDING',
      clock_timestamp(), clock_timestamp()
    );
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = context, public, pg_temp;
        """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE plugin_schema_migrations "
        "DROP CONSTRAINT IF EXISTS plugin_schema_migrations_plugin_id_fkey;"
    )
    op.execute(
        "ALTER TABLE plugin_schema_migrations "
        "DROP CONSTRAINT IF EXISTS plugin_schema_migrations_tenant_id_fkey;"
    )
    op.execute("DROP INDEX IF EXISTS ix_plugin_schema_migrations_plugin_id;")
    op.execute("DROP INDEX IF EXISTS ix_plugin_schema_migrations_tenant_id;")
    op.execute("DROP INDEX IF EXISTS ix_ai_messages_deleted_at;")
    op.execute("DROP INDEX IF EXISTS ix_ai_messages_id;")
    op.execute("DROP INDEX IF EXISTS ix_ai_sessions_deleted_at;")
    op.execute("DROP INDEX IF EXISTS ix_ai_sessions_id;")
    op.execute(
        "ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_user_role_key;"
    )
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_tenant_id_email_key;")
    op.execute("ALTER TABLE plugins ALTER COLUMN category DROP NOT NULL;")
    op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS details;")
    op.execute("ALTER TABLE ai_commands DROP COLUMN IF EXISTS parsed_dsl;")
    op.execute("ALTER TABLE ai_commands DROP COLUMN IF EXISTS raw_input;")
