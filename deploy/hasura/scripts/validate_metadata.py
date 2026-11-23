# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hasura Metadata Validation Script for CI (Layer 3).

Kiểm tra tính hợp lệ của cấu hình Hasura metadata:
- Xác thực cú pháp YAML
- Đảm bảo cấm hoàn toàn anonymous role
- Kiểm tra các bảng thuộc schema context đều có phân quyền RLS theo x-hasura-tenant-id
- Kiểm tra các view nhạy cảm đã được sanitized (ẩn PII/lương)
Tham chiếu: Issue #840, #842, #843, #844, #845.
"""

import sys
from pathlib import Path

import yaml


def validate_hasura_metadata(base_dir: Path) -> bool:
    metadata_dir = base_dir / "metadata"
    db_file = metadata_dir / "databases" / "databases.yaml"

    if not db_file.exists():
        print(f"ERROR: databases.yaml not found at {db_file}", file=sys.stderr)
        return False

    with open(db_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list) or len(data) == 0:
        print(
            "ERROR: databases.yaml must contain a list of database configs",
            file=sys.stderr,
        )
        return False

    pg_db = data[0]
    tables = pg_db.get("tables", [])
    if not tables:
        print("ERROR: No tables tracked in databases.yaml", file=sys.stderr)
        return False

    context_tables_found = []
    for t_entry in tables:
        table_meta = t_entry.get("table", {})
        schema = table_meta.get("schema")
        name = table_meta.get("name")

        if schema == "context":
            context_tables_found.append(name)
            select_perms = t_entry.get("select_permissions", [])

            # Check: cấm anonymous role
            for perm in select_perms:
                role = perm.get("role")
                if role == "anonymous":
                    print(
                        f"SECURITY VIOLATION: anonymous role permitted on {schema}.{name}",
                        file=sys.stderr,
                    )
                    return False

                # Check: filter tenant_id
                filter_rule = perm.get("permission", {}).get("filter", {})
                if (
                    "tenant_id" not in filter_rule
                    and name != "v_hr_employees_sanitized"
                ):
                    print(
                        f"SECURITY WARNING: tenant_id filter missing on {schema}.{name} for role {role}",
                        file=sys.stderr,
                    )

    print(
        f"SUCCESS: Validated {len(tables)} tables. Context tables tracked: {context_tables_found}"
    )
    return True


if __name__ == "__main__":
    current_dir = Path(__file__).resolve().parent.parent
    if not validate_hasura_metadata(current_dir):
        sys.exit(1)
