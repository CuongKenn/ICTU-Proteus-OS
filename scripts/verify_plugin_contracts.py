#!/usr/bin/env python3
# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kiểm định hợp đồng tĩnh cho toàn bộ Plugin dưới `plugins/*`:
1. Không chứa UTF-8 BOM và parse JSON/YAML hợp lệ cho manifest.yaml, workflows/*.json, dashboards/*.json, ui/*.json.
2. Đường dẫn tham chiếu trong manifest.yaml (seed_file, workflows[].file, dashboards[].file, ui.appsmith_app)
   tồn tại và không vượt khỏi thư mục plugin (anti path-traversal).
3. database.tables và các cột ngsi.entities trong manifest.yaml được định nghĩa đầy đủ ở CẢ HAI nơi độc lập:
   - db/seed_data.sql (cài mới / fresh install)
   - tập hợp lũy kế migrations/*.sql có version <= manifest.version (nâng cấp / upgrade), và không có file
     migration nào mang version lớn hơn manifest.version (#885).
4. workflows[].webhook_path (nếu có) khớp với node n8n-nodes-base.webhook trong file workflow tương ứng.
5. event_subscriptions tham chiếu đúng source_plugin tồn tại dưới `plugins/` và mọi event_type đăng ký đều
   được khai báo trong event_publications (hoặc events_published) của source_plugin (#885).
6. Cả 9 plugins đều khai báo khối `ngsi.entities` hợp lệ, `table` nằm trong `database.tables`,
   cột `column` khớp thực tế trong SQL và tuyệt đối không chứa cột cấm PII/nhạy cảm (#871, #887).
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

ALTER_ADD_COLUMN_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:[a-zA-Z0-9_]+\.)?\"?([a-zA-Z0-9_]+)\"?\s+"
    r"ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?\"?([a-zA-Z0-9_]+)\"?",
    re.IGNORECASE,
)

MIGRATION_FILE_RE = re.compile(r"^V(\d+\.\d+\.\d+)__.+\.sql$")

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
        "cccd",
        "cmnd",
        "citizen_id",
        "national_id",
        "salary",
        "base_salary",
        "net_salary",
        "gross_salary",
        "bonus",
        "allowance",
        "deduction",
        "tax",
        "tax_code",
        "bank_account",
        "bank_name",
        "password",
        "password_hash",
        "secret",
        "token",
        "api_key",
        "ssn",
        "dob",
        "date_of_birth",
        "phone",
        "personal_email",
        "address_detail",
        "medical_record",
        "fingerprint",
        "biometric",
        "id_card_number",
        "credit_card_info",
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


def _parse_semver(ver_str: str) -> tuple[int, int, int] | None:
    m = re.match(r"^\s*v?(\d+)\.(\d+)\.(\d+)", str(ver_str or ""))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _extract_tables(sql_contents: list[str]) -> set[str]:
    defined: set[str] = set()
    for sql in sql_contents:
        cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        cleaned = re.sub(r"--[^\n]*", "", cleaned)
        defined.update(m.group(1).lower() for m in CREATE_TABLE_RE.finditer(cleaned))
    return defined


def _extract_table_columns(sql_contents: list[str]) -> dict[str, set[str]]:
    """Trích xuất danh sách cột từ CREATE TABLE và ALTER TABLE ... ADD COLUMN."""
    table_cols: dict[str, set[str]] = {}
    for sql in sql_contents:
        cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        cleaned = re.sub(r"--[^\n]*", "", cleaned)
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
        for alter_match in ALTER_ADD_COLUMN_RE.finditer(cleaned):
            tname = alter_match.group(1).lower()
            cname = alter_match.group(2).lower()
            if cname not in SQL_CONSTRAINT_KEYWORDS and re.match(
                r"^[a-z_][a-z0-9_]*$", cname
            ):
                table_cols.setdefault(tname, set()).add(cname)
    return table_cols


def _extract_published_events(manifest: dict) -> set[str]:
    published: set[str] = set()
    raw_pubs = (
        manifest.get("event_publications")
        or manifest.get("events_published")
        or []
    )
    if isinstance(raw_pubs, list):
        for item in raw_pubs:
            if isinstance(item, dict):
                ev = str(item.get("event_type") or item.get("name") or "").strip()
            else:
                ev = str(item or "").strip()
            if ev:
                published.add(ev)
    return published


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

    is_official_repo = (
        plugins_root.resolve()
        == (Path(__file__).resolve().parent.parent / "plugins").resolve()
    )
    if is_official_repo:
        found_plugin_names = {p.name for p in plugin_dirs}
        missing_official = sorted(EXPECTED_OFFICIAL_PLUGINS - found_plugin_names)
        if missing_official:
            errors.append(
                f"Thiếu plugin chính thức trong {plugins_root}: {', '.join(missing_official)}"
            )

    loaded_manifests: dict[str, dict] = {}
    manifests_by_dir: dict[Path, dict] = {}
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
        manifests_by_dir[plugin_dir] = manifest
        loaded_manifests[plugin_dir.name] = manifest
        m_name = str(manifest.get("name") or "").strip()
        if m_name:
            loaded_manifests[m_name] = manifest

    published_by_plugin = {
        name: _extract_published_events(mf) for name, mf in loaded_manifests.items()
    }

    for plugin_dir in plugin_dirs:
        manifest = manifests_by_dir.get(plugin_dir)
        if manifest is None:
            continue

        manifest_ver_str = str(manifest.get("version") or "").strip()
        manifest_ver = _parse_semver(manifest_ver_str)
        if manifest_ver is None:
            errors.append(
                f"[{plugin_dir.name}] manifest.version không hợp lệ (cần X.Y.Z): '{manifest_ver_str}'"
            )

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

        # Kiểm tra UTF-8 BOM cho các file SQL
        for sql_file in plugin_dir.rglob("*.sql"):
            if "node_modules" in sql_file.parts or "dist" in sql_file.parts:
                continue
            if sql_file.read_bytes().startswith(b"\xef\xbb\xbf"):
                errors.append(
                    f"[{plugin_dir.name}] File SQL chứa UTF-8 BOM: {sql_file.relative_to(plugin_dir)}"
                )

        # 2. Kiểm tra độc lập database.seed_file VÀ migrations/*.sql (<= manifest.version)
        db_cfg = manifest.get("database") or {}
        declared_table_list = [
            (tbl.get("name") if isinstance(tbl, dict) else str(tbl)).lower()
            for tbl in (db_cfg.get("tables") or [])
            if tbl
        ]
        declared_tables = set(declared_table_list)

        seed_file = db_cfg.get("seed_file")
        seed_sql_contents: list[str] = []
        has_valid_seed = False
        if seed_file:
            seed_path = _check_safe_path(plugin_dir, seed_file)
            if seed_path is None or not seed_path.exists():
                errors.append(
                    f"[{plugin_dir.name}] Thiếu hoặc path không hợp lệ cho seed_file: {seed_file}"
                )
            else:
                has_valid_seed = True
                seed_sql_contents.append(seed_path.read_text(encoding="utf-8"))

        migrations_dir = plugin_dir / "migrations"
        mig_sql_contents: list[str] = []
        has_migrations = migrations_dir.exists()
        if is_official_repo and plugin_dir.name in EXPECTED_OFFICIAL_PLUGINS:
            if not has_migrations or not list(migrations_dir.glob("*.sql")):
                errors.append(
                    f"[{plugin_dir.name}] Plugin chính thức thiếu thư mục migrations/*.sql"
                )

        if has_migrations:
            versioned_migs: list[tuple[tuple[int, int, int], Path]] = []
            for mig in sorted(migrations_dir.glob("*.sql")):
                m = MIGRATION_FILE_RE.match(mig.name)
                if not m:
                    errors.append(
                        f"[{plugin_dir.name}] Tên file migration không đúng chuẩn V<X.Y.Z>__<mô_tả>.sql: {mig.name}"
                    )
                    continue
                mig_ver_str = m.group(1)
                mig_ver = _parse_semver(mig_ver_str)
                assert mig_ver is not None
                if manifest_ver is not None and mig_ver > manifest_ver:
                    errors.append(
                        f"[{plugin_dir.name}] Migration '{mig.name}' có version {mig_ver_str} vượt quá manifest.version ({manifest_ver_str})"
                    )
                    continue
                versioned_migs.append((mig_ver, mig))
            versioned_migs.sort(key=lambda item: (item[0], item[1].name))
            for _, mig in versioned_migs:
                mig_sql_contents.append(mig.read_text(encoding="utf-8"))

        seed_tables = _extract_tables(seed_sql_contents)
        mig_tables = _extract_tables(mig_sql_contents)
        seed_table_columns = _extract_table_columns(seed_sql_contents)
        mig_table_columns = _extract_table_columns(mig_sql_contents)

        if has_valid_seed:
            for tname in declared_table_list:
                if tname and tname not in seed_tables:
                    errors.append(
                        f"[{plugin_dir.name}] Bảng '{tname}' trong manifest.yaml chưa có CREATE TABLE trong {seed_file}"
                    )

        if has_migrations:
            for tname in declared_table_list:
                if tname and tname not in mig_tables:
                    errors.append(
                        f"[{plugin_dir.name}] Bảng '{tname}' trong manifest.yaml chưa có CREATE TABLE trong migrations/*.sql (<= {manifest_ver_str})"
                    )

        if not has_valid_seed and not has_migrations:
            for tname in declared_table_list:
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

        # 5. Kiểm tra event_subscriptions đối chiếu với source_plugin & event_publications
        for s_idx, sub in enumerate(manifest.get("event_subscriptions") or []):
            if not isinstance(sub, dict):
                errors.append(
                    f"[{plugin_dir.name}] event_subscriptions[{s_idx}] phải là object"
                )
                continue
            src_plugin = str(sub.get("source_plugin") or "").strip()
            if not src_plugin:
                errors.append(
                    f"[{plugin_dir.name}] event_subscriptions[{s_idx}] thiếu 'source_plugin'"
                )
            elif src_plugin not in loaded_manifests:
                errors.append(
                    f"[{plugin_dir.name}] event_subscriptions[{s_idx}] tham chiếu source_plugin không tồn tại: '{src_plugin}'"
                )
            else:
                src_published = published_by_plugin.get(src_plugin, set())
                sub_events = sub.get("event_types")
                if not isinstance(sub_events, list) or len(sub_events) == 0:
                    errors.append(
                        f"[{plugin_dir.name}] event_subscriptions[{s_idx}].event_types phải là danh sách không rỗng"
                    )
                else:
                    for ev in sub_events:
                        ev_name = str(ev or "").strip()
                        if not ev_name:
                            errors.append(
                                f"[{plugin_dir.name}] event_subscriptions[{s_idx}] chứa event_type rỗng"
                            )
                        elif ev_name not in src_published:
                            errors.append(
                                f"[{plugin_dir.name}] event_subscriptions[{s_idx}] đăng ký event '{ev_name}' chưa được khai báo trong event_publications của '{src_plugin}'"
                            )

            handler_wf = str(sub.get("handler_workflow") or "").strip()
            if handler_wf and (
                "/" in handler_wf or "\\" in handler_wf or handler_wf.endswith(".json")
            ):
                hw_path = _check_safe_path(plugin_dir, handler_wf)
                if hw_path is None or not hw_path.exists():
                    errors.append(
                        f"[{plugin_dir.name}] event_subscriptions[{s_idx}] handler_workflow không tồn tại: '{handler_wf}'"
                    )

        # 6. Kiểm tra hợp đồng NGSI-LD cho toàn bộ plugins (#871, #885, #887)
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
                        seed_cols = seed_table_columns.get(ent_table, set())
                        mig_cols = mig_table_columns.get(ent_table, set())
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
                            if has_valid_seed and col.lower() not in seed_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] cột '{col}' không tồn tại trong '{ent_table}' của {seed_file}"
                                )
                            if has_migrations and col.lower() not in mig_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] cột '{col}' không tồn tại trong '{ent_table}' của migrations/*.sql (<= {manifest_ver_str})"
                                )

                    rels = ent.get("relationships") or []
                    if not isinstance(rels, list):
                        errors.append(
                            f"[{plugin_dir.name}] ngsi.entities[{e_idx}].relationships phải là danh sách"
                        )
                    else:
                        seed_cols = seed_table_columns.get(ent_table, set())
                        mig_cols = mig_table_columns.get(ent_table, set())
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
                            if has_valid_seed and r_col.lower() not in seed_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] relationship cột '{r_col}' không tồn tại trong '{ent_table}' của {seed_file}"
                                )
                            if has_migrations and r_col.lower() not in mig_cols:
                                errors.append(
                                    f"[{plugin_dir.name}] ngsi.entities[{e_idx}] relationship cột '{r_col}' không tồn tại trong '{ent_table}' của migrations/*.sql (<= {manifest_ver_str})"
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
