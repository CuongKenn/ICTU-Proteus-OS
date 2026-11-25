#!/usr/bin/env python3
# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kiểm định hợp đồng tĩnh cho toàn bộ Plugin dưới `plugins/*`:
1. Không chứa UTF-8 BOM và parse JSON/YAML hợp lệ cho manifest.yaml, workflows/*.json, dashboards/*.json, ui/*.json.
2. Đường dẫn tham chiếu trong manifest.yaml (seed_file, workflows[].file, dashboards[].file, ui.appsmith_app)
   tồn tại và không vượt khỏi thư mục plugin (anti path-traversal).
3. database.tables trong manifest.yaml khớp với các bảng CREATE TABLE trong seed_data.sql + migrations/*.sql.
4. workflows[].webhook_path (nếu có) khớp với node n8n-nodes-base.webhook trong file workflow tương ứng.
5. Cả 9 plugins đều khai báo khối `ngsi.entities` hợp lệ, `table` nằm trong `database.tables`,
   cột `column` khớp thực tế trong SQL và tuyệt đối không chứa cột cấm PII/nhạy cảm (#871).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[a-zA-Z0-9_]+\.)?\"?([a-zA-Z0-9_]+)\"?",
    re.IGNORECASE,
)

CREATE_TABLE_BLOCK_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[a-zA-Z0-9_]+\.)?\"?([a-zA-Z0-9_]+)\"?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)

SQL_CONSTRAINT_KEYWORDS = frozenset(
    {
        "constraint",
        "primary",
        "foreign",
        "unique",
        "check",
        "exclude",
        "like",
    }
)

PROHIBITED_NGSI_COLUMNS = frozenset(
    {
        "password",
        "hashed_password",
        "secret",
        "salary",
        "base_salary",
        "gross_salary",
        "net_salary",
        "tax_id",
        "tax_code",
        "bank_account",
        "ssn",
        "identity_card",
        "id_card_number",
        "credit_card_info",
        "token",
        "api_key",
        "private_key",
        "access_pin_code",
    }
)

EXPECTED_OFFICIAL_PLUGINS = frozenset(
    {
        "asset-module",
        "crm-module",
        "document-module",
        "finance-module",
        "hr-module",
        "it-helpdesk-module",
        "meeting-module",
        "procurement-module",
        "project-module",
    }
)


def _extract_table_columns(sql_contents: list[str]) -> dict[str, set[str]]:
    """Trích xuất danh sách cột từ các câu lệnh CREATE TABLE trong SQL."""
    table_cols: dict[str, set[str]] = {}
    for sql in sql_contents:
        cleaned = re.sub(r"--[^\n]*", "", sql)
        for match in CREATE_TABLE_BLOCK_RE.finditer(cleaned):
            tname = match.group(1).lower()
            body = match.group(2)
            cols = table_cols.setdefault(tname, set())
            for raw_line in body.splitlines():
                line = raw_line.strip().rstrip(",").strip()
                if not line:
                    continue
                first_token = line.split()[0].strip('"').lower()
                if first_token in SQL_CONSTRAINT_KEYWORDS or first_token.startswith(
                    "("
                ):
                    continue
                if re.match(r"^[a-z_][a-z0-9_]*$", first_token):
                    cols.add(first_token)
    return table_cols


def _check_safe_path(plugin_dir: Path, rel_path: str) -> Path | None:
    if not rel_path or ".." in Path(rel_path).parts:
        return None
    resolved = (plugin_dir / rel_path).resolve()
    if not resolved.is_relative_to(plugin_dir.resolve()):
        return None
    return resolved


def verify_all_plugins(plugins_root: Path) -> list[str]:
    errors: list[str] = []
    plugin_dirs = sorted(
        p
        for p in plugins_root.iterdir()
        if p.is_dir() and (p / "manifest.yaml").exists()
    )
    if not plugin_dirs:
        errors.append(f"Không tìm thấy plugin nào dưới {plugins_root}")
        return errors

    if (
        plugins_root.resolve()
        == (Path(__file__).resolve().parent.parent / "plugins").resolve()
    ):
        found_plugin_names = {p.name for p in plugin_dirs}
        missing_official = sorted(EXPECTED_OFFICIAL_PLUGINS - found_plugin_names)
        if missing_official:
            errors.append(
                f"Thiếu plugin chính thức trong {plugins_root}: {', '.join(missing_official)}"
            )

    for plugin_dir in plugin_dirs:
        manifest_path = plugin_dir / "manifest.yaml"
        manifest_bytes = manifest_path.read_bytes()
        if manifest_bytes.startswith(b"\xef\xbb\xbf"):
            errors.append(f"[{plugin_dir.name}] File chứa UTF-8 BOM: manifest.yaml")
        try:
            manifest = yaml.safe_load(manifest_bytes.decode("utf-8")) or {}
        except Exception as exc:
            errors.append(f"[{plugin_dir.name}] Lỗi đọc manifest.yaml: {exc}")
            continue

        # 1. Kiểm tra UTF-8 BOM và parse JSON trong plugin
        for json_file in plugin_dir.rglob("*.json"):
            if "node_modules" in json_file.parts or "dist" in json_file.parts:
                continue
            raw = json_file.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                errors.append(
                    f"[{plugin_dir.name}] File chứa UTF-8 BOM: {json_file.relative_to(plugin_dir)}"
                )
            try:
                json.loads(raw.decode("utf-8"))
            except Exception as exc:
                errors.append(
                    f"[{plugin_dir.name}] JSON không hợp lệ ({json_file.relative_to(plugin_dir)}): {exc}"
                )

        # 2. Kiểm tra database.seed_file & database.tables vs SQL
        db_cfg = manifest.get("database") or {}
        seed_file = db_cfg.get("seed_file")
        sql_contents: list[str] = []
        if seed_file:
            seed_path = _check_safe_path(plugin_dir, seed_file)
            if seed_path is None or not seed_path.exists():
                errors.append(
                    f"[{plugin_dir.name}] Thiếu hoặc path không hợp lệ cho seed_file: {seed_file}"
                )
            else:
                sql_contents.append(seed_path.read_text(encoding="utf-8"))

        migrations_dir = plugin_dir / "migrations"
        if migrations_dir.exists():
            for mig in sorted(migrations_dir.glob("*.sql")):
                sql_contents.append(mig.read_text(encoding="utf-8"))

        defined_tables: set[str] = set()
        for sql in sql_contents:
            defined_tables.update(
                m.group(1).lower() for m in CREATE_TABLE_RE.finditer(sql)
            )

        for tbl in db_cfg.get("tables") or []:
            tname = (tbl.get("name") if isinstance(tbl, dict) else str(tbl)).lower()
            if tname and tname not in defined_tables:
                errors.append(
                    f"[{plugin_dir.name}] Bảng '{tname}' trong manifest.yaml chưa có CREATE TABLE trong seed/migrations"
                )

        # 3. Kiểm tra workflows[].file & webhook_path
        for wf in manifest.get("workflows") or []:
            wf_file = wf.get("file")
            if not wf_file:
                continue
            wf_path = _check_safe_path(plugin_dir, wf_file)
            if wf_path is None or not wf_path.exists():
                errors.append(f"[{plugin_dir.name}] Thiếu workflow file: {wf_file}")
                continue
            try:
                wf_json = json.loads(wf_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            expected_hook = (wf.get("webhook_path") or "").strip("/")
            is_webhook_trigger = wf.get("trigger") == "webhook"
            if expected_hook or is_webhook_trigger:
                webhook_paths = [
                    str((n.get("parameters") or {}).get("path", "")).strip("/")
                    for n in wf_json.get("nodes") or []
                    if n.get("type") == "n8n-nodes-base.webhook"
                ]
                if is_webhook_trigger and not webhook_paths:
                    errors.append(
                        f"[{plugin_dir.name}] Workflow '{wf_file}' trigger='webhook' nhưng thiếu node 'n8n-nodes-base.webhook'"
                    )
                if expected_hook and expected_hook not in webhook_paths:
                    errors.append(
                        f"[{plugin_dir.name}] Workflow '{wf_file}' webhook_path='{expected_hook}' không khớp node webhook ({webhook_paths})"
                    )

        # 4. Kiểm tra dashboards[].file & ui.appsmith_app
        for db in manifest.get("dashboards") or []:
            db_file = db.get("file")
            if db_file:
                db_path = _check_safe_path(plugin_dir, db_file)
                if db_path is None or not db_path.exists():
                    errors.append(
                        f"[{plugin_dir.name}] Thiếu dashboard file: {db_file}"
                    )

        ui_cfg = manifest.get("ui") or {}
        appsmith_app = ui_cfg.get("appsmith_app")
        if appsmith_app:
            app_path = _check_safe_path(plugin_dir, appsmith_app)
            if app_path is None or not app_path.exists():
                errors.append(
                    f"[{plugin_dir.name}] Thiếu ui.appsmith_app: {appsmith_app}"
                )

        # 5. Kiểm tra hợp đồng NGSI-LD cho toàn bộ plugins (#871)
        declared_tables = {
            (tbl.get("name") if isinstance(tbl, dict) else str(tbl)).lower()
            for tbl in (db_cfg.get("tables") or [])
            if tbl
        }
        table_columns = _extract_table_columns(sql_contents)
        ngsi_cfg = manifest.get("ngsi")
        if not isinstance(ngsi_cfg, dict):
            errors.append(
                f"[{plugin_dir.name}] Thiếu khối khai báo 'ngsi' trong manifest.yaml"
            )
        else:
            ngsi_entities = ngsi_cfg.get("entities")
            if not isinstance(ngsi_entities, list) or len(ngsi_entities) == 0:
                errors.append(
                    f"[{plugin_dir.name}] 'ngsi.entities' phải là danh sách không rỗng"
                )
            else:
                for e_idx, ent in enumerate(ngsi_entities):
                    if not isinstance(ent, dict):
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}] phải là object"
                        )
                        continue
                    ent_table = str(ent.get("table") or "").strip().lower()
                    ent_type = str(ent.get("type") or "").strip()
                    if not ent_table:
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}] thiếu 'table'"
                        )
                    elif ent_table not in declared_tables:
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}].table '{ent_table}' không nằm trong database.tables"
                        )
                    if not ent_type:
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}] thiếu 'type'"
                        )

                    attrs = ent.get("attributes")
                    if not isinstance(attrs, list) or len(attrs) == 0:
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}].attributes phải là danh sách không rỗng"
                        )
                    else:
                        sql_cols = table_columns.get(ent_table, set())
                        for a_idx, attr in enumerate(attrs):
                            if not isinstance(attr, dict):
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}].attributes[{a_idx}] phải là object"
                                )
                                continue
                            col = str(attr.get("column") or "").strip()
                            target = str(attr.get("target") or "").strip()
                            if not col or not target:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}].attributes[{a_idx}] thiếu 'column' hoặc 'target'"
                                )
                                continue
                            if (
                                col.lower() in PROHIBITED_NGSI_COLUMNS
                                or target.lower() in PROHIBITED_NGSI_COLUMNS
                            ):
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] chứa cột cấm PII/nhạy cảm: '{col}' -> '{target}'"
                                )
                            if sql_cols and col.lower() not in sql_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] cột '{col}' không tồn tại trong CREATE TABLE '{ent_table}'"
                                )

                    rels = ent.get("relationships") or []
                    if not isinstance(rels, list):
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}].relationships phải là danh sách"
                        )
                    else:
                        sql_cols = table_columns.get(ent_table, set())
                        for r_idx, rel in enumerate(rels):
                            if not isinstance(rel, dict):
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}].relationships[{r_idx}] phải là object"
                                )
                                continue
                            r_col = str(rel.get("column") or "").strip()
                            r_target = str(rel.get("target") or "").strip()
                            r_etype = str(rel.get("entity_type") or "").strip()
                            if not r_col or not r_target or not r_etype:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}].relationships[{r_idx}] thiếu 'column', 'target' hoặc 'entity_type'"
                                )
                                continue
                            if r_col.lower() in PROHIBITED_NGSI_COLUMNS:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] relationship chứa cột cấm PII: '{r_col}'"
                                )
                            if sql_cols and r_col.lower() not in sql_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] relationship cột '{r_col}' không tồn tại trong CREATE TABLE '{ent_table}'"
                                )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    plugins_root = repo_root / "plugins"
    errors = verify_all_plugins(plugins_root)
    if errors:
        print(f"Found {len(errors)} plugin contract error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("All plugin contracts verified successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
