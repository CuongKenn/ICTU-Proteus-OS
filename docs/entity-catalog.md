<!--
Copyright (c) 2026 CuongKenn & ICTU Team
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Proteus OS — Entity Catalog & Ma Trận Chia Sẻ Dữ Liệu (Layer 3)

Tài liệu này xác định danh mục thực thể (Entity Catalog) chuẩn hoá theo chuẩn quốc tế **ETSI NGSI-LD** và ma trận chia sẻ dữ liệu (Data Sharing Matrix) xuyên suốt 9 phân hệ nghiệp vụ của Proteus OS.

---

## 1. Nguyên Tắc Bảo Mật & Phân Quyền Dữ Liệu

1. **Nguyên tắc Tối thiểu Hóa Dữ liệu (Data Minimization):** Chỉ chia sẻ những thuộc tính cần thiết phục vụ vận hành đa phân hệ, điều phối AI và hiển thị Digital Twin.
2. **Loại bỏ Hoàn toàn Dữ liệu Nhạy cảm (PII & Financial Secrets):** Các cột lương thưởng, tài khoản ngân hàng, thông tin định danh cá nhân, thẻ tín dụng, nội dung hợp đồng hoặc mật mã kỹ thuật tuyệt đối **KHÔNG ĐƯỢC PHÉP** đồng bộ sang Context Broker và GraphQL.
3. **Phân vùng Chia sẻ (Sharing Scopes):**
   - **Intra-Tenant (Nội bộ tổ chức):** Mọi người dùng thuộc cùng `tenant_id` có quyền xem theo vai trò RBAC.
   - **Cross-Tenant (Liên tổ chức):** Chỉ chia sẻ các thực thể công cộng đã được cấp phép (VD: danh mục dịch vụ đối tác, trạng thái giao vận logistics).
   - **Internal Only (Nội bộ module):** Không chia sẻ ra ngoài database của module.

---

## 2. Ma Trận Chia Sẻ Dữ Liệu 9 Phân Hệ Nghiệp Vụ

| Phân hệ (Plugin) | Bảng nguồn (PostgreSQL) | NGSI-LD Entity Type | Thuộc tính Chia sẻ (Shared Attributes) | Quan hệ (Relationships) | Cột KHÔNG chia sẻ (Sensitive / PII) | Phạm vi (Scope) |
|---|---|---|---|---|---|---|
| **hr-module** | `hr_employees` | `Employee` | `employeeCode`, `fullName`, `workEmail`, `jobTitle`, `status` | `isMemberOf` (`Department`) | `salary`, `bank_account`, `id_card_number`, `home_address`, `health_record` | Intra-Tenant |
| **hr-module** | `hr_departments` | `Department` | `deptCode`, `name`, `status`, `headCount` | `managedBy` (`Employee`), `parentDept` (`Department`) | `budget_allocated`, `internal_notes` | Intra-Tenant |
| **asset-module** | `asset_items` | `Asset` / `Device` | `assetCode`, `name`, `category`, `status`, `serialNumber` | `assignedTo` (`Employee`), `locatedAt` (`Room` / `Location`) | `purchase_price`, `depreciation_rate`, `supplier_contract_id` | Intra-Tenant |
| **meeting-module** | `meeting_rooms` | `Room` | `roomCode`, `name`, `capacity`, `status`, `equipmentList` | `belongsToFacility` (`Location`) | `access_pin_code`, `internal_budget` | Intra-Tenant |
| **meeting-module** | `meeting_schedules` | `Meeting` | `title`, `startTime`, `endTime`, `status` | `heldIn` (`Room`), `organizedBy` (`Employee`) | `private_notes`, `confidential_minutes`, `attachment_url` | Intra-Tenant |
| **project-module** | `project_items` | `Project` | `projectCode`, `name`, `status`, `completionPct`, `startDate`, `endDate` | `leadBy` (`Employee`) | `profit_margin`, `client_confidential_terms` | Intra-Tenant |
| **project-module** | `project_tasks` | `Task` | `taskCode`, `title`, `priority`, `status`, `dueDate` | `partOfProject` (`Project`), `assignedTo` (`Employee`) | `hourly_billing_rate`, `internal_cost` | Intra-Tenant |
| **crm-module** | `crm_customers` | `Customer` / `Organization` | `customerCode`, `companyName`, `industry`, `status`, `tier` | `accountManager` (`Employee`) | `credit_card_info`, `tax_id_personal`, `contract_value` | Intra-Tenant |
| **crm-module** | `crm_leads` | `Lead` | `leadCode`, `title`, `source`, `status`, `qualification` | `assignedTo` (`Employee`) | `personal_phone`, `private_note` | Intra-Tenant |
| **finance-module** | `finance_invoices` | `Invoice` | `invoiceNumber`, `status`, `totalAmount`, `currency`, `issueDate`, `dueDate` | `billedTo` (`Customer`), `issuedBy` (`Employee`) | `tax_details`, `full_bank_routing`, `accounting_journal_refs` | Intra-Tenant |
| **it-helpdesk-module** | `helpdesk_tickets` | `Ticket` / `Incident` | `ticketCode`, `title`, `category`, `priority`, `status`, `createdAt` | `reportedBy` (`Employee`), `assignedTo` (`Employee`), `relatedAsset` (`Asset`) | `internal_investigation_log`, `vulnerability_details` | Intra-Tenant |
| **procurement-module**| `procurement_orders` | `PurchaseOrder` | `poNumber`, `status`, `totalCost`, `orderDate`, `expectedDelivery` | `orderedBy` (`Employee`), `suppliedBy` (`Supplier`) | `discount_negotiation_notes`, `payment_secret_terms` | Intra-Tenant |
| **procurement-module**| `procurement_suppliers`| `Supplier` | `supplierCode`, `name`, `businessDomain`, `rating`, `status` | `locatedAt` (`Location`) | `beneficiary_bank_account`, `private_tax_filing` | Intra-Tenant |
| **document-module** | `document_files` | `Document` | `docCode`, `title`, `mimeType`, `version`, `status`, `updatedAt` | `ownedBy` (`Employee`), `linkedEntity` (`Project` / `Asset`) | `raw_binary_content`, `confidential_body_text`, `decryption_keys` | Intra-Tenant |

---

## 3. Ví Dụ Payload Đã Ẩn Dữ Liệu Nhạy Cảm (Masked Payload)

### 3.1. Thực thể Nhân sự (Employee) — Loại bỏ PII
```json
{
  "id": "urn:ngsi-ld:Employee:00000000-0000-0000-0000-000000000001:emp-10024",
  "type": "Employee",
  "employeeCode": {
    "type": "Property",
    "value": "EMP-10024"
  },
  "fullName": {
    "type": "Property",
    "value": "Nguyễn Văn An"
  },
  "workEmail": {
    "type": "Property",
    "value": "an.nv@proteus.local"
  },
  "jobTitle": {
    "type": "Property",
    "value": "Kỹ sư Tự động hóa"
  },
  "status": {
    "type": "Property",
    "value": "ACTIVE"
  },
  "isMemberOf": {
    "type": "Relationship",
    "object": "urn:ngsi-ld:Department:00000000-0000-0000-0000-000000000001:dept-eng"
  },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://context.proteus.local/ngsi-ld/enterprise-context.jsonld"
  ]
}
```
*(Ghi chú bảo mật: Trường `salary`, `bank_account`, `id_card_number` đã bị loại bỏ hoàn toàn trước khi tạo NGSI payload).*

### 3.2. Thực thể Phòng họp (Room) & Thiết bị (Asset)
```json
{
  "id": "urn:ngsi-ld:Room:00000000-0000-0000-0000-000000000001:room-p301",
  "type": "Room",
  "roomCode": {
    "type": "Property",
    "value": "ROOM-P301"
  },
  "name": {
    "type": "Property",
    "value": "Phòng Hội thảo Sơn La"
  },
  "capacity": {
    "type": "Property",
    "value": 24
  },
  "status": {
    "type": "Property",
    "value": "AVAILABLE"
  },
  "location": {
    "type": "GeoProperty",
    "value": {
      "type": "Point",
      "coordinates": [105.804817, 21.028511]
    }
  },
  "@context": [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    "http://context.proteus.local/ngsi-ld/enterprise-context.jsonld"
  ]
}
```
