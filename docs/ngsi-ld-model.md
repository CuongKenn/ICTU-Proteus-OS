<!--
Copyright (c) 2026 CuongKenn & ICTU Team
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Proteus OS — Đặc Tả Mô Hình Thực Thể NGSI-LD (ETSI GS CIM 009)

Tài liệu này quy chuẩn cấu trúc dữ liệu, quy ước định danh và cơ chế biểu diễn ngữ cảnh số (Context Broker / Digital Twin) theo tiêu chuẩn **ETSI NGSI-LD v1.6+**.

---

## 1. Quy Ước Định Danh Thực Thể (Entity ID Convention)

Mọi thực thể (Entity) trong hệ thống Proteus OS phải có mã định danh toàn cầu duy nhất dạng URN theo định dạng chuẩn:

```
urn:ngsi-ld:{EntityType}:{tenant_id}:{entity_id}
```

* **`EntityType`**: Tên kiểu thực thể viết hoa chữ cái đầu (PascalCase), ví dụ: `Room`, `Employee`, `Asset`, `Project`, `Task`, `Invoice`, `Ticket`.
* **`tenant_id`**: Mã định danh tổ chức UUID v4 (chuẩn hóa chữ thường không dấu ngoặc).
* **`entity_id`**: Khóa chính duy nhất của bản ghi nghiệp vụ (UUID hoặc mã duy nhất dạng `slug`/mã định danh).

**Ví dụ hợp lệ:**
* Phòng họp: `urn:ngsi-ld:Room:00000000-0000-0000-0000-000000000001:room-101`
* Nhân viên: `urn:ngsi-ld:Employee:00000000-0000-0000-0000-000000000001:emp-0089`
* Thiết bị: `urn:ngsi-ld:Asset:00000000-0000-0000-0000-000000000001:ast-laptop-dell-9320`

---

## 2. Quy Chuẩn Thành Phần Dữ Liệu NGSI-LD

Trong mô hình NGSI-LD, mọi thuộc tính đều phải được phân loại rõ ràng thành 1 trong 3 nhóm chính:

### 2.1. Thuộc tính Giá trị (Property)
Dùng để mô tả thông tin trạng thái hoặc giá trị vô hướng:
```json
"capacity": {
  "type": "Property",
  "value": 30,
  "unitCode": "C62"
}
```

### 2.2. Quan hệ Thực thể (Relationship)
Dùng để liên kết tới một thực thể NGSI-LD khác thông qua `object` mang định dạng URN:
```json
"assignedTo": {
  "type": "Relationship",
  "object": "urn:ngsi-ld:Employee:00000000-0000-0000-0000-000000000001:emp-0089"
}
```

### 2.3. Thuộc tính Không gian (GeoProperty)
Dùng để xác định vị trí tọa độ địa lý chuẩn GeoJSON (WGS84, EPSG:4326):
```json
"location": {
  "type": "GeoProperty",
  "value": {
    "type": "Point",
    "coordinates": [105.804817, 21.028511]
  }
}
```

---

## 3. Định Nghĩa Ngữ Cảnh `@context`

Mọi thực thể đồng bộ qua Orion-LD hoặc truy vấn GraphQL bắt buộc khai báo mảng `@context`:

```json
"@context": [
  "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
  "http://context.proteus.local/ngsi-ld/enterprise-context.jsonld"
]
```

Nội dung file ngữ cảnh doanh nghiệp `enterprise-context.jsonld`:
* Định nghĩa namespace của Proteus OS: `"proteus": "https://proteus.local/ontology/v1#"`
* Ánh xạ các thuộc tính nghiệp vụ (`fullName`, `capacity`, `jobTitle`, `roomCode`, `completionPct`) vào namespace.

---

## 4. Quản Lý Phiên Bản Schema & Tiến Hóa Thực Thể (Temporal Evolution)

1. **Schema Versioning:**
   - Mỗi Entity Type mang thuộc tính nội bộ `schemaVersion`: `"1.0.0"`.
   - Khi có thay đổi cấu trúc, tuân thủ nguyên tắc mở rộng tương thích ngược (Backward Compatibility): Chỉ thêm thuộc tính tùy chọn, không xóa hoặc đổi kiểu dữ liệu của thuộc tính hiện tại.
2. **Temporal Evolution:**
   - Orion-LD tự động lưu trữ dấu thời gian `observedAt` và `modifiedAt` khi thực thể nhận cập nhật.
   - Khi có sự kiện thay đổi từ PostgreSQL Outbox, worker đính kèm timestamp thực tế từ database vào thuộc tính `observedAt`.

---

## 5. Ví Dụ Payload Hoàn Chỉnh

### 5.1. Phòng họp thông minh (Smart Meeting Room)
```json
{
  "id": "urn:ngsi-ld:Room:00000000-0000-0000-0000-000000000001:room-hanoi-01",
  "type": "Room",
  "roomCode": {
    "type": "Property",
    "value": "ROOM-HN01"
  },
  "name": {
    "type": "Property",
    "value": "Phòng Họp Tràng An"
  },
  "capacity": {
    "type": "Property",
    "value": 16
  },
  "status": {
    "type": "Property",
    "value": "AVAILABLE"
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [105.78234, 21.03125]
    }
  },
  "belongsToFacility": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Facility:00000000-0000-0000-0000-000000000001:building-a"
  },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://context.proteus.local/ngsi-ld/enterprise-context.jsonld"
  ]
}
```

### 5.2. Tài sản / Thiết bị (Device Asset)
```json
{
  "id": "urn:ngsi-ld:Asset:00000000-0000-0000-0000-000000000001:ast-99012",
  "type": "Asset",
  "assetCode": {
    "type": "Property",
    "value": "AST-99012"
  },
  "name": {
    "type": "Property",
    "value": "Màn hình tương tác thông minh Maxhub 86 inch"
  },
  "category": {
    "type": "Property",
    "value": "OFFICE_EQUIPMENT"
  },
  "status": {
    "type": "Property",
    "value": "IN_USE"
  },
  "locatedAt": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Room:00000000-0000-0000-0000-000000000001:room-hanoi-01"
  },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://context.proteus.local/ngsi-ld/enterprise-context.jsonld"
  ]
}
```
