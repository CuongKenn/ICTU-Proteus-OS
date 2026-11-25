<!--
Copyright (c) 2026 CuongKenn & ICTU Team
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Hướng dẫn Phát triển Plugin Nguồn mở trên Proteus OS (`proteus-sdk`)

Tài liệu này hướng dẫn các nhà phát triển cộng đồng và đối tác xây dựng, kiểm định và đóng góp các phân hệ nghiệp vụ (Plugins) chuẩn hóa lên nền tảng đa thuê bao **Proteus OS**.

---

## 1. Kiến trúc một Plugin chuẩn Proteus OS

Mỗi Plugin là một gói độc lập (Self-contained Package) nằm dưới thư mục `plugins/<plugin-code-name>/` gồm 5 thành phần cốt lõi:

```text
plugins/<plugin-code-name>/
├── manifest.yaml                 # Hợp đồng khai báo Metadata, RBAC, DB, Workflows, NGSI-LD
├── db/
│   └── seed_data.sql             # Khởi tạo bảng (CREATE TABLE) & dữ liệu mẫu ban đầu
├── migrations/
│   └── V1.0.0__initial.sql       # Migration SQL định danh phiên bản (idempotent)
├── workflows/
│   └── sample_webhook.json       # Luồng tự động hóa n8n gắn node n8n-nodes-base.webhook
└── frontend/
    └── src/App.tsx               # Giao diện Micro-Frontend chuẩn Swiss Slate (?embed=1)
```

---

## 2. Khởi tạo nhanh bằng `proteus-sdk` CLI

Chạy trực tiếp từ thư mục gốc dự án với `PYTHONPATH=sdk`:

```bash
# Khởi tạo phân hệ Quản lý Thiết bị Phòng Lab
PYTHONPATH=sdk python -m proteus_sdk init lab-equipment-module \
  --output-dir plugins \
  --display-name "Quản lý Thiết bị Phòng Lab"
```

Lệnh `init` tự động sinh đầy đủ:
- Header bản quyền chuẩn nguồn mở `SPDX-License-Identifier: AGPL-3.0-or-later` (UTF-8 không BOM).
- Bảng dữ liệu có tiền tố khớp tên phân hệ (`lab_items`) kèm cột cô lập đa thuê bao `tenant_id UUID NOT NULL`.
- Luồng mẫu n8n có node `n8n-nodes-base.webhook` khớp chính xác với `webhook_path` trong `manifest.yaml`.
- Khối ánh xạ `ngsi.entities` chuẩn chuẩn quốc tế **ETSI NGSI-LD** không chứa thông tin nhạy cảm (PII).

---

## 3. Các Quy tắc Bảo mật & Kiến trúc Bắt buộc

### 3.1. Cô lập Dữ liệu Đa thuê bao (PostgreSQL RLS)
- Mọi tên bảng trong `database.tables` bắt buộc mang tiền tố `<prefix>_` (ví dụ `lab-equipment-module` → `lab_*`).
- Mọi bảng nghiệp vụ phải có cột `tenant_id UUID NOT NULL` và sử dụng `current_setting('app.current_tenant_id')::uuid` khi seed dữ liệu mẫu.

### 3.2. Cổng kiểm duyệt PII trên NGSI-LD (`PII Gatekeeper` — L3-004)
- Khối `ngsi.entities[].attributes` chỉ dùng để xuất bản dữ liệu ngữ cảnh đô thị / tổ chức lên **Orion-LD Context Broker**.
- **TUYỆT ĐỐI CẤM** ánh xạ các cột dữ liệu định danh hoặc tài chính nhạy cảm: `salary`, `base_salary`, `gross_salary`, `net_salary`, `password`, `hashed_password`, `secret`, `ssn`, `bank_account`, `tax_id`, `identity_card`, `cccd`, `token`, `api_key`.

### 3.3. Nhúng mượt Giao diện Micro-Frontend (`?embed=1`)
- Khi nhúng vào Core Engine qua `/plugins/<code_name>`, hệ thống tự động truyền `?embed=1&theme=light|dark` và đồng bộ chế độ Sáng/Tối qua `window.postMessage({ type: "proteus-theme", theme })`.
- Sử dụng biến màu CSS `var(--mfe-bg)`, `var(--mfe-panel)`, `var(--mfe-text)`, `var(--mfe-line)`, `var(--mfe-accent)` để đồng nhất giao diện Swiss Slate.

---

## 4. Kiểm định Hợp đồng Tĩnh trước khi tạo Pull Request

Trước khi đóng gói hoặc gửi PR, bắt buộc chạy trình kiểm định `validate`:

```bash
PYTHONPATH=sdk python -m proteus_sdk validate plugins/lab-equipment-module
```

Công cụ `validate` sẽ trả về `exit code = 0` khi tất cả 6 chốt chặn đều đạt:
1. Không tồn tại ký tự ẩn **UTF-8 BOM** (`EF BB BF`) trong bất kỳ tệp YAML, JSON, SQL, TS/TSX, Python nào.
2. Cú pháp `manifest.yaml` hợp lệ, đủ trường bắt buộc, đúng chuẩn `kebab-case` & `SemVer`.
3. Chống tấn công **Path Traversal** (`..` hoặc đường dẫn tuyệt đối) trên mọi đường dẫn file tham chiếu.
4. Tất cả bảng trong `database.tables` đều có câu lệnh `CREATE TABLE` thực tế trong `db/seed_data.sql` hoặc `migrations/*.sql`.
5. Mọi workflow có `trigger: webhook` đều chứa node `n8n-nodes-base.webhook` khớp `webhook_path`.
6. Vượt qua chốt chặn **PII Gatekeeper** trên toàn bộ thực thể `ngsi.entities`.
