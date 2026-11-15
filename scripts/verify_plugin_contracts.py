#!/usr/bin/env python3
# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kiểm định hợp đồng tĩnh cho toàn bộ Plugin dưới `plugins/*`:
1. Không chứa UTF-8 BOM và parse JSON hợp lệ cho workflows/*.json, dashboards/*.json, ui/*.json.
2. Đường dẫn tham chiếu trong manifest.yaml (seed_file, workflows[].file, dashboards[].file, ui.appsmith_app)
   tồn tại và không vượt khỏi thư mục plugin (anti path-traversal).
3. database.tables trong manifest.yaml khớp với các bảng CREATE TABLE trong seed_data.sql + migrations/*.sql.
4. workflows[].webhook_path (nếu có) khớp với node n8n-nodes-base.webhook trong file workflow tương ứng.
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
        p for p in plugins_root.iterdir() if p.is_dir() and (p / "manifest.yaml").exists()
    )
    if not plugin_dirs:
        errors.append(f"Không tìm thấy plugin nào dưới {plugins_root}")
        return errors

    for plugin_dir in plugin_dirs:
        manifest_path = plugin_dir / "manifest.yaml"
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(f"[{plugin_dir.name}] Lỗi đọc manifest.yaml: {exc}")
            continue

        # 1. Kiểm tra UTF-8 BOM và parse JSON trong plugin
        for json_file in plugin_dir.rglob("*.json"):
            if "node_modules" in json_file.parts or "dist" in json_file.parts:
                continue
            raw = json_file.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                errors.append(f"[{plugin_dir.name}] File chứa UTF-8 BOM: {json_file.relative_to(plugin_dir)}")
            try:
                json.loads(raw.decode("utf-8"))
            except Exception as exc:
                errors.append(f"[{plugin_dir.name}] JSON không hợp lệ ({json_file.relative_to(plugin_dir)}): {exc}")

        # 2. Kiểm tra database.seed_file & database.tables vs SQL
        db_cfg = manifest.get("database") or {}
        seed_file = db_cfg.get("seed_file")
        sql_contents: list[str] = []
        if seed_file:
            seed_path = _check_safe_path(plugin_dir, seed_file)
            if seed_path is None or not seed_path.exists():
                errors.append(f"[{plugin_dir.name}] Thiếu hoặc path không hợp lệ cho seed_file: {seed_file}")
            else:
                sql_contents.append(seed_path.read_text(encoding="utf-8"))

        migrations_dir = plugin_dir / "migrations"
        if migrations_dir.exists():
            for mig in sorted(migrations_dir.glob("*.sql")):
                sql_contents.append(mig.read_text(encoding="utf-8"))

        defined_tables: set[str] = set()
        for sql in sql_contents:
            defined_tables.update(m.group(1).lower() for m in CREATE_TABLE_RE.finditer(sql))

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
                    errors.append(f"[{plugin_dir.name}] Thiếu dashboard file: {db_file}")

        ui_cfg = manifest.get("ui") or {}
        appsmith_app = ui_cfg.get("appsmith_app")
        if appsmith_app:
            app_path = _check_safe_path(plugin_dir, appsmith_app)
            if app_path is None or not app_path.exists():
                errors.append(f"[{plugin_dir.name}] Thiếu ui.appsmith_app: {appsmith_app}")

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

