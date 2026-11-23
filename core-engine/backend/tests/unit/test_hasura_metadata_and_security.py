# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Hasura GraphQL metadata, Keycloak JWT integration, and Tenant isolation.

Tham chiếu: Issue #840 [L3-501], #841 [L3-502], #842 [L3-503], #843 [L3-504], #844 [L3-505], #845 [L3-506].
"""

import json
from pathlib import Path
import pytest
import yaml


def test_hasura_metadata_files_valid_yaml():
    deploy_dir = Path(__file__).parents[4] / "deploy"
    hasura_dir = deploy_dir / "hasura"
    assert hasura_dir.exists(), "deploy/hasura must exist"

    config_path = hasura_dir / "config.yaml"
    version_path = hasura_dir / "metadata" / "version.yaml"
    databases_path = hasura_dir / "metadata" / "databases" / "databases.yaml"

    assert config_path.exists()
    assert version_path.exists()
    assert databases_path.exists()

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert config["version"] == 3

    with open(version_path, "r", encoding="utf-8") as f:
        version = yaml.safe_load(f)
    assert version["version"] == 3

    with open(databases_path, "r", encoding="utf-8") as f:
        dbs = yaml.safe_load(f)
    assert isinstance(dbs, list)
    assert dbs[0]["name"] == "default"


def test_hasura_tracked_tables_and_tenant_isolation_rules():
    deploy_dir = Path(__file__).parents[4] / "deploy"
    databases_path = deploy_dir / "hasura" / "metadata" / "databases" / "databases.yaml"

    with open(databases_path, "r", encoding="utf-8") as f:
        dbs = yaml.safe_load(f)

    default_db = dbs[0]
    tables = default_db.get("tables", [])
    tracked_names = [t["table"]["name"] for t in tables]

    assert "entity_state" in tracked_names
    assert "context_outbox" in tracked_names
    assert "sync_cursor" in tracked_names
    assert "subscriptions" in tracked_names

    # Check entity_state permissions
    entity_state_entry = next(t for t in tables if t["table"]["name"] == "entity_state")
    perms = entity_state_entry.get("select_permissions", [])
    roles = {p["role"]: p["permission"] for p in perms}

    assert "user" in roles
    assert roles["user"]["filter"] == {"tenant_id": {"_eq": "X-Hasura-Tenant-Id"}}
    assert (
        "tenant_id" not in roles["user"]["columns"]
    )  # Hide internal tenant_id column from plain users

    assert "tenant_admin" in roles
    assert roles["tenant_admin"]["filter"] == {
        "tenant_id": {"_eq": "X-Hasura-Tenant-Id"}
    }

    # Check object relationship to tenants table
    relationships = entity_state_entry.get("object_relationships", [])
    assert any(r["name"] == "tenant" for r in relationships)


def test_keycloak_hasura_claims_scope():
    deploy_dir = Path(__file__).parents[4] / "deploy"
    realm_path = deploy_dir / "keycloak" / "realm-import.json"
    assert realm_path.exists()

    with open(realm_path, "r", encoding="utf-8") as f:
        realm = json.load(f)

    client_scopes = realm.get("clientScopes", [])
    hasura_scope = next((s for s in client_scopes if s["name"] == "hasura"), None)
    assert (
        hasura_scope is not None
    ), "Scope 'hasura' must be configured in Keycloak realm"

    mappers = hasura_scope.get("protocolMappers", [])
    claim_names = [m["config"].get("claim.name") for m in mappers]
    assert "x-hasura-tenant-id" in claim_names
    assert "x-hasura-default-role" in claim_names
    assert "x-hasura-allowed-roles" in claim_names

    default_scopes = realm.get("defaultDefaultClientScopes", [])
    assert "hasura" in default_scopes


def test_sanitized_views_omit_sensitive_columns():
    deploy_dir = Path(__file__).parents[4] / "deploy"
    migration_dir = Path(__file__).parents[2] / "migrations" / "versions"
    sanitized_migrations = list(
        migration_dir.glob("*_create_hasura_sanitized_views.py")
    )
    assert len(sanitized_migrations) == 1

    content = sanitized_migrations[0].read_text(encoding="utf-8")
    assert "v_hr_employees_sanitized" in content
    assert "security_barrier = true" in content

    # Verify sensitive columns are NOT in the view
    assert "base_salary" not in content
    assert "salary" not in content
    assert "bank_account" not in content
