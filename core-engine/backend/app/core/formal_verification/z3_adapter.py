# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Z3 SMT Solver Adapter for Formal Verification of DX-DSL (Issue #873).
Ensures zero-hallucination and mathematical Poka-yoke at the architectural level.
"""

from __future__ import annotations

import math
import re
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from z3 import (
    And,
    Bool,
    Int,
    IntVal,
    Real,
    RealVal,
    Solver,
    String,
    StringVal,
    sat,
    unsat,
)

from app.core.domain.exceptions import DSLInvalidParametersError

logger = structlog.get_logger(__name__)

CRITICAL_BUDGET_THRESHOLD = 50_000_000.0
_TIME_ONLY_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


class Z3VerificationError(Exception):
    """Raised when DX-DSL payload violates Z3 formal invariants (UNSAT)."""

    def __init__(self, message: str, proof: dict[str, Any] | None = None):
        super().__init__(message)
        self.proof = proof


class Z3FormalVerifier:
    """Z3 SMT Solver verifier supporting both boolean check and proof contract."""

    def __init__(self, tenant_id: str | None = None, user_id: str | None = None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.last_proof: dict[str, Any] | None = None

    def _to_float(self, field: str, value: Any) -> float:
        """Ép số an toàn — sai định dạng hoặc NaN/Inf → 400, không 500 (#735)."""
        try:
            if isinstance(value, bool):
                raise ValueError("bool is not a valid number")
            val = float(value)
            if not math.isfinite(val):
                raise ValueError("Value must be finite (not NaN or Inf)")
            return val
        except (TypeError, ValueError) as exc:
            raise DSLInvalidParametersError(
                f"Tham số '{field}' phải là số hợp lệ (hữu hạn, không NaN/Inf)."
            ) from exc

    @staticmethod
    def _real_val(num: float):
        """Chuyển float hữu hạn sang z3.RealVal chính xác không dính khoa học."""
        return RealVal(format(Decimal(str(num)), "f"))

    @staticmethod
    def _display_num(raw: Any, parsed: float) -> int | float:
        """Giữ định dạng số gọn gàng khi hiển thị biểu thức vi phạm."""
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        if isinstance(raw, float):
            return int(raw) if raw.is_integer() else raw
        return int(parsed) if parsed.is_integer() else parsed

    def _parse_time_value(self, field: str, value: Any) -> float:
        """Chuyển ISO-8601, HH:MM[:SS] hoặc số giờ/epoch sang giây để so sánh SMT."""
        if isinstance(value, bool) or isinstance(value, dict | list):
            raise DSLInvalidParametersError(
                f"Tham số '{field}' phải là thời gian ISO-8601, HH:MM hoặc số."
            )
        if isinstance(value, int | float):
            return self._to_float(field, value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise DSLInvalidParametersError(
                    f"Tham số '{field}' không được để trống."
                )
            try:
                num = float(raw)
                if not math.isfinite(num):
                    raise ValueError("Non-finite time value")
                return num
            except ValueError:
                pass

            m = _TIME_ONLY_RE.match(raw)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2))
                ss = int(m.group(3) or 0)
                if (
                    (0 <= hh <= 23 or (hh == 24 and mm == 0 and ss == 0))
                    and 0 <= mm <= 59
                    and 0 <= ss <= 59
                ):
                    return float(hh * 3600 + mm * 60 + ss)
                raise DSLInvalidParametersError(
                    f"Tham số '{field}' có giá trị giờ/phút không hợp lệ: '{value}'."
                )

            iso = f"{raw[:-1]}+00:00" if raw.endswith(("Z", "z")) else raw
            try:
                dt = datetime.fromisoformat(iso)
            except ValueError as exc:
                raise DSLInvalidParametersError(
                    f"Tham số '{field}' phải là thời gian ISO-8601, HH:MM hoặc số."
                ) from exc
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.timestamp()

        raise DSLInvalidParametersError(
            f"Tham số '{field}' phải là thời gian ISO-8601, HH:MM hoặc số."
        )

    def verify_with_proof(
        self, dsl_payload: dict[str, Any], context_tenant_id: str | None = None
    ) -> dict[str, Any]:
        """Kiểm chứng DX-DSL bằng Z3 SMT Solver và trả về proof_dict chuẩn (#873)."""
        t0 = time.perf_counter()
        if not isinstance(dsl_payload, dict):
            raise DSLInvalidParametersError("DSL payload phải là một JSON object.")

        params = dsl_payload.get("parameters", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise DSLInvalidParametersError("Parameters phải là một JSON object.")

        eff_ctx_tenant = (
            str(context_tenant_id)
            if context_tenant_id is not None
            else (str(self.tenant_id) if self.tenant_id is not None else "")
        )

        solver = Solver()
        invariants_checked: list[str] = []
        tracked_meta: list[tuple[Any, str, dict[str, Any]]] = []
        escalated_to_critical = False

        def _track(expr: Any, label: str, violated_expr: str, cex: dict[str, Any]):
            idx = len(tracked_meta)
            tracker = Bool(f"__z3_inv_{idx}")
            invariants_checked.append(label)
            tracked_meta.append((tracker, violated_expr, cex))
            solver.assert_and_track(expr, tracker)

        # 1. Bất biến chung: Tenant Isolation (RLS)
        root_tenant = dsl_payload.get("tenant_id")
        param_tenant = params.get("tenant_id")
        for cand in (root_tenant, param_tenant):
            if cand is not None and (
                isinstance(cand, dict | list | bool)
                or not isinstance(cand, str | uuid.UUID)
            ):
                raise DSLInvalidParametersError(
                    "Tham số 'tenant_id' phải là chuỗi UUID hợp lệ."
                )

        provided_tenant: str | None = None
        if param_tenant is not None and str(param_tenant) != eff_ctx_tenant:
            provided_tenant = str(param_tenant)
        elif root_tenant is not None:
            provided_tenant = str(root_tenant)
        elif param_tenant is not None:
            provided_tenant = str(param_tenant)

        effective_req_tenant = (
            provided_tenant if provided_tenant is not None else eff_ctx_tenant
        )
        req_tenant_var = String("req_tenant_id")
        ctx_tenant_var = String("ctx_tenant_id")
        solver.add(req_tenant_var == StringVal(effective_req_tenant))
        solver.add(ctx_tenant_var == StringVal(eff_ctx_tenant))
        tenant_violation = (
            f"req.tenant_id ('{effective_req_tenant}') "
            f"== ctx.tenant_id ('{eff_ctx_tenant}')"
        )
        _track(
            req_tenant_var == ctx_tenant_var,
            "tenant_isolation: req.tenant_id == ctx.tenant_id",
            tenant_violation,
            {
                "req_tenant_id": effective_req_tenant,
                "ctx_tenant_id": eff_ctx_tenant,
            },
        )

        action = str(dsl_payload.get("action") or "")
        effect = dsl_payload.get("effect")
        if effect is None and action:
            from app.core.use_cases.action_catalog import derive_action_effect

            effect = derive_action_effect(action)

        # 2. Miền HR (hr.* — nghỉ phép, nhân sự, lương)
        if action.startswith("hr."):
            days_key = (
                "days"
                if params.get("days") is not None
                else (
                    "duration_days" if params.get("duration_days") is not None else None
                )
            )
            rem_key = (
                "remaining_leave_balance"
                if params.get("remaining_leave_balance") is not None
                else (
                    "remaining_days"
                    if params.get("remaining_days") is not None
                    else None
                )
            )
            if days_key is not None:
                days_raw = params[days_key]
                days_val = self._to_float(days_key, days_raw)
                days_disp = self._display_num(days_raw, days_val)
                days_var = Real("days")
                solver.add(days_var == self._real_val(days_val))

                if rem_key is not None:
                    rem_raw = params[rem_key]
                    rem_val = self._to_float(rem_key, rem_raw)
                    rem_disp = self._display_num(rem_raw, rem_val)
                    rem_var = Real("remaining_leave_balance")
                    solver.add(rem_var == self._real_val(rem_val))
                    leave_violation = (
                        f"0 < days ({days_disp}) "
                        f"<= remaining_leave_balance ({rem_disp})"
                    )
                    _track(
                        And(days_var > 0, days_var <= rem_var),
                        "hr_leave_bounds: 0 < days <= remaining_leave_balance",
                        leave_violation,
                        {
                            "days": days_disp,
                            "remaining_leave_balance": rem_disp,
                        },
                    )
                else:
                    _track(
                        days_var > 0,
                        "hr_leave_positive: days > 0",
                        f"days ({days_disp}) > 0",
                        {days_key: days_disp},
                    )

            for sal_field in ("salary", "base_salary", "allowance"):
                if params.get(sal_field) is not None:
                    sal_raw = params[sal_field]
                    sal_val = self._to_float(sal_field, sal_raw)
                    sal_disp = self._display_num(sal_raw, sal_val)
                    sal_var = Real(sal_field)
                    solver.add(sal_var == self._real_val(sal_val))
                    _track(
                        sal_var > 0,
                        f"hr_{sal_field}_positive: {sal_field} > 0",
                        f"{sal_field} ({sal_disp}) > 0",
                        {sal_field: sal_disp},
                    )

        # 3. Miền Meeting (meeting.* — đặt phòng họp / giảng đường)
        elif action.startswith("meeting."):
            if (
                params.get("start_time") is not None
                and params.get("end_time") is not None
            ):
                start_raw = params["start_time"]
                end_raw = params["end_time"]
                start_sec = self._parse_time_value("start_time", start_raw)
                end_sec = self._parse_time_value("end_time", end_raw)
                start_var = Real("start_time")
                end_var = Real("end_time")
                solver.add(start_var == self._real_val(start_sec))
                solver.add(end_var == self._real_val(end_sec))
                _track(
                    start_var < end_var,
                    "meeting_time_order: start_time < end_time",
                    f"start_time ({start_raw}) < end_time ({end_raw})",
                    {"start_time": start_raw, "end_time": end_raw},
                )

            att_key = (
                "attendees"
                if params.get("attendees") is not None
                else (
                    "participant_count"
                    if params.get("participant_count") is not None
                    else None
                )
            )
            cap_key = (
                "room_capacity"
                if params.get("room_capacity") is not None
                else ("capacity" if params.get("capacity") is not None else None)
            )
            if att_key is not None:
                att_raw = params[att_key]
                att_val = self._to_float(att_key, att_raw)
                att_disp = self._display_num(att_raw, att_val)
                use_int = att_val.is_integer() and (
                    cap_key is None
                    or self._to_float(cap_key, params[cap_key]).is_integer()
                )
                if use_int:
                    att_var: Any = Int("attendees")
                    solver.add(att_var == IntVal(int(att_val)))
                else:
                    att_var = Real("attendees")
                    solver.add(att_var == self._real_val(att_val))

                _track(
                    att_var > 0,
                    "meeting_attendees_positive: attendees > 0",
                    f"attendees ({att_disp}) > 0",
                    {att_key: att_disp},
                )

                if cap_key is not None:
                    cap_raw = params[cap_key]
                    cap_val = self._to_float(cap_key, cap_raw)
                    cap_disp = self._display_num(cap_raw, cap_val)
                    if use_int:
                        cap_var: Any = Int("room_capacity")
                        solver.add(cap_var == IntVal(int(cap_val)))
                    else:
                        cap_var = Real("room_capacity")
                        solver.add(cap_var == self._real_val(cap_val))
                    _track(
                        att_var <= cap_var,
                        "meeting_room_capacity: attendees <= room_capacity",
                        f"attendees ({att_disp}) <= room_capacity ({cap_disp})",
                        {"attendees": att_disp, "room_capacity": cap_disp},
                    )

        # 4. Miền Procurement & Finance (procurement.*, finance.*)
        elif action.startswith("procurement.") or action.startswith("finance."):
            amount_key = next(
                (
                    k
                    for k in ("amount", "total_amount", "estimated_amount")
                    if params.get(k) is not None
                ),
                None,
            )
            if amount_key is not None:
                amount_raw = params[amount_key]
                amount_val = self._to_float(amount_key, amount_raw)
                amount_disp = self._display_num(amount_raw, amount_val)
                amount_var = Real("amount")
                solver.add(amount_var == self._real_val(amount_val))
                _track(
                    amount_var > 0,
                    f"finance_amount_positive: {amount_key} > 0",
                    f"{amount_key} ({amount_disp}) > 0",
                    {amount_key: amount_disp},
                )

                if params.get("remaining_budget") is not None:
                    budget_raw = params["remaining_budget"]
                    budget_val = self._to_float("remaining_budget", budget_raw)
                    budget_disp = self._display_num(budget_raw, budget_val)
                    budget_var = Real("remaining_budget")
                    solver.add(budget_var == self._real_val(budget_val))
                    budget_violation = (
                        f"{amount_key} ({amount_disp}) "
                        f"<= remaining_budget ({budget_disp})"
                    )
                    _track(
                        amount_var <= budget_var,
                        f"budget_cap: {amount_key} <= remaining_budget",
                        budget_violation,
                        {
                            amount_key: amount_disp,
                            "remaining_budget": budget_disp,
                        },
                    )

                if amount_val >= CRITICAL_BUDGET_THRESHOLD and effect == "write":
                    escalated_to_critical = True
                    invariants_checked.append(
                        f"dual_approval_escalation: "
                        f"{amount_key} >= 50_000_000 -> critical"
                    )

            if params.get("quantity") is not None:
                qty_raw = params["quantity"]
                qty_val = self._to_float("quantity", qty_raw)
                qty_disp = self._display_num(qty_raw, qty_val)
                if qty_val.is_integer():
                    qty_var: Any = Int("quantity")
                    solver.add(qty_var == IntVal(int(qty_val)))
                else:
                    qty_var = Real("quantity")
                    solver.add(qty_var == self._real_val(qty_val))
                _track(
                    qty_var > 0,
                    "procurement_quantity_positive: quantity > 0",
                    f"quantity ({qty_disp}) > 0",
                    {"quantity": qty_disp},
                )

            if params.get("unit_price") is not None:
                up_raw = params["unit_price"]
                up_val = self._to_float("unit_price", up_raw)
                up_disp = self._display_num(up_raw, up_val)
                up_var = Real("unit_price")
                solver.add(up_var == self._real_val(up_val))
                _track(
                    up_var >= 0,
                    "procurement_unit_price_non_negative: unit_price >= 0",
                    f"unit_price ({up_disp}) >= 0",
                    {"unit_price": up_disp},
                )

            if params.get("tax_rate") is not None:
                tax_raw = params["tax_rate"]
                tax_val = self._to_float("tax_rate", tax_raw)
                tax_disp = self._display_num(tax_raw, tax_val)
                tax_var = Real("tax_rate")
                solver.add(tax_var == self._real_val(tax_val))
                _track(
                    And(tax_var >= 0, tax_var <= 1.0),
                    "finance_tax_rate_bounds: 0 <= tax_rate <= 1",
                    f"0 <= tax_rate ({tax_disp}) <= 1",
                    {"tax_rate": tax_disp},
                )

        # 5. Miền Asset (asset.* — điều chuyển tài sản)
        elif action.startswith("asset."):
            from_loc_val = params.get("from_location")
            to_loc_val = params.get("to_location")
            if from_loc_val is not None and to_loc_val is not None:
                if isinstance(from_loc_val, dict | list) or isinstance(
                    to_loc_val, dict | list
                ):
                    raise DSLInvalidParametersError(
                        "Tham số 'from_location'/'to_location' phải là chuỗi."
                    )
                from_str = str(from_loc_val).strip()
                to_str = str(to_loc_val).strip()
                from_var = String("from_location")
                to_var = String("to_location")
                solver.add(from_var == StringVal(from_str))
                solver.add(to_var == StringVal(to_str))
                _track(
                    from_var != to_var,
                    "asset_transfer_distinct_locations: from_location != to_location",
                    f"from_location ('{from_loc_val}') != to_location ('{to_loc_val}')",
                    {
                        "from_location": str(from_loc_val),
                        "to_location": str(to_loc_val),
                    },
                )

        result = solver.check()
        solve_time_ms = round((time.perf_counter() - t0) * 1000, 2)

        if result == sat:
            proof: dict[str, Any] = {
                "status": "SAT",
                "verified": True,
                "solve_time_ms": solve_time_ms,
                "invariants_checked": invariants_checked,
                "violated_constraint": None,
                "counter_example": None,
                "escalated_to_critical": escalated_to_critical,
            }
            self.last_proof = proof
            return proof

        violated_constraint = "Model is UNSAT"
        counter_example: dict[str, Any] | None = None
        if result == unsat:
            core = set(solver.unsat_core())
            for tracker, v_expr, cex in tracked_meta:
                if tracker in core:
                    violated_constraint = v_expr
                    counter_example = cex
                    break
        else:
            violated_constraint = "Z3 Solver returned unknown state"

        proof = {
            "status": "UNSAT",
            "verified": False,
            "solve_time_ms": solve_time_ms,
            "invariants_checked": invariants_checked,
            "violated_constraint": violated_constraint,
            "counter_example": counter_example,
            "escalated_to_critical": escalated_to_critical,
        }
        self.last_proof = proof
        return proof

    def verify_dsl(self, dsl_payload: dict[str, Any]) -> bool:
        """
        Verify the DX-DSL payload against mathematical and logical invariants.
        Raises Z3VerificationError if the model is unsatisfiable (violates invariants).
        Giữ 100% tương thích ngược với bộ kiểm thử cũ (#735).
        """
        if not isinstance(dsl_payload, dict):
            raise DSLInvalidParametersError("DSL payload phải là một JSON object.")
        params = dsl_payload.get("parameters", {})
        if not isinstance(params, dict):
            raise DSLInvalidParametersError("Parameters phải là một JSON object.")

        action = dsl_payload.get("action", "")
        if action == "finance.invoices.create" and params.get("amount") is None:
            raise DSLInvalidParametersError("Tham số 'amount' là bắt buộc cho hóa đơn.")
        if action == "asset.transfer" and (
            params.get("from_location") is None or params.get("to_location") is None
        ):
            raise DSLInvalidParametersError(
                "Cả hai tham số 'from_location' và 'to_location' "
                "đều bắt buộc khi điều chuyển tài sản."
            )

        ctx_tid = str(self.tenant_id) if self.tenant_id is not None else ""
        proof = self.verify_with_proof(dsl_payload, context_tenant_id=ctx_tid)
        if proof["verified"]:
            return True

        detail = proof.get("violated_constraint")
        suffix = f" Violated: {detail}" if detail else ""
        raise Z3VerificationError(
            "Formal Verification Failed: The DX-DSL payload violates critical "
            f"mathematical invariants. Model is UNSAT.{suffix}",
            proof=proof,
        )


Z3Adapter = Z3FormalVerifier

__all__ = [
    "CRITICAL_BUDGET_THRESHOLD",
    "Z3Adapter",
    "Z3FormalVerifier",
    "Z3VerificationError",
]
