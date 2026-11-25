# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
External/Adapter re-export for Z3 SMT Solver Poka-yoke (#873).
Đồng nhất đường dẫn import `app.adapters.external.z3_adapter` với
`app.core.formal_verification.z3_adapter`.
"""

from app.core.formal_verification.z3_adapter import (
    CRITICAL_BUDGET_THRESHOLD,
    Z3Adapter,
    Z3FormalVerifier,
    Z3VerificationError,
)

__all__ = [
    "CRITICAL_BUDGET_THRESHOLD",
    "Z3Adapter",
    "Z3FormalVerifier",
    "Z3VerificationError",
]
