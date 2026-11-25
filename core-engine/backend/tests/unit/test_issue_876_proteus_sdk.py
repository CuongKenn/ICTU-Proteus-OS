# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests cho bộ công cụ CLI `proteus-sdk` (Issue #876)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
SDK_DIR = REPO_ROOT / "sdk"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from proteus_sdk.cli import main as sdk_main  # noqa: E402


def test_sdk_init_and_validate_roundtrip_passes_100_percent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`init` sinh plugin chuẩn trong `tmp_path` và `validate` đạt exit_code == 0."""
    init_code = sdk_main(
        [
            "init",
            "lab-inventory-module",
            "--output-dir",
            str(tmp_path),
            "--display-name",
            "Quản lý Thiết bị Lab",
        ]
    )
    assert init_code == 0

    plugin_dir = tmp_path / "lab-inventory-module"
    expected_files = [
        plugin_dir / "manifest.yaml",
        plugin_dir / "db" / "seed_data.sql",
        plugin_dir / "migrations" / "V1.0.0__initial.sql",
        plugin_dir / "workflows" / "sample_webhook.json",
        plugin_dir / "frontend" / "src" / "App.tsx",
    ]
    for fpath in expected_files:
        assert fpath.exists(), f"Thiếu file bắt buộc: {fpath}"
        raw = fpath.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"File chứa UTF-8 BOM: {fpath}"
        assert b"SPDX-License-Identifier: AGPL-3.0-or-later" in raw

    val_code = sdk_main(["validate", str(plugin_dir)])
    captured = capsys.readouterr()
    assert val_code == 0
    assert "PASS" in captured.out


def test_sdk_validate_blocks_pii_column_base_salary_in_ngsi(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Khi chèn cột nhạy cảm `base_salary` vào `ngsi.entities[].attributes`,
    `validate` phải phát hiện và trả `exit_code == 1` kèm thông báo lỗi PII rõ ràng.
    """
    init_code = sdk_main(
        [
            "init",
            "hr-ext-module",
            "--output-dir",
            str(tmp_path),
            "--display-name",
            "HR Extended",
        ]
    )
    assert init_code == 0

    plugin_dir = tmp_path / "hr-ext-module"
    manifest_path = plugin_dir / "manifest.yaml"
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    manifest_data["ngsi"]["entities"][0]["attributes"].append(
        {
            "column": "base_salary",
            "target": "baseSalary",
            "type": "Property",
        }
    )
    manifest_path.write_text(
        yaml.safe_dump(manifest_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    capsys.readouterr()
    val_code = sdk_main(["validate", str(plugin_dir)])
    captured = capsys.readouterr()

    assert val_code == 1
    assert "PII" in captured.err
    assert "base_salary" in captured.err


def test_sdk_validate_catches_bom_and_webhook_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Kiểm chứng phát hiện UTF-8 BOM và lệch webhook_path."""
    assert (
        sdk_main(["init", "asset-audit-module", "--output-dir", str(tmp_path)]) == 0
    )
    plugin_dir = tmp_path / "asset-audit-module"

    # Cố tình ghi BOM vào file SQL và sửa sai webhook_path trong manifest
    seed_file = plugin_dir / "db" / "seed_data.sql"
    seed_file.write_bytes(b"\xef\xbb\xbf" + seed_file.read_bytes())

    manifest_path = plugin_dir / "manifest.yaml"
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_data["workflows"][0]["webhook_path"] = "wrong-path-not-in-n8n"
    manifest_path.write_text(
        yaml.safe_dump(manifest_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    capsys.readouterr()
    val_code = sdk_main(["validate", str(plugin_dir)])
    captured = capsys.readouterr()

    assert val_code == 1
    assert "UTF-8 BOM" in captured.err
    assert "webhook_path" in captured.err


def test_sdk_module_cli_execution_via_python_m(tmp_path: Path) -> None:
    """Chạy trực tiếp qua `python -m proteus_sdk` với PYTHONPATH=sdk."""
    env = os.environ.copy()
    existing_py_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{SDK_DIR}{os.pathsep}{existing_py_path}"
        if existing_py_path
        else str(SDK_DIR)
    )

    init_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "proteus_sdk",
            "init",
            "campus-parking-module",
            "--output-dir",
            str(tmp_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_proc.returncode == 0, init_proc.stderr

    val_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "proteus_sdk",
            "validate",
            str(tmp_path / "campus-parking-module"),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert val_proc.returncode == 0, val_proc.stderr
