// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// DigitalTwinClient — Trung tâm Điều hành Bản sao số Thời gian thực (Issue #872)
// Swiss Slate v4.0 (Light & Dark Mode):
// 1. Realtime Architecture Pipeline Bar + KPI Counters + Quick Filter & Search
// 2. Interactive 2D PostGIS Spatial Map (WGS84 / EPSG:4326 SVG) + Entity Grid Toggle
// 3. Entity Inspector Panel (Tab 1: Linked Graph & Sanitized Props, Tab 2: ETSI NGSI-LD JSON-LD)

"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { clsx } from "clsx";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  Clock,
  Code2,
  Copy,
  Cpu,
  Database,
  GitFork,
  Layers,
  LayoutGrid,
  Map as MapIcon,
  MapPin,
  Network,
  Radio,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  Ticket,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  DigitalTwinEntity,
  TwinConnectionMode,
  TwinRelationship,
  TwinStatusIndicator,
  useDigitalTwinLive,
} from "@/hooks/useDigitalTwinLive";

type ViewMode = "map" | "grid";
type InspectorTab = "graph" | "jsonld";

const CANONICAL_TYPES = [
  { key: "ALL", label: "Tất cả", icon: Layers },
  { key: "Room", label: "Room", icon: Building2 },
  { key: "Asset", label: "Asset", icon: Cpu },
  { key: "Ticket", label: "Ticket", icon: Ticket },
  { key: "Department", label: "Department", icon: Network },
  { key: "Employee", label: "Employee", icon: Users },
] as const;

interface CampusZone {
  id: string;
  code: string;
  name: string;
  subtitle: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

const CAMPUS_ZONES: CampusZone[] = [
  {
    id: "zone-c1",
    code: "C1",
    name: "Tòa C1 — Điều hành & Smart Class",
    subtitle: "Phòng học thông minh • IoT Hub",
    x: 165,
    y: 120,
    w: 215,
    h: 118,
  },
  {
    id: "zone-c6",
    code: "C6",
    name: "Tòa C6 — Tổ hợp AI & Bán dẫn",
    subtitle: "AI Lab • GPU Cluster • Cleanroom",
    x: 560,
    y: 95,
    w: 245,
    h: 132,
  },
  {
    id: "zone-tts",
    code: "TTS",
    name: "Trung tâm Số (Digital Center)",
    subtitle: "NOC • Orion-LD • PostGIS Core",
    x: 375,
    y: 268,
    w: 215,
    h: 116,
  },
  {
    id: "zone-c2",
    code: "C2",
    name: "Tòa C2 — Giảng đường Công nghệ",
    subtitle: "Giảng đường đa phương tiện",
    x: 125,
    y: 335,
    w: 205,
    h: 115,
  },
  {
    id: "zone-gd",
    code: "HT",
    name: "Hội trường Đa năng & Không gian Số",
    subtitle: "Sự kiện • Hội thảo Khoa học",
    x: 630,
    y: 325,
    w: 205,
    h: 120,
  },
];

// Khung tọa độ mặc định WGS84 (ICTU Campus Thái Nguyên)
const DEFAULT_GEO_BOUNDS = {
  minLon: 105.8044,
  maxLon: 105.8086,
  minLat: 21.5836,
  maxLat: 21.5868,
};

const SVG_WIDTH = 920;
const SVG_HEIGHT = 520;
const SVG_PAD_X = 72;
const SVG_PAD_Y = 54;

function getEntityDisplayName(entity: DigitalTwinEntity): string {
  const p = entity.payload ?? {};
  const candidates = [p.name, p.title, p.label, p.roomName, p.code];
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c.trim();
    if (c && typeof c === "object" && "value" in c) {
      const v = (c as Record<string, unknown>).value;
      if (typeof v === "string" && v.trim()) return v.trim();
    }
  }
  const parts = entity.entity_id.split(":");
  return parts.length >= 5 ? parts.slice(4).join(":") : entity.entity_id;
}

function getShortUrn(urn: string): string {
  const parts = urn.split(":");
  if (parts.length >= 5 && parts[0] === "urn" && parts[1] === "ngsi-ld") {
    return `${parts[2]}:${parts.slice(4).join(":")}`;
  }
  return urn;
}

function getStatusConfig(status: TwinStatusIndicator): {
  label: string;
  badgeClass: string;
  colorVar: string;
  pulse: boolean;
} {
  switch (status) {
    case "critical":
      return {
        label: "Khẩn cấp (Critical)",
        badgeClass: "status-badge status-badge--failed",
        colorVar: "var(--rose)",
        pulse: true,
      };
    case "warning":
      return {
        label: "Cảnh báo (Warning)",
        badgeClass: "status-badge status-badge--warning",
        colorVar: "var(--amber)",
        pulse: true,
      };
    case "busy":
      return {
        label: "Đang bận (Busy)",
        badgeClass:
          "status-badge border border-accent/30 bg-accent-soft text-accent",
        colorVar: "var(--cyan)",
        pulse: true,
      };
    case "normal":
    default:
      return {
        label: "Ổn định (Normal)",
        badgeClass: "status-badge status-badge--active",
        colorVar: "var(--emerald)",
        pulse: false,
      };
  }
}

function getConnectionBadge(
  mode: TwinConnectionMode,
  liveEnabled: boolean,
  isSandboxMode: boolean
): {
  label: string;
  dotColor: string;
  pillClass: string;
} {
  if (!liveEnabled) {
    return {
      label: "Tạm dừng Realtime",
      dotColor: "var(--dim)",
      pillClass: "border-line bg-paper-subtle text-muted",
    };
  }
  if (isSandboxMode) {
    return {
      label: "Sandbox NGSI-LD Live",
      dotColor: "var(--violet)",
      pillClass: "border-line-hi bg-paper-subtle text-ink",
    };
  }
  switch (mode) {
    case "hasura_ws":
      return {
        label: "Hasura GraphQL WS (<2s)",
        dotColor: "var(--emerald)",
        pillClass: "border-semantic-emerald/30 bg-success-light text-semantic-emerald",
      };
    case "live_poll":
      return {
        label: "Live Polling Sync (4s)",
        dotColor: "var(--cyan)",
        pillClass: "border-accent/30 bg-accent-soft text-accent",
      };
    case "reconnecting":
      return {
        label: "Đang kết nối lại (Fallback 4s)",
        dotColor: "var(--amber)",
        pillClass: "border-semantic-amber/30 bg-warning-light text-semantic-amber",
      };
    case "offline":
    default:
      return {
        label: "Ngoại tuyến (Offline)",
        dotColor: "var(--rose)",
        pillClass: "border-semantic-rose/30 bg-danger-light text-semantic-rose",
      };
  }
}

function getTypeIcon(type: string): React.ElementType {
  switch (type.toLowerCase()) {
    case "room":
      return Building2;
    case "asset":
      return Cpu;
    case "ticket":
      return Ticket;
    case "department":
      return Network;
    case "employee":
      return Users;
    default:
      return Layers;
  }
}

interface NormalizedProperty {
  key: string;
  value: string;
  unitCode?: string;
  observedAt?: string;
}

function extractNormalizedProperties(
  entity: DigitalTwinEntity
): NormalizedProperty[] {
  const skipKeys = new Set([
    "@context",
    "id",
    "type",
    "location",
    "coordinates",
  ]);
  const props: NormalizedProperty[] = [];

  for (const [key, rawVal] of Object.entries(entity.payload ?? {})) {
    if (skipKeys.has(key)) continue;

    if (rawVal && typeof rawVal === "object" && !Array.isArray(rawVal)) {
      const rec = rawVal as Record<string, unknown>;
      if (rec.type === "Relationship" || rec.type === "GeoProperty") {
        continue;
      }
      if ("value" in rec) {
        const inner = rec.value;
        const formatted =
          typeof inner === "object" && inner !== null
            ? JSON.stringify(inner)
            : String(inner ?? "—");
        props.push({
          key,
          value: formatted,
          unitCode:
            typeof rec.unitCode === "string" ? rec.unitCode : undefined,
          observedAt:
            typeof rec.observedAt === "string" ? rec.observedAt : undefined,
        });
        continue;
      }
    }

    const formatted =
      typeof rawVal === "object" && rawVal !== null
        ? JSON.stringify(rawVal)
        : String(rawVal ?? "—");
    props.push({ key, value: formatted });
  }

  return props;
}

function buildCanonicalJsonLd(
  entity: DigitalTwinEntity
): Record<string, unknown> {
  const basePayload = entity.payload ?? {};
  const contextValue = basePayload["@context"] ?? [
    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context-v1.6.jsonld",
    "https://schema.proteus-os.ictu.edu.vn/ngsi-ld/v1/digital-twin.jsonld",
  ];

  const doc: Record<string, unknown> = {
    "@context": contextValue,
    id: entity.entity_id,
    type: entity.type,
  };

  for (const [k, v] of Object.entries(basePayload)) {
    if (k === "@context" || k === "id" || k === "type") continue;
    doc[k] = v;
  }

  if (!doc.location && entity.coordinates) {
    doc.location = {
      type: "GeoProperty",
      value: {
        type: "Point",
        coordinates: entity.coordinates,
      },
    };
  }

  for (const rel of entity.relationships) {
    if (!(rel.predicate in doc)) {
      doc[rel.predicate] = {
        type: "Relationship",
        object: rel.target_id,
      };
    }
  }

  return doc;
}

function formatTimeShort(iso: string | null): string {
  if (!iso) return "Chưa đồng bộ";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export const DigitalTwinClient: React.FC = () => {
  const {
    entities,
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
  } = useDigitalTwinLive();

  const [viewMode, setViewMode] = useState<ViewMode>("map");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("graph");
  const [copiedJsonLd, setCopiedJsonLd] = useState<boolean>(false);

  // Interactive SVG Zoom & Pan state
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{
    clientX: number;
    clientY: number;
    panX: number;
    panY: number;
  } | null>(null);

  // Bộ đếm KPI theo loại thực thể
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: entities.length };
    for (const ent of entities) {
      counts[ent.type] = (counts[ent.type] ?? 0) + 1;
    }
    return counts;
  }, [entities]);

  // Danh sách tab lọc động (gồm các loại chuẩn + loại mở rộng từ Plugin)
  const filterTabs = useMemo(() => {
    const knownKeys = new Set<string>(CANONICAL_TYPES.map((t) => t.key));
    const extraTypes = Object.keys(typeCounts)
      .filter((k) => k !== "ALL" && !knownKeys.has(k))
      .map((k) => ({ key: k, label: k, icon: Layers }));
    return [...CANONICAL_TYPES, ...extraTypes];
  }, [typeCounts]);

  // Lọc thực thể theo loại & từ khóa tìm kiếm
  const filteredEntities = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return entities.filter((ent) => {
      if (typeFilter !== "ALL" && ent.type !== typeFilter) return false;
      if (!q) return true;
      const name = getEntityDisplayName(ent).toLowerCase();
      return (
        name.includes(q) ||
        ent.entity_id.toLowerCase().includes(q) ||
        ent.type.toLowerCase().includes(q) ||
        JSON.stringify(ent.payload).toLowerCase().includes(q)
      );
    });
  }, [entities, searchQuery, typeFilter]);

  const entityById = useMemo(
    () => new Map(entities.map((e) => [e.entity_id, e])),
    [entities]
  );

  // Tự động chọn thực thể đầu tiên khi danh sách có dữ liệu mà chưa chọn gì
  useEffect(() => {
    if (selectedId && entityById.has(selectedId)) return;
    if (filteredEntities.length > 0) {
      setSelectedId(filteredEntities[0].entity_id);
    } else if (entities.length === 0) {
      setSelectedId(null);
    }
  }, [entities.length, entityById, filteredEntities, selectedId]);

  const selectedEntity = selectedId ? entityById.get(selectedId) ?? null : null;

  // Khung chiếu tọa độ địa lý PostGIS WGS84 -> SVG 2D
  const geoBounds = useMemo(() => {
    const coords = entities
      .map((e) => e.coordinates)
      .filter((c): c is [number, number] => c !== null);

    if (coords.length === 0) return DEFAULT_GEO_BOUNDS;

    let minLon = DEFAULT_GEO_BOUNDS.minLon;
    let maxLon = DEFAULT_GEO_BOUNDS.maxLon;
    let minLat = DEFAULT_GEO_BOUNDS.minLat;
    let maxLat = DEFAULT_GEO_BOUNDS.maxLat;

    const outsideCampus = coords.some(
      ([lon, lat]) =>
        lon < DEFAULT_GEO_BOUNDS.minLon - 0.01 ||
        lon > DEFAULT_GEO_BOUNDS.maxLon + 0.01 ||
        lat < DEFAULT_GEO_BOUNDS.minLat - 0.01 ||
        lat > DEFAULT_GEO_BOUNDS.maxLat + 0.01
    );

    if (outsideCampus) {
      minLon = Math.min(...coords.map((c) => c[0]));
      maxLon = Math.max(...coords.map((c) => c[0]));
      minLat = Math.min(...coords.map((c) => c[1]));
      maxLat = Math.max(...coords.map((c) => c[1]));
      const lonPad = Math.max((maxLon - minLon) * 0.16, 0.0012);
      const latPad = Math.max((maxLat - minLat) * 0.16, 0.001);
      return {
        minLon: minLon - lonPad,
        maxLon: maxLon + lonPad,
        minLat: minLat - latPad,
        maxLat: maxLat + latPad,
      };
    }

    for (const [lon, lat] of coords) {
      if (lon < minLon) minLon = lon - 0.0003;
      if (lon > maxLon) maxLon = lon + 0.0003;
      if (lat < minLat) minLat = lat - 0.0003;
      if (lat > maxLat) maxLat = lat + 0.0003;
    }

    return { minLon, maxLon, minLat, maxLat };
  }, [entities]);

  // Chiếu tọa độ thực thể sang điểm SVG + tránh chồng lấp khi cùng 1 tọa độ phòng
  const projectedPins = useMemo(() => {
    const spatial = filteredEntities.filter(
      (e): e is DigitalTwinEntity & { coordinates: [number, number] } =>
        e.coordinates !== null
    );

    const lonSpan = Math.max(geoBounds.maxLon - geoBounds.minLon, 0.0001);
    const latSpan = Math.max(geoBounds.maxLat - geoBounds.minLat, 0.0001);
    const usableW = SVG_WIDTH - SVG_PAD_X * 2;
    const usableH = SVG_HEIGHT - SVG_PAD_Y * 2;

    const bucketCount = new Map<string, number>();

    return spatial.map((entity) => {
      const [lon, lat] = entity.coordinates;
      const baseX = SVG_PAD_X + ((lon - geoBounds.minLon) / lonSpan) * usableW;
      const baseY =
        SVG_HEIGHT -
        SVG_PAD_Y -
        ((lat - geoBounds.minLat) / latSpan) * usableH;

      const bucketKey = `${lon.toFixed(5)}_${lat.toFixed(5)}`;
      const idx = bucketCount.get(bucketKey) ?? 0;
      bucketCount.set(bucketKey, idx + 1);

      const angle = idx * (Math.PI / 2.4);
      const radius = idx === 0 ? 0 : 18 + Math.floor((idx - 1) / 4) * 14;
      const x = baseX + Math.cos(angle) * radius;
      const y = baseY + Math.sin(angle) * radius;

      return {
        entity,
        x,
        y,
      };
    });
  }, [filteredEntities, geoBounds]);

  const pinPosById = useMemo(
    () => new Map(projectedPins.map((p) => [p.entity.entity_id, { x: p.x, y: p.y }])),
    [projectedPins]
  );

  // Tập hợp liên kết 2 chiều (outgoing + inbound) cho thực thể đang chọn
  const selectedGraphLinks = useMemo(() => {
    if (!selectedEntity) return [];

    const links: Array<
      TwinRelationship & { direction: "outbound" | "inbound"; existsInLoaded: boolean }
    > = [];
    const seen = new Set<string>();

    for (const rel of selectedEntity.relationships) {
      const key = `out:${rel.predicate}:${rel.target_id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const targetEnt = entityById.get(rel.target_id);
      links.push({
        predicate: rel.predicate,
        target_id: rel.target_id,
        target_type: targetEnt?.type ?? rel.target_type,
        target_label: targetEnt
          ? getEntityDisplayName(targetEnt)
          : rel.target_label,
        direction: "outbound",
        existsInLoaded: Boolean(targetEnt),
      });
    }

    for (const other of entities) {
      if (other.entity_id === selectedEntity.entity_id) continue;
      for (const rel of other.relationships) {
        if (rel.target_id === selectedEntity.entity_id) {
          const key = `in:${rel.predicate}:${other.entity_id}`;
          if (seen.has(key)) continue;
          seen.add(key);
          links.push({
            predicate: rel.predicate,
            target_id: other.entity_id,
            target_type: other.type,
            target_label: getEntityDisplayName(other),
            direction: "inbound",
            existsInLoaded: true,
          });
        }
      }
    }

    return links;
  }, [entities, entityById, selectedEntity]);

  const nonSpatialCount = useMemo(
    () => filteredEntities.filter((e) => e.coordinates === null).length,
    [filteredEntities]
  );

  const alertCount = useMemo(
    () =>
      entities.filter(
        (e) =>
          e.status_indicator === "critical" || e.status_indicator === "warning"
      ).length,
    [entities]
  );

  const connBadge = getConnectionBadge(
    connectionMode,
    liveEnabled,
    isSandboxMode
  );

  const handleZoomIn = () => setZoom((z) => Math.min(2.4, +(z + 0.25).toFixed(2)));
  const handleZoomOut = () => setZoom((z) => Math.max(0.75, +(z - 0.25).toFixed(2)));
  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if ((e.target as HTMLElement).closest("[data-pin-node='true']")) return;
    setIsDragging(true);
    dragStartRef.current = {
      clientX: e.clientX,
      clientY: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!isDragging || !dragStartRef.current) return;
    const dx = e.clientX - dragStartRef.current.clientX;
    const dy = e.clientY - dragStartRef.current.clientY;
    setPan({
      x: Math.max(-320, Math.min(320, dragStartRef.current.panX + dx)),
      y: Math.max(-220, Math.min(220, dragStartRef.current.panY + dy)),
    });
  };

  const handlePointerUp = () => {
    setIsDragging(false);
    dragStartRef.current = null;
  };

  const handleJumpToEntity = (targetId: string) => {
    if (entityById.has(targetId)) {
      if (typeFilter !== "ALL") {
        const target = entityById.get(targetId);
        if (target && target.type !== typeFilter) {
          setTypeFilter("ALL");
        }
      }
      if (searchQuery) {
        setSearchQuery("");
      }
      setSelectedId(targetId);
    }
  };

  const handleCopyJsonLd = async () => {
    if (!selectedEntity) return;
    try {
      const jsonStr = JSON.stringify(
        buildCanonicalJsonLd(selectedEntity),
        null,
        2
      );
      await navigator.clipboard.writeText(jsonStr);
      setCopiedJsonLd(true);
      setTimeout(() => setCopiedJsonLd(false), 1800);
    } catch {
      /* Clipboard không khả dụng */
    }
  };

  // Lưới kinh độ / vĩ độ WGS84 trên bản đồ SVG
  const lonTicks = useMemo(() => {
    const steps = 4;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const ratio = i / steps;
      const val =
        geoBounds.minLon + (geoBounds.maxLon - geoBounds.minLon) * ratio;
      const x = SVG_PAD_X + (SVG_WIDTH - SVG_PAD_X * 2) * ratio;
      return { x, label: `${val.toFixed(4)}°E` };
    });
  }, [geoBounds]);

  const latTicks = useMemo(() => {
    const steps = 3;
    return Array.from({ length: steps + 1 }, (_, i) => {
      const ratio = i / steps;
      const val =
        geoBounds.minLat + (geoBounds.maxLat - geoBounds.minLat) * ratio;
      const y =
        SVG_HEIGHT - SVG_PAD_Y - (SVG_HEIGHT - SVG_PAD_Y * 2) * ratio;
      return { y, label: `${val.toFixed(4)}°N` };
    });
  }, [geoBounds]);

  return (
    <div className="p-4 md:p-6 space-y-4 max-w-[1600px] mx-auto animate-fade-in">
      {/* ═══════════════════════════════════════════════════════════
          1. THANH PIPELINE TRẠNG THÁI THỜI GIAN THỰC & ĐIỀU KHIỂN
         ═══════════════════════════════════════════════════════════ */}
      <section className="card p-4 md:p-5 space-y-4">
        {/* Top Row: Title + Live Status + Controls */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border border-accent/25 bg-accent-soft text-accent"
                aria-hidden="true"
              >
                <Network className="w-4 h-4" />
              </div>
              <h1 className="font-heading text-lg md:text-xl font-bold text-ink tracking-tight">
                Digital Twin Command Center
              </h1>
              <span
                className={clsx(
                  "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
                  connBadge.pillClass
                )}
              >
                <span
                  className={clsx(
                    "w-2 h-2 rounded-full shrink-0",
                    liveEnabled && "animate-pulse"
                  )}
                  style={{ backgroundColor: connBadge.dotColor }}
                />
                {connBadge.label}
              </span>
              <span className="mono-tag hidden sm:inline-flex">
                <ShieldCheck className="w-3.5 h-3.5 text-semantic-emerald" />
                PII Gatekeeper Active
              </span>
            </div>
            <p className="text-xs md:text-[13px] text-muted">
              Bản sao số không gian & đồ thị ngữ cảnh thời gian thực chuẩn quốc tế{" "}
              <span className="font-medium text-ink-soft">ETSI NGSI-LD v1.6</span>{" "}
              • Nguồn:{" "}
              <code className="font-mono text-[11.5px] px-1.5 py-0.5 rounded bg-paper-subtle border border-line text-ink-soft">
                {source}
              </code>{" "}
              • Đồng bộ lúc{" "}
              <span className="tabular-nums font-medium text-ink-soft">
                {formatTimeShort(lastUpdatedAt)}
              </span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isSandboxMode ? (
              <button
                type="button"
                onClick={exitSandboxMode}
                className="btn-ghost btn-sm text-semantic-violet border-semantic-violet/30"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Quay lại dữ liệu thực
              </button>
            ) : (
              <button
                type="button"
                onClick={activateSandboxMode}
                className="btn-ghost btn-sm"
                title="Nạp tập thực thể mẫu chuẩn NGSI-LD để trình diễn bản đồ & đồ thị liên kết"
              >
                <Sparkles className="w-3.5 h-3.5 text-accent" />
                Sandbox mẫu ICTU
              </button>
            )}

            <button
              type="button"
              onClick={() => setLiveEnabled(!liveEnabled)}
              className={clsx(
                "btn-sm inline-flex items-center gap-1.5 font-medium transition-colors border",
                liveEnabled
                  ? "bg-accent-soft text-accent border-accent/30 hover:bg-accent/15"
                  : "bg-paper-subtle text-muted border-line-hi hover:text-ink"
              )}
              aria-pressed={liveEnabled}
            >
              <Radio
                className={clsx("w-3.5 h-3.5", liveEnabled && "animate-pulse")}
              />
              {liveEnabled ? "Realtime: BẬT" : "Realtime: TẮT"}
            </button>

            <button
              type="button"
              onClick={() => void refresh()}
              disabled={isRefreshing}
              className="btn-ghost btn-sm"
            >
              <RefreshCw
                className={clsx("w-3.5 h-3.5", isRefreshing && "animate-spin")}
              />
              Làm mới
            </button>
          </div>
        </div>

        {/* Live 3-Stage Architecture Pipeline Strip */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 p-3 rounded-xl bg-paper-subtle/75 border border-line">
          <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-paper-white border border-line">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-md flex items-center justify-center bg-accent-soft text-accent shrink-0">
                <Database className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-ink truncate">
                  ① PostgreSQL Outbox (ACID)
                </div>
                <div className="text-[11px] text-dim truncate">
                  Transactional Event Capture & RLS
                </div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-accent shrink-0 hidden md:block" />
          </div>

          <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-paper-white border border-line">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-md flex items-center justify-center bg-accent-soft text-accent shrink-0">
                <Server className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-ink truncate">
                  ② FIWARE Orion-LD (ETSI NGSI-LD v1.6)
                </div>
                <div className="text-[11px] text-dim truncate">
                  Context Broker & Anti-Loop Sync
                </div>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-accent shrink-0 hidden md:block" />
          </div>

          <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-paper-white border border-line">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-md flex items-center justify-center bg-success-light text-semantic-emerald shrink-0">
                <Activity className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-ink truncate">
                  ③ PostGIS Spatial & Hasura Live
                </div>
                <div className="text-[11px] text-dim truncate">
                  WGS84 Geometry •{" "}
                  <span className="tabular-nums font-medium text-ink-soft">
                    {entities.length}
                  </span>{" "}
                  thực thể ({alertCount} cảnh báo)
                </div>
              </div>
            </div>
            <span className="pulse-dot" />
          </div>
        </div>

        {/* Filter Chips + Search + View Switcher */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pt-1">
          {/* Quick Entity Type KPI Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            {filterTabs.map((tab) => {
              const count = typeCounts[tab.key] ?? 0;
              const active = typeFilter === tab.key;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setTypeFilter(tab.key)}
                  className={clsx(
                    "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border tabular-nums",
                    active
                      ? "bg-accent-solid text-white border-transparent shadow-sm"
                      : "bg-paper-white text-muted border-line hover:border-line-hi hover:text-ink"
                  )}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span>{tab.label}</span>
                  <span
                    className={clsx(
                      "px-1.5 py-0.2 rounded-full text-[11px] font-semibold",
                      active
                        ? "bg-white/20 text-white"
                        : "bg-paper-subtle text-dim"
                    )}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search Input + Map/Grid Mode Switch */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
            <div className="relative min-w-[240px] sm:w-[280px]">
              <Search className="w-4 h-4 text-dim absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm thực thể, mã phòng, URN..."
                aria-label="Tìm kiếm thực thể số"
                className="input-field input-field-icon py-1.5 text-xs h-9"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-dim hover:text-ink"
                  aria-label="Xóa tìm kiếm"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div
              className="inline-flex rounded-lg p-0.5 bg-paper-subtle border border-line shrink-0"
              role="tablist"
              aria-label="Chế độ hiển thị không gian"
            >
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "map"}
                onClick={() => setViewMode("map")}
                className={clsx(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                  viewMode === "map"
                    ? "bg-paper-white text-ink shadow-sm border border-line"
                    : "text-muted hover:text-ink"
                )}
              >
                <MapIcon className="w-3.5 h-3.5" />
                Bản đồ Không gian 2D
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "grid"}
                onClick={() => setViewMode("grid")}
                className={clsx(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                  viewMode === "grid"
                    ? "bg-paper-white text-ink shadow-sm border border-line"
                    : "text-muted hover:text-ink"
                )}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                Lưới Thực thể Số
                {nonSpatialCount > 0 && (
                  <span className="px-1.5 rounded-full bg-accent-soft text-accent text-[11px] tabular-nums">
                    +{nonSpatialCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Thông báo lỗi hoặc gợi ý bật Sandbox khi CSDL chưa có thực thể */}
        {error && !isSandboxMode && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-semantic-amber/30 bg-warning-light text-xs text-ink">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-semantic-amber shrink-0" />
              <span>
                {error} — Bạn có thể bật{" "}
                <strong>Sandbox mẫu ICTU</strong> để kiểm tra trực quan Bản đồ
                PostGIS & Đồ thị NGSI-LD ngay lập tức.
              </span>
            </div>
            <button
              type="button"
              onClick={activateSandboxMode}
              className="btn-accent btn-sm shrink-0"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Mở Sandbox Trình diễn
            </button>
          </div>
        )}

        {!isLoading && !error && entities.length === 0 && !isSandboxMode && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-lg border border-line bg-paper-subtle text-xs text-muted">
            <div className="flex items-center gap-2.5">
              <MapPin className="w-4 h-4 text-accent shrink-0" />
              <span>
                Chưa có bản ghi thực thể nào trong{" "}
                <code className="font-mono text-ink">context.entity_state</code>{" "}
                cho tổ chức hiện tại. Khởi tạo dữ liệu từ Plugin hoặc bật chế độ
                mô phỏng Khuôn viên Số ICTU.
              </span>
            </div>
            <button
              type="button"
              onClick={activateSandboxMode}
              className="btn-accent btn-sm shrink-0"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Nạp dữ liệu mẫu ICTU Campus
            </button>
          </div>
        )}
      </section>

      {/* ═══════════════════════════════════════════════════════════
          2. KHÔNG GIAN CHÍNH: BẢN ĐỒ 2D / LƯỚI THỰC THỂ + INSPECTOR
         ═══════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left / Center Canvas (7 or 8 cols when inspector open, 12 cols if none selected) */}
        <div
          className={clsx(
            selectedEntity ? "lg:col-span-7 xl:col-span-8" : "lg:col-span-12",
            "space-y-3"
          )}
        >
          {viewMode === "map" ? (
            <div className="card overflow-hidden">
              {/* Map Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-line bg-paper-subtle/60">
                <div className="flex items-center gap-2 text-xs">
                  <MapPin className="w-3.5 h-3.5 text-accent" />
                  <span className="font-semibold text-ink">
                    Bản đồ Không gian PostGIS 2D
                  </span>
                  <span className="font-mono text-[11px] text-dim hidden sm:inline">
                    WGS84 • EPSG:4326
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {/* Legend */}
                  <div className="hidden md:flex items-center gap-3 text-[11px] text-muted">
                    <span className="inline-flex items-center gap-1">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: "var(--emerald)" }}
                      />
                      Ổn định
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: "var(--cyan)" }}
                      />
                      Đang bận
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: "var(--amber)" }}
                      />
                      Cảnh báo
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: "var(--rose)" }}
                      />
                      Khẩn cấp
                    </span>
                  </div>

                  {/* Zoom Controls */}
                  <div className="inline-flex items-center rounded-lg border border-line bg-paper-white p-0.5">
                    <button
                      type="button"
                      onClick={handleZoomOut}
                      className="icon-btn w-7 h-7"
                      title="Thu nhỏ (Zoom Out)"
                      aria-label="Thu nhỏ bản đồ"
                    >
                      <ZoomOut className="w-3.5 h-3.5" />
                    </button>
                    <span className="px-2 text-[11px] font-mono tabular-nums text-ink-soft">
                      {Math.round(zoom * 100)}%
                    </span>
                    <button
                      type="button"
                      onClick={handleZoomIn}
                      className="icon-btn w-7 h-7"
                      title="Phóng to (Zoom In)"
                      aria-label="Phóng to bản đồ"
                    >
                      <ZoomIn className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={handleResetView}
                      className="icon-btn w-7 h-7 border-l border-line rounded-l-none"
                      title="Đặt lại góc nhìn (Reset View)"
                      aria-label="Đặt lại góc nhìn bản đồ"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Interactive SVG Spatial Viewport */}
              <div className="relative w-full aspect-[16/9.2] min-h-[380px] bg-paper select-none overflow-hidden">
                <svg
                  viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
                  className={clsx(
                    "w-full h-full block",
                    isDragging ? "cursor-grabbing" : "cursor-grab"
                  )}
                  onPointerDown={handlePointerDown}
                  onPointerMove={handlePointerMove}
                  onPointerUp={handlePointerUp}
                  onPointerLeave={handlePointerUp}
                  role="img"
                  aria-label="Bản đồ không gian số PostGIS EPSG:4326"
                >
                  <defs>
                    <pattern
                      id="dt-minor-grid"
                      width="28"
                      height="28"
                      patternUnits="userSpaceOnUse"
                    >
                      <path
                        d="M 28 0 L 0 0 0 28"
                        fill="none"
                        stroke="var(--line)"
                        strokeWidth="0.7"
                        strokeOpacity="0.65"
                      />
                    </pattern>
                  </defs>

                  {/* Base Map Background */}
                  <rect
                    x="0"
                    y="0"
                    width={SVG_WIDTH}
                    height={SVG_HEIGHT}
                    fill="var(--paper)"
                  />

                  <g
                    transform={`translate(${SVG_WIDTH / 2 + pan.x}, ${
                      SVG_HEIGHT / 2 + pan.y
                    }) scale(${zoom}) translate(${-SVG_WIDTH / 2}, ${
                      -SVG_HEIGHT / 2
                    })`}
                  >
                    {/* Architectural Sub-grid */}
                    <rect
                      x={SVG_PAD_X - 24}
                      y={SVG_PAD_Y - 20}
                      width={SVG_WIDTH - (SVG_PAD_X - 24) * 2}
                      height={SVG_HEIGHT - (SVG_PAD_Y - 20) * 2}
                      rx="14"
                      fill="url(#dt-minor-grid)"
                      stroke="var(--line-hi)"
                      strokeWidth="1"
                    />

                    {/* WGS84 Graticule Longitude Lines */}
                    {lonTicks.map((t) => (
                      <g key={`lon-${t.label}`}>
                        <line
                          x1={t.x}
                          y1={SVG_PAD_Y - 20}
                          x2={t.x}
                          y2={SVG_HEIGHT - SVG_PAD_Y + 20}
                          stroke="var(--line-hi)"
                          strokeWidth="0.85"
                          strokeDasharray="4 4"
                        />
                        <text
                          x={t.x}
                          y={SVG_HEIGHT - 14}
                          textAnchor="middle"
                          fill="var(--dim)"
                          fontSize="10"
                          fontFamily="monospace"
                        >
                          {t.label}
                        </text>
                      </g>
                    ))}

                    {/* WGS84 Graticule Latitude Lines */}
                    {latTicks.map((t) => (
                      <g key={`lat-${t.label}`}>
                        <line
                          x1={SVG_PAD_X - 24}
                          y1={t.y}
                          x2={SVG_WIDTH - SVG_PAD_X + 24}
                          y2={t.y}
                          stroke="var(--line-hi)"
                          strokeWidth="0.85"
                          strokeDasharray="4 4"
                        />
                        <text
                          x={SVG_PAD_X - 30}
                          y={t.y + 3}
                          textAnchor="end"
                          fill="var(--dim)"
                          fontSize="10"
                          fontFamily="monospace"
                        >
                          {t.label}
                        </text>
                      </g>
                    ))}

                    {/* Campus Spine Roads & Fiber Conduits */}
                    <path
                      d="M 95 256 L 845 256 M 482 70 L 482 465"
                      stroke="var(--line-hi)"
                      strokeWidth="10"
                      strokeLinecap="round"
                      opacity="0.45"
                    />
                    <path
                      d="M 95 256 L 845 256 M 482 70 L 482 465"
                      stroke="var(--accent)"
                      strokeWidth="1.2"
                      strokeDasharray="6 6"
                      opacity="0.4"
                    />

                    {/* Campus Architectural Building Zones */}
                    {CAMPUS_ZONES.map((zone) => (
                      <g key={zone.id}>
                        <rect
                          x={zone.x}
                          y={zone.y}
                          width={zone.w}
                          height={zone.h}
                          rx="10"
                          fill="var(--paper-white)"
                          fillOpacity="0.88"
                          stroke="var(--line-hi)"
                          strokeWidth="1.35"
                        />
                        <rect
                          x={zone.x + 10}
                          y={zone.y + 10}
                          width="34"
                          height="20"
                          rx="5"
                          fill="var(--accent-soft)"
                          stroke="var(--accent)"
                          strokeOpacity="0.35"
                          strokeWidth="0.9"
                        />
                        <text
                          x={zone.x + 27}
                          y={zone.y + 24}
                          textAnchor="middle"
                          fill="var(--accent)"
                          fontSize="10.5"
                          fontWeight="700"
                        >
                          {zone.code}
                        </text>
                        <text
                          x={zone.x + 52}
                          y={zone.y + 23}
                          fill="var(--ink)"
                          fontSize="11"
                          fontWeight="600"
                        >
                          {zone.name}
                        </text>
                        <text
                          x={zone.x + 12}
                          y={zone.y + 43}
                          fill="var(--dim)"
                          fontSize="9.8"
                        >
                          {zone.subtitle}
                        </text>
                      </g>
                    ))}

                    {/* Active Relationship Graph Arcs on Spatial Map */}
                    {selectedEntity &&
                      pinPosById.has(selectedEntity.entity_id) &&
                      selectedGraphLinks.map((lnk) => {
                        const from = pinPosById.get(selectedEntity.entity_id);
                        const to = pinPosById.get(lnk.target_id);
                        if (!from || !to) return null;
                        const midX = (from.x + to.x) / 2;
                        const midY = (from.y + to.y) / 2 - 14;
                        return (
                          <g key={`arc-${lnk.predicate}-${lnk.target_id}`}>
                            <path
                              d={`M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`}
                              fill="none"
                              stroke="var(--accent)"
                              strokeWidth="1.8"
                              strokeDasharray="5 4"
                            />
                            <rect
                              x={midX - 38}
                              y={midY - 9}
                              width="76"
                              height="16"
                              rx="4"
                              fill="var(--paper-raised)"
                              stroke="var(--accent)"
                              strokeWidth="0.8"
                            />
                            <text
                              x={midX}
                              y={midY + 2}
                              textAnchor="middle"
                              fill="var(--accent)"
                              fontSize="8.8"
                              fontFamily="monospace"
                            >
                              {lnk.predicate}
                            </text>
                          </g>
                        );
                      })}

                    {/* Projected NGSI-LD Spatial Entity Pins */}
                    {projectedPins.map(({ entity, x, y }) => {
                      const st = getStatusConfig(entity.status_indicator);
                      const isSelected =
                        selectedEntity?.entity_id === entity.entity_id;
                      const label = getEntityDisplayName(entity);
                      const shortLabel =
                        label.length > 22 ? `${label.slice(0, 21)}…` : label;

                      return (
                        <g
                          key={entity.entity_id}
                          data-pin-node="true"
                          transform={`translate(${x}, ${y})`}
                          onClick={(ev) => {
                            ev.stopPropagation();
                            setSelectedId(entity.entity_id);
                          }}
                          className="cursor-pointer"
                        >
                          {/* Pulse Ring for warning / critical / busy */}
                          {st.pulse && (
                            <circle
                              r={isSelected ? 22 : 17}
                              fill={st.colorVar}
                              fillOpacity="0.18"
                            >
                              <animate
                                attributeName="r"
                                values={isSelected ? "12;25;12" : "10;20;10"}
                                dur={
                                  entity.status_indicator === "critical"
                                    ? "1.5s"
                                    : "2.4s"
                                }
                                repeatCount="indefinite"
                              />
                              <animate
                                attributeName="fill-opacity"
                                values="0.32;0.04;0.32"
                                dur={
                                  entity.status_indicator === "critical"
                                    ? "1.5s"
                                    : "2.4s"
                                }
                                repeatCount="indefinite"
                              />
                            </circle>
                          )}

                          {/* Selection Halo */}
                          {isSelected && (
                            <circle
                              r="15"
                              fill="none"
                              stroke="var(--accent)"
                              strokeWidth="2.2"
                            />
                          )}

                          {/* Pin Outer & Core */}
                          <circle
                            r={isSelected ? "10.5" : "8.5"}
                            fill="var(--paper-white)"
                            stroke={st.colorVar}
                            strokeWidth={isSelected ? "3" : "2.4"}
                          />
                          <circle r="4.2" fill={st.colorVar} />

                          {/* Crisp Callout Pill */}
                          <g transform="translate(0, -17)">
                            <rect
                              x={-(shortLabel.length * 3.1 + 10)}
                              y="-15"
                              width={shortLabel.length * 6.2 + 20}
                              height="18"
                              rx="5"
                              fill={
                                isSelected
                                  ? "var(--ink)"
                                  : "var(--paper-raised)"
                              }
                              stroke={
                                isSelected ? "var(--ink)" : "var(--line-hi)"
                              }
                              strokeWidth="1"
                            />
                            <text
                              x="0"
                              y="-3"
                              textAnchor="middle"
                              fill={
                                isSelected ? "var(--paper-white)" : "var(--ink)"
                              }
                              fontSize="9.8"
                              fontWeight={isSelected ? "700" : "500"}
                            >
                              {shortLabel}
                            </text>
                          </g>
                        </g>
                      );
                    })}
                  </g>

                  {/* Compass Rose & Scale Overlay (Fixed HUD) */}
                  <g transform={`translate(${SVG_WIDTH - 48}, 38)`}>
                    <circle
                      r="17"
                      fill="var(--paper-raised)"
                      stroke="var(--line-hi)"
                      strokeWidth="1"
                    />
                    <polygon points="0,-11 4,3 0,0 -4,3" fill="var(--accent)" />
                    <text
                      x="0"
                      y="12"
                      textAnchor="middle"
                      fill="var(--muted)"
                      fontSize="8.5"
                      fontWeight="700"
                    >
                      N
                    </text>
                  </g>
                </svg>

                {isLoading && (
                  <div className="absolute inset-0 bg-paper/70 backdrop-blur-[1px] flex items-center justify-center">
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-paper-white border border-line shadow-card text-xs font-medium text-ink">
                      <RefreshCw className="w-4 h-4 animate-spin text-accent" />
                      Đang đồng bộ không gian thực thể số...
                    </div>
                  </div>
                )}
              </div>

              {/* Map Footer Status */}
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-t border-line bg-paper-subtle/50 text-xs text-muted">
                <div className="flex flex-wrap items-center gap-3">
                  <span>
                    Hiển thị{" "}
                    <strong className="text-ink tabular-nums">
                      {projectedPins.length}
                    </strong>{" "}
                    điểm thực thể có tọa độ GPS
                  </span>
                  <span className="text-dim hidden sm:inline">•</span>
                  <span className="hidden sm:inline">
                    Kéo chuột để di chuyển bản đồ, bấm vào điểm nút để mở Đồ thị
                    & JSON-LD
                  </span>
                </div>

                {nonSpatialCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setViewMode("grid")}
                    className="text-accent hover:underline font-medium inline-flex items-center gap-1"
                  >
                    Xem thêm {nonSpatialCount} thực thể logic (không tọa độ GPS)
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* ═══════════════════════════════════════════════════════════
               CHẾ ĐỘ LƯỚI THỰC THỂ SỐ (ENTITY GRID CHO CẢ CÓ & KHÔNG GPS)
               ═══════════════════════════════════════════════════════════ */
            <div className="card p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2 text-xs">
                  <LayoutGrid className="w-4 h-4 text-accent" />
                  <span className="font-semibold text-ink">
                    Lưới Thực thể Số (Digital Twin Entity Grid)
                  </span>
                  <span className="mono-tag tabular-nums">
                    {filteredEntities.length} thực thể
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setViewMode("map")}
                  className="btn-ghost btn-sm"
                >
                  <MapIcon className="w-3.5 h-3.5" />
                  Chuyển sang Bản đồ 2D
                </button>
              </div>

              {filteredEntities.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted">
                  Không có thực thể nào khớp với bộ lọc hiện tại.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {filteredEntities.map((entity) => {
                    const Icon = getTypeIcon(entity.type);
                    const st = getStatusConfig(entity.status_indicator);
                    const isSelected =
                      selectedEntity?.entity_id === entity.entity_id;

                    return (
                      <button
                        key={entity.entity_id}
                        type="button"
                        onClick={() => setSelectedId(entity.entity_id)}
                        className={clsx(
                          "card-interactive text-left p-3.5 space-y-2.5",
                          isSelected &&
                            "ring-2 ring-accent border-accent bg-accent-soft/30"
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-paper-subtle border border-line text-accent shrink-0">
                              <Icon className="w-4 h-4" />
                            </div>
                            <div className="min-w-0">
                              <div className="text-sm font-semibold text-ink truncate">
                                {getEntityDisplayName(entity)}
                              </div>
                              <div className="text-[11px] font-mono text-dim truncate">
                                {getShortUrn(entity.entity_id)}
                              </div>
                            </div>
                          </div>
                          <span className="tag-chip shrink-0">{entity.type}</span>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-line text-[11px]">
                          <span className={st.badgeClass}>{st.label}</span>
                          <span className="text-dim font-mono tabular-nums">
                            {entity.coordinates
                              ? `${entity.coordinates[0].toFixed(4)}, ${entity.coordinates[1].toFixed(4)}`
                              : "Logical (No GPS)"}
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-[11px] text-muted">
                          <span className="inline-flex items-center gap-1">
                            <GitFork className="w-3 h-3 text-accent" />
                            {entity.relationships.length} liên kết đồ thị
                          </span>
                          <span className="inline-flex items-center gap-1 tabular-nums">
                            <Clock className="w-3 h-3" />
                            {formatTimeShort(entity.updated_at)}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ═══════════════════════════════════════════════════════════
            3. ENTITY INSPECTOR PANEL / DRAWER (BÊN PHẢI)
           ═══════════════════════════════════════════════════════════ */}
        {selectedEntity && (
          <aside
            aria-label="Chi tiết thực thể bản sao số"
            className="lg:col-span-5 xl:col-span-4 card overflow-hidden animate-scale-in"
          >
            {/* Inspector Header */}
            <div className="p-4 border-b border-line bg-paper-subtle/50 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2.5 min-w-0">
                  {(() => {
                    const Icon = getTypeIcon(selectedEntity.type);
                    return (
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-accent-soft border border-accent/25 text-accent shrink-0 mt-0.5">
                        <Icon className="w-4 h-4" />
                      </div>
                    );
                  })()}
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="tag-chip">{selectedEntity.type}</span>
                      <span
                        className={
                          getStatusConfig(selectedEntity.status_indicator)
                            .badgeClass
                        }
                      >
                        {
                          getStatusConfig(selectedEntity.status_indicator)
                            .label
                        }
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-ink mt-1 leading-snug">
                      {getEntityDisplayName(selectedEntity)}
                    </h2>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedId(null)}
                  className="icon-btn p-1.5 shrink-0"
                  aria-label="Đóng bảng chi tiết thực thể"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="p-2 rounded-lg bg-paper-white border border-line font-mono text-[11px] text-ink-soft break-all">
                {selectedEntity.entity_id}
              </div>

              {/* PII Gatekeeper Security Assurance Badge */}
              <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-semantic-emerald/25 bg-success-light text-xs">
                <span className="inline-flex items-center gap-1.5 font-semibold text-semantic-emerald">
                  <ShieldCheck className="w-4 h-4 shrink-0" />
                  🛡️ PII Gatekeeper Protected
                </span>
                <span className="text-[11px] text-muted">
                  Zero PII Leaked
                </span>
              </div>

              {/* Inspector Tabs */}
              <div
                className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-paper-white border border-line"
                role="tablist"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={inspectorTab === "graph"}
                  onClick={() => setInspectorTab("graph")}
                  className={clsx(
                    "inline-flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all",
                    inspectorTab === "graph"
                      ? "bg-accent-solid text-white shadow-sm"
                      : "text-muted hover:text-ink"
                  )}
                >
                  <GitFork className="w-3.5 h-3.5" />
                  Thuộc tính & Đồ thị
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={inspectorTab === "jsonld"}
                  onClick={() => setInspectorTab("jsonld")}
                  className={clsx(
                    "inline-flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all",
                    inspectorTab === "jsonld"
                      ? "bg-accent-solid text-white shadow-sm"
                      : "text-muted hover:text-ink"
                  )}
                >
                  <Code2 className="w-3.5 h-3.5" />
                  JSON-LD (@context)
                </button>
              </div>
            </div>

            {/* Inspector Body */}
            <div className="p-4 max-h-[560px] overflow-y-auto space-y-4">
              {inspectorTab === "graph" ? (
                <>
                  {/* Spatial Coordinates Summary */}
                  <div className="p-3 rounded-lg bg-paper-subtle/70 border border-line flex items-center justify-between gap-2 text-xs">
                    <span className="text-muted inline-flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-accent" />
                      Tọa độ PostGIS (WGS84):
                    </span>
                    {selectedEntity.coordinates ? (
                      <span className="font-mono font-semibold text-ink tabular-nums">
                        [{selectedEntity.coordinates[0].toFixed(5)},{" "}
                        {selectedEntity.coordinates[1].toFixed(5)}]
                      </span>
                    ) : (
                      <span className="text-dim italic">
                        Thực thể logic (Không gắn GPS)
                      </span>
                    )}
                  </div>

                  {/* Normalized Attributes */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-dim">
                      Thuộc tính Chuẩn hóa (NGSI-LD Properties)
                    </h3>
                    {(() => {
                      const props = extractNormalizedProperties(selectedEntity);
                      if (props.length === 0) {
                        return (
                          <div className="p-3 rounded-lg border border-line text-xs text-muted">
                            Thực thể chưa khai báo thuộc tính mở rộng.
                          </div>
                        );
                      }
                      return (
                        <div className="divide-y divide-line rounded-lg border border-line bg-paper-white">
                          {props.map((p) => (
                            <div
                              key={p.key}
                              className="flex items-center justify-between gap-3 px-3 py-2 text-xs"
                            >
                              <span className="font-mono text-muted truncate">
                                {p.key}
                              </span>
                              <span className="font-medium text-ink text-right break-all tabular-nums">
                                {p.value}
                                {p.unitCode && (
                                  <span className="ml-1 text-[11px] font-mono text-dim">
                                    ({p.unitCode})
                                  </span>
                                )}
                              </span>
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>

                  {/* Linked Graph Relationships */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-dim">
                        Liên kết Đồ thị Ngữ cảnh (Linked Graph)
                      </h3>
                      <span className="tag-chip tabular-nums">
                        {selectedGraphLinks.length} liên kết
                      </span>
                    </div>

                    {selectedGraphLinks.length === 0 ? (
                      <div className="p-3.5 rounded-lg border border-dashed border-line text-xs text-muted text-center">
                        Thực thể này hiện chưa có cạnh liên kết (`Relationship`)
                        sang thực thể khác.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {selectedGraphLinks.map((rel, idx) => {
                          const TargetIcon = getTypeIcon(rel.target_type);
                          return (
                            <button
                              key={`${rel.direction}-${rel.predicate}-${rel.target_id}-${idx}`}
                              type="button"
                              disabled={!rel.existsInLoaded}
                              onClick={() => handleJumpToEntity(rel.target_id)}
                              className={clsx(
                                "w-full text-left p-3 rounded-lg border transition-all flex items-center justify-between gap-2.5",
                                rel.existsInLoaded
                                  ? "bg-paper-white border-line hover:border-accent hover:bg-accent-soft/40 cursor-pointer group"
                                  : "bg-paper-subtle/50 border-line opacity-75 cursor-default"
                              )}
                            >
                              <div className="min-w-0 space-y-1">
                                <div className="flex items-center gap-1.5 text-[11px] font-mono text-accent">
                                  <span>
                                    {rel.direction === "outbound" ? "──" : "◀──"}
                                  </span>
                                  <span className="px-1.5 py-0.5 rounded bg-accent-soft font-semibold">
                                    {rel.predicate}
                                  </span>
                                  <span>
                                    {rel.direction === "outbound" ? "──▶" : "──"}
                                  </span>
                                  <span className="tag-chip">
                                    {rel.target_type}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2 min-w-0">
                                  <TargetIcon className="w-3.5 h-3.5 text-muted shrink-0" />
                                  <span className="text-xs font-semibold text-ink truncate">
                                    {rel.target_label}
                                  </span>
                                </div>
                                <div className="text-[10.5px] font-mono text-dim truncate">
                                  {rel.target_id}
                                </div>
                              </div>

                              {rel.existsInLoaded && (
                                <ArrowRight className="w-4 h-4 text-dim group-hover:text-accent group-hover:translate-x-0.5 transition-all shrink-0" />
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                /* Tab 2: Chuẩn Quốc tế ETSI NGSI-LD JSON-LD (@context) */
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-xs font-semibold text-ink flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-semantic-emerald" />
                        ETSI NGSI-LD v1.6 Payload
                      </div>
                      <p className="text-[11px] text-muted">
                        Tương thích liên thông FIWARE Orion-LD & Smart Data
                        Models quốc tế.
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => void handleCopyJsonLd()}
                      className="btn-accent btn-sm shrink-0"
                    >
                      {copiedJsonLd ? (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          Đã sao chép!
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          Copy JSON-LD
                        </>
                      )}
                    </button>
                  </div>

                  <pre
                    className="p-3.5 rounded-xl font-mono text-[11.5px] leading-relaxed overflow-x-auto border"
                    style={{
                      background: "var(--plate)",
                      color: "#E2E8F0",
                      borderColor: "var(--plate-border)",
                    }}
                  >
                    {JSON.stringify(
                      buildCanonicalJsonLd(selectedEntity),
                      null,
                      2
                    )}
                  </pre>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
};
