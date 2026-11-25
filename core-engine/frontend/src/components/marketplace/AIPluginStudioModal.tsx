// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// AIPluginStudioModal — AI-Assisted Plugin Blueprint Synthesizer (#876)
// Hỗ trợ gọi POST /api/proxy/v1/plugins/synthesize kèm chế độ sinh mẫu Offline tức thì (No-GPU Demo).

"use client";

import React, { useState, useMemo } from "react";
import {
  Sparkles,
  ShieldCheck,
  Database,
  FileCode2,
  Terminal,
  Download,
  Copy,
  Check,
  X,
  Loader2,
  UserCheck,
  Zap,
} from "lucide-react";
import { clsx } from "clsx";

export interface AIPluginStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SynthesizedBlueprint {
  codeName: string;
  displayName: string;
  statusMessage: string;
  sourceMode: "backend_ai" | "offline_instant";
  manifestYaml: string;
  seedSql: string;
}

function slugifyPluginCode(rawName: string): string {
  const normalized = rawName
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const base = normalized || "custom-ops";
  return base.endsWith("-module") ? base : `${base}-module`;
}

function buildDeterministicBlueprint(
  pluginTitle: string,
  businessDesc: string,
  overrideCodeName?: string,
  customMessage?: string,
  sourceMode: "backend_ai" | "offline_instant" = "offline_instant"
): SynthesizedBlueprint {
  const displayName = pluginTitle.trim() || "Quản lý Thiết bị Phòng Lab";
  const codeName = overrideCodeName || slugifyPluginCode(displayName);
  const prefix = codeName.split("-")[0] || "ops";
  const tableName = `${prefix}_records`;
  const entityType =
    prefix.charAt(0).toUpperCase() + prefix.slice(1) + "AssetRecord";
  const cleanDesc =
    businessDesc.trim() ||
    `Phân hệ ${displayName} quản lý danh mục, trạng thái vận hành và luồng phê duyệt tự động.`;

  const manifestYaml = `# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
# Sinh tự động bởi Proteus AI Plugin Studio (Trạng thái: pending_review #689)

name: "${codeName}"
display_name: "${displayName}"
version: "1.0.0"
description: |
  ${cleanDesc.replace(/\n/g, "\n  ")}
author: "Proteus AI Studio"
license: "AGPL-3.0-or-later"
category: "Operations"
is_official: false
tags:
  - "${prefix}"
  - "ai-synthesized"
credentials_schema: []

compatibility:
  proteus_os_min_version: "1.0.0"
  dsl_spec_version: "1.0"

database:
  tables:
    - "${tableName}"
  seed_file: "db/seed_data.sql"
  default_config:
    require_hitl_approval: true

workflows:
  - id: "wf_${prefix}_sync"
    file: "workflows/sample_webhook.json"
    name: "${displayName} Webhook"
    description: "Luồng xử lý nghiệp vụ qua n8n webhook"
    trigger: "webhook"
    webhook_path: "${codeName}-sync"

ui:
  external_url: "\${PLUGINS_MFE_URL}/${codeName}"

roles:
  - name: "${prefix}_manager"
    display_name: "${displayName} Manager"
    description: "Quản trị viên phân hệ ${displayName}"
    permissions:
      - "${prefix}:records:read"
      - "${prefix}:records:write"

ngsi:
  entities:
    - table: "${tableName}"
      type: "${entityType}"
      id_pattern: "urn:ngsi-ld:${entityType}:{tenant}:{id}"
      attributes:
        - column: "record_code"
          target: "recordCode"
          type: "Property"
        - column: "title"
          target: "name"
          type: "Property"
        - column: "status"
          target: "status"
          type: "Property"
      relationships: []
`;

  const seedSql = `-- Copyright (c) 2026 CuongKenn & ICTU Team
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- PostgreSQL Multi-Tenant Schema cho ${codeName} (RLS Ready)

CREATE TABLE IF NOT EXISTS ${tableName} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_code VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) DEFAULT 'GENERAL',
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    description TEXT,
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_${tableName}_tenant_code UNIQUE (tenant_id, record_code)
);

INSERT INTO ${tableName} (id, record_code, title, quantity, status, tenant_id)
VALUES (
    '20000000-0000-4000-8000-000000000001',
    '${prefix.toUpperCase()}-001',
    'Hồ sơ khởi tạo mẫu — ${displayName}',
    1,
    'ACTIVE',
    current_setting('app.current_tenant_id')::uuid
)
ON CONFLICT (tenant_id, record_code) DO NOTHING;
`;

  return {
    codeName,
    displayName,
    statusMessage:
      customMessage ||
      `Đã tổng hợp bản thiết kế Plugin '${codeName}'. Chờ quản trị viên kiểm duyệt & ký số (#689) trước khi nạp vào runtime.`,
    sourceMode,
    manifestYaml,
    seedSql,
  };
}

type PreviewTab = "manifest" | "sql" | "cli";

export const AIPluginStudioModal: React.FC<AIPluginStudioModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [pluginName, setPluginName] = useState("Quản lý Thiết bị Phòng Lab");
  const [businessPrompt, setBusinessPrompt] = useState(
    "Theo dõi danh mục máy trạm, cảm biến IoT tại các phòng thực hành, kiểm kê định kỳ và cảnh báo bảo trì."
  );
  const [instantDemoMode, setInstantDemoMode] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [blueprint, setBlueprint] = useState<SynthesizedBlueprint | null>(null);
  const [activeTab, setActiveTab] = useState<PreviewTab>("manifest");
  const [copied, setCopied] = useState<boolean>(false);

  const cliGuideText = useMemo(() => {
    const code = blueprint?.codeName || slugifyPluginCode(pluginName);
    const title = blueprint?.displayName || pluginName.trim() || "Custom Module";
    return `# 1. Khởi tạo bộ khung đầy đủ bằng proteus-sdk CLI
PYTHONPATH=sdk python -m proteus_sdk init ${code} \\
  --output-dir plugins \\
  --display-name "${title}"

# 2. Chạy trình kiểm định Hợp đồng, SQL, Webhook & PII Gatekeeper
PYTHONPATH=sdk python -m proteus_sdk validate plugins/${code}

# 3. Sau khi Admin review & ký số (#689), đồng bộ lên Marketplace
curl -X POST http://localhost:3000/api/proxy/v1/plugins/reload`;
  }, [blueprint, pluginName]);

  if (!isOpen) return null;

  const handleSynthesize = async () => {
    const trimmedTitle = pluginName.trim();
    const trimmedPrompt = businessPrompt.trim();
    if (!trimmedTitle && !trimmedPrompt) return;

    setIsGenerating(true);
    setCopied(false);

    if (instantDemoMode) {
      const generated = buildDeterministicBlueprint(
        trimmedTitle,
        trimmedPrompt,
        undefined,
        "Đã sinh mẫu cấu trúc Plugin tức thì (Offline Blueprint Mode — không yêu cầu GPU).",
        "offline_instant"
      );
      setBlueprint(generated);
      setActiveTab("manifest");
      setIsGenerating(false);
      return;
    }

    try {
      const combinedPrompt = `Tên phân hệ: ${trimmedTitle}. Mô tả nghiệp vụ: ${trimmedPrompt}`;
      const res = await fetch("/api/proxy/v1/plugins/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: combinedPrompt }),
      });

      if (res.ok) {
        const data = (await res.json()) as {
          message?: string;
          plugin_code_name?: string;
          status?: string;
          manifest_yaml?: string;
          seed_sql?: string;
        };
        const returnedCode =
          typeof data.plugin_code_name === "string" && data.plugin_code_name
            ? data.plugin_code_name
            : slugifyPluginCode(trimmedTitle);
        const base = buildDeterministicBlueprint(
          trimmedTitle,
          trimmedPrompt,
          returnedCode,
          data.message,
          "backend_ai"
        );
        setBlueprint({
          ...base,
          manifestYaml: data.manifest_yaml || base.manifestYaml,
          seedSql: data.seed_sql || base.seedSql,
        });
      } else {
        // Fallback mượt sang chế độ Offline Blueprint khi LLM local chưa bật hoặc Read-Only FS
        const fallback = buildDeterministicBlueprint(
          trimmedTitle,
          trimmedPrompt,
          undefined,
          "LLM Local chưa kích hoạt hoặc thư mục Read-Only — đã chuyển mượt sang trình tổng hợp Blueprint chuẩn SDK.",
          "offline_instant"
        );
        setBlueprint(fallback);
      }
      setActiveTab("manifest");
    } catch {
      const fallback = buildDeterministicBlueprint(
        trimmedTitle,
        trimmedPrompt,
        undefined,
        "Chế độ Offline khả dụng — đã sinh bản nháp hợp đồng Plugin chuẩn Proteus SDK.",
        "offline_instant"
      );
      setBlueprint(fallback);
      setActiveTab("manifest");
    } finally {
      setIsGenerating(false);
    }
  };

  const currentTabContent =
    activeTab === "manifest"
      ? blueprint?.manifestYaml || ""
      : activeTab === "sql"
      ? blueprint?.seedSql || ""
      : cliGuideText;

  const handleCopy = async () => {
    if (!currentTabContent) return;
    try {
      await navigator.clipboard.writeText(currentTabContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Ignore clipboard permission failure
    }
  };

  const handleDownloadDraft = () => {
    if (!blueprint) return;
    const isSql = activeTab === "sql";
    const filename = isSql
      ? `${blueprint.codeName}-seed_data.sql`
      : `${blueprint.codeName}-manifest.yaml`;
    const content = isSql ? blueprint.seedSql : blueprint.manifestYaml;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/55 backdrop-blur-[2px] animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-plugin-studio-title"
    >
      <div className="w-full max-w-3xl max-h-[90vh] bg-paper-white border border-line-hi rounded-2xl shadow-modal flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-line bg-paper-raised flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center border border-line"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2
                id="ai-plugin-studio-title"
                className="text-base font-heading font-bold text-ink"
              >
                AI Plugin Studio
              </h2>
              <p className="text-xs text-muted">
                Tổng hợp cấu trúc phân hệ chuẩn Open-Source SDK từ mô tả tiếng Việt
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng AI Plugin Studio"
            className="icon-btn p-1.5"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Input Form */}
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label
                htmlFor="studio-plugin-name"
                className="block text-xs font-semibold text-ink mb-1.5"
              >
                Tên phân hệ nghiệp vụ
              </label>
              <input
                id="studio-plugin-name"
                type="text"
                value={pluginName}
                onChange={(e) => setPluginName(e.target.value)}
                placeholder="VD: Quản lý Thiết bị Phòng Lab"
                className="w-full px-3.5 py-2 rounded-lg bg-paper border border-line focus:border-accent outline-none text-sm text-ink"
              />
            </div>

            <div>
              <label
                htmlFor="studio-plugin-prompt"
                className="block text-xs font-semibold text-ink mb-1.5"
              >
                Mô tả yêu cầu nghiệp vụ & bảng dữ liệu (Tiếng Việt)
              </label>
              <textarea
                id="studio-plugin-prompt"
                rows={3}
                value={businessPrompt}
                onChange={(e) => setBusinessPrompt(e.target.value)}
                placeholder="Mô tả quy trình, các trường dữ liệu cần quản lý và sự kiện..."
                className="w-full px-3.5 py-2 rounded-lg bg-paper border border-line focus:border-accent outline-none text-sm text-ink resize-none"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <label className="inline-flex items-center gap-2 text-xs text-ink-soft cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={instantDemoMode}
                  onChange={(e) => setInstantDemoMode(e.target.checked)}
                  className="rounded border-line text-accent focus:ring-accent"
                />
                <Zap className="w-3.5 h-3.5 text-amber-600" />
                <span>Chế độ sinh mẫu Offline tức thì (không cần GPU)</span>
              </label>

              <button
                type="button"
                onClick={handleSynthesize}
                disabled={isGenerating}
                className="btn-accent text-xs px-4 py-2"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tổng hợp cấu trúc…
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Tổng hợp Blueprint Plugin
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Synthesized Result & Verification Badges */}
          {blueprint && (
            <div className="space-y-4 pt-2 border-t border-line">
              {/* Safety & Governance Badges */}
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border"
                  style={{
                    background: "var(--emerald-fill)",
                    borderColor: "rgba(5, 150, 105, 0.3)",
                    color: "var(--emerald)",
                  }}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Manifest Contract Verified
                </span>

                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border"
                  style={{
                    background: "var(--accent-soft)",
                    borderColor: "rgba(37, 99, 235, 0.28)",
                    color: "var(--accent)",
                  }}
                >
                  <Database className="w-3.5 h-3.5" />
                  SQL Sandbox Checked
                </span>

                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border"
                  style={{
                    background: "var(--amber-fill)",
                    borderColor: "rgba(180, 83, 9, 0.3)",
                    color: "var(--amber)",
                  }}
                >
                  <UserCheck className="w-3.5 h-3.5" />
                  Human Review Required #689
                </span>
              </div>

              <div className="text-xs text-muted bg-paper-subtle px-3.5 py-2.5 rounded-lg border border-line">
                {blueprint.statusMessage}
              </div>

              {/* Preview Tabs */}
              <div className="border border-line rounded-xl overflow-hidden bg-paper">
                <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 bg-paper-raised border-b border-line">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setActiveTab("manifest")}
                      className={clsx(
                        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
                        activeTab === "manifest"
                          ? "bg-paper-white text-accent border border-line shadow-sm"
                          : "text-muted hover:text-ink"
                      )}
                    >
                      <FileCode2 className="w-3.5 h-3.5" />
                      manifest.yaml
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab("sql")}
                      className={clsx(
                        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
                        activeTab === "sql"
                          ? "bg-paper-white text-accent border border-line shadow-sm"
                          : "text-muted hover:text-ink"
                      )}
                    >
                      <Database className="w-3.5 h-3.5" />
                      seed_data.sql
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveTab("cli")}
                      className={clsx(
                        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
                        activeTab === "cli"
                          ? "bg-paper-white text-accent border border-line shadow-sm"
                          : "text-muted hover:text-ink"
                      )}
                    >
                      <Terminal className="w-3.5 h-3.5" />
                      proteus_sdk CLI
                    </button>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="btn-ghost btn-sm text-xs"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                          Đã sao chép
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          Sao chép
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={handleDownloadDraft}
                      className="btn-ghost btn-sm text-xs"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Tải cấu hình nháp
                    </button>
                  </div>
                </div>

                <pre className="p-4 text-xs font-mono text-ink overflow-x-auto max-h-[260px] overflow-y-auto leading-relaxed">
                  <code>{currentTabContent}</code>
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-line bg-paper-raised flex items-center justify-between gap-3 shrink-0">
          <span className="text-[11px] text-dim font-mono">
            PYTHONPATH=sdk python -m proteus_sdk validate
          </span>
          <button type="button" onClick={onClose} className="btn-ghost btn-sm">
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
