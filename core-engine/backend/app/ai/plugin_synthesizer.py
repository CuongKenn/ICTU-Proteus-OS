# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# AI Engine - Autonomous Plugin Synthesizer
# Dịch yêu cầu ngôn ngữ tự nhiên thành một plugin khai báo an toàn (YAML + SQL + n8n JSON).

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from app.core.domain.ports import AbstractLLMPort
from app.infrastructure.config import settings

logger = logging.getLogger(__name__)

SAFE_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_PLUGIN_NAME_LENGTH = 64

PROTECTED_PLUGIN_NAMES: frozenset[str] = frozenset(
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
        "mfe-gateway",
    }
)


def _resolve_plugins_dir(raw_dir: str, repo_root: Path) -> Path:
    """Resolve PLUGINS_DIR safely across Docker (`/plugins`), Linux dev, and Windows."""
    normalized = str(raw_dir).replace("\\", "/")
    raw_path = Path(raw_dir)
    if normalized == "/plugins":
        if raw_path.is_absolute() and raw_path.exists():
            return raw_path.resolve()
        return (repo_root / "plugins").resolve()
    if not raw_path.is_absolute():
        return (repo_root / raw_dir).resolve()
    return raw_path.resolve()


class PluginSynthesizer:
    def __init__(self, llm: AbstractLLMPort | None = None):
        # __file__ = <repo>/core-engine/backend/app/ai/plugin_synthesizer.py
        # parents[2] = backend, parents[3] = core-engine, parents[4] = repo root
        repo_root = Path(__file__).resolve().parents[4]
        self._plugins_dir = _resolve_plugins_dir(settings.PLUGINS_DIR, repo_root)
        self.llm = llm
        self.last_result: dict[str, str] | None = None

    async def synthesize(self, prompt: str) -> str:
        """
        Nhận một prompt (VD: 'Tạo plugin quản lý bệnh viện với chức năng khám bệnh')
        và tự động sinh cấu trúc khai báo (manifest.yaml, db/seed_data.sql, workflows)
        cho plugin đó. Tuyệt đối KHÔNG ghi đè plugin hiện có và KHÔNG sinh mã Python thực thi.
        """
        logger.info("Synthesizing plugin from prompt: %s", prompt)

        system_prompt = """
        Bạn là Proteus OS AI Plugin Synthesizer.
        Hãy tạo một Plugin khai báo (declarative) cho hệ thống dựa trên yêu cầu của người dùng.

        Hệ thống yêu cầu trả về ĐÚNG MỘT JSON hợp lệ (không markdown) với cấu trúc sau:
        {
            "code_name": "ten-plugin-khong-dau",
            "manifest_yaml": "nội dung file manifest.yaml",
            "seed_sql": "nội dung file db/seed_data.sql chứa CREATE TABLE"
        }

        Quy tắc manifest.yaml:
        - name: <code_name> (kebab-case, không trùng các module chính thức)
        - display_name: <Tên hiển thị>
        - version: '1.0.0'
        - description: <mô tả>
        - author: 'Proteus AI'
        - license: 'AGPL-3.0-or-later'
        - category: 'Operations'
        - is_official: false
        - synthesized: true
        - reviewed: false
        - compatibility:
            proteus_os_min_version: '1.0.0'
            dsl_spec_version: '1.0'
        - database:
            tables:
              - '<prefix>_items'
            seed_file: 'db/seed_data.sql'
        - workflows:
            - id: 'wf_<prefix>_items_sync'
              file: 'workflows/sample_webhook.json'
              name: '<Tên hiển thị> Sync Webhook'
              trigger: 'webhook'
              webhook_path: '<code_name>-items-sync'

        Quy tắc seed_sql:
        - Phải dùng PostgreSQL với UUID PRIMARY KEY DEFAULT uuid_generate_v4().
        - Bảng <prefix>_items có các cột { id, name, description, created_at, updated_at }.
        - Không được có cột tenant_id (hệ thống sẽ tự tiêm) và KHÔNG sinh mã Python (main.py).
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            if self.llm is None:
                return self._mock_synthesize(prompt)

            response = await self.llm.ainvoke(messages)
            content = str(response.content or "").strip()

            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()

            data = json.loads(content)
            plugin_name = str(data.get("code_name", "unknown-plugin")).strip()

            self._validate_plugin_target(plugin_name)
            self._write_plugin_files(plugin_name, data)
            return plugin_name

        except Exception as e:
            logger.error("Error synthesizing plugin: %s", e, exc_info=True)
            raise e

    async def synthesize_full(self, prompt: str) -> dict[str, str]:
        """Sinh plugin và trả về đầy đủ blueprint (`code_name`, `manifest_yaml`, `seed_sql`)."""
        plugin_name = await self.synthesize(prompt)
        if isinstance(self.last_result, dict):
            return dict(self.last_result)
        return {"code_name": plugin_name, "manifest_yaml": "", "seed_sql": ""}

    def _validate_plugin_target(self, plugin_name: str) -> Path:
        if not SAFE_PLUGIN_NAME_PATTERN.match(plugin_name):
            raise ValueError(f"LLM trả về plugin_name không hợp lệ: {plugin_name}")

        if len(plugin_name) > MAX_PLUGIN_NAME_LENGTH:
            raise ValueError(f"plugin_name quá dài: {len(plugin_name)} chars")

        if plugin_name in PROTECTED_PLUGIN_NAMES:
            raise ValueError(
                f"Plugin '{plugin_name}' đã tồn tại (official plugin), không được phép ghi đè."
            )

        base_resolved = self._plugins_dir.resolve()
        plugin_path = (self._plugins_dir / plugin_name).resolve()
        if (
            not plugin_path.is_relative_to(base_resolved)
            or plugin_path == base_resolved
        ):
            raise ValueError(f"Path traversal detected: {plugin_path}")

        if plugin_path.exists():
            raise ValueError(
                f"Plugin '{plugin_name}' đã tồn tại, không được phép ghi đè."
            )

        return plugin_path

    def _sanitize_manifest(
        self, plugin_name: str, raw_manifest_yaml: str, has_seed_sql: bool
    ) -> tuple[str, dict[str, Any]]:
        prefix = plugin_name.split("-")[0]
        default_table = f"{prefix}_items"

        parsed = yaml.safe_load(raw_manifest_yaml) if raw_manifest_yaml else {}
        if not isinstance(parsed, dict):
            raise ValueError("LLM trả về manifest_yaml không phải YAML mapping hợp lệ.")

        manifest_dict: dict[str, Any] = dict(parsed)
        manifest_dict["name"] = plugin_name
        manifest_dict.setdefault(
            "display_name",
            " ".join(w.capitalize() for w in plugin_name.split("-")),
        )
        manifest_dict.setdefault("version", "1.0.0")
        manifest_dict.setdefault("description", f"Synthesized plugin {plugin_name}")
        manifest_dict.setdefault("author", "Proteus AI")
        manifest_dict.setdefault("license", "AGPL-3.0-or-later")
        manifest_dict.setdefault("category", "Operations")

        # Hard security invariants (#880): synthesized plugins are NEVER trusted/official
        manifest_dict["is_official"] = False
        manifest_dict["synthesized"] = True
        manifest_dict["reviewed"] = False

        raw_compat = manifest_dict.get("compatibility")
        compat_dict = dict(raw_compat) if isinstance(raw_compat, dict) else {}
        compat_dict.pop("proteus", None)
        compat_dict["proteus_os_min_version"] = str(
            compat_dict.get("proteus_os_min_version") or "1.0.0"
        )
        compat_dict.setdefault("dsl_spec_version", "1.0")
        manifest_dict["compatibility"] = compat_dict

        raw_db = manifest_dict.get("database")
        db_dict = dict(raw_db) if isinstance(raw_db, dict) else {}
        raw_tables = db_dict.get("tables")
        normalized_tables: list[str] = []
        if isinstance(raw_tables, list):
            for tbl in raw_tables:
                if isinstance(tbl, dict) and tbl.get("name"):
                    normalized_tables.append(str(tbl["name"]).strip())
                elif isinstance(tbl, str) and tbl.strip():
                    normalized_tables.append(tbl.strip())
        if not normalized_tables:
            normalized_tables = [default_table]
        db_dict["tables"] = normalized_tables
        if has_seed_sql:
            db_dict.setdefault("seed_file", "db/seed_data.sql")
        manifest_dict["database"] = db_dict

        sanitized_yaml = yaml.safe_dump(
            manifest_dict, allow_unicode=True, sort_keys=False
        )
        return sanitized_yaml, manifest_dict

    def _write_plugin_files(self, plugin_name: str, data: dict[str, Any]) -> None:
        plugin_path = self._validate_plugin_target(plugin_name)

        if data.get("python_main"):
            logger.warning(
                "Security (#880): Stripping untrusted python_main from synthesized plugin '%s'.",
                plugin_name,
            )

        seed_sql = str(data.get("seed_sql") or "").strip()
        sanitized_yaml, manifest_dict = self._sanitize_manifest(
            plugin_name=plugin_name,
            raw_manifest_yaml=str(data.get("manifest_yaml") or ""),
            has_seed_sql=bool(seed_sql),
        )

        plugin_path.mkdir(parents=True, exist_ok=False)

        with open(
            plugin_path / "manifest.yaml", "w", encoding="utf-8", newline="\n"
        ) as f:
            f.write(sanitized_yaml)

        db_path = plugin_path / "db"
        db_path.mkdir(exist_ok=True)
        if seed_sql:
            with open(
                db_path / "seed_data.sql", "w", encoding="utf-8", newline="\n"
            ) as f:
                f.write(seed_sql + "\n")

        workflows_cfg = manifest_dict.get("workflows")
        if isinstance(workflows_cfg, list):
            for wf in workflows_cfg:
                if not isinstance(wf, dict):
                    continue
                wf_rel = str(wf.get("file") or "").strip()
                if (
                    not wf_rel
                    or ".." in Path(wf_rel).parts
                    or Path(wf_rel).is_absolute()
                ):
                    continue
                wf_file = (plugin_path / wf_rel).resolve()
                if not wf_file.is_relative_to(plugin_path.resolve()):
                    continue
                if not wf_file.exists():
                    hook_path = str(
                        wf.get("webhook_path") or f"{plugin_name}-items-sync"
                    ).strip("/")
                    wf_payload = {
                        "name": str(wf.get("name") or f"{plugin_name} Sync Webhook"),
                        "nodes": [
                            {
                                "parameters": {
                                    "httpMethod": "POST",
                                    "path": hook_path,
                                    "responseMode": "lastNode",
                                    "options": {},
                                },
                                "name": "Webhook",
                                "type": "n8n-nodes-base.webhook",
                                "typeVersion": 1,
                                "position": [240, 300],
                            }
                        ],
                        "connections": {},
                        "active": False,
                        "settings": {},
                    }
                    wf_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(wf_file, "w", encoding="utf-8", newline="\n") as wf_fh:
                        wf_fh.write(
                            json.dumps(wf_payload, ensure_ascii=False, indent=2) + "\n"
                        )

        self.last_result = {
            "code_name": plugin_name,
            "manifest_yaml": sanitized_yaml,
            "seed_sql": seed_sql,
        }
        logger.info(
            "Successfully generated declarative plugin files at %s", plugin_path
        )

    def _mock_synthesize(self, prompt: str) -> str:
        """Mock behavior cho CI/CD khi không có LLM key."""
        plugin_name = (
            "hospital-module" if "bệnh viện" in prompt.lower() else "demo-module"
        )
        display_name = (
            "Bệnh viện" if plugin_name == "hospital-module" else "Demo Module"
        )
        prefix = plugin_name.split("-")[0]
        table_name = f"{prefix}_items"
        webhook_path = f"{plugin_name}-items-sync"
        entity_type = f"{prefix.capitalize()}Item"

        manifest_yaml = (
            f"name: '{plugin_name}'\n"
            f"display_name: '{display_name}'\n"
            f"version: '1.0.0'\n"
            f"description: 'Generated declaratively by Proteus AI'\n"
            f"author: 'Proteus AI'\n"
            f"license: 'AGPL-3.0-or-later'\n"
            f"category: 'Operations'\n"
            f"is_official: false\n"
            f"synthesized: true\n"
            f"reviewed: false\n"
            f"compatibility:\n"
            f"  proteus_os_min_version: '1.0.0'\n"
            f"  dsl_spec_version: '1.0'\n"
            f"database:\n"
            f"  tables:\n"
            f"    - '{table_name}'\n"
            f"  seed_file: 'db/seed_data.sql'\n"
            f"workflows:\n"
            f"  - id: 'wf_{prefix}_items_sync'\n"
            f"    file: 'workflows/sample_webhook.json'\n"
            f"    name: '{display_name} Sync Webhook'\n"
            f"    trigger: 'webhook'\n"
            f"    webhook_path: '{webhook_path}'\n"
            f"ngsi:\n"
            f"  entities:\n"
            f"    - table: '{table_name}'\n"
            f"      type: '{entity_type}'\n"
            f"      id_pattern: 'urn:ngsi-ld:{entity_type}:{{tenant}}:{{id}}'\n"
            f"      attributes:\n"
            f"        - column: 'name'\n"
            f"          target: 'name'\n"
            f"          type: 'Property'\n"
            f"        - column: 'description'\n"
            f"          target: 'description'\n"
            f"          type: 'Property'\n"
        )

        seed_sql = (
            f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
            f"    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),\n"
            f"    name VARCHAR(255) NOT NULL,\n"
            f"    description TEXT,\n"
            f"    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
            f"    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
            f");"
        )

        data = {
            "code_name": plugin_name,
            "manifest_yaml": manifest_yaml,
            "seed_sql": seed_sql,
        }

        self._write_plugin_files(plugin_name, data)
        return plugin_name
