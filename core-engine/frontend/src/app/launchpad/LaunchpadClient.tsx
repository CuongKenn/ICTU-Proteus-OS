// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState, useEffect } from "react";
import { usePlugins } from "@/hooks/usePlugins";
import { AppIcon } from "@/components/ui/AppIcon";
import { useSession } from "next-auth/react";
import { useNotificationStore } from "@/store/notificationStore";
import {
  Blocks,
  BarChart3,
  FileText,
  MessageSquare,
  Workflow,
  X,
  Store,
  Bot,
  Calendar,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { useLang } from "@/components/i18n/LanguageContext";

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || "http://workflow.proteus.local";

export function LaunchpadClient() {
  const { data: session } = useSession();
  const hasRole = useAuthStore((state) => state.hasRole);
  const isAdmin =
    hasRole("tenant_admin") ||
    hasRole("superadmin") ||
    hasRole("system_admin") ||
    hasRole("admin");
  const { plugins, isLoading } = usePlugins();
  const [activeApp, setActiveApp] = useState<string | null>(null);
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [isIframeLoading, setIsIframeLoading] = useState(false);
  const addToast = useNotificationStore((state) => state.addToast);
  const router = useRouter();
  const { t, lang } = useLang();

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && activeApp) closeIframe();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [activeApp]);

  const openIframe = (appId: string, url: string) => {
    setActiveApp(appId);
    setIframeUrl(url);
    setIsIframeLoading(true);
  };

  const handleOpenMetabase = async () => {
    setIsIframeLoading(true);
    setActiveApp("metabase");
    try {
      const res = await fetch("/api/embed/metabase?dashboard_id=1");
      if (!res.ok) throw new Error("Failed to fetch signed URL");
      const data = await res.json();
      setIframeUrl(data.url);
    } catch {
      addToast("error", "Không thể tải báo cáo Metabase");
      setActiveApp(null);
    }
  };

  const closeIframe = () => {
    setActiveApp(null);
    setIframeUrl(null);
  };

  const handleOpenPlugin = (code_name: string) => {
    const plugin = plugins.find((p) => p.code_name === code_name);
    const targetUrl =
      plugin?.external_url ||
      plugin?.homepage_url ||
      `${process.env.NEXT_PUBLIC_APPSMITH_URL || "http://apps.proteus.local"}/app/${code_name}`;
    openIframe(code_name, targetUrl);
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    const timeOfDay =
      hour < 12
        ? t("launchpad.morning")
        : hour < 18
        ? t("launchpad.afternoon")
        : t("launchpad.evening");
    return lang === "en" ? `Good ${timeOfDay}` : `Chào buổi ${timeOfDay}`;
  };

  const visiblePlugins = plugins.filter((p) => {
    if (isAdmin) return true;
    if (!p.roles || p.roles.length === 0) return true;
    return p.roles.some((r) => hasRole(r));
  });

  const activePluginCount = visiblePlugins.filter((p) => p.status === "ACTIVE").length;

  return (
    <div className="relative">
      <div className="p-6 md:p-8 max-w-[1200px] mx-auto space-y-8">
        {/* Executive Workspace Header */}
        <div className="card p-6 flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div>
            <div className="inline-flex items-center gap-2 text-xs font-medium text-muted mb-2">
              <Calendar className="w-3.5 h-3.5 text-dim" />
              <span>
                {new Date().toLocaleDateString("vi-VN", {
                  weekday: "long",
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
            </div>
            <h1 className="text-2xl font-heading font-bold tracking-tight text-ink">
              {getGreeting()},{" "}
              <span className="text-accent">{session?.user?.name || "bạn"}</span>
            </h1>
            <p className="text-sm text-muted mt-1">
              Truy cập nhanh các công cụ cộng tác, điều hành và phân hệ nghiệp vụ trong tổ chức.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => router.push("/ai")}
              className="btn-ghost"
            >
              <Bot className="w-4 h-4 text-accent" />
              Proteus AI
            </button>
            <button
              type="button"
              onClick={() => router.push("/marketplace")}
              className="btn-accent"
            >
              <Store className="w-4 h-4" />
              Marketplace
            </button>
          </div>
        </div>

        {/* System Core Tools (H-P-D) */}
        <section className="space-y-3.5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-heading font-semibold text-ink">
              {t("launchpad.system")}
            </h2>
            <span className="text-xs text-dim">Dịch vụ nền tảng lõi</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <AppIcon
              appName="Mattermost"
              subtitle="Giao tiếp & Phê duyệt"
              icon={<MessageSquare className="w-5 h-5 text-accent" strokeWidth={1.75} />}
              onClick={() => router.push("/chat")}
              isActive
            />
            <AppIcon
              appName="Outline Wiki"
              subtitle="Kho tri thức nội bộ"
              icon={<FileText className="w-5 h-5 text-ink-soft" strokeWidth={1.75} />}
              onClick={() => router.push("/wiki")}
              isActive
            />
            {isAdmin && (
              <AppIcon
                appName="n8n Workflow"
                subtitle="Tự động hóa quy trình"
                icon={<Workflow className="w-5 h-5" style={{ color: "var(--amber)" }} strokeWidth={1.75} />}
                onClick={() => openIframe("n8n", N8N_URL)}
                isActive
              />
            )}
            {isAdmin && (
              <AppIcon
                appName="Metabase"
                subtitle="Phân tích & Báo cáo BI"
                icon={<BarChart3 className="w-5 h-5" style={{ color: "var(--emerald)" }} strokeWidth={1.75} />}
                onClick={handleOpenMetabase}
                isActive
              />
            )}
          </div>
        </section>

        {/* Installed Business Modules */}
        <section className="space-y-3.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <h2 className="text-sm font-heading font-semibold text-ink">
                {t("launchpad.plugins")}
              </h2>
              {!isLoading && visiblePlugins.length > 0 && (
                <span className="status-badge status-badge--active tabular-nums">
                  {activePluginCount} đang hoạt động
                </span>
              )}
            </div>
            {!isLoading && visiblePlugins.length > 0 && (
              <button
                type="button"
                onClick={() => router.push("/marketplace")}
                className="text-xs font-medium text-accent hover:underline cursor-pointer"
              >
                Quản lý ứng dụng
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="card p-4 flex-row items-center gap-3.5 animate-pulse"
                >
                  <div className="w-11 h-11 rounded-lg bg-paper-subtle shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 rounded bg-paper-subtle w-2/3" />
                    <div className="h-3 rounded bg-paper-subtle w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : visiblePlugins.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {visiblePlugins.map((plugin) => (
                <AppIcon
                  key={plugin.id}
                  appName={plugin.display_name}
                  subtitle={plugin.category || plugin.code_name}
                  icon={<Blocks className="w-5 h-5 text-accent" strokeWidth={1.75} />}
                  onClick={() => handleOpenPlugin(plugin.code_name)}
                  isActive={plugin.status === "ACTIVE"}
                />
              ))}
            </div>
          ) : (
            <div className="card p-10 text-center items-center border-dashed">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 bg-paper-subtle border border-line">
                <Blocks className="w-6 h-6 text-dim" />
              </div>
              <h3 className="text-base font-heading font-semibold text-ink mb-1.5">
                {t("launchpad.no_plugins")}
              </h3>
              <p className="text-sm text-muted max-w-md mb-5">
                Không gian làm việc của bạn chưa cài đặt phân hệ nghiệp vụ nào. Truy cập Marketplace để triển khai nhanh.
              </p>
              <button
                type="button"
                onClick={() => router.push("/marketplace")}
                className="btn-accent"
              >
                {t("launchpad.explore")}
              </button>
            </div>
          )}
        </section>
      </div>

      {/* Fullscreen Iframe Overlay */}
      {activeApp && iframeUrl && (
        <div className="fixed inset-0 z-[100] flex flex-col bg-paper animate-fade-in">
          <div className="h-12 flex items-center justify-between px-4 md:px-6 shrink-0 border-b border-line bg-paper-raised">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="pulse-dot" />
              <h2 className="text-sm font-semibold text-ink truncate">
                {activeApp === "metabase"
                  ? "Metabase Analytics"
                  : activeApp === "n8n"
                  ? "n8n Workflow"
                  : plugins.find((p) => p.code_name === activeApp)?.display_name || activeApp}
              </h2>
            </div>
            <button
              type="button"
              onClick={closeIframe}
              className="btn-ghost btn-sm"
              title="Đóng (Esc)"
            >
              <X className="w-4 h-4" />
              Đóng
            </button>
          </div>
          <div className="flex-1 relative">
            {isIframeLoading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10 bg-paper">
                <div
                  className="w-7 h-7 border-2 rounded-full animate-spin"
                  style={{ borderColor: "var(--line)", borderTopColor: "var(--accent)" }}
                />
                <span className="text-xs text-muted">Đang tải ứng dụng...</span>
              </div>
            )}
            <iframe
              src={iframeUrl}
              className="w-full h-full border-none"
              onLoad={() => setIsIframeLoading(false)}
              allow="clipboard-read; clipboard-write; fullscreen"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />
          </div>
        </div>
      )}
    </div>
  );
}
