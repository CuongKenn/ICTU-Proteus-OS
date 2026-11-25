// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState, useMemo, useEffect } from "react";
import { useSession } from "@/hooks/useSession";
import { useRBAC } from "@/hooks/useRBAC";
import { PluginCard, type PluginData, type PluginStatus } from "@/components/marketplace/PluginCard";
import { CategoryFilter } from "@/components/marketplace/CategoryFilter";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { Modal } from "@/components/ui/Modal";
import { InstallPreviewDialog } from "./InstallPreviewDialog";
import { InstallProgressModal } from "@/components/marketplace/InstallProgressModal";
import { AIPluginStudioModal } from "@/components/marketplace/AIPluginStudioModal";
import { useMarketplace } from "@/hooks/useMarketplace";
import { usePlugins } from "@/hooks/usePlugins";
import { PackageOpen, AlertTriangle, Sparkles } from "lucide-react";
import type { CredentialFieldSchema, CredentialInput } from "@/types";

const CATEGORIES = ["HR", "CRM", "Finance", "IT", "Operations", "Utilities", "Analytics", "Communication"];

export const MarketplaceClient: React.FC = () => {
  useSession();
  const { hasPermission } = useRBAC();
  const canInstall = hasPermission("plugins:install");

  const {
    plugins: installedPlugins,
    isLoading: isLoadingInstalled,
    refetch: refetchInstalled,
    enable,
    upgrade,
  } = usePlugins();
  const {
    plugins: availablePlugins,
    isLoading: isLoadingAvailable,
    installingId,
    installProgress,
    installStatus,
    installSteps,
    installPlugin,
    uninstallPlugin,
    closeProgress,
  } = useMarketplace(refetchInstalled);

  const [previewPlugin, setPreviewPlugin] = useState<PluginData | null>(null);
  const [previewCredSchema, setPreviewCredSchema] = useState<CredentialFieldSchema[]>([]);
  const [isInstallPreviewOpen, setIsInstallPreviewOpen] = useState(false);
  const [isProgressModalHidden, setIsProgressModalHidden] = useState(false);
  const [isStudioOpen, setIsStudioOpen] = useState(false);

  const [uninstallPluginData, setUninstallPluginData] = useState<{ id: string; name: string } | null>(null);
  const [isUninstallConfirmOpen, setIsUninstallConfirmOpen] = useState(false);
  const [isUninstalling, setIsUninstalling] = useState(false);

  useEffect(() => {
    if (installingId) {
      setIsProgressModalHidden(false);
    }
  }, [installingId]);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  const allPlugins = useMemo(() => {
    const list: Array<{
      data: PluginData;
      credSchema: CredentialFieldSchema[];
      status: PluginStatus;
      isInstalled: boolean;
    }> = [];

    installedPlugins.forEach((p) => {
      if (p.status === "DELETED") return;
      let uiStatus: PluginStatus = "active";
      if (p.status === "FAILED_DIRTY") uiStatus = "failed";
      else if (p.status === "DISABLED") uiStatus = "disabled";
      else if (p.status === "INSTALLING") uiStatus = "installing";
      else if (p.status === "UNINSTALLING") uiStatus = "uninstalling";
      else if (p.status === "PENDING_CREDENTIALS") uiStatus = "failed";

      list.push({
        data: {
          id: p.id,
          codeName: p.code_name,
          name: p.display_name,
          version: p.version,
          description: p.description || "Không có mô tả cho ứng dụng này.",
          tablesCount: p.tables_count ?? 0,
          workflowsCount: p.workflows_count ?? 0,
          requiredRoles: p.roles ?? [],
          isOfficial: p.is_official,
          category: p.category || "Utilities",
          author: p.author ?? undefined,
          tags: p.tags ?? [],
          iconUrl: p.icon_url ?? undefined,
        },
        credSchema: p.credentials_schema ?? [],
        status: uiStatus,
        isInstalled: true,
      });
    });

    availablePlugins.forEach((p) => {
      if (!installedPlugins.find((ip) => ip.code_name === p.code_name)) {
        list.push({
          data: {
            id: p.id,
            codeName: p.code_name,
            name: p.display_name,
            version: p.version,
            description: p.description || "Không có mô tả cho ứng dụng này.",
            tablesCount: p.tables_count ?? 0,
            workflowsCount: p.workflows_count ?? 0,
            requiredRoles: p.roles ?? [],
            isOfficial: p.is_official,
            category: p.category || "Utilities",
            author: p.author ?? undefined,
            tags: p.tags ?? [],
            iconUrl: p.icon_url ?? undefined,
          },
          credSchema: p.credentials_schema ?? [],
          status: "available",
          isInstalled: false,
        });
      }
    });

    return list;
  }, [availablePlugins, installedPlugins]);

  const filteredPlugins = useMemo(() => {
    return allPlugins.filter((p) => {
      const matchCategory = selectedCategory === "All" || p.data.category === selectedCategory;
      const searchLower = searchQuery.toLowerCase();
      const matchSearch =
        p.data.name.toLowerCase().includes(searchLower) ||
        p.data.description.toLowerCase().includes(searchLower) ||
        p.data.tags?.some((tag) => tag.toLowerCase().includes(searchLower));
      return matchCategory && matchSearch;
    });
  }, [allPlugins, searchQuery, selectedCategory]);

  const isLoading = isLoadingAvailable || isLoadingInstalled;

  const handleInstallClick = (id: string) => {
    if (!canInstall) return;
    const found = allPlugins.find((p) => p.data.id === id);
    if (found) {
      setPreviewPlugin(found.data);
      setPreviewCredSchema(found.credSchema);
      setIsInstallPreviewOpen(true);
    }
  };

  const handleConfirmInstall = async (credentials: CredentialInput[]) => {
    if (previewPlugin && canInstall) {
      setIsInstallPreviewOpen(false);
      await installPlugin(previewPlugin.id || "", credentials);
    }
  };

  const handleUninstallClick = (id: string) => {
    if (!canInstall) return;
    const plugin = allPlugins.find((p) => p.data.id === id)?.data;
    if (plugin) {
      setUninstallPluginData({ id: plugin.id || "", name: plugin.codeName || plugin.name });
      setIsUninstallConfirmOpen(true);
    }
  };

  const handleOpenClick = (id: string) => {
    const plugin = allPlugins.find((p) => p.data.id === id)?.data;
    if (plugin) {
      window.location.href = `/plugins/${plugin.codeName || plugin.id}`;
    }
  };

  const handleRetryClick = (id: string) => {
    handleInstallClick(id);
  };

  const handleEnableClick = async (id: string) => {
    try {
      await enable(id);
      refetchInstalled();
    } catch {
      // handled in hook toast
    }
  };

  const handleUpdateClick = async (id: string) => {
    try {
      await upgrade(id);
      refetchInstalled();
    } catch {
      // handled in hook toast
    }
  };

  const handleConfirmUninstall = async () => {
    if (!uninstallPluginData || !canInstall) return;
    setIsUninstalling(true);
    try {
      await uninstallPlugin(uninstallPluginData.id, uninstallPluginData.name);
      setIsUninstallConfirmOpen(false);
      setUninstallPluginData(null);
      refetchInstalled();
    } catch {
      // Toast thông báo lỗi đã hiển thị trong hook; giữ modal ổn định không kẹt loading
    } finally {
      setIsUninstalling(false);
    }
  };

  const handleCloseProgressModal = () => {
    setIsProgressModalHidden(true);
    closeProgress?.();
  };

  return (
    <div className="flex flex-col gap-6 pb-16 w-full max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pt-6 md:pt-8">
      {/* Header Panel */}
      <div className="card p-6 md:p-7">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-5 border-b border-line">
          <div className="max-w-2xl">
            <h1 className="text-2xl font-heading font-bold tracking-tight text-ink">
              Khám phá Ứng dụng
            </h1>
            <p className="text-sm text-muted mt-1 leading-relaxed">
              Mở rộng năng lực quản trị tổ chức với các phân hệ nghiệp vụ tiêu chuẩn, tự động cài đặt bảng dữ liệu, quy trình và báo cáo.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            {!isLoading && (
              <div className="flex items-center gap-3 text-xs text-muted tabular-nums">
                <span>
                  <strong className="text-ink font-semibold">{installedPlugins.length}</strong> đã cài
                </span>
                <span className="text-ghost">/</span>
                <span>
                  <strong className="text-ink font-semibold">{allPlugins.length}</strong> tổng phân hệ
                </span>
              </div>
            )}
            <button
              id="marketplace-ai-plugin-studio-btn"
              type="button"
              onClick={() => setIsStudioOpen(true)}
              className="btn-accent text-xs px-3.5 py-2"
            >
              <Sparkles className="w-3.5 h-3.5" />
              AI Plugin Studio
            </button>
          </div>
        </div>

        <div className="pt-5 w-full">
          <CategoryFilter
            categories={CATEGORIES}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
          />
        </div>
      </div>

      {/* Main Grid */}
      <div className="flex flex-col gap-5">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : allPlugins.length === 0 ? (
          <div className="card p-16 items-center text-center border-dashed">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 bg-paper-subtle border border-line">
              <PackageOpen className="w-6 h-6 text-dim" />
            </div>
            <h3 className="text-base font-heading font-semibold text-ink mb-1.5">
              Chưa có Plugin nào trên Marketplace
            </h3>
            <p className="text-sm text-muted max-w-md">
              Hệ thống hiện chưa có ứng dụng nào được phát hành. Vui lòng quay lại sau.
            </p>
          </div>
        ) : filteredPlugins.length === 0 ? (
          <div className="card p-16 items-center text-center border-dashed">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 bg-paper-subtle border border-line">
              <PackageOpen className="w-6 h-6 text-dim" />
            </div>
            <h3 className="text-base font-heading font-semibold text-ink mb-1.5">
              Không tìm thấy ứng dụng phù hợp
            </h3>
            <p className="text-sm text-muted max-w-md">
              {searchQuery
                ? `Không có kết quả nào khớp với "${searchQuery}". Hãy thử từ khóa khác.`
                : "Marketplace hiện chưa có ứng dụng nào trong danh mục này."}
            </p>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="btn-ghost mt-5"
              >
                Xóa bộ lọc tìm kiếm
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-fr">
            {filteredPlugins.map(({ data, status }) => {
              const currentStatus = installingId === data.id ? installStatus || status : status;
              return (
                <PluginCard
                  key={data.id}
                  plugin={data}
                  status={currentStatus as PluginStatus}
                  installProgress={installingId === data.id ? installProgress : 0}
                  canInstall={canInstall}
                  onInstall={handleInstallClick}
                  onUninstall={handleUninstallClick}
                  onOpen={handleOpenClick}
                  onRetry={handleRetryClick}
                  onEnable={handleEnableClick}
                  onUpdate={handleUpdateClick}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Install Preview Dialog */}
      <InstallPreviewDialog
        isOpen={isInstallPreviewOpen}
        plugin={previewPlugin}
        credentialsSchema={previewCredSchema}
        onClose={() => setIsInstallPreviewOpen(false)}
        onConfirm={handleConfirmInstall}
      />

      {/* Install Progress Modal */}
      <InstallProgressModal
        isOpen={Boolean(installingId) && !isProgressModalHidden}
        pluginName={allPlugins.find((p) => p.data.id === installingId)?.data.name}
        steps={installSteps || []}
        overallProgress={installProgress}
        status={installStatus}
        onClose={handleCloseProgressModal}
      />

      {/* Uninstall Confirm Modal */}
      <Modal
        isOpen={isUninstallConfirmOpen}
        title="Gỡ cài đặt Plugin"
        onClose={() => {
          setIsUninstallConfirmOpen(false);
          setUninstallPluginData(null);
        }}
        confirmKeyword={uninstallPluginData?.name}
        onConfirm={handleConfirmUninstall}
        confirmLabel="Gỡ cài đặt"
        confirmVariant="danger"
        isConfirmLoading={isUninstalling}
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-soft">
            Bạn có chắc chắn muốn gỡ cài đặt ứng dụng{" "}
            <strong className="text-ink font-semibold">{uninstallPluginData?.name}</strong>?
          </p>
          <div
            className="text-sm p-3.5 rounded-lg flex items-start gap-2.5 border"
            style={{
              background: "var(--rose-fill)",
              borderColor: "rgba(190, 18, 60, 0.25)",
              color: "var(--rose)",
            }}
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="text-xs leading-relaxed">
              <strong>Cảnh báo:</strong> Hành động này không thể hoàn tác. Toàn bộ dữ liệu nghiệp vụ, bảng dữ liệu và workflows liên quan đến ứng dụng này sẽ bị xóa vĩnh viễn khỏi hệ thống.
            </p>
          </div>
        </div>
      </Modal>
      {/* AI Plugin Studio Modal (#876) */}
      <AIPluginStudioModal
        isOpen={isStudioOpen}
        onClose={() => setIsStudioOpen(false)}
        canInstall={canInstall}
      />
    </div>
  );
};
