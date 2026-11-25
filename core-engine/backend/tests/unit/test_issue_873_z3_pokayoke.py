# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Unit tests cho Issue #873 — Mở rộng Poka-yoke Toán học Z3 SMT Solver.
Kiểm chứng:
- Z3Adapter.verify_with_proof (SAT & UNSAT, solve_time_ms < 50, violated_constraint,
  counter_example, invariants_checked, escalated_to_critical) cho hr, meeting,
  procurement, finance, asset và tenant_isolation.
- Tương thích ngược với Z3FormalVerifier.verify_dsl.
- AICommandUseCase: đính kèm z3_verification khi PENDING_APPROVAL, chặn UNSAT kèm
  thông tin vi phạm, nâng mức phê duyệt kép (>= 50_000_000 -> critical), và
  fallback mượt khi z3_adapter là MagicMock / AsyncMock cũ.
- AIChatUseCase (execute & execute_stream): truyền z3_verification qua step,
  result["z3_verification"], result["dsl_preview"]["z3_verification"] và SSE events.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.external.z3_adapter import (
    CRITICAL_BUDGET_THRESHOLD,
    Z3Adapter,
    Z3FormalVerifier,
    Z3VerificationError,
)
from app.core.domain.entities import AICommandStatus, PluginStatus, TenantContext
from app.core.domain.exceptions import DSLInvalidParametersError
from app.core.use_cases.ai_chat import AIChatDTO, AIChatUseCase
from app.core.use_cases.ai_command import AICommandDTO, AICommandUseCase


def _assert_valid_proof_contract(proof: dict, *, expected_status: str) -> None:
    assert isinstance(proof, dict)
    assert proof["status"] == expected_status
    assert proof["verified"] is (expected_status == "SAT")
    assert isinstance(proof["solve_time_ms"], float)
    assert 0.0 <= proof["solve_time_ms"] < 50.0
    assert isinstance(proof["invariants_checked"], list)
    assert any("tenant_isolation" in inv for inv in proof["invariants_checked"])
    assert isinstance(proof["escalated_to_critical"], bool)
    if expected_status == "SAT":
        assert proof["violated_constraint"] is None
        assert proof["counter_example"] is None
    else:
        assert isinstance(proof["violated_constraint"], str)
        assert len(proof["violated_constraint"]) > 0
        assert isinstance(proof["counter_example"], dict)


# ─── 1. Tenant Isolation & Backward Compatibility ─────────────────────────────


def test_z3_adapter_alias_and_tenant_isolation():
    assert Z3Adapter is Z3FormalVerifier
    adapter = Z3Adapter()

    sat_proof = adapter.verify_with_proof(
        {
            "action": "hr.employees.read",
            "effect": "read",
            "parameters": {"tenant_id": "tenant-ictu"},
        },
        context_tenant_id="tenant-ictu",
    )
    _assert_valid_proof_contract(sat_proof, expected_status="SAT")

    unsat_proof = adapter.verify_with_proof(
        {
            "action": "hr.employees.read",
            "effect": "read",
            "parameters": {"tenant_id": "tenant-hacker"},
        },
        context_tenant_id="tenant-ictu",
    )
    _assert_valid_proof_contract(unsat_proof, expected_status="UNSAT")
    assert "req.tenant_id" in unsat_proof["violated_constraint"]
    assert unsat_proof["counter_example"] == {
        "req_tenant_id": "tenant-hacker",
        "ctx_tenant_id": "tenant-ictu",
    }


def test_z3_legacy_verify_dsl_calls_verify_with_proof():
    verifier = Z3FormalVerifier(tenant_id="t-1", user_id="u-1")
    assert (
        verifier.verify_dsl(
            {
                "action": "hr.leave_requests.create",
                "parameters": {"days": 3, "remaining_leave_balance": 10},
            }
        )
        is True
    )
    assert verifier.last_proof is not None
    assert verifier.last_proof["status"] == "SAT"

    with pytest.raises(Z3VerificationError) as exc:
        verifier.verify_dsl(
            {
                "action": "hr.leave_requests.create",
                "parameters": {"days": 15, "remaining_leave_balance": 5},
            }
        )
    assert "Formal Verification Failed" in str(exc.value)
    assert exc.value.proof is not None
    assert exc.value.proof["status"] == "UNSAT"


# ─── 2. HR Domain (hr.*) ──────────────────────────────────────────────────────


def test_z3_hr_leave_and_salary_sat_and_unsat():
    adapter = Z3Adapter()

    # SAT: 0 < days <= remaining_leave_balance & salary > 0
    sat_proof = adapter.verify_with_proof(
        {
            "action": "hr.leave_requests.create",
            "effect": "write",
            "parameters": {
                "days": 4,
                "remaining_leave_balance": 12,
                "base_salary": 15_000_000,
                "allowance": 2_000_000,
            },
        },
        context_tenant_id="t-hr",
    )
    _assert_valid_proof_contract(sat_proof, expected_status="SAT")

    # UNSAT: days > remaining_leave_balance (kiểm tra đúng format violated_constraint)
    unsat_balance = adapter.verify_with_proof(
        {
            "action": "hr.leave_requests.create",
            "effect": "write",
            "parameters": {"days": 15, "remaining_leave_balance": 5},
        },
        context_tenant_id="t-hr",
    )
    _assert_valid_proof_contract(unsat_balance, expected_status="UNSAT")
    assert (
        unsat_balance["violated_constraint"]
        == "0 < days (15) <= remaining_leave_balance (5)"
    )
    assert unsat_balance["counter_example"] == {
        "days": 15,
        "remaining_leave_balance": 5,
    }

    # UNSAT: duration_days <= 0 (không có remaining_days)
    unsat_days_zero = adapter.verify_with_proof(
        {
            "action": "hr.leave_requests.create",
            "effect": "write",
            "parameters": {"duration_days": 0},
        },
        context_tenant_id="t-hr",
    )
    _assert_valid_proof_contract(unsat_days_zero, expected_status="UNSAT")
    assert "days (0) > 0" in unsat_days_zero["violated_constraint"]

    # UNSAT: salary <= 0
    unsat_salary = adapter.verify_with_proof(
        {
            "action": "hr.payroll.update",
            "effect": "write",
            "parameters": {"salary": -5_000_000},
        },
        context_tenant_id="t-hr",
    )
    _assert_valid_proof_contract(unsat_salary, expected_status="UNSAT")
    assert "salary (-5000000) > 0" in unsat_salary["violated_constraint"]


# ─── 3. Meeting Domain (meeting.*) ────────────────────────────────────────────


def test_z3_meeting_time_and_capacity_sat_and_unsat():
    adapter = Z3Adapter()

    # SAT với ISO-8601 time & attendees <= room_capacity
    sat_iso = adapter.verify_with_proof(
        {
            "action": "meeting.bookings.create",
            "effect": "write",
            "parameters": {
                "start_time": "2026-11-26T08:00:00Z",
                "end_time": "2026-11-26T10:30:00Z",
                "attendees": 25,
                "room_capacity": 40,
            },
        },
        context_tenant_id="t-meet",
    )
    _assert_valid_proof_contract(sat_iso, expected_status="SAT")

    # SAT với HH:MM & participant_count <= capacity
    sat_hhmm = adapter.verify_with_proof(
        {
            "action": "meeting.rooms.book",
            "effect": "write",
            "parameters": {
                "start_time": "13:30",
                "end_time": "15:00",
                "participant_count": 10,
                "capacity": 10,
            },
        },
        context_tenant_id="t-meet",
    )
    _assert_valid_proof_contract(sat_hhmm, expected_status="SAT")

    # UNSAT: start_time >= end_time
    unsat_time = adapter.verify_with_proof(
        {
            "action": "meeting.bookings.create",
            "effect": "write",
            "parameters": {
                "start_time": "2026-11-26T15:00:00+07:00",
                "end_time": "2026-11-26T14:00:00+07:00",
            },
        },
        context_tenant_id="t-meet",
    )
    _assert_valid_proof_contract(unsat_time, expected_status="UNSAT")
    assert "start_time" in unsat_time["violated_constraint"]
    assert "< end_time" in unsat_time["violated_constraint"]

    # UNSAT: attendees > room_capacity
    unsat_cap = adapter.verify_with_proof(
        {
            "action": "meeting.bookings.create",
            "effect": "write",
            "parameters": {"attendees": 60, "room_capacity": 50},
        },
        context_tenant_id="t-meet",
    )
    _assert_valid_proof_contract(unsat_cap, expected_status="UNSAT")
    assert unsat_cap["violated_constraint"] == "attendees (60) <= room_capacity (50)"

    # UNSAT: attendees <= 0
    unsat_zero_att = adapter.verify_with_proof(
        {
            "action": "meeting.bookings.create",
            "effect": "write",
            "parameters": {"attendees": 0, "room_capacity": 30},
        },
        context_tenant_id="t-meet",
    )
    _assert_valid_proof_contract(unsat_zero_att, expected_status="UNSAT")
    assert "attendees (0) > 0" in unsat_zero_att["violated_constraint"]


# ─── 4. Procurement & Finance Domains (procurement.*, finance.*) ──────────────


def test_z3_procurement_and_finance_sat_unsat_and_escalation():
    adapter = Z3Adapter()
    assert CRITICAL_BUDGET_THRESHOLD == 50_000_000

    # SAT dưới ngưỡng 50M -> escalated_to_critical = False
    sat_normal = adapter.verify_with_proof(
        {
            "action": "procurement.po.create",
            "effect": "write",
            "parameters": {
                "total_amount": 20_000_000,
                "remaining_budget": 100_000_000,
                "quantity": 10,
                "unit_price": 2_000_000,
                "tax_rate": 0.08,
            },
        },
        context_tenant_id="t-proc",
    )
    _assert_valid_proof_contract(sat_normal, expected_status="SAT")
    assert sat_normal["escalated_to_critical"] is False

    # SAT >= 50M với effect="write" -> escalated_to_critical = True
    sat_escalated = adapter.verify_with_proof(
        {
            "action": "procurement.po.create",
            "effect": "write",
            "parameters": {
                "estimated_amount": 50_000_000,
                "remaining_budget": 80_000_000,
                "quantity": 5,
                "unit_price": 10_000_000,
            },
        },
        context_tenant_id="t-proc",
    )
    _assert_valid_proof_contract(sat_escalated, expected_status="SAT")
    assert sat_escalated["escalated_to_critical"] is True

    # UNSAT: vượt ngân sách remaining_budget
    unsat_budget = adapter.verify_with_proof(
        {
            "action": "finance.expense_requests.create",
            "effect": "write",
            "parameters": {
                "amount": 120_000_000,
                "remaining_budget": 80_000_000,
            },
        },
        context_tenant_id="t-fin",
    )
    _assert_valid_proof_contract(unsat_budget, expected_status="UNSAT")
    assert (
        unsat_budget["violated_constraint"]
        == "amount (120000000) <= remaining_budget (80000000)"
    )

    # UNSAT: quantity <= 0
    unsat_qty = adapter.verify_with_proof(
        {
            "action": "procurement.po.create",
            "effect": "write",
            "parameters": {"quantity": -2, "unit_price": 100_000},
        },
        context_tenant_id="t-proc",
    )
    _assert_valid_proof_contract(unsat_qty, expected_status="UNSAT")
    assert "quantity (-2) > 0" in unsat_qty["violated_constraint"]

    # UNSAT: unit_price < 0
    unsat_up = adapter.verify_with_proof(
        {
            "action": "procurement.po.create",
            "effect": "write",
            "parameters": {"quantity": 2, "unit_price": -1},
        },
        context_tenant_id="t-proc",
    )
    _assert_valid_proof_contract(unsat_up, expected_status="UNSAT")
    assert "unit_price (-1) >= 0" in unsat_up["violated_constraint"]

    # UNSAT: tax_rate ngoài [0, 1]
    unsat_tax = adapter.verify_with_proof(
        {
            "action": "finance.invoices.create",
            "effect": "write",
            "parameters": {"amount": 1_000_000, "tax_rate": 1.2},
        },
        context_tenant_id="t-fin",
    )
    _assert_valid_proof_contract(unsat_tax, expected_status="UNSAT")
    assert "0 <= tax_rate (1.2) <= 1" in unsat_tax["violated_constraint"]


# ─── 5. Asset Domain (asset.*) ────────────────────────────────────────────────


def test_z3_asset_transfer_sat_and_unsat():
    adapter = Z3Adapter()

    sat_asset = adapter.verify_with_proof(
        {
            "action": "asset.items.transfer",
            "effect": "write",
            "parameters": {"from_location": "Phòng C101", "to_location": "Phòng C202"},
        },
        context_tenant_id="t-asset",
    )
    _assert_valid_proof_contract(sat_asset, expected_status="SAT")

    unsat_asset = adapter.verify_with_proof(
        {
            "action": "asset.items.transfer",
            "effect": "write",
            "parameters": {"from_location": "Kho A", "to_location": "Kho A"},
        },
        context_tenant_id="t-asset",
    )
    _assert_valid_proof_contract(unsat_asset, expected_status="UNSAT")
    assert (
        unsat_asset["violated_constraint"]
        == "from_location ('Kho A') != to_location ('Kho A')"
    )
    assert unsat_asset["counter_example"] == {
        "from_location": "Kho A",
        "to_location": "Kho A",
    }

    # Invalid type cho thời gian meeting -> DSLInvalidParametersError
    with pytest.raises(DSLInvalidParametersError):
        adapter.verify_with_proof(
            {
                "action": "meeting.bookings.create",
                "parameters": {"start_time": "not-a-time", "end_time": "10:00"},
            },
            context_tenant_id="t-meet",
        )


# ─── 6. AICommandUseCase Integration (Pending, UNSAT, Escalation, Mock Compat) ─


def _make_command_use_case(z3_adapter=None):
    plugin_repo = AsyncMock()
    plugin_repo.get_tenant_plugin_status_by_code.return_value = PluginStatus.ACTIVE
    ai_command_repo = AsyncMock()
    dry_run_repo = AsyncMock()
    dry_run_repo.execute_dry_run.return_value = {"affected_count": 1, "preview": []}
    role_repo = AsyncMock()
    mattermost = AsyncMock()
    mattermost.send_interactive_message.return_value = "mm-msg-1"
    n8n = AsyncMock()
    return AICommandUseCase(
        plugin_repo=plugin_repo,
        ai_command_repo=ai_command_repo,
        dsl_dry_run_repo=dry_run_repo,
        role_repo=role_repo,
        mattermost_adapter=mattermost,
        n8n_adapter=n8n,
        z3_adapter=z3_adapter,
    )


@pytest.mark.asyncio
async def test_ai_command_pending_attaches_z3_verification_and_escalates_50m(
    monkeypatch,
):
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "MATTERMOST_SYSTEM_CHANNEL_ID", "ch-sys")
    uc = _make_command_use_case()
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )

    dto = AICommandDTO(
        command_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        dsl_version="1.0",
        action="procurement.po.create",
        effect="write",
        parameters={
            "amount": 65_000_000,
            "remaining_budget": 100_000_000,
            "quantity": 5,
            "unit_price": 13_000_000,
        },
        approval_message="Đề xuất mua 5 máy chủ lab AI",
    )

    status, msg, dry_res = await uc.execute(dto, ctx)

    assert status == AICommandStatus.PENDING_APPROVAL
    # Tự động nâng từ write (30 phút) -> critical (15 phút, cần 2 người duyệt)
    assert dto.effect == "critical"
    assert dry_res["effect"] == "critical"
    assert "15 phút" in msg
    assert "z3_verification" in dry_res
    z3_v = dry_res["z3_verification"]
    _assert_valid_proof_contract(z3_v, expected_status="SAT")
    assert z3_v["escalated_to_critical"] is True

    created_row = uc.ai_command_repo.create_command.call_args[0][0]
    assert created_row["effect"] == "critical"
    diff_sec = (
        created_row["approval_deadline"] - created_row["created_at"]
    ).total_seconds()
    assert diff_sec == 900


@pytest.mark.asyncio
async def test_ai_command_unsat_blocks_and_returns_violated_constraint():
    uc = _make_command_use_case()
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )

    dto = AICommandDTO(
        command_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        dsl_version="1.0",
        action="hr.leave_requests.create",
        effect="write",
        parameters={"days": 15, "remaining_leave_balance": 5},
    )

    status, msg, res = await uc.execute(dto, ctx)

    assert status == AICommandStatus.FAILED
    assert "0 < days (15) <= remaining_leave_balance (5)" in msg
    assert res is not None
    assert res["z3_verification"]["status"] == "UNSAT"
    assert res["z3_verification"]["verified"] is False
    assert (
        res["z3_verification"]["violated_constraint"]
        == "0 < days (15) <= remaining_leave_balance (5)"
    )
    uc.mattermost_adapter.send_interactive_message.assert_not_called()


@pytest.mark.asyncio
async def test_ai_command_magicmock_z3_adapter_backward_compatibility(monkeypatch):
    """Đảm bảo MagicMock / AsyncMock cũ không có verify_with_proof không bị lỗi
    và không nâng nhầm write -> critical."""
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "MATTERMOST_SYSTEM_CHANNEL_ID", "ch-sys")
    legacy_mock = MagicMock()
    legacy_mock.verify_dsl.return_value = True

    uc = _make_command_use_case(z3_adapter=legacy_mock)
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    dto = AICommandDTO(
        command_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        dsl_version="1.0",
        action="procurement.po.create",
        effect="write",
        parameters={"item": "Laptop"},
    )

    with patch(
        "app.core.use_cases.ai_command.DSLValidator.validate",
        new_callable=AsyncMock,
        return_value=True,
    ):
        status, _, dry_res = await uc.execute(dto, ctx)

    assert status == AICommandStatus.PENDING_APPROVAL
    assert dto.effect == "write"
    assert dry_res["effect"] == "write"
    assert dry_res["z3_verification"]["status"] == "SAT"
    legacy_mock.verify_dsl.assert_called_once()


# ─── 7. AIChatUseCase Integration (execute & execute_stream SSE) ──────────────


@pytest.mark.asyncio
async def test_ai_chat_propagates_z3_verification_on_pending_and_stream(monkeypatch):
    from app.infrastructure.config import settings

    monkeypatch.setattr(settings, "MATTERMOST_SYSTEM_CHANNEL_ID", "ch-sys")
    cmd_uc = _make_command_use_case()
    cmd_uc.ai_command_repo.get_command_by_id.return_value = {
        "approval_deadline": "2026-11-25T12:30:00+00:00"
    }

    dsl_json = json.dumps(
        {
            "action": "meeting.bookings.create",
            "effect": "write",
            "parameters": {
                "start_time": "2026-11-26T09:00:00Z",
                "end_time": "2026-11-26T10:30:00Z",
                "attendees": 12,
                "room_capacity": 20,
            },
            "approval_message": "Đặt phòng họp A1",
        }
    )

    class _MockStreamLLM:
        async def ainvoke_json(self, messages):
            return SimpleNamespace(content=dsl_json)

        async def astream(self, messages):
            yield dsl_json

    chat_uc = AIChatUseCase(llm_port=_MockStreamLLM(), ai_command_use_case=cmd_uc)
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    chat_dto = AIChatDTO(
        session_id=uuid.uuid4(),
        natural_language_input="Đặt phòng họp A1 cho 12 người từ 9h đến 10h30",
    )

    # 1) execute()
    status, _, result = await chat_uc.execute(chat_dto, ctx)
    assert status == AICommandStatus.PENDING_APPROVAL
    assert result["z3_verification"]["status"] == "SAT"
    assert result["dsl_preview"]["z3_verification"]["status"] == "SAT"
    assert result["dsl_preview"]["dry_run_result"]["z3_verification"]["status"] == "SAT"
    assert result["steps"][0]["z3_verification"]["status"] == "SAT"

    # 2) execute_stream()
    events = [ev async for ev in chat_uc.execute_stream(chat_dto, ctx)]
    step_ev = next(e for e in events if e["event"] == "step")
    res_ev = next(e for e in events if e["event"] == "result")
    assert step_ev["z3_verification"]["status"] == "SAT"
    assert res_ev["z3_verification"]["status"] == "SAT"
    assert res_ev["result"]["dsl_preview"]["z3_verification"]["status"] == "SAT"


@pytest.mark.asyncio
async def test_ai_chat_propagates_z3_unsat_on_execute_and_stream():
    cmd_uc = _make_command_use_case()
    bad_dsl_json = json.dumps(
        {
            "action": "hr.leave_requests.create",
            "effect": "write",
            "parameters": {"days": 20, "remaining_leave_balance": 4},
            "approval_message": "Xin nghỉ phép 20 ngày",
        }
    )

    llm_calls = 0

    class _SingleShotLLM:
        async def ainvoke_json(self, messages):
            nonlocal llm_calls
            llm_calls += 1
            return SimpleNamespace(content=bad_dsl_json)

        async def astream(self, messages):
            yield bad_dsl_json

    chat_uc = AIChatUseCase(llm_port=_SingleShotLLM(), ai_command_use_case=cmd_uc)
    ctx = TenantContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        roles=["tenant_admin"],
    )
    chat_dto = AIChatDTO(
        session_id=uuid.uuid4(),
        natural_language_input="Cho tôi nghỉ 20 ngày trong khi còn 4 ngày phép",
    )

    # 1) execute() dừng ngay khi Z3 UNSAT (không tốn thêm LLM ReAct retry)
    status, message, result = await chat_uc.execute(chat_dto, ctx)
    assert status == AICommandStatus.FAILED
    assert llm_calls == 1
    assert "0 < days (20) <= remaining_leave_balance (4)" in message
    assert result["z3_verification"]["status"] == "UNSAT"
    assert result["dsl_preview"]["z3_verification"]["status"] == "UNSAT"
    assert result["steps"][0]["z3_verification"]["status"] == "UNSAT"

    # 2) execute_stream() trả đầy đủ z3_verification trong step & result event
    events = [ev async for ev in chat_uc.execute_stream(chat_dto, ctx)]
    step_ev = next(e for e in events if e["event"] == "step")
    res_ev = next(e for e in events if e["event"] == "result")
    assert step_ev["status"] == "FAILED"
    assert step_ev["z3_verification"]["status"] == "UNSAT"
    assert (
        step_ev["z3_verification"]["violated_constraint"]
        == "0 < days (20) <= remaining_leave_balance (4)"
    )
    assert res_ev["status"] == "FAILED"
    assert res_ev["z3_verification"]["status"] == "UNSAT"
    assert res_ev["result"]["dsl_preview"]["z3_verification"]["status"] == "UNSAT"
