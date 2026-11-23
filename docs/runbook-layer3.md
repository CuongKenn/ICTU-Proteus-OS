# Hướng dẫn Vận hành, Xử lý Sự cố & Rollback Lớp 3 (Runbook — Layer 3)

**Dự án:** Proteus OS  
**Giấy phép:** AGPL-3.0-or-later  
**Tham chiếu:** Issue #855 [L3-705], docs/architecture.md, docs/deployment.md  

---

## 1. Hướng dẫn Triển khai (Deployment)

### 1.1. Khởi động Lớp 3
Lớp 3 được đóng gói dưới Docker Compose profile `layer3`. Để bật các dịch vụ Context Broker, Hasura, MongoDB, và Context Sync Worker:

```bash
cd deploy
# 1. Chạy migration cơ sở dữ liệu
docker compose exec backend alembic upgrade head

# 2. Khởi động các dịch vụ Lớp 3
docker compose --profile layer3 up -d
```

### 1.2. Kiểm tra Trạng thái (Healthchecks)
```bash
# Kiểm tra PostgreSQL & PostGIS
docker compose exec postgres pg_isready -U proteus -d proteus
docker compose exec postgres psql -U proteus -d proteus -c "SELECT PostGIS_Version();"

# Kiểm tra MongoDB
docker compose exec mongo mongosh --eval "db.runCommand({ ping: 1 })"

# Kiểm tra Orion-LD
docker compose exec orion-ld curl -f http://localhost:1026/version

# Kiểm tra Hasura GraphQL
docker compose exec hasura curl -f http://localhost:8080/healthz

# Kiểm tra Context Sync Worker logs
docker compose logs -f context-sync-worker
```

---

## 2. Giám sát & Xử lý Sự cố (Troubleshooting)

### 2.1. Kiểm tra Độ trễ Outbox (Outbox Queue Lag)
Truy vấn số lượng bản ghi đang chờ xử lý (`PENDING`) trong bảng outbox:
```sql
SELECT status, count(*), min(created_at), max(created_at)
FROM context.context_outbox
GROUP BY status;
```

### 2.2. Xử lý Hàng đợi Chết (Dead Letter Queue — DLQ)
Khi một bản ghi thử lại quá 5 lần (`max_retries`) do lỗi payload hoặc hệ thống đích không phản hồi, bản ghi sẽ chuyển sang trạng thái `DLQ`:
```sql
-- Xem các bản ghi lỗi trong DLQ
SELECT id, tenant_id, entity_type, entity_id, error_message, updated_at
FROM context.context_outbox
WHERE status = 'DLQ'
ORDER BY updated_at DESC
LIMIT 50;

-- Sau khi sửa lỗi nguyên nhân gốc, retry lại toàn bộ bản ghi DLQ:
UPDATE context.context_outbox
SET status = 'PENDING', retry_count = 0, error_message = NULL, updated_at = NOW()
WHERE status = 'DLQ';
```

---

## 3. Sao lưu & Phục hồi (Backup & Restore)

### 3.1. Sao lưu MongoDB Orion-LD
```bash
./deploy/scripts/backup_mongo.sh
```
File sao lưu nén `.archive.gz` được lưu tại `/backups/mongo/` và tự động dọn dẹp sau 7 ngày.

### 3.2. Phục hồi MongoDB Orion-LD
```bash
# Phục hồi từ bản sao lưu gần nhất:
./deploy/scripts/restore_mongo.sh

# Hoặc chỉ định rõ file:
./deploy/scripts/restore_mongo.sh /backups/mongo/mongo_orion_backup_2026-11-23_180000.archive.gz
```

---

## 4. Kế hoạch Hoàn tác (Rollback Plan)

Trong trường hợp xảy ra sự cố nghiêm trọng cần hoàn tác lại phiên bản trước khi triển khai Lớp 3:

### Bước 1: Dừng các container Lớp 3
```bash
docker compose --profile layer3 stop mongo orion-ld hasura context-sync-worker
docker compose rm -f mongo orion-ld hasura context-sync-worker
```

### Bước 2: Rollback Alembic Migrations
```bash
docker compose exec backend alembic downgrade l6g7h8i9j0k1
```
Lệnh này sẽ tuần tự:
1. `DROP VIEW IF EXISTS context.v_hr_employees_sanitized;`
2. `DROP FUNCTION IF EXISTS context.fn_generic_outbox_notify();`
3. `DROP TABLE IF EXISTS context.subscriptions, context.sync_cursor, context.entity_state, context.context_outbox;`
4. `DROP SCHEMA IF EXISTS context;`
5. Kiểm tra an toàn trước khi drop extension `postgis`.

### Bước 3: Khôi phục cấu hình Docker Compose
Đặt `LAYER3_ENABLED=false` trong `deploy/.env` và khởi động lại stack chuẩn:
```bash
docker compose up -d
```
Hệ thống Proteus OS hoạt động bình thường với cơ sở dữ liệu và dữ liệu cũ nguyên vẹn.
