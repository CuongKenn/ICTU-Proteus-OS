// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// useDigitalTwinLive — Realtime Digital Twin Hook (Issues #849 & #872)
// 1. Tải snapshot ban đầu từ BFF `/api/proxy/v1/context/entities`.
// 2. Nếu `NEXT_PUBLIC_HASURA_WS_URL` được cấu hình: mở Hasura GraphQL Subscription (`< 2s`).
// 3. Tự động chuyển sang Live Polling Fallback mượt (chu kỳ 4s) khi môi trường local/demo
//    chưa bật Hasura WS hoặc khi WS đang kết nối lại.

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, { extractErrorMessage } from "@/lib/api";
import { HasuraLiveClient } from "@/lib/hasuraLiveClient";
import { logger } from "@/lib/logger";
import { useSession } from "@/hooks/useSession";

export type TwinStatusIndicator = "normal" | "busy" | "warning" | "critical";

export type TwinConnectionMode =
  | "hasura_ws"
  | "live_poll"
  | "reconnecting"
  | "offline";

export interface TwinRelationship {
  predicate: string;
  target_id: string;
  target_type: string;
  target_label: string;
}

export interface DigitalTwinEntity {
  entity_id: string;
  type: string;
  tenant_id: string;
  payload: Record<string, unknown>;
  coordinates: [number, number] | null; // [lon, lat] — WGS84 / EPSG:4326
  status_indicator: TwinStatusIndicator;
  relationships: TwinRelationship[];
  updated_at: string | null;
}

export interface EntitiesResponse {
  entities?: DigitalTwinEntity[];
  items?: DigitalTwinEntity[];
  total: number;
  source: string;
  tenant_id?: string;
  center?: unknown;
}

const LIVE_POLL_INTERVAL_MS = 4_000;

export const HASURA_ENTITY_SUBSCRIPTION = `
  subscription WatchDigitalTwinEntities {
    context_entity_state(
      order_by: { updated_at: desc }
      limit: 250
    ) {
      entity_id
      type
      payload
      updated_at
    }
  }
`;

function unwrapNgsiValue(prop: unknown): unknown {
  if (prop && typeof prop === "object" && !Array.isArray(prop)) {
    const rec = prop as Record<string, unknown>;
    if ("value" in rec) return rec.value;
    if ("object" in rec) return rec.object;
  }
  return prop;
}

function extractCoordinatesFromPayload(
  rawCoords: unknown,
  payload: Record<string, unknown>
): [number, number] | null {
  if (
    Array.isArray(rawCoords) &&
    rawCoords.length >= 2 &&
    typeof rawCoords[0] === "number" &&
    typeof rawCoords[1] === "number" &&
    Number.isFinite(rawCoords[0]) &&
    Number.isFinite(rawCoords[1])
  ) {
    return [rawCoords[0], rawCoords[1]];
  }

  const loc = payload.location as Record<string, any> | undefined;
  const geoCoords =
    loc?.value?.coordinates ?? loc?.coordinates ?? payload.coordinates;
  if (
    Array.isArray(geoCoords) &&
    geoCoords.length >= 2 &&
    typeof geoCoords[0] === "number" &&
    typeof geoCoords[1] === "number" &&
    Number.isFinite(geoCoords[0]) &&
    Number.isFinite(geoCoords[1])
  ) {
    return [geoCoords[0], geoCoords[1]];
  }
  return null;
}

function inferStatusIndicator(
  explicit: unknown,
  payload: Record<string, unknown>
): TwinStatusIndicator {
  if (
    explicit === "normal" ||
    explicit === "busy" ||
    explicit === "warning" ||
    explicit === "critical"
  ) {
    return explicit;
  }

  const rawStatus = String(
    unwrapNgsiValue(payload.status) ??
      unwrapNgsiValue(payload.state) ??
      unwrapNgsiValue(payload.severity) ??
      unwrapNgsiValue(payload.occupancyStatus) ??
      ""
  ).toLowerCase();

  if (
    rawStatus.includes("critical") ||
    rawStatus.includes("error") ||
    rawStatus.includes("down") ||
    rawStatus.includes("fault") ||
    rawStatus.includes("urgent")
  ) {
    return "critical";
  }
  if (
    rawStatus.includes("warn") ||
    rawStatus.includes("degrad") ||
    rawStatus.includes("maintenance") ||
    rawStatus.includes("open") ||
    rawStatus.includes("pending")
  ) {
    return "warning";
  }
  if (
    rawStatus.includes("busy") ||
    rawStatus.includes("occupied") ||
    rawStatus.includes("in_use") ||
    rawStatus.includes("in_progress") ||
    rawStatus.includes("high")
  ) {
    return "busy";
  }
  return "normal";
}

function parseUrnLabel(urn: string): { type: string; shortId: string } {
  const parts = urn.split(":");
  if (parts.length >= 5 && parts[0] === "urn" && parts[1] === "ngsi-ld") {
    return {
      type: parts[2] || "Entity",
      shortId: parts.slice(4).join(":"),
    };
  }
  return {
    type: "Entity",
    shortId: urn,
  };
}

function extractRelationships(
  explicit: unknown,
  payload: Record<string, unknown>
): TwinRelationship[] {
  if (Array.isArray(explicit)) {
    return explicit
      .filter((r) => r && typeof r === "object" && (r as any).target_id)
      .map((r: any) => {
        const parsed = parseUrnLabel(String(r.target_id));
        return {
          predicate: String(r.predicate || "relatedTo"),
          target_id: String(r.target_id),
          target_type: String(r.target_type || parsed.type),
          target_label: String(r.target_label || parsed.shortId),
        };
      });
  }

  const derived: TwinRelationship[] = [];
  for (const [key, val] of Object.entries(payload)) {
    if (!val || typeof val !== "object" || Array.isArray(val)) continue;
    const rec = val as Record<string, unknown>;
    if (rec.type === "Relationship" && typeof rec.object === "string") {
      const parsed = parseUrnLabel(rec.object);
      derived.push({
        predicate: key,
        target_id: rec.object,
        target_type: parsed.type,
        target_label:
          typeof rec.targetLabel === "string" ? rec.targetLabel : parsed.shortId,
      });
    }
  }
  return derived;
}

export function normalizeTwinEntity(
  raw: Record<string, any>,
  fallbackTenantId?: string | null
): DigitalTwinEntity | null {
  const entityId = typeof raw?.entity_id === "string" ? raw.entity_id : raw?.id;
  if (!entityId || typeof entityId !== "string") return null;

  let payload: Record<string, unknown> = {};
  if (typeof raw.payload === "string") {
    try {
      payload = JSON.parse(raw.payload);
    } catch {
      payload = {};
    }
  } else if (raw.payload && typeof raw.payload === "object") {
    payload = raw.payload as Record<string, unknown>;
  }

  const parsedUrn = parseUrnLabel(entityId);
  const entityType =
    typeof raw.type === "string" && raw.type
      ? raw.type
      : typeof payload.type === "string" && payload.type
        ? payload.type
        : parsedUrn.type;

  const tenantId =
    typeof raw.tenant_id === "string" && raw.tenant_id
      ? raw.tenant_id
      : fallbackTenantId ?? "default";

  const coordinates = extractCoordinatesFromPayload(raw.coordinates, payload);
  const statusIndicator = inferStatusIndicator(raw.status_indicator, payload);
  const relationships = extractRelationships(raw.relationships, payload);

  return {
    entity_id: entityId,
    type: entityType,
    tenant_id: tenantId,
    payload,
    coordinates,
    status_indicator: statusIndicator,
    relationships,
    updated_at: typeof raw.updated_at === "string" ? raw.updated_at : null,
  };
}

/**
 * Bộ dữ liệu mô phỏng chuẩn ETSI NGSI-LD v1.6 của Khuôn viên Số ICTU (Sandbox Showcase)
 * phục vụ trình diễn trực tiếp khi CSDL local chưa seed bản ghi thực thể.
 */
export function buildCampusSandboxEntities(tenantId: string): DigitalTwinEntity[] {
  const t = tenantId || "ictu-campus-2026";
  const now = new Date().toISOString();
  const urn = (type: string, id: string) => `urn:ngsi-ld:${type}:${t}:${id}`;

  return [
    {
      entity_id: urn("Room", "C1-202"),
      type: "Room",
      tenant_id: t,
      coordinates: [105.8058, 21.5858],
      status_indicator: "busy",
      updated_at: now,
      relationships: [
        {
          predicate: "containsAsset",
          target_id: urn("Asset", "Maxhub-C1-202"),
          target_type: "Asset",
          target_label: "Màn hình tương tác Maxhub 86\" C1-202",
        },
        {
          predicate: "hasActiveTicket",
          target_id: urn("Ticket", "TCK-2026-089"),
          target_type: "Ticket",
          target_label: "Ticket #089 — Kiểm tra cảm biến CO2 phòng C1-202",
        },
        {
          predicate: "managedBy",
          target_id: urn("Department", "Khoa-CNTT"),
          target_type: "Department",
          target_label: "Khoa Công nghệ Thông tin",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Room", "C1-202"),
        type: "Room",
        name: { type: "Property", value: "Phòng học Thông minh C1-202" },
        buildingCode: { type: "Property", value: "C1" },
        floor: { type: "Property", value: 2 },
        capacity: { type: "Property", value: 65, unitCode: "P1" },
        currentOccupancy: { type: "Property", value: 58, unitCode: "P1" },
        temperature: { type: "Property", value: 24.6, unitCode: "CEL" },
        co2Level: { type: "Property", value: 780, unitCode: "59" },
        occupancyStatus: { type: "Property", value: "occupied" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8058, 21.5858] },
        },
      },
    },
    {
      entity_id: urn("Asset", "Maxhub-C1-202"),
      type: "Asset",
      tenant_id: t,
      coordinates: [105.806, 21.5857],
      status_indicator: "normal",
      updated_at: now,
      relationships: [
        {
          predicate: "locatedIn",
          target_id: urn("Room", "C1-202"),
          target_type: "Room",
          target_label: "Phòng học Thông minh C1-202",
        },
        {
          predicate: "assignedCustodian",
          target_id: urn("Employee", "KT-014"),
          target_type: "Employee",
          target_label: "Kỹ sư Trực vận hành Thiết bị Số #KT-014",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Asset", "Maxhub-C1-202"),
        type: "Asset",
        name: {
          type: "Property",
          value: "Màn hình tương tác Maxhub V6 86-inch",
        },
        category: { type: "Property", value: "SmartClassroomDisplay" },
        firmwareVersion: { type: "Property", value: "v6.4.12-LTS" },
        powerConsumptionKw: { type: "Property", value: 0.32, unitCode: "KWT" },
        status: { type: "Property", value: "online" },
        locatedIn: {
          type: "Relationship",
          object: urn("Room", "C1-202"),
        },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.806, 21.5857] },
        },
      },
    },
    {
      entity_id: urn("Ticket", "TCK-2026-089"),
      type: "Ticket",
      tenant_id: t,
      coordinates: [105.8056, 21.5859],
      status_indicator: "warning",
      updated_at: now,
      relationships: [
        {
          predicate: "concernsRoom",
          target_id: urn("Room", "C1-202"),
          target_type: "Room",
          target_label: "Phòng học Thông minh C1-202",
        },
        {
          predicate: "assignedTo",
          target_id: urn("Employee", "KT-014"),
          target_type: "Employee",
          target_label: "Kỹ sư Trực vận hành Thiết bị Số #KT-014",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Ticket", "TCK-2026-089"),
        type: "Ticket",
        name: {
          type: "Property",
          value: "Ticket bảo trì #089 — Hiệu chuẩn cảm biến CO2 & lọc khí tươi",
        },
        priority: { type: "Property", value: "HIGH" },
        status: { type: "Property", value: "pending_inspection" },
        slaRemainingMinutes: { type: "Property", value: 45, unitCode: "MIN" },
        concernsRoom: {
          type: "Relationship",
          object: urn("Room", "C1-202"),
        },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8056, 21.5859] },
        },
      },
    },
    {
      entity_id: urn("Room", "C6-AI-Lab"),
      type: "Room",
      tenant_id: t,
      coordinates: [105.8077, 21.5861],
      status_indicator: "critical",
      updated_at: now,
      relationships: [
        {
          predicate: "containsAsset",
          target_id: urn("Asset", "GPU-Cluster-C6"),
          target_type: "Asset",
          target_label: "Cụm máy chủ AI Inference Node C6",
        },
        {
          predicate: "hasActiveTicket",
          target_id: urn("Ticket", "TCK-2026-094"),
          target_type: "Ticket",
          target_label: "Ticket khẩn #094 — Cảnh báo nhiệt độ tủ Rack B2",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Room", "C6-AI-Lab"),
        type: "Room",
        name: {
          type: "Property",
          value: "Phòng Thí nghiệm Trọng điểm AI & Bán dẫn (C6-301)",
        },
        buildingCode: { type: "Property", value: "C6" },
        floor: { type: "Property", value: 3 },
        temperature: { type: "Property", value: 29.4, unitCode: "CEL" },
        humidityPercent: { type: "Property", value: 52, unitCode: "P1" },
        status: { type: "Property", value: "critical_thermal_alert" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8077, 21.5861] },
        },
      },
    },
    {
      entity_id: urn("Asset", "GPU-Cluster-C6"),
      type: "Asset",
      tenant_id: t,
      coordinates: [105.8079, 21.586],
      status_indicator: "warning",
      updated_at: now,
      relationships: [
        {
          predicate: "locatedIn",
          target_id: urn("Room", "C6-AI-Lab"),
          target_type: "Room",
          target_label: "Phòng Thí nghiệm Trọng điểm AI & Bán dẫn (C6-301)",
        },
        {
          predicate: "hasActiveTicket",
          target_id: urn("Ticket", "TCK-2026-094"),
          target_type: "Ticket",
          target_label: "Ticket khẩn #094 — Cảnh báo nhiệt độ tủ Rack B2",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Asset", "GPU-Cluster-C6"),
        type: "Asset",
        name: {
          type: "Property",
          value: "Cụm máy chủ vLLM / Qdrant Vector Node C6",
        },
        gpuUtilizationPercent: { type: "Property", value: 88, unitCode: "P1" },
        rackInletTempC: { type: "Property", value: 28.9, unitCode: "CEL" },
        status: { type: "Property", value: "warning_high_load" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8079, 21.586] },
        },
      },
    },
    {
      entity_id: urn("Ticket", "TCK-2026-094"),
      type: "Ticket",
      tenant_id: t,
      coordinates: [105.8075, 21.5862],
      status_indicator: "critical",
      updated_at: now,
      relationships: [
        {
          predicate: "concernsAsset",
          target_id: urn("Asset", "GPU-Cluster-C6"),
          target_type: "Asset",
          target_label: "Cụm máy chủ vLLM / Qdrant Vector Node C6",
        },
        {
          predicate: "concernsRoom",
          target_id: urn("Room", "C6-AI-Lab"),
          target_type: "Room",
          target_label: "Phòng Thí nghiệm Trọng điểm AI & Bán dẫn (C6-301)",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Ticket", "TCK-2026-094"),
        type: "Ticket",
        name: {
          type: "Property",
          value: "Ticket khẩn #094 — Quá nhiệt điều hòa chính xác phòng máy C6",
        },
        priority: { type: "Property", value: "CRITICAL" },
        status: { type: "Property", value: "critical_open" },
        slaRemainingMinutes: { type: "Property", value: 12, unitCode: "MIN" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8075, 21.5862] },
        },
      },
    },
    {
      entity_id: urn("Room", "TrungTamSo-NOC"),
      type: "Room",
      tenant_id: t,
      coordinates: [105.8066, 21.5849],
      status_indicator: "normal",
      updated_at: now,
      relationships: [
        {
          predicate: "managedBy",
          target_id: urn("Department", "Trung-Tam-So"),
          target_type: "Department",
          target_label: "Trung tâm Số & Hạ tầng Dữ liệu",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Room", "TrungTamSo-NOC"),
        type: "Room",
        name: {
          type: "Property",
          value: "Phòng Điều hành Mạng & Bản sao số (NOC)",
        },
        buildingCode: { type: "Property", value: "TTS" },
        temperature: { type: "Property", value: 21.2, unitCode: "CEL" },
        powerPue: { type: "Property", value: 1.34 },
        status: { type: "Property", value: "optimal" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8066, 21.5849] },
        },
      },
    },
    {
      entity_id: urn("Room", "C2-105"),
      type: "Room",
      tenant_id: t,
      coordinates: [105.8052, 21.5844],
      status_indicator: "normal",
      updated_at: now,
      relationships: [
        {
          predicate: "managedBy",
          target_id: urn("Department", "Khoa-CNTT"),
          target_type: "Department",
          target_label: "Khoa Công nghệ Thông tin",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Room", "C2-105"),
        type: "Room",
        name: { type: "Property", value: "Giảng đường Đa phương tiện C2-105" },
        buildingCode: { type: "Property", value: "C2" },
        capacity: { type: "Property", value: 120, unitCode: "P1" },
        currentOccupancy: { type: "Property", value: 0, unitCode: "P1" },
        occupancyStatus: { type: "Property", value: "available" },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8052, 21.5844] },
        },
      },
    },
    {
      entity_id: urn("Department", "Khoa-CNTT"),
      type: "Department",
      tenant_id: t,
      coordinates: null,
      status_indicator: "normal",
      updated_at: now,
      relationships: [
        {
          predicate: "operatesRoom",
          target_id: urn("Room", "C1-202"),
          target_type: "Room",
          target_label: "Phòng học Thông minh C1-202",
        },
        {
          predicate: "operatesRoom",
          target_id: urn("Room", "C2-105"),
          target_type: "Room",
          target_label: "Giảng đường Đa phương tiện C2-105",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Department", "Khoa-CNTT"),
        type: "Department",
        name: { type: "Property", value: "Khoa Công nghệ Thông tin" },
        code: { type: "Property", value: "FIT-ICTU" },
        activeRoomsCount: { type: "Property", value: 24 },
        piiPolicy: { type: "Property", value: "GATEKEEPER_SANITIZED" },
      },
    },
    {
      entity_id: urn("Department", "Trung-Tam-So"),
      type: "Department",
      tenant_id: t,
      coordinates: null,
      status_indicator: "normal",
      updated_at: now,
      relationships: [
        {
          predicate: "operatesRoom",
          target_id: urn("Room", "TrungTamSo-NOC"),
          target_type: "Room",
          target_label: "Phòng Điều hành Mạng & Bản sao số (NOC)",
        },
        {
          predicate: "employsSpecialist",
          target_id: urn("Employee", "KT-014"),
          target_type: "Employee",
          target_label: "Kỹ sư Trực vận hành Thiết bị Số #KT-014",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Department", "Trung-Tam-So"),
        type: "Department",
        name: { type: "Property", value: "Trung tâm Số & Hạ tầng Dữ liệu" },
        code: { type: "Property", value: "DDC-ICTU" },
        slaCompliancePercent: { type: "Property", value: 99.8, unitCode: "P1" },
      },
    },
    {
      entity_id: urn("Employee", "KT-014"),
      type: "Employee",
      tenant_id: t,
      coordinates: [105.8063, 21.5853],
      status_indicator: "busy",
      updated_at: now,
      relationships: [
        {
          predicate: "belongsTo",
          target_id: urn("Department", "Trung-Tam-So"),
          target_type: "Department",
          target_label: "Trung tâm Số & Hạ tầng Dữ liệu",
        },
        {
          predicate: "handlingTicket",
          target_id: urn("Ticket", "TCK-2026-089"),
          target_type: "Ticket",
          target_label: "Ticket #089 — Kiểm tra cảm biến CO2 phòng C1-202",
        },
      ],
      payload: {
        "@context": [
          "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
        ],
        id: urn("Employee", "KT-014"),
        type: "Employee",
        name: {
          type: "Property",
          value: "Kỹ sư Trực vận hành Thiết bị Số #KT-014",
        },
        roleTitle: { type: "Property", value: "Senior IoT & Facility Engineer" },
        shiftStatus: { type: "Property", value: "on_duty_busy" },
        piiRedacted: {
          type: "Property",
          value: true,
        },
        location: {
          type: "GeoProperty",
          value: { type: "Point", coordinates: [105.8063, 21.5853] },
        },
      },
    },
  ];
}

export interface UseDigitalTwinLiveReturn {
  entities: DigitalTwinEntity[];
  total: number;
  source: string;
  connectionMode: TwinConnectionMode;
  liveEnabled: boolean;
  setLiveEnabled: (enabled: boolean) => void;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  lastUpdatedAt: string | null;
  isSandboxMode: boolean;
  activateSandboxMode: () => void;
  exitSandboxMode: () => void;
  refresh: () => Promise<void>;
}

export function useDigitalTwinLive(): UseDigitalTwinLiveReturn {
  const { user, status: sessionStatus } = useSession();
  const tenantId = user?.tenant_id ?? null;
  const hasuraWsUrl = (process.env.NEXT_PUBLIC_HASURA_WS_URL ?? "").trim();

  const [entities, setEntities] = useState<DigitalTwinEntity[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [source, setSource] = useState<string>("context.entity_state");
  const [liveEnabled, setLiveEnabled] = useState<boolean>(true);
  const [connectionMode, setConnectionMode] =
    useState<TwinConnectionMode>("live_poll");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [isSandboxMode, setIsSandboxMode] = useState<boolean>(false);

  const inFlightRef = useRef<boolean>(false);
  const wsConnectedRef = useRef<boolean>(false);

  const fetchSnapshot = useCallback(
    async (silent = false) => {
      if (isSandboxMode) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;

      if (!silent) {
        setIsRefreshing(true);
      }

      try {
        const res = await api.get("/v1/context/entities");
        const rawData = res.data ?? {};
        const rawItems: Record<string, any>[] = Array.isArray(rawData.entities)
          ? rawData.entities
          : Array.isArray(rawData.items)
            ? rawData.items
            : Array.isArray(rawData)
              ? rawData
              : [];

        const normalized = rawItems
          .map((item) => normalizeTwinEntity(item, tenantId))
          .filter((item): item is DigitalTwinEntity => {
            if (!item) return false;
            // Cô lập tenant phía client
            if (tenantId && item.tenant_id && item.tenant_id !== tenantId) {
              return false;
            }
            return true;
          });

        setEntities(normalized);
        setTotal(
          typeof rawData.total === "number" ? rawData.total : normalized.length
        );
        setSource(
          typeof rawData.source === "string" && rawData.source
            ? rawData.source
            : "context.entity_state"
        );
        setError(null);
        setLastUpdatedAt(new Date().toISOString());

        if (liveEnabled && !wsConnectedRef.current) {
          setConnectionMode((prev) =>
            prev === "reconnecting" ? "reconnecting" : "live_poll"
          );
        }
      } catch (err) {
        logger.warn("Failed to fetch Digital Twin entities snapshot", err);
        setError(
          extractErrorMessage(
            err,
            "Chưa kết nối được dịch vụ Context Broker / Digital Twin."
          )
        );
        if (!wsConnectedRef.current) {
          setConnectionMode("offline");
        }
      } finally {
        inFlightRef.current = false;
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [isSandboxMode, liveEnabled, tenantId]
  );

  // 1. Tải snapshot ban đầu khi phiên sẵn sàng
  useEffect(() => {
    if (sessionStatus === "loading") return;
    if (sessionStatus === "unauthenticated") {
      setIsLoading(false);
      setConnectionMode("offline");
      return;
    }
    void fetchSnapshot(false);
  }, [sessionStatus, fetchSnapshot]);

  // 2. Kết nối Hasura WebSocket Subscription nếu `NEXT_PUBLIC_HASURA_WS_URL` được cấu hình
  useEffect(() => {
    if (
      !liveEnabled ||
      isSandboxMode ||
      !hasuraWsUrl ||
      sessionStatus !== "authenticated"
    ) {
      wsConnectedRef.current = false;
      if (!liveEnabled) {
        setConnectionMode("offline");
      }
      return;
    }

    let client: HasuraLiveClient | null = null;
    let unsubscribe: (() => void) | null = null;

    try {
      client = new HasuraLiveClient({
        url: hasuraWsUrl,
        tenantId,
        onStatusChange: (st) => {
          if (st === "connected") {
            wsConnectedRef.current = true;
            setConnectionMode("hasura_ws");
            setError(null);
          } else if (st === "reconnecting") {
            wsConnectedRef.current = false;
            setConnectionMode("reconnecting");
          } else if (st === "closed") {
            wsConnectedRef.current = false;
          }
        },
      });

      unsubscribe = client.subscribe<{
        context_entity_state?: Record<string, any>[];
      }>({
        id: "digital_twin_live",
        query: HASURA_ENTITY_SUBSCRIPTION,
        variables: {},
        onNext: (data) => {
          const rows = data?.context_entity_state;
          if (!Array.isArray(rows)) return;

          const incoming = rows
            .map((r) => normalizeTwinEntity(r, tenantId))
            .filter((item): item is DigitalTwinEntity => Boolean(item));

          setEntities((prev) => {
            if (prev.length === 0) return incoming;
            const prevById = new Map(prev.map((p) => [p.entity_id, p]));
            return incoming.map((inc) => {
              const existing = prevById.get(inc.entity_id);
              // Giữ lại coordinates/relationships giàu ngữ nghĩa từ BFF nếu row raw chưa đính kèm
              return {
                ...inc,
                coordinates: inc.coordinates ?? existing?.coordinates ?? null,
                relationships:
                  inc.relationships.length > 0
                    ? inc.relationships
                    : existing?.relationships ?? [],
              };
            });
          });
          setTotal(incoming.length);
          setSource("hasura.graphql-transport-ws");
          setLastUpdatedAt(new Date().toISOString());
        },
        onError: (wsErr) => {
          logger.warn("Hasura subscription reported error, falling back to live polling", wsErr);
          wsConnectedRef.current = false;
          setConnectionMode("live_poll");
          unsubscribe?.();
          client?.dispose();
        },
      });
    } catch (initErr) {
      logger.warn("Could not initialize HasuraLiveClient, using poll fallback", initErr);
      wsConnectedRef.current = false;
      setConnectionMode("live_poll");
    }

    return () => {
      wsConnectedRef.current = false;
      unsubscribe?.();
      client?.dispose();
    };
  }, [hasuraWsUrl, isSandboxMode, liveEnabled, sessionStatus, tenantId]);

  // 3. Live Polling Fallback mượt (chu kỳ 4s) khi chưa bật Hasura WS hoặc khi WS đang reconnecting
  useEffect(() => {
    if (!liveEnabled) {
      setConnectionMode("offline");
      return;
    }

    if (isSandboxMode) {
      setConnectionMode("live_poll");
      return;
    }

    if (sessionStatus !== "authenticated") return;

    const timer = setInterval(() => {
      if (wsConnectedRef.current) return;
      if (
        typeof document !== "undefined" &&
        document.visibilityState === "hidden"
      ) {
        return;
      }
      void fetchSnapshot(true);
    }, LIVE_POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
    };
  }, [fetchSnapshot, isSandboxMode, liveEnabled, sessionStatus]);

  const activateSandboxMode = useCallback(() => {
    const demoItems = buildCampusSandboxEntities(tenantId ?? "ictu-campus-2026");
    setIsSandboxMode(true);
    setEntities(demoItems);
    setTotal(demoItems.length);
    setSource("sandbox.ngsi-ld.v1.6");
    setError(null);
    setIsLoading(false);
    setLastUpdatedAt(new Date().toISOString());
    setConnectionMode(liveEnabled ? "live_poll" : "offline");
  }, [liveEnabled, tenantId]);

  const exitSandboxMode = useCallback(() => {
    setIsSandboxMode(false);
    setIsLoading(true);
  }, []);

  const refresh = useCallback(async () => {
    if (isSandboxMode) {
      const demoItems = buildCampusSandboxEntities(tenantId ?? "ictu-campus-2026");
      setEntities(demoItems);
      setTotal(demoItems.length);
      setLastUpdatedAt(new Date().toISOString());
      return;
    }
    await fetchSnapshot(false);
  }, [fetchSnapshot, isSandboxMode, tenantId]);

  return useMemo(
    () => ({
      entities,
      total,
      source,
      connectionMode,
      liveEnabled,
      setLiveEnabled,
      isLoading,
      isRefreshing,
      error,
      lastUpdatedAt,
      isSandboxMode,
      activateSandboxMode,
      exitSandboxMode,
      refresh,
    }),
    [
      activateSandboxMode,
      connectionMode,
      entities,
      error,
      exitSandboxMode,
      isLoading,
      isRefreshing,
      isSandboxMode,
      lastUpdatedAt,
      liveEnabled,
      refresh,
      source,
      total,
    ]
  );
}
