# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest

from app.core.domain.exceptions import DSLInvalidParametersError
from app.core.formal_verification.z3_adapter import (
    Z3FormalVerifier,
    Z3VerificationError,
)


def test_z3_nan_or_inf_raises_400():
    verifier = Z3FormalVerifier(tenant_id="tenant-1", user_id="user-1")

    # NaN in amount
    with pytest.raises(DSLInvalidParametersError) as exc:
        verifier.verify_dsl(
            {
                "action": "finance.invoices.create",
                "parameters": {"amount": float("nan"), "tax_rate": 0.1},
            }
        )
    assert "số hợp lệ" in str(exc.value)

    # Inf in amount
    with pytest.raises(DSLInvalidParametersError) as exc:
        verifier.verify_dsl(
            {
                "action": "finance.invoices.create",
                "parameters": {"amount": float("inf"), "tax_rate": 0.1},
            }
        )
    assert "số hợp lệ" in str(exc.value)


def test_z3_tenant_boundary_in_parameters():
    verifier = Z3FormalVerifier(tenant_id="tenant-1", user_id="user-1")

    # tenant_id mismatch in parameters
    with pytest.raises(Z3VerificationError):
        verifier.verify_dsl(
            {
                "action": "finance.invoices.create",
                "parameters": {"amount": 100.0, "tenant_id": "different-tenant"},
            }
        )

    # tenant_id match in parameters
    res = verifier.verify_dsl(
        {
            "action": "finance.invoices.create",
            "parameters": {"amount": 100.0, "tenant_id": "tenant-1"},
        }
    )
    assert res is True


def test_z3_missing_parameters_rejects():
    verifier = Z3FormalVerifier(tenant_id="tenant-1", user_id="user-1")

    # Missing amount in finance invoice
    with pytest.raises(DSLInvalidParametersError):
        verifier.verify_dsl(
            {
                "action": "finance.invoices.create",
                "parameters": {"tax_rate": 0.1},
            }
        )

    # Missing location in asset transfer
    with pytest.raises(DSLInvalidParametersError):
        verifier.verify_dsl(
            {
                "action": "asset.transfer",
                "parameters": {"from_location": "Warehouse A"},
            }
        )
