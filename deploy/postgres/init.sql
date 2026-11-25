-- Copyright (c) 2026 CuongKenn & ICTU Team
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- Proteus OS — PostgreSQL Core Schema Initialization
-- File này chạy tự động khi container PostgreSQL khởi động lần đầu.
-- Đồng bộ 100% với ORM (`app/infrastructure/models.py`) và Alembic head `q1l2m3n4o5p6`.

-- ─────────────────────────────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Full-text search support
CREATE EXTENSION IF NOT EXISTS "postgis";  -- Spatial queries and geometry support (Lớp 3)

-- Role dùng trong RLS policy của bảng plugin và kết nối app (Issue #690).
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user WITH LOGIN PASSWORD 'app_user_password';
  ELSE
    ALTER ROLE app_user WITH LOGIN;
  END IF;
END $$;

DO $$
DECLARE
  current_db text := current_database();
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO app_user', current_db);
END $$;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

-- ─────────────────────────────────────────────────────────────
-- SCHEMA SEPARATION
-- Mỗi service OSS có schema riêng để tránh xung đột với Core
-- ─────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS keycloak;
CREATE SCHEMA IF NOT EXISTS n8n;
CREATE SCHEMA IF NOT EXISTS mattermost;
CREATE SCHEMA IF NOT EXISTS context;

GRANT USAGE ON SCHEMA context TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA context TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA context TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA context GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA context GRANT ALL ON SEQUENCES TO app_user;

-- ─────────────────────────────────────────────────────────────
-- BẢNG: TENANTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              VARCHAR(255) NOT NULL,
    slug              VARCHAR(255) NOT NULL,
    domain            VARCHAR(255),
    keycloak_realm    VARCHAR(255) NOT NULL,
    plan              VARCHAR(50)  NOT NULL DEFAULT 'free',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    notify_channel_id VARCHAR(255),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_tenants_id ON tenants(id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_slug ON tenants(slug);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tenants_domain ON tenants(domain);
CREATE INDEX IF NOT EXISTS ix_tenants_deleted_at ON tenants(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: USERS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    keycloak_id        UUID NOT NULL,
    email              VARCHAR(255) NOT NULL,
    full_name          VARCHAR(255) NOT NULL,
    avatar_url         VARCHAR(1024),
    mattermost_user_id VARCHAR(255),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at      TIMESTAMPTZ,
    joined_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at         TIMESTAMPTZ,
    CONSTRAINT users_tenant_id_email_key UNIQUE (tenant_id, email)
);

CREATE INDEX IF NOT EXISTS ix_users_id ON users(id);
CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_keycloak_id ON users(keycloak_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: PLUGINS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS plugins (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code_name          VARCHAR(255) NOT NULL,
    display_name       VARCHAR(255) NOT NULL,
    description        TEXT,
    version            VARCHAR(50)  NOT NULL,
    author             VARCHAR(255) NOT NULL,
    license            VARCHAR(50)  NOT NULL DEFAULT 'AGPL-3.0',
    icon_url           VARCHAR(1024),
    manifest_url       VARCHAR(1024) NOT NULL,
    is_official        BOOLEAN NOT NULL DEFAULT FALSE,
    download_count     INTEGER NOT NULL DEFAULT 0,
    category           VARCHAR(100) NOT NULL DEFAULT 'Utilities',
    tags               VARCHAR[] DEFAULT '{}',
    screenshots        JSONB DEFAULT '[]',
    long_description   TEXT,
    credentials_schema JSONB DEFAULT '[]',
    homepage_url       VARCHAR(1024),
    published_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_plugins_id ON plugins(id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_plugins_code_name ON plugins(code_name);
CREATE INDEX IF NOT EXISTS ix_plugins_category ON plugins(category);
CREATE INDEX IF NOT EXISTS ix_plugins_deleted_at ON plugins(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: TENANT_PLUGINS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_plugins (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plugin_id            UUID NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    status               VARCHAR(50) NOT NULL DEFAULT 'INSTALLING',
    installed_version    VARCHAR(50) NOT NULL,
    config_override      JSONB DEFAULT '{}',
    install_error_log    TEXT,
    installed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    install_steps_log    JSONB DEFAULT '[]',
    credential_ids       JSONB DEFAULT '[]',
    install_task_id      UUID,
    upgrade_task_id      UUID,
    installed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at           TIMESTAMPTZ,
    CONSTRAINT uq_tenant_plugin UNIQUE (tenant_id, plugin_id)
);

CREATE INDEX IF NOT EXISTS ix_tenant_plugins_id ON tenant_plugins(id);
CREATE INDEX IF NOT EXISTS ix_tenant_plugins_tenant_id ON tenant_plugins(tenant_id);
CREATE INDEX IF NOT EXISTS ix_tenant_plugins_plugin_id ON tenant_plugins(plugin_id);
CREATE INDEX IF NOT EXISTS ix_tenant_plugins_deleted_at ON tenant_plugins(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: PLUGIN_SCHEMA_MIGRATIONS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS plugin_schema_migrations (
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plugin_id   UUID NOT NULL REFERENCES plugins(id) ON DELETE CASCADE,
    version     VARCHAR(50) NOT NULL,
    filename    VARCHAR(255) NOT NULL,
    checksum    VARCHAR(64) NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_plugin_schema_migrations PRIMARY KEY (tenant_id, plugin_id, version)
);
CREATE INDEX IF NOT EXISTS idx_plugin_schema_migrations_tenant_plugin
    ON plugin_schema_migrations (tenant_id, plugin_id);
CREATE INDEX IF NOT EXISTS ix_plugin_schema_migrations_tenant_id
    ON plugin_schema_migrations (tenant_id);
CREATE INDEX IF NOT EXISTS ix_plugin_schema_migrations_plugin_id
    ON plugin_schema_migrations (plugin_id);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: ROLES
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        UUID REFERENCES tenants(id) ON DELETE CASCADE,
    plugin_code_name VARCHAR(255),
    name             VARCHAR(255) NOT NULL,
    display_name     VARCHAR(255) NOT NULL,
    description      TEXT,
    is_system_role   BOOLEAN NOT NULL DEFAULT FALSE,
    permissions      JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_roles_id ON roles(id);
CREATE INDEX IF NOT EXISTS ix_roles_tenant_id ON roles(tenant_id);
CREATE INDEX IF NOT EXISTS ix_roles_plugin_code_name ON roles(plugin_code_name);
CREATE INDEX IF NOT EXISTS ix_roles_deleted_at ON roles(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: USER_ROLES
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_roles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id             UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT user_roles_user_role_key UNIQUE (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS ix_user_roles_id ON user_roles(id);
CREATE INDEX IF NOT EXISTS ix_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS ix_user_roles_role_id ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS ix_user_roles_deleted_at ON user_roles(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: AUDIT_LOGS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_type      VARCHAR(50) NOT NULL,
    action          VARCHAR(255) NOT NULL,
    resource_type   VARCHAR(50) NOT NULL,
    resource_id     UUID,
    payload         JSONB,
    result          JSONB,
    details         JSONB,
    status          VARCHAR(50) NOT NULL DEFAULT 'success',
    ip_address      VARCHAR(45),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs(id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_deleted_at ON audit_logs(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: AI_COMMANDS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_commands (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    issued_by_user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dsl_version           VARCHAR(50) NOT NULL DEFAULT '1.0',
    raw_input             TEXT,
    parsed_dsl            JSONB,
    action                VARCHAR(255) NOT NULL,
    effect                VARCHAR(50) NOT NULL,
    parameters            JSONB,
    dry_run_result        JSONB,
    status                VARCHAR(50) NOT NULL DEFAULT 'PENDING_APPROVAL',
    approved_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    second_approver_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    mattermost_message_id VARCHAR(255),
    approval_deadline     TIMESTAMPTZ,
    execution_result      JSONB,
    approved_at           TIMESTAMPTZ,
    executed_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_ai_commands_id ON ai_commands(id);
CREATE INDEX IF NOT EXISTS ix_ai_commands_tenant_id ON ai_commands(tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_commands_issued_by_user_id ON ai_commands(issued_by_user_id);
CREATE INDEX IF NOT EXISTS ix_ai_commands_status ON ai_commands(status);
CREATE INDEX IF NOT EXISTS ix_ai_commands_deleted_at ON ai_commands(deleted_at);

-- ─────────────────────────────────────────────────────────────
-- BẢNG: AI_SESSIONS & AI_MESSAGES (Conversation Memory)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_ai_sessions_id ON ai_sessions(id);
CREATE INDEX IF NOT EXISTS ix_ai_sessions_tenant_id ON ai_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_sessions_user_id ON ai_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_ai_sessions_deleted_at ON ai_sessions(deleted_at);

CREATE TABLE IF NOT EXISTS ai_messages (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL REFERENCES ai_sessions(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,
    content     TEXT NOT NULL,
    command_id  UUID,
    citations   JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_ai_messages_id ON ai_messages(id);
CREATE INDEX IF NOT EXISTS ix_ai_messages_session_id ON ai_messages(session_id);
CREATE INDEX IF NOT EXISTS ix_ai_messages_tenant_id ON ai_messages(tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_messages_deleted_at ON ai_messages(deleted_at);

-- ───────────────────────────────────────────────────────────────
-- TRIGGER: auto-update updated_at
-- ───────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_plugins_updated_at
    BEFORE UPDATE ON plugins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_tenant_plugins_updated_at
    BEFORE UPDATE ON tenant_plugins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_ai_sessions_updated_at
    BEFORE UPDATE ON ai_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_ai_messages_updated_at
    BEFORE UPDATE ON ai_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ─────────────────────────────────────────────────────────────
-- ROW-LEVEL SECURITY (RLS) CHO CORE TABLES
-- ─────────────────────────────────────────────────────────────
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_plugins ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_plugins FORCE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_commands FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_messages FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_users ON users
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_tenant_plugins ON tenant_plugins
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_roles ON roles
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_audit_logs ON audit_logs
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_ai_commands ON ai_commands
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_ai_sessions ON ai_sessions
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

CREATE POLICY tenant_isolation_policy_ai_messages ON ai_messages
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

-- ─────────────────────────────────────────────────────────────
-- BẢNG: TENANT_INTEGRATIONS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenant_integrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider        VARCHAR(50) NOT NULL,
    config          JSONB NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_tenant_integrations_id ON tenant_integrations(id);
CREATE INDEX IF NOT EXISTS ix_tenant_integrations_tenant_id ON tenant_integrations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_tenant_integrations_deleted_at ON tenant_integrations(deleted_at);

ALTER TABLE tenant_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_integrations FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_tenant_integrations ON tenant_integrations
    FOR ALL TO PUBLIC USING (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    )
    WITH CHECK (
        current_setting('app.current_tenant_id', true) = '__system__'
        OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
    );

-- ─────────────────────────────────────────────────────────────
-- LỚP 3 — CONTEXT BROKER, DIGITAL TWIN & REALTIME TABLES
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS context.context_outbox (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type     VARCHAR(128) NOT NULL,
    entity_id       VARCHAR(255) NOT NULL,
    op              VARCHAR(32) NOT NULL,
    payload         JSONB NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    retry_count     INT NOT NULL DEFAULT 0,
    idempotency_key VARCHAR(255) UNIQUE,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_worker ON context.context_outbox (status, created_at) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_outbox_tenant_entity ON context.context_outbox (tenant_id, entity_type, entity_id);

ALTER TABLE context.context_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE context.context_outbox FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_context_outbox ON context.context_outbox
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

CREATE TABLE IF NOT EXISTS context.entity_state (
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_id       VARCHAR(255) NOT NULL,
    type            VARCHAR(128) NOT NULL,
    payload         JSONB NOT NULL,
    location        GEOGRAPHY(Point, 4326),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_state_location ON context.entity_state USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_entity_state_type ON context.entity_state (tenant_id, type);

ALTER TABLE context.entity_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE context.entity_state FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_entity_state ON context.entity_state
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

CREATE TABLE IF NOT EXISTS context.sync_cursor (
    consumer_id     VARCHAR(128) NOT NULL,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    last_event_id   VARCHAR(255) NOT NULL,
    last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (consumer_id, tenant_id)
);

ALTER TABLE context.sync_cursor ENABLE ROW LEVEL SECURITY;
ALTER TABLE context.sync_cursor FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_sync_cursor ON context.sync_cursor
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

CREATE TABLE IF NOT EXISTS context.subscriptions (
    subscription_id VARCHAR(255) PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type     VARCHAR(128) NOT NULL,
    endpoint        VARCHAR(512) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE context.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE context.subscriptions FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy_subscriptions ON context.subscriptions
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

-- Trigger function generic ghi nhận outbox tự động khi thực thể thay đổi (#881)
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
      tenant_id, entity_type, entity_id, op, payload, status, created_at, updated_at
    ) VALUES (
      v_tenant_id, v_entity_type, v_entity_id, v_op, v_payload, 'PENDING', clock_timestamp(), clock_timestamp()
    );
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = context, public, pg_temp;

-- ─────────────────────────────────────────────────────────────
-- ALEMBIC VERSION STAMP (#879)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num)
VALUES ('q1l2m3n4o5p6')
ON CONFLICT (version_num) DO NOTHING;
