#!/bin/bash
set -eo pipefail

# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Script thực thi sao lưu dữ liệu MongoDB (Context Broker backing store) tự động

BACKUP_DIR=${BACKUP_DIR:-"/backups/mongo"}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
MONGO_HOST=${MONGO_HOST:-"mongo"}
MONGO_PORT=${MONGO_PORT:-27017}
MONGO_USER=${MONGO_INITDB_ROOT_USERNAME:-"proteus_orion"}
MONGO_PASSWORD=${MONGO_INITDB_ROOT_PASSWORD:-"proteus_orion_secret"}
MONGO_DB=${MONGO_INITDB_DATABASE:-"orion"}
MATTERMOST_WEBHOOK_URL=${MATTERMOST_WEBHOOK_URL:-""}

send_notification() {
    local message="$1"
    if [ -n "${MATTERMOST_WEBHOOK_URL}" ] && [[ "${MATTERMOST_WEBHOOK_URL}" != *"CHANGE_ME"* ]]; then
        local payload="{\"text\": \"${message}\"}"
        if command -v curl >/dev/null 2>&1; then
            curl -s -X POST -H 'Content-Type: application/json' -d "${payload}" "${MATTERMOST_WEBHOOK_URL}" || true
        elif command -v wget >/dev/null 2>&1; then
            wget -qO- --header="Content-Type: application/json" --post-data="${payload}" "${MATTERMOST_WEBHOOK_URL}" >/dev/null 2>&1 || true
        fi
    fi
}

mkdir -p "${BACKUP_DIR}"

DATE=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/mongo_orion_backup_${DATE}.archive.gz"

echo "Starting backup of MongoDB ${MONGO_DB} at ${MONGO_HOST}:${MONGO_PORT} to ${BACKUP_FILE}..."

if mongodump --host="${MONGO_HOST}" --port="${MONGO_PORT}" --username="${MONGO_USER}" --password="${MONGO_PASSWORD}" --authenticationDatabase="admin" --db="${MONGO_DB}" --archive="${BACKUP_FILE}" --gzip; then
    echo "MongoDB backup completed successfully."
    
    echo "Cleaning up old backups (older than ${BACKUP_RETENTION_DAYS} days)..."
    find "${BACKUP_DIR}" -name "mongo_orion_backup_*.archive.gz" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete
    
    send_notification "✅ **[Proteus OS]** Backup MongoDB Orion-LD thành công! File: \`$(basename "${BACKUP_FILE}")\`"
else
    echo "MongoDB backup failed!"
    send_notification "❌ **[Proteus OS]** CẢNH BÁO: Backup MongoDB Orion-LD thất bại!"
    exit 1
fi
