#!/bin/bash
set -eo pipefail

# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Script phục hồi dữ liệu MongoDB (Context Broker backing store) từ bản sao lưu

BACKUP_DIR=${BACKUP_DIR:-"/backups/mongo"}
MONGO_HOST=${MONGO_HOST:-"mongo"}
MONGO_PORT=${MONGO_PORT:-27017}
MONGO_USER=${MONGO_USER:-${MONGO_INITDB_ROOT_USERNAME:-""}}
MONGO_PASSWORD=${MONGO_PASSWORD:-${MONGO_INITDB_ROOT_PASSWORD:-""}}
MONGO_AUTH_DB=${MONGO_AUTH_DB:-"admin"}

# Kiểm tra file backup
if [ -n "${1:-}" ]; then
    RESTORE_FILE="$1"
else
    # Lấy file mới nhất
    RESTORE_FILE=$(ls -t "${BACKUP_DIR}"/mongo_orion_backup_*.archive.gz 2>/dev/null | head -n 1 || true)
fi

if [ -z "${RESTORE_FILE}" ] || [ ! -f "${RESTORE_FILE}" ]; then
    echo "Error: Không tìm thấy file backup MongoDB để phục hồi!"
    exit 1
fi

AUTH_ARGS=()
if [ -n "${MONGO_USER}" ]; then
    AUTH_ARGS=(
        "--username=${MONGO_USER}"
        "--password=${MONGO_PASSWORD}"
        "--authenticationDatabase=${MONGO_AUTH_DB}"
    )
fi

echo "Starting full multi-tenant MongoDB restore from ${RESTORE_FILE} into ${MONGO_HOST}:${MONGO_PORT}..."

mongorestore \
    --host="${MONGO_HOST}" \
    --port="${MONGO_PORT}" \
    "${AUTH_ARGS[@]}" \
    --archive="${RESTORE_FILE}" \
    --gzip \
    --drop

echo "MongoDB restore completed successfully!"
