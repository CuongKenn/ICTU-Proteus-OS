# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import glob
import json
import os

import pytest

from app.infrastructure.models import UserModel


def test_user_model_has_mattermost_user_id():
    """UserModel có cột mattermost_user_id (#745)."""
    assert hasattr(UserModel, "mattermost_user_id")


def test_all_webhook_workflows_with_respond_node_have_response_mode_response_node():
    """Các webhook workflow có node respondToWebhook phải cấu hình responseMode: responseNode (#745)."""
    plugins_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../plugins")
    )
    for filepath in glob.glob(f"{plugins_dir}/**/workflows/*.json", recursive=True):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        has_respond = any(
            n.get("type") == "n8n-nodes-base.respondToWebhook"
            for n in data.get("nodes", [])
        )
        if has_respond:
            for node in data.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    mode = node.get("parameters", {}).get("responseMode")
                    assert (
                        mode == "responseNode"
                    ), f"Workflow {os.path.basename(filepath)} có respondToWebhook nhưng responseMode là '{mode}'"


def test_all_schedule_trigger_nodes_have_interval():
    """Các scheduleTrigger node phải cấu hình rule.interval đúng chuẩn (#745)."""
    plugins_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../plugins")
    )
    for filepath in glob.glob(f"{plugins_dir}/**/workflows/*.json", recursive=True):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for node in data.get("nodes", []):
            if node.get("type") == "n8n-nodes-base.scheduleTrigger":
                params = node.get("parameters", {})
                rule = params.get("rule", {})
                assert (
                    "interval" in rule
                ), f"Workflow {os.path.basename(filepath)} thiếu rule.interval"
                assert isinstance(
                    rule["interval"], list
                ), f"rule.interval trong {os.path.basename(filepath)} phải là list"


def test_asset_inventory_check_connected():
    """asset_inventory_check.json phải có connection từ Schedule - Monthly (#745)."""
    plugins_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../../plugins")
    )
    filepath = os.path.join(
        plugins_dir, "asset-module/workflows/asset_inventory_check.json"
    )
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    conns = data.get("connections", {})
    assert "Schedule - Monthly" in conns
    targets = [tgt["node"] for tgt in conns["Schedule - Monthly"]["main"][0]]
    assert "Get All Assets" in targets
