# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Z3 SMT Solver Adapter for Formal Verification of DX-DSL.
Ensures zero-hallucination at the architectural level.
"""

from typing import Any

import structlog
from z3 import Real, Solver, StringVal, sat, unsat

from app.core.domain.exceptions import DSLInvalidParametersError

logger = structlog.get_logger(__name__)


class Z3VerificationError(Exception):
    pass


class Z3FormalVerifier:
    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def _to_float(self, field: str, value: Any) -> float:
        """Ép số an toàn — sai định dạng hoặc NaN/Inf → 400 (DSLInvalidParametersError), không 500 (#735)."""
        import math

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

    def verify_dsl(self, dsl_payload: dict[str, Any]) -> bool:
        """
        Verify the DX-DSL payload against mathematical and logical invariants.
        Raises Z3VerificationError if the model is unsatisfiable (violates invariants).
        """
        solver = Solver()

        # 1. Tenant Boundary Invariant (RLS)
        # Ensure that if the DSL attempts to specify a tenant_id, it MUST match the context tenant_id.
        # Fix M13: không str(dict) — tenant_id phải là str/UUID, ngược lại 400 rõ ràng.
        ctx_tenant = StringVal(str(self.tenant_id))
        params = dsl_payload.get("parameters", {})
        if not isinstance(params, dict):
            raise DSLInvalidParametersError("Parameters phải là một JSON object.")

        # Kiểm tra tenant_id ở cả root và parameters (#735)
        provided_tenant = dsl_payload.get("tenant_id") or params.get("tenant_id")
        if provided_tenant is not None:
            if isinstance(provided_tenant, (dict, list)) or not isinstance(
                provided_tenant, str
            ):
                raise DSLInvalidParametersError(
                    "Tham số 'tenant_id' phải là chuỗi UUID hợp lệ."
                )
            provided_tenant_val = StringVal(str(provided_tenant))
            solver.add(provided_tenant_val == ctx_tenant)

        # 2. Action specific mathematical invariants
        action = dsl_payload.get("action", "")

        if action == "finance.invoices.create":
            # Invariant: Invoice amount must be strictly greater than 0
            # Tham số amount là bắt buộc (#735)
            amount_val = params.get("amount")
            if amount_val is None:
                raise DSLInvalidParametersError(
                    "Tham số 'amount' là bắt buộc cho hóa đơn."
                )
            amount_var = Real("amount")
            solver.add(amount_var == self._to_float("amount", amount_val))
            solver.add(amount_var > 0)

            tax_val = params.get("tax_rate")
            if tax_val is not None:
                tax_var = Real("tax_rate")
                solver.add(tax_var == self._to_float("tax_rate", tax_val))
                solver.add(tax_var >= 0)
                solver.add(tax_var <= 1.0)

        elif action == "asset.transfer":
            # Invariant: From Location and To Location must be different and required (#735)
            from_loc_val = params.get("from_location")
            to_loc_val = params.get("to_location")

            if from_loc_val is None or to_loc_val is None:
                raise DSLInvalidParametersError(
                    "Cả hai tham số 'from_location' và 'to_location' đều bắt buộc khi điều chuyển tài sản."
                )
            if isinstance(from_loc_val, (dict, list)) or isinstance(
                to_loc_val, (dict, list)
            ):
                raise DSLInvalidParametersError(
                    "Tham số 'from_location'/'to_location' phải là chuỗi."
                )
            from_var = StringVal(str(from_loc_val))
            to_var = StringVal(str(to_loc_val))
            solver.add(from_var != to_var)

        # Check for Satisfiability
        result = solver.check()

        if result == sat:
            return True
        elif result == unsat:
            raise Z3VerificationError(
                "Formal Verification Failed: The DX-DSL payload violates critical mathematical invariants. Model is UNSAT."
            )
        else:
            raise Z3VerificationError(
                "Formal Verification Failed: Z3 Solver returned unknown state."
            )
