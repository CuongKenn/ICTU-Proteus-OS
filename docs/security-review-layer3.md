# Đánh giá An toàn Thông tin & Bảo mật Lớp 3 (Security Review — Layer 3)

**Dự án:** Proteus OS  
**Tác giả:** CuongKenn & ICTU Team  
**Giấy phép:** AGPL-3.0-or-later  
**Tham chiếu:** Issue #851 [L3-701], ADR-003, ADR-004, ADR-005  

---

## 1. Tổng quan Phạm vi Đánh giá

Lớp 3 chịu trách nhiệm quản lý **Trạng thái Thực thể (Digital Twin)**, **Context Broker (Orion-LD / NGSI-LD)**, **Transactional Outbox**, và **GraphQL Engine (Hasura)**. Mục tiêu bảo mật cốt lõi:
1. Đảm bảo phân tách đa khách hàng tuyệt đối (Multi-tenant Strict Isolation).
2. Chặn rò rỉ dữ liệu nhạy cảm và thông tin cá nhân (PII Protection).
3. Đảm bảo an toàn mạng nội bộ và kiểm soát điểm vào (Perimeter & Network Security).
4. Phòng chống vòng lặp sự kiện và cạn kiệt tài nguyên (Anti-sync loop & DoS Prevention).

---

## 2. Kết quả Đánh giá Chi tiết

### 2.1. Phân tách Đa khách hàng (Tenant Isolation & RLS)
- **Cơ chế:** Toàn bộ các bảng trong schema `context` (`context_outbox`, `entity_state`, `sync_cursor`, `subscriptions`) đều được cấu hình:
  ```sql
  ALTER TABLE context.<table_name> ENABLE ROW LEVEL SECURITY;
  ALTER TABLE context.<table_name> FORCE ROW LEVEL SECURITY;
  ```
  `FORCE ROW LEVEL SECURITY` đảm bảo ngay cả owner của bảng cũng bị áp dụng policy.
- **Dual Session GUC Support:** RLS policy hỗ trợ kép cả FastAPI và Hasura GraphQL Engine:
  ```sql
  CREATE POLICY tenant_isolation_policy_<tbl> ON context.<tbl>
    FOR ALL TO PUBLIC USING (
      current_setting('app.current_tenant_id', true) = '__system__'
      OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
      OR tenant_id = NULLIF(current_setting('hasura.user', true)::jsonb ->> 'x-hasura-tenant-id', '')::uuid
    );
  ```
- **Fail-closed:** Nếu một request không có token hoặc thiếu `tenant_id`, chuỗi rỗng `''` được truyền vào, `NULLIF` chuyển thành `NULL`, dẫn đến mệnh đề `tenant_id = NULL` luôn trả về `false` (không rò rỉ bất kỳ bản ghi nào).

### 2.2. Kiểm soát PII & Dữ liệu Nhạy cảm
- **Manifest Validator Gatekeeper:** Tại tầng cài đặt plugin, `ManifestValidator` quét toàn bộ block `ngsi.entities[].attributes[]`. Nếu phát hiện bất kỳ trường nào nằm trong danh mục cấm:
  - Mật khẩu & bí mật: `password`, `hashed_password`, `secret`, `token`, `api_key`
  - Thu nhập & ngân hàng: `salary`, `base_salary`, `bank_account`, `tax_id`
  - Định danh định danh cá nhân: `ssn`, `identity_card`
  Hệ thống **từ chối cài đặt (Hard Reject)** và báo lỗi rõ ràng.
- **Sanitized Views:** Với các bảng nghiệp vụ có chứa trường nhạy cảm (như `hr_employees` chứa `base_salary`), hệ thống tạo view `context.v_hr_employees_sanitized` với `WITH (security_barrier = true)` chỉ chọn các trường công khai.

### 2.3. Cách ly Mạng & Container Hardening
- **Mạng nội bộ:** `mongo`, `orion-ld`, và `context-sync-worker` nằm hoàn toàn trong bridge network `proteus-net` và **không map ports** ra host ở môi trường production.
- **Hasura Edge Ingress:** Hasura chỉ cho phép truy cập qua Traefik Reverse Proxy với JWT Secret bắt buộc (`HASURA_GRAPHQL_JWT_SECRET`) trỏ tới JWKS của Keycloak. Bật `HASURA_GRAPHQL_UNAUTHORIZED_ROLE: anonymous` và gán quyền `anonymous` không có quyền đọc `entity_state` hay `context_outbox`.

### 2.4. Chống Vòng Lặp Đồng Bộ (Anti-sync Loop)
- Luồng đồng bộ từ Outbox Worker -> Orion-LD chỉ thực hiện một chiều.
- Khi Orion-LD gửi webhook notification về endpoint `/api/v1/context/notifications`, backend chỉ cập nhật trực tiếp vào bảng cache `context.entity_state` và stream Redis, **không bao giờ ghi ngược lại `context.context_outbox`**. Điều này triệt tiêu hoàn toàn nguy cơ vòng lặp đệ quy gây nghẽn hàng đợi hoặc quá tải CPU.

---

## 3. Kết luận
Lớp 3 đạt tiêu chuẩn an toàn thông tin cấp doanh nghiệp, tuân thủ nguyên tắc Least Privilege, Defense-in-Depth và Zero-Trust multi-tenancy.
