// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import Image from "next/image";
import clsx from "clsx";
import {
  Download,
  CheckCircle2,
  ArrowUpCircle,
  XCircle,
  Trash2,
  ShieldCheck,
  Lock,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";

export type PluginStatus =
  | "available"
  | "installing"
  | "uninstalling"
  | "upgrading"
  | "active"
  | "update_available"
  | "failed"
  | "disabled";

export interface PluginData {
  id: string;
  name: string;
  codeName?: string;
  version: string;
  description: string;
  tablesCount?: number;
  workflowsCount?: number;
  requiredRoles?: string[];
  isOfficial?: boolean;
  developer?: string;
  author?: string | null;
  iconUrl?: string | null;
  rating?: number;
  category?: string;
  tags?: string[];
  /** URL public của Plugin UI (React MFE gateway). */
  externalUrl?: string | null;
}

export interface PluginCardProps {
  plugin: PluginData;
  status: PluginStatus;
  installProgress?: number;
  canInstall?: boolean;
  onInstall?: (id: string) => void;
  onUpdate?: (id: string) => void;
  onOpen?: (id: string) => void;
  onRetry?: (id: string) => void;
  onEnable?: (id: string) => void;
  onUninstall?: (id: string) => void;
}

export const PluginCard: React.FC<PluginCardProps> = ({
  plugin,
  status,
  installProgress = 0,
  canInstall = false,
  onInstall,
  onUpdate,
  onOpen,
  onRetry,
  onEnable,
  onUninstall,
}) => {
  const isDisabled = status === "disabled";
  const category = plugin.category || "Utilities";
  const developer = plugin.author || plugin.developer || "Proteus Core";
  const tags = plugin.tags ?? [];

  const renderUninstallButton = () => {
    if (!onUninstall) return null;
    return (
      <Button
        variant="ghost"
        onClick={() => onUninstall(plugin.id)}
        disabled={!canInstall}
        className={clsx("!px-2.5", canInstall ? "hover:!text-error hover:!border-error/40" : "opacity-50 cursor-not-allowed")}
        title={!canInstall ? "Bạn không có quyền thao tác" : "Gỡ cài đặt"}
        aria-label={!canInstall ? "Bạn không có quyền thao tác" : "Gỡ cài đặt"}
      >
        {!canInstall ? <Lock className="w-4 h-4" /> : <Trash2 className="w-4 h-4" />}
      </Button>
    );
  };

  const statusBadge = () => {
    switch (status) {
      case "active":
        return (
          <span className="status-badge status-badge--active">
            <CheckCircle2 className="w-3.5 h-3.5" /> Đang chạy
          </span>
        );
      case "failed":
        return (
          <span className="status-badge status-badge--failed">
            <XCircle className="w-3.5 h-3.5" /> Lỗi cài đặt
          </span>
        );
      case "disabled":
        return (
          <span className="status-badge status-badge--disabled">
            Tạm tắt
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={clsx(
        "card-interactive p-5 flex flex-col gap-3.5",
        isDisabled && "opacity-65 grayscale-[35%]"
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3.5">
        <div className="plugin-icon">
          {plugin.iconUrl ? (
            <Image
              src={plugin.iconUrl}
              alt={plugin.name}
              width={28}
              height={28}
              className="object-contain"
              unoptimized
            />
          ) : (
            <span className="text-base font-bold font-heading text-accent">
              {plugin.name.charAt(0)}
            </span>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <h3 className="text-[15px] font-semibold font-heading text-ink truncate">
              {plugin.name}
            </h3>
            {plugin.isOfficial && (
              <ShieldCheck
                className="w-4 h-4 shrink-0 text-accent"
                aria-label="Official Plugin"
              />
            )}
          </div>
          <p className="text-xs text-dim truncate mt-0.5">{developer}</p>

          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <span className="font-mono text-[11px] font-medium px-2 py-0.5 rounded bg-paper-subtle text-muted border border-line">
              v{plugin.version}
            </span>
            <span
              className="text-[11px] font-medium px-2 py-0.5 rounded"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              {category}
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      <p className="text-[13.5px] line-clamp-2 min-h-[2.6rem] leading-relaxed text-muted">
        {plugin.description}
      </p>

      {/* Tags */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.slice(0, 3).map((tag) => (
            <span key={tag} className="tag-chip">
              {tag}
            </span>
          ))}
          {tags.length > 3 && (
            <span className="tag-chip text-dim">+{tags.length - 3}</span>
          )}
        </div>
      )}

      {/* Footer Actions */}
      <div className="mt-auto pt-3.5 border-t border-line flex items-center justify-between min-h-[2.5rem] gap-2">
        {status === "available" && (
          <Button
            onClick={() => canInstall && onInstall?.(plugin.id)}
            disabled={!canInstall}
            className="w-full"
          >
            {!canInstall ? <Lock className="w-4 h-4" /> : <Download className="w-4 h-4" />}
            Nhận
          </Button>
        )}

        {(status === "installing" || status === "uninstalling" || status === "upgrading") && (
          <div className="w-full">
            <ProgressBar
              progress={installProgress}
              label={
                status === "uninstalling"
                  ? "Đang gỡ cài đặt..."
                  : status === "upgrading"
                  ? "Đang nâng cấp..."
                  : "Đang cài đặt..."
              }
              status="installing"
            />
          </div>
        )}

        {status === "active" && (
          <div className="flex items-center justify-between w-full gap-2">
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => onOpen?.(plugin.id)}>
                <ExternalLink className="w-3.5 h-3.5" />
                Mở
              </Button>
              {renderUninstallButton()}
            </div>
            {statusBadge()}
          </div>
        )}

        {status === "update_available" && (
          <Button
            onClick={() => onUpdate?.(plugin.id)}
            className="btn-accent w-full"
            style={{ background: "var(--amber)" }}
          >
            <ArrowUpCircle className="w-4 h-4" /> Cập nhật
          </Button>
        )}

        {status === "failed" && (
          <div className="flex items-center justify-between w-full gap-2">
            <div className="flex items-center gap-2">
              <Button variant="danger" onClick={() => onRetry?.(plugin.id)}>
                Thử lại
              </Button>
              {renderUninstallButton()}
            </div>
            {statusBadge()}
          </div>
        )}

        {status === "disabled" && (
          <div className="flex items-center justify-between w-full gap-2">
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => onEnable?.(plugin.id)}>
                Bật
              </Button>
              {renderUninstallButton()}
            </div>
            {statusBadge()}
          </div>
        )}
      </div>
    </div>
  );
};
