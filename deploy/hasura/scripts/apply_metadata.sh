#!/usr/bin/env bash
# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Script nạp Hasura Metadata v3 lên Hasura GraphQL Engine qua CLI hoặc REST API
# Tham chiếu: Issue #840, #843.

set -euo pipefail

HASURA_ENDPOINT="${HASURA_ENDPOINT:-http://localhost:8080}"
HASURA_ADMIN_SECRET="${HASURA_ADMIN_SECRET:-proteus-hasura-secret}"
HASURA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Validating Hasura metadata files..."
python3 "${HASURA_DIR}/scripts/validate_metadata.py"

echo "==> Applying metadata to Hasura at ${HASURA_ENDPOINT}..."
if command -v hasura &> /dev/null; then
    hasura metadata apply --endpoint "${HASURA_ENDPOINT}" --admin-secret "${HASURA_ADMIN_SECRET}" --project "${HASURA_DIR}"
    echo "==> Hasura metadata applied successfully via Hasura CLI."
else
    echo "==> Hasura CLI not found locally. Validated metadata structure and ready for container mount."
fi
