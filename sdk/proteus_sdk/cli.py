# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proteus OS Plugin SDK CLI (`init` & `validate`).

Hỗ trợ khởi tạo nhanh bộ khung Plugin chuẩn AGPL-3.0-or-later và kiểm định
toàn diện hợp đồng tĩnh (BOM, YAML schema, SQL tables, n8n webhook, Path
Traversal, và PII Gatekeeper trên NGSI-LD Context Broker).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:[a-zA-Z0-9_]+\.)?\"?([a-zA-Z0-9_]+)\"?",
    re.IGNORECASE,
)

REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "name",
    "display_name",
    "version",
    "description",
    "author",
    "license",
)

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        "HR",
        "CRM",
        "Finance",
        "Analytics",
        "Communication",
        "Utilities",
        "IT",
        "Operations",
        "Legal",
        "Other",
    }
)

PROHIBITED_NGSI_PII_COLUMNS: frozenset[str] = frozenset(
    {
        "password",
        "hashed_password",
        "secret",
        "salary",
        "base_salary",
        "gross_salary",
        "net_salary",
        "tax_id",
        "bank_account",
        "ssn",
        "identity_card",
        "cccd",
        "cmnd",
        "token",
        "api_key",
        "private_key",
        "credit_card",
    }
)


def _derive_display_name(code_name: str) -> str:
    words = [w for w in code_name.split("-") if w and w != "module"]
    if not words:
        words = code_name.split("-")
    return " ".join(w.capitalize() for w in words)


def _derive_entity_type(code_name: str) -> str:
    words = [w for w in code_name.split("-") if w and w != "module"]
    if not words:
        words = ["Custom"]
    return "".join(w.capitalize() for w in words) + "Item"


def _write_utf8_no_bom(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def _resolve_safe_subpath(plugin_root: Path, rel_path: str) -> Path | None:
    cleaned = rel_path.strip()
    if not cleaned:
        return None
    candidate_rel = Path(cleaned)
    if candidate_rel.is_absolute() or ".." in candidate_rel.parts:
        return None
    resolved = (plugin_root / candidate_rel).resolve()
    if not resolved.is_relative_to(plugin_root.resolve()):
        return None
    return resolved


def init_plugin(
    code_name: str,
    output_dir: Path,
    display_name: str | None = None,
) -> tuple[int, str]:
    """Khởi tạo bộ khung Plugin chuẩn nguồn mở Proteus OS."""
    clean_code = code_name.strip()
    if not KEBAB_CASE_RE.match(clean_code) or len(clean_code) > 64:
        return (
            1,
            f"[ERROR] Mã plugin '{clean_code}' không hợp lệ "
            "(bắt buộc kebab-case, tối đa 64 ký tự).",
        )

    base_dir = output_dir.resolve()
    target_dir = (base_dir / clean_code).resolve()
    if not target_dir.is_relative_to(base_dir):
        return (1, f"[ERROR] Phát hiện path traversal tại '{target_dir}'.")

    if target_dir.exists() and any(target_dir.iterdir()):
        return (
            1,
            f"[ERROR] Thư mục đích '{target_dir}' đã tồn tại và không rỗng.",
        )

    final_display_name = (
        display_name.strip()
        if display_name and display_name.strip()
        else _derive_display_name(clean_code)
    )
    prefix = clean_code.split("-")[0]
    table_name = f"{prefix}_items"
    webhook_path = f"{clean_code}-items-sync"
    workflow_id = f"wf_{prefix}_items_sync"
    entity_type = _derive_entity_type(clean_code)

    manifest_content = f"""# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Plugin Manifest — {clean_code} ({final_display_name})

name: "{clean_code}"
display_name: "{final_display_name}"
version: "1.0.0"
description: |
  Phân hệ nghiệp vụ {final_display_name} vận hành trên kiến trúc đa thuê bao Proteus OS.
author: "ICTU Open-Source Community"
license: "AGPL-3.0-or-later"
category: "Operations"
is_official: false
tags:
  - "{prefix}"
  - "proteus-sdk"
credentials_schema: []

compatibility:
  proteus_os_min_version: "1.0.0"
  dsl_spec_version: "1.0"

database:
  tables:
    - "{table_name}"
  seed_file: "db/seed_data.sql"
  default_config:
    auto_archive_days: 90

workflows:
  - id: "{workflow_id}"
    file: "workflows/sample_webhook.json"
    name: "{final_display_name} Sync Webhook"
    description: "Xử lý yêu cầu đồng bộ bản ghi qua n8n webhook"
    trigger: "webhook"
    webhook_path: "{webhook_path}"

ui:
  external_url: "${{PLUGINS_MFE_URL}}/{clean_code}"

roles:
  - name: "{prefix}_manager"
    display_name: "{final_display_name} Manager"
    description: "Quản trị toàn quyền dữ liệu phân hệ {final_display_name}"
    permissions:
      - "{prefix}:items:read"
      - "{prefix}:items:write"
      - "{prefix}:items:approve"
  - name: "{prefix}_viewer"
    display_name: "{final_display_name} Viewer"
    description: "Quyền tra cứu chỉ đọc trên phân hệ {final_display_name}"
    permissions:
      - "{prefix}:items:read"

event_subscriptions: []

event_publications:
  - event_type: "{prefix}.item.created"
    description: "Phát sự kiện khi bản ghi nghiệp vụ mới được khởi tạo"
    payload_schema:
      item_id: "uuid"
      code: "string"
      status: "string"

dependencies:
  required: []
  optional: []

ngsi:
  entities:
    - table: "{table_name}"
      type: "{entity_type}"
      id_pattern: "urn:ngsi-ld:{entity_type}:{{tenant}}:{{id}}"
      attributes:
        - column: "item_code"
          target: "itemCode"
          type: "Property"
        - column: "title"
          target: "name"
          type: "Property"
        - column: "status"
          target: "operationalStatus"
          type: "Property"
      relationships: []
"""

    seed_sql_content = f"""-- Copyright (c) 2026 CuongKenn & ICTU Team
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- Seed Data & Initial Schema for {clean_code}

CREATE TABLE IF NOT EXISTS {table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_code VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    notes TEXT,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_{table_name}_tenant_code UNIQUE (tenant_id, item_code)
);

INSERT INTO {table_name} (id, item_code, title, status, tenant_id)
VALUES (
    '10000000-0000-4000-8000-000000000001',
    '{prefix.upper()}-001',
    'Bản ghi mẫu {final_display_name}',
    'ACTIVE',
    current_setting('app.current_tenant_id')::uuid
)
ON CONFLICT (tenant_id, item_code) DO NOTHING;
"""

    migration_sql_content = f"""-- Copyright (c) 2026 CuongKenn & ICTU Team
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- V1.0.0 Initial Migration for {clean_code}

CREATE TABLE IF NOT EXISTS {table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_code VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    notes TEXT,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_{table_name}_tenant_code UNIQUE (tenant_id, item_code)
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_tenant_status
    ON {table_name}(tenant_id, status);
"""

    workflow_obj: dict[str, Any] = {
        "_license": (
            "Copyright (c) 2026 CuongKenn & ICTU Team | "
            "SPDX-License-Identifier: AGPL-3.0-or-later"
        ),
        "name": f"{final_display_name} — Sync Webhook",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "lastNode",
                    "options": {},
                },
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [240, 300],
                "webhookId": f"{clean_code}-webhook",
            },
            {
                "parameters": {
                    "jsCode": (
                        "const body = $('Webhook').first()?.json?.body || {};\n"
                        "return [{ json: { status: 'ok', plugin: '"
                        + clean_code
                        + "', echo: body } }];"
                    )
                },
                "name": "Process Action",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [480, 300],
            },
        ],
        "connections": {
            "Webhook": {
                "main": [
                    [{"node": "Process Action", "type": "main", "index": 0}]
                ]
            }
        },
        "active": False,
        "settings": {},
    }
    workflow_json_content = (
        json.dumps(workflow_obj, ensure_ascii=False, indent=2) + "\n"
    )

    mfe_app_content = f"""// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Micro-Frontend Module — {final_display_name} ({clean_code})
// Styled with Enterprise Swiss Slate CSS tokens & ?embed=1 ready.

import React, {{ useEffect, useState }} from 'react';

interface ItemRow {{
  id: string;
  item_code: string;
  title: string;
  status: string;
}}

export const App: React.FC = () => {{
  const [rows, setRows] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {{
    let active = true;
    fetch('/api/proxy/v1/plugins/{clean_code}/records/{table_name}')
      .then((res) => (res.ok ? res.json() : {{ rows: [] }}))
      .then((data) => {{
        if (active && Array.isArray(data?.rows)) {{
          setRows(data.rows);
        }}
      }})
      .catch(() => undefined)
      .finally(() => {{
        if (active) setLoading(false);
      }});
    return () => {{
      active = false;
    }};
  }}, []);

  return (
    <div
      style={{
        background: 'var(--mfe-bg, #f8fafc)',
        color: 'var(--mfe-text, #0f172a)',
        padding: '1.5rem',
        fontFamily: 'var(--mfe-font-sans, Inter, system-ui, sans-serif)',
      }}
    >
      <div
        style={{
          background: 'var(--mfe-panel, #ffffff)',
          border: '1px solid var(--mfe-line, #e2e8f0)',
          borderRadius: 12,
          padding: '1.25rem 1.5rem',
        }}
      >
        <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>
          {final_display_name}
        </h1>
        <p
          style={{
            margin: '0.35rem 0 1rem',
            color: 'var(--mfe-muted, #64748b)',
            fontSize: '0.875rem',
          }}
        >
          Phân hệ chuẩn Proteus SDK — hỗ trợ đồng bộ đa thuê bao RLS &amp; NGSI-LD.
        </p>
        {{loading ? (
          <div style={{ fontSize: '0.85rem', color: 'var(--mfe-muted, #64748b)' }}>
            Đang tải dữ liệu...
          </div>
        ) : (
          <div style={{ fontSize: '0.85rem' }}>
            Tổng số bản ghi hiện tại: <strong>{{rows.length}}</strong>
          </div>
        )}}
      </div>
    </div>
  );
}};

export default App;
"""

    _write_utf8_no_bom(target_dir / "manifest.yaml", manifest_content)
    _write_utf8_no_bom(target_dir / "db" / "seed_data.sql", seed_sql_content)
    _write_utf8_no_bom(
        target_dir / "migrations" / "V1.0.0__initial.sql", migration_sql_content
    )
    _write_utf8_no_bom(
        target_dir / "workflows" / "sample_webhook.json", workflow_json_content
    )
    _write_utf8_no_bom(target_dir / "frontend" / "src" / "App.tsx", mfe_app_content)

    return (
        0,
        f"[OK] Đã khởi tạo plugin '{clean_code}' "
        f"({final_display_name}) tại {target_dir}",
    )


def validate_plugin(plugin_path: Path) -> tuple[int, list[str]]:
    """Kiểm định toàn diện một Plugin đơn lẻ theo chuẩn Proteus OS."""
    errors: list[str] = []
    root = plugin_path.resolve()

    if not root.exists() or not root.is_dir():
        return (1, [f"Thư mục plugin không tồn tại: {plugin_path}"])

    manifest_file = root / "manifest.yaml"
    if not manifest_file.exists():
        return (1, [f"Thiếu file bắt buộc manifest.yaml tại {root}"])

    # 1. Quét UTF-8 BOM trên tất cả các tệp mã nguồn & cấu hình
    checked_suffixes = {".yaml", ".yml", ".json", ".sql", ".py", ".ts", ".tsx"}
    for fpath in root.rglob("*"):
        if not fpath.is_file():
            continue
        if "node_modules" in fpath.parts or "dist" in fpath.parts:
            continue
        if fpath.suffix.lower() in checked_suffixes:
            raw_bytes = fpath.read_bytes()
            if raw_bytes.startswith(b"\xef\xbb\xbf"):
                rel = fpath.relative_to(root)
                errors.append(f"Phát hiện UTF-8 BOM bị cấm trong file: {rel}")
            if fpath.suffix.lower() == ".json":
                try:
                    json.loads(raw_bytes.decode("utf-8"))
                except Exception as exc:
                    rel = fpath.relative_to(root)
                    errors.append(f"JSON không hợp lệ ({rel}): {exc}")

    # 2. Đọc và kiểm tra cấu trúc YAML của manifest.yaml
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8")
        manifest = yaml.safe_load(manifest_text)
    except Exception as exc:
        return (1, [*errors, f"Không thể đọc/parse manifest.yaml: {exc}"])

    if not isinstance(manifest, dict):
        return (1, [*errors, "manifest.yaml phải là một YAML dictionary hợp lệ."])

    for req_field in REQUIRED_MANIFEST_FIELDS:
        val = manifest.get(req_field)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"manifest.yaml thiếu trường bắt buộc '{req_field}'.")

    plugin_name = str(manifest.get("name") or "").strip()
    if plugin_name and not KEBAB_CASE_RE.match(plugin_name):
        errors.append(
            f"manifest.name '{plugin_name}' phải ở định dạng kebab-case."
        )

    version = str(manifest.get("version") or "").strip()
    if version and not SEMVER_RE.match(version):
        errors.append(
            f"manifest.version '{version}' không tuân thủ chuẩn SemVer (X.Y.Z)."
        )

    category = str(manifest.get("category") or "Utilities")
    if category not in VALID_CATEGORIES:
        errors.append(
            f"manifest.category '{category}' không thuộc danh mục hợp lệ."
        )

    compat = manifest.get("compatibility")
    if not isinstance(compat, dict) or not compat.get("proteus_os_min_version"):
        errors.append(
            "manifest.compatibility thiếu trường 'proteus_os_min_version'."
        )

    # 3. Kiểm tra database.tables, prefix bảng & khớp với SQL
    expected_prefix = (
        f"{plugin_name.split('-')[0]}_" if plugin_name else ""
    )
    db_cfg = manifest.get("database") or {}
    if not isinstance(db_cfg, dict):
        errors.append("manifest.database phải là một object.")
        db_cfg = {}

    raw_tables = db_cfg.get("tables") or []
    declared_tables: list[str] = []
    if not isinstance(raw_tables, list):
        errors.append("database.tables phải là danh sách tên bảng.")
    else:
        for tbl in raw_tables:
            tname = (
                str(tbl.get("name", "")).strip()
                if isinstance(tbl, dict)
                else str(tbl).strip()
            )
            if not tname:
                continue
            declared_tables.append(tname.lower())
            if expected_prefix and not tname.lower().startswith(expected_prefix):
                errors.append(
                    f"Bảng '{tname}' phải bắt đầu bằng tiền tố '{expected_prefix}'."
                )

    sql_chunks: list[str] = []
    seed_rel = db_cfg.get("seed_file")
    if seed_rel is not None:
        seed_path = _resolve_safe_subpath(root, str(seed_rel))
        if seed_path is None:
            errors.append(
                f"Path traversal hoặc đường dẫn không hợp lệ ở seed_file: {seed_rel}"
            )
        elif not seed_path.exists():
            errors.append(f"Không tìm thấy file seed_file: {seed_rel}")
        else:
            sql_chunks.append(seed_path.read_text(encoding="utf-8", errors="replace"))

    migrations_dir = root / "migrations"
    if migrations_dir.exists() and migrations_dir.is_dir():
        for mig_file in sorted(migrations_dir.glob("*.sql")):
            sql_chunks.append(
                mig_file.read_text(encoding="utf-8", errors="replace")
            )

    sql_defined_tables: set[str] = set()
    for chunk in sql_chunks:
        sql_defined_tables.update(
            m.group(1).lower() for m in CREATE_TABLE_RE.finditer(chunk)
        )

    for tbl_lower in declared_tables:
        if tbl_lower not in sql_defined_tables:
            errors.append(
                f"Bảng '{tbl_lower}' khai báo trong database.tables nhưng chưa có "
                "lệnh CREATE TABLE trong seed_data.sql hoặc migrations/*.sql."
            )

    # 4. Kiểm tra workflows, anti path-traversal & khớp webhook_path
    workflows = manifest.get("workflows") or []
    if not isinstance(workflows, list):
        errors.append("manifest.workflows phải là một danh sách.")
    else:
        seen_ids: set[str] = set()
        for idx, wf in enumerate(workflows):
            if not isinstance(wf, dict):
                errors.append(f"workflows[{idx}] phải là một object.")
                continue
            wf_id = wf.get("id")
            if wf_id:
                if wf_id in seen_ids:
                    errors.append(f"workflows[{idx}].id '{wf_id}' bị trùng lặp.")
                seen_ids.add(str(wf_id))

            trigger = str(wf.get("trigger") or "")
            if trigger == "cron" and not wf.get("cron_expression"):
                errors.append(
                    f"workflows[{idx}] có trigger='cron' nhưng thiếu cron_expression."
                )

            wf_rel = wf.get("file")
            if not wf_rel:
                errors.append(f"workflows[{idx}] thiếu trường 'file'.")
                continue

            wf_path = _resolve_safe_subpath(root, str(wf_rel))
            if wf_path is None:
                errors.append(
                    f"Path traversal bị chặn tại workflows[{idx}].file: {wf_rel}"
                )
                continue
            if not wf_path.exists():
                errors.append(f"Thiếu file workflow đã khai báo: {wf_rel}")
                continue

            try:
                wf_json = json.loads(wf_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            expected_hook = str(wf.get("webhook_path") or "").strip("/")
            if trigger == "webhook" or expected_hook:
                webhook_nodes = [
                    str((node.get("parameters") or {}).get("path", "")).strip("/")
                    for node in (wf_json.get("nodes") or [])
                    if isinstance(node, dict)
                    and node.get("type") == "n8n-nodes-base.webhook"
                ]
                if trigger == "webhook" and not webhook_nodes:
                    errors.append(
                        f"Workflow '{wf_rel}' có trigger='webhook' nhưng thiếu node "
                        "'n8n-nodes-base.webhook'."
                    )
                if expected_hook and expected_hook not in webhook_nodes:
                    errors.append(
                        f"Workflow '{wf_rel}' khai báo webhook_path='{expected_hook}' "
                        f"không khớp với node webhook ({webhook_nodes})."
                    )

    # 5. Kiểm tra path traversal trên dashboards & ui.appsmith_app (nếu có)
    for idx, dash in enumerate(manifest.get("dashboards") or []):
        if isinstance(dash, dict) and dash.get("file"):
            dpath = _resolve_safe_subpath(root, str(dash["file"]))
            if dpath is None or not dpath.exists():
                errors.append(
                    f"dashboards[{idx}].file không hợp lệ hoặc thiếu: {dash['file']}"
                )

    ui_cfg = manifest.get("ui")
    if isinstance(ui_cfg, dict) and ui_cfg.get("appsmith_app"):
        ui_path = _resolve_safe_subpath(root, str(ui_cfg["appsmith_app"]))
        if ui_path is None or not ui_path.exists():
            errors.append(
                f"ui.appsmith_app không hợp lệ hoặc thiếu: {ui_cfg['appsmith_app']}"
            )

    # 6. Kiểm tra PII Gatekeeper trên khối ngsi.entities (Chuẩn bảo mật L3-004)
    ngsi_cfg = manifest.get("ngsi")
    if ngsi_cfg is not None:
        if not isinstance(ngsi_cfg, dict):
            errors.append("manifest.ngsi phải là một object.")
        else:
            entities = ngsi_cfg.get("entities") or []
            if not isinstance(entities, list):
                errors.append("ngsi.entities phải là một danh sách.")
            else:
                for e_idx, entity in enumerate(entities):
                    if not isinstance(entity, dict):
                        errors.append(f"ngsi.entities[{e_idx}] phải là object.")
                        continue
                    etable = str(entity.get("table") or "").strip().lower()
                    if not etable:
                        errors.append(
                            f"ngsi.entities[{e_idx}] thiếu trường 'table'."
                        )
                    elif declared_tables and etable not in declared_tables:
                        errors.append(
                            f"ngsi.entities[{e_idx}].table '{etable}' không nằm trong "
                            "database.tables."
                        )

                    if not entity.get("type"):
                        errors.append(
                            f"ngsi.entities[{e_idx}] thiếu trường 'type'."
                        )

                    attrs = entity.get("attributes") or []
                    if not isinstance(attrs, list):
                        errors.append(
                            f"ngsi.entities[{e_idx}].attributes phải là danh sách."
                        )
                        continue

                    for a_idx, attr in enumerate(attrs):
                        if not isinstance(attr, dict):
                            errors.append(
                                f"ngsi.entities[{e_idx}].attributes[{a_idx}] "
                                "phải là object."
                            )
                            continue
                        col_raw = str(attr.get("column") or "").strip()
                        target_raw = str(attr.get("target") or "").strip()
                        if not col_raw or not target_raw:
                            errors.append(
                                f"ngsi.entities[{e_idx}].attributes[{a_idx}] "
                                "yêu cầu đủ 'column' và 'target'."
                            )
                            continue

                        col_lower = col_raw.lower()
                        if col_lower in PROHIBITED_NGSI_PII_COLUMNS:
                            errors.append(
                                f"[PII GATEKEEPER BLOCKED] ngsi.entities[{e_idx}] "
                                f"(table='{etable}'): Cột nhạy cảm PII '{col_raw}' "
                                "bị cấm xuất bản lên NGSI-LD Context Broker (L3-004)."
                            )

    if errors:
        return (1, errors)
    return (0, [])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proteus-sdk",
        description="Bộ công cụ phát triển và kiểm định Plugin nguồn mở Proteus OS.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser(
        "init",
        help="Khởi tạo bộ khung Plugin chuẩn Proteus OS (manifest, SQL, n8n, MFE).",
    )
    init_cmd.add_argument(
        "plugin_code_name",
        help="Mã định danh kebab-case của plugin (VD: lab-asset-module).",
    )
    init_cmd.add_argument(
        "--output-dir",
        default="plugins",
        help="Thư mục gốc chứa plugin được sinh ra (mặc định: plugins).",
    )
    init_cmd.add_argument(
        "--display-name",
        default=None,
        help="Tên hiển thị tiếng Việt/Anh của phân hệ.",
    )

    validate_cmd = subparsers.add_parser(
        "validate",
        help="Kiểm định hợp đồng tĩnh, SQL, Webhook & PII Gatekeeper cho một Plugin.",
    )
    validate_cmd.add_argument(
        "plugin_path",
        help="Đường dẫn tới thư mục plugin cần kiểm định.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        code, message = init_plugin(
            code_name=args.plugin_code_name,
            output_dir=Path(args.output_dir),
            display_name=args.display_name,
        )
        stream = sys.stdout if code == 0 else sys.stderr
        print(message, file=stream)
        return code

    if args.command == "validate":
        target = Path(args.plugin_path)
        code, errs = validate_plugin(target)
        if code == 0:
            print(
                f"[PASS] Plugin '{target.name}' vượt qua toàn bộ "
                "kiểm định hợp đồng & PII Gatekeeper!"
            )
            return 0
        print(
            f"[FAIL] Phát hiện {len(errs)} lỗi hợp đồng tại '{target}':",
            file=sys.stderr,
        )
        for item in errs:
            print(f"  - {item}", file=sys.stderr)
        return 1

    return 1
