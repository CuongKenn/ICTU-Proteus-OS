# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Core Domain — Dynamic DX-DSL Action Catalog.
# Dựng danh sách actions AI được phép gọi từ:
#   1. Core actions tĩnh (docs/dsl-spec.md §3.1), và
#   2. Workflows trigger=webhook của các plugin tenant đã cài (ACTIVE).
# Effect là heuristic theo tên action (list/get/read/search/summary/report → read,
# còn lại → write) vì manifest v1 chưa khai báo effect — hiển thị rõ cho LLM
# là "gợi ý", quyết định cuối thuộc về DSLValidator + Human-in-the-loop.

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ACTION_SEGMENT_PATTERN = re.compile(r"^[a-z0-9_-]+$")
_PLUGIN_CODE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_KNOWN_PLUGIN_PREFIXES: dict[str, str] = {
    "it": "it-helpdesk-module",
}
_DEFAULT_PLUGINS_DIR = Path(__file__).resolve().parents[5] / "plugins"


def _ensure_inside_plugins_dir(plugins_dir: Path, target: Path) -> Path:
    """Resolve + chặn path traversal (../) — raise ValueError nếu vượt ngoài."""
    base = plugins_dir.resolve()
    resolved = (
        (base / target).resolve() if not target.is_absolute() else target.resolve()
    )
    try:
        _inside = resolved.is_relative_to(base)
    except AttributeError:  # Python < 3.9
        _inside = base in resolved.parents or resolved == base
    if not _inside:
        raise ValueError(f"Path vượt ngoài plugins_dir: {target}")
    return resolved


READ_HINTS = (
    "list",
    "get",
    "read",
    "search",
    "summary",
    "report",
    "balance",
    "check",
    "overview",
    "metrics",
)


@dataclass
class CatalogAction:
    action: str
    effect_hint: str
    description: str


CORE_ACTIONS: list[CatalogAction] = [
    CatalogAction(
        "core.chat.reply",
        "read",
        "Trả lời chào hỏi / câu chuyện ngoài nghiệp vụ. Không chạm dữ liệu.",
    ),
    CatalogAction("core.plugins.list", "read", "Liệt kê plugin đã cài của tổ chức."),
    CatalogAction(
        "core.plugins.install", "write", "Cài plugin mới (cần tenant_admin)."
    ),
    CatalogAction("core.users.list", "read", "Liệt kê người dùng trong tenant."),
    CatalogAction(
        "core.users.deactivate", "critical", "Vô hiệu hóa tài khoản (2 duyệt)."
    ),
    CatalogAction(
        "core.knowledge.search", "read", "Tìm kiếm tri thức nội bộ (RAG, có trích dẫn)."
    ),
    CatalogAction("core.knowledge.ingest", "write", "Nạp tài liệu mới vào RAG."),
    CatalogAction(
        "core.knowledge.save",
        "write",
        "Lưu/tạo tài liệu mới vào tri thức nội bộ (Outline Wiki). Cần phê duyệt.",
    ),
]

# Core read actions mở cho MỌI role đã đăng nhập (docs/dsl-spec.md §3.1,
# clarification §9 RAG Assistant): chỉ đọc dữ liệu tenant mình, không duyệt.
CORE_PUBLIC_READ_ACTIONS: frozenset[str] = frozenset(
    {
        "core.chat.reply",
        "core.plugins.list",
        "core.knowledge.search",
    }
)


def derive_action_effect(action: str) -> str:
    """Server-side derive effect (read | write | critical) từ catalog (#684)."""
    for ca in CORE_ACTIONS:
        if ca.action == action:
            return ca.effect_hint

    critical_keywords = (
        "delete",
        "purge",
        "destroy",
        "drop",
        "deactivate",
        "revoke",
        "reset_password",
    )
    action_lower = action.lower()
    if any(k in action_lower for k in critical_keywords):
        return "critical"

    parts = action.split(".")
    if len(parts) >= 3:
        verb = parts[-1].lower()
        if any(h in verb for h in READ_HINTS):
            return "read"
        return "write"

    if any(h in action_lower for h in READ_HINTS):
        return "read"
    return "write"


def infer_effect(action_id: str) -> str:
    lowered = action_id.lower()
    if any(h in lowered for h in READ_HINTS):
        return "read"
    return "write"


FALLBACK_PROMPT_ACTIONS = (
    '1. "hr.leave_requests.batch_approve": (effect: write) Duyệt nghỉ phép, '
    "phê duyệt đơn.\n"
    '2. "core.users.delete": (effect: critical) Xóa người dùng, xoá nhân viên.\n'
    '3. "hr.employees.read": (effect: read) Tìm kiếm thông tin nhân viên, '
    "đọc thông tin."
)


def build_catalog(
    plugin_repo=None,
    manifest_parser=None,
    tenant_id=None,
    include_static: bool = True,
) -> list[CatalogAction]:
    """Dựng catalog đồng bộ từ manifests (dùng cho prompt/UI).

    Phiên bản async ở dưới dùng khi cần lọc theo plugin ACTIVE của tenant.
    """
    actions: list[CatalogAction] = list(CORE_ACTIONS) if include_static else []
    if manifest_parser is None:
        return actions
    plugins_dir: Path | None = getattr(manifest_parser, "plugins_dir", None)
    if plugins_dir is None:
        plugins_dir = getattr(manifest_parser, "_plugins_dir", None)
    if plugins_dir is None:
        return actions
    try:
        for manifest_path in sorted(Path(plugins_dir).glob("*/manifest.yaml")):
            try:
                manifest = manifest_parser.parse(manifest_path.parent.name)
            except Exception as e:
                logger.warning("Bỏ qua manifest lỗi %s: %s", manifest_path, e)
                continue
            for wf in manifest.workflows or []:
                if getattr(wf, "trigger", None) != "webhook":
                    continue
                action_id = getattr(wf, "id", None) or Path(wf.file).stem
                prefix = manifest.name.split("-")[0]
                actions.append(
                    CatalogAction(
                        action=f"{prefix}.{action_id}",
                        effect_hint=infer_effect(action_id),
                        description=getattr(wf, "description", "")
                        or getattr(wf, "name", action_id),
                    )
                )
    except Exception as e:
        logger.warning("Không dựng được catalog động: %s", e)
    return actions


async def build_catalog_for_tenant(
    plugin_repo,
    manifest_parser,
    tenant_id,
    include_static: bool = True,
) -> list[CatalogAction]:
    """Catalog chỉ gồm plugin ACTIVE của tenant (+ core tĩnh)."""
    actions: list[CatalogAction] = list(CORE_ACTIONS) if include_static else []
    if plugin_repo is None or manifest_parser is None or tenant_id is None:
        return actions
    try:
        plugins, _ = await plugin_repo.list_installed(tenant_id=tenant_id)
    except Exception as e:
        logger.warning("Không liệt kê được plugin đã cài: %s", e)
        return actions
    for plugin in plugins:
        code = getattr(plugin, "code_name", None)
        if not code:
            continue
        try:
            manifest = manifest_parser.parse(code)
        except Exception as e:
            logger.warning("Bỏ qua manifest lỗi %s: %s", code, e)
            continue
        for wf in manifest.workflows or []:
            if getattr(wf, "trigger", None) != "webhook":
                continue
            action_id = getattr(wf, "id", None) or Path(wf.file).stem
            prefix = manifest.name.split("-")[0]
            actions.append(
                CatalogAction(
                    action=f"{prefix}.{action_id}",
                    effect_hint=infer_effect(action_id),
                    description=getattr(wf, "description", "")
                    or getattr(wf, "name", action_id),
                )
            )
    return actions


def render_for_prompt(actions: list[CatalogAction], limit: int = 60) -> str:
    lines = []
    for a in actions[:limit]:
        lines.append(f'- "{a.action}" (effect gợi ý: {a.effect_hint}) {a.description}')
    if len(actions) > limit:
        lines.append(f"... và {len(actions) - limit} actions khác.")
    return "\n".join(lines)


def resolve_workflow_webhook_url(
    manifest_parser, plugin_code: str, action_id: str, tenant_id: Any = None
) -> str:
    """Dựng n8n webhook URL cho action 2-part {prefix}.{workflow_id}.

    Đọc workflow JSON của plugin, lấy webhook node path (giống
    PluginActionUseCase._resolve_webhook_url để 2 đường gọi nhất quán).
    Validate regex từng segment + chặn ../ + resolve().is_relative_to().
    """
    from app.infrastructure.config import settings

    if not isinstance(plugin_code, str) or not _PLUGIN_CODE_PATTERN.match(plugin_code):
        raise ValueError(f"Plugin '{plugin_code}' không hợp lệ.")
    if (
        not isinstance(action_id, str)
        or ".." in action_id
        or "/" in action_id
        or "\\" in action_id
        or not _ACTION_SEGMENT_PATTERN.match(action_id)
    ):
        raise ValueError(f"Action '{action_id}' không hợp lệ.")
    manifest = manifest_parser.parse(plugin_code)
    wf_file: str | None = None
    wf_webhook_path: str | None = None
    for wf in manifest.workflows or []:
        effective_id = getattr(wf, "id", None) or Path(wf.file).stem
        if effective_id == action_id and getattr(wf, "trigger", None) == "webhook":
            wf_file = wf.file
            wf_webhook_path = getattr(wf, "webhook_path", None)
            break
    if wf_file is None:
        raise ValueError(
            f"Action '{action_id}' không thuộc plugin '{plugin_code}' "
            f"hoặc không phải webhook trigger."
        )
    if ".." in wf_file or wf_file.startswith("/"):
        raise ValueError(f"File workflow '{wf_file}' không hợp lệ.")
    plugins_dir = manifest_parser.plugins_dir
    wf_path = _ensure_inside_plugins_dir(Path(plugins_dir), Path(plugin_code) / wf_file)
    if not wf_path.is_file():
        raise ValueError(f"File workflow '{wf_file}' không tồn tại.")
    try:
        with open(wf_path, encoding="utf-8-sig") as f:
            wf_json = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"File workflow '{wf_file}' không đọc được: {exc}") from exc
    path = None
    for node in wf_json.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            path = (node.get("parameters", {}) or {}).get("path")
            if path:
                break
    if not path and wf_webhook_path:
        path = wf_webhook_path
    if not path:
        raise ValueError(
            f"Workflow '{wf_file}' không có webhook node — "
            f"chỉ workflow webhook mới gọi được."
        )
    if tenant_id:
        tenant_short = str(tenant_id).replace("-", "")[:8]
        clean_path = str(path).lstrip("/")
        if not clean_path.startswith(f"t_{tenant_short}_"):
            path = f"t_{tenant_short}_{clean_path}"
    base = settings.N8N_URL.rstrip("/")
    return f"{base}/webhook/{str(path).lstrip('/')}"


def _read_manifest_name(manifest_file: Path) -> str | None:
    """Đọc nhanh trường top-level `name:` từ manifest.yaml."""
    try:
        for line in manifest_file.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if stripped.startswith("name:"):
                raw_name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if raw_name and _PLUGIN_CODE_PATTERN.match(raw_name):
                    return raw_name
    except OSError:
        return None
    return None


def resolve_plugin_code(
    prefix: str,
    *,
    plugins_dir: Path | str | None = None,
    manifest_parser: Any = None,
) -> str:
    """Ánh xạ prefix sang tên plugin thật trong `plugins/` (#884).

    Hỗ trợ cả `{prefix}-module` chuẩn (VD: `hr` -> `hr-module`) lẫn plugin nhiều từ
    như `it` -> `it-helpdesk-module` hoặc `lab` -> `lab-asset-module`.
    """
    clean = str(prefix or "").strip()
    if not clean or not _ACTION_SEGMENT_PATTERN.match(clean):
        return f"{clean}-module"
    if clean.endswith("-module") and _PLUGIN_CODE_PATTERN.match(clean):
        return clean

    candidate_dirs: list[Path] = []
    if plugins_dir is not None and isinstance(plugins_dir, str | Path):
        p = Path(plugins_dir)
        if p.is_dir():
            candidate_dirs.append(p)
    if manifest_parser is not None:
        raw_pdir = getattr(manifest_parser, "plugins_dir", None) or getattr(
            manifest_parser, "_plugins_dir", None
        )
        if callable(raw_pdir):
            try:
                raw_pdir = raw_pdir()
            except Exception:
                raw_pdir = None
        if isinstance(raw_pdir, str | Path):
            p = Path(raw_pdir)
            if p.is_dir() and p not in candidate_dirs:
                candidate_dirs.append(p)
    if _DEFAULT_PLUGINS_DIR.is_dir() and _DEFAULT_PLUGINS_DIR not in candidate_dirs:
        candidate_dirs.append(_DEFAULT_PLUGINS_DIR)

    for pdir in candidate_dirs:
        exact_mod = pdir / f"{clean}-module"
        if exact_mod.is_dir():
            mfile = exact_mod / "manifest.yaml"
            return _read_manifest_name(mfile) or exact_mod.name

        multi_matches = sorted(
            d
            for d in pdir.glob(f"{clean}-*-module")
            if d.is_dir() and _PLUGIN_CODE_PATTERN.match(d.name)
        )
        if not multi_matches:
            multi_matches = sorted(
                d
                for d in pdir.glob(f"{clean}-*")
                if d.is_dir()
                and (d / "manifest.yaml").is_file()
                and _PLUGIN_CODE_PATTERN.match(d.name)
            )
        if multi_matches:
            chosen = multi_matches[0]
            if manifest_parser is not None:
                try:
                    parsed = manifest_parser.parse(chosen.name)
                    pname = getattr(parsed, "name", None)
                    if isinstance(pname, str) and _PLUGIN_CODE_PATTERN.match(pname):
                        return pname
                except Exception:
                    pass
            mfile = chosen / "manifest.yaml"
            return _read_manifest_name(mfile) or chosen.name

    if clean in _KNOWN_PLUGIN_PREFIXES:
        known = _KNOWN_PLUGIN_PREFIXES[clean]
        if manifest_parser is not None:
            try:
                manifest_parser.parse(known)
                return known
            except Exception:
                try:
                    manifest_parser.parse(f"{clean}-module")
                    return f"{clean}-module"
                except Exception:
                    return known
        return known

    return f"{clean}-module"


def split_plugin_action(
    action: str,
    *,
    plugins_dir: Path | str | None = None,
    manifest_parser: Any = None,
) -> tuple[str, str] | None:
    """Tách action 2-part {prefix}.{workflow_id} → (plugin_code, workflow_id).

    Ưu tiên phân giải tên plugin thực tế trong `plugins/` (VD: `it` →
    `it-helpdesk-module`, `lab` → `lab-asset-module`), fallback `{prefix}-module`.
    Validate mỗi segment ^[a-z0-9_-]+$, chặn '../' và '/' (M3).
    """
    if not isinstance(action, str) or not action:
        return None
    if ".." in action or "/" in action or "\\" in action:
        return None
    parts = action.split(".")
    if len(parts) != 2 or not all(parts):
        return None
    if not all(_ACTION_SEGMENT_PATTERN.match(p) for p in parts):
        return None
    plugin_code = resolve_plugin_code(
        parts[0], plugins_dir=plugins_dir, manifest_parser=manifest_parser
    )
    return plugin_code, parts[1]
