// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// useMarketplace — Custom Hook quản lý Marketplace
// Tích hợp luồng cài đặt Plugin (State Machine) từ usePlugins.

import { useEffect, useState, useCallback, useRef } from "react";
import { getSession } from "next-auth/react";
import api from "@/lib/api";
import { logger } from "@/lib/logger";
import { useNotificationStore } from "@/store/notificationStore";
import { usePlugins } from "@/hooks/usePlugins";
import type { PluginInfo, InstallTaskStatus, CredentialInput, InstallTaskStep } from "@/types";
import type { PluginStatus } from "@/components/marketplace/PluginCard";

interface UseMarketplaceReturn {
  plugins: PluginInfo[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
  // Install Flow State Machine
  installingId: string | null;
  installProgress: number;
  installStatus: PluginStatus | null;
  installSteps: InstallTaskStep[];
  installPlugin: (pluginId: string, credentials?: CredentialInput[]) => Promise<void>;
  uninstallPlugin: (pluginId: string, confirmName?: string) => Promise<void | { task_id: string }>;
  closeProgress: () => void;
}

export function useMarketplace(onInstallSuccess?: () => void): UseMarketplaceReturn {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trigger, setTrigger] = useState(0);

  // Install State Machine
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installProgress, setInstallProgress] = useState(0);
  const [installStatus, setInstallStatus] = useState<PluginStatus | null>(null);
  const [installSteps, setInstallSteps] = useState<InstallTaskStep[]>([]);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollInFlightRef = useRef(false);
  const onInstallSuccessRef = useRef(onInstallSuccess);
  onInstallSuccessRef.current = onInstallSuccess;

  const { install, uninstall } = usePlugins();

  const clearResetTimer = useCallback(() => {
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
  }, []);

  const scheduleInstallReset = useCallback(() => {
    clearResetTimer();
    resetTimerRef.current = setTimeout(() => {
      resetTimerRef.current = null;
      setInstallingId(null);
      setInstallStatus(null);
      setInstallProgress(0);
      setInstallSteps([]);
    }, 2000);
  }, [clearResetTimer]);

  useEffect(() => {
    return () => {
      // Cleanup interval and reset timer when hook unmounts
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      clearResetTimer();
    };
  }, [clearResetTimer]);

  useEffect(() => {
    let cancelled = false;

    const fetchPlugins = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await api.get<{ items: PluginInfo[]; total: number }>("/v1/plugins");

        if (!cancelled) {
          setPlugins(response.data.items || []);
        }
      } catch (err: unknown) {
        logger.error("[useMarketplace] fetch error:", err);
        if (!cancelled) {
          if (process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
            import("../__tests__/marketplace.mock").then(({ MOCK_PLUGINS }) => {
              setPlugins(MOCK_PLUGINS);
            });
          } else {
            setError("Không thể tải danh sách Plugin. Vui lòng thử lại.");
            useNotificationStore.getState().addToast("error", "Không thể tải danh sách Plugin.");
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchPlugins();
    return () => { cancelled = true; };
  }, [trigger]);

  const pollStatus = useCallback(async (taskId: string, pluginId: string) => {
    if (pollInFlightRef.current) return;
    pollInFlightRef.current = true;
    try {
      const response = await api.get<InstallTaskStatus>(`/v1/plugins/install/${taskId}/status`);

      const statusData = response.data;

      if (statusData) {
        // Tính progress từ steps thực tế
        if (statusData.steps && statusData.steps.length > 0) {
          setInstallSteps(statusData.steps);
          const completedSteps = statusData.steps.filter(
            (s) => s.status === "DONE"
          ).length;
          const realProgress = Math.round((completedSteps / statusData.steps.length) * 100);
          setInstallProgress((prev) => Math.max(prev, realProgress));
        } else {
          // Fallback khi steps rỗng — cap at 95 để luôn còn chỗ cho completion
          setInstallProgress((prev) => Math.min(prev + 5, 95));
        }

        // Check terminal status — dùng overall_status từ API mới
        const overallStatus = statusData.overall_status;
        if (overallStatus === "ACTIVE" || overallStatus === "COMPLETED") {
          setInstallProgress(100);
          setInstallStatus("active");
          useNotificationStore.getState().addToast("success", "Cài đặt Plugin thành công!");
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setTrigger((t) => t + 1);
          onInstallSuccessRef.current?.();
          scheduleInstallReset();
        } else if (
          overallStatus === "FAILED_DIRTY" ||
          overallStatus === "FAILED" ||
          overallStatus === "ROLLING_BACK"
        ) {
          setInstallStatus("failed");
          useNotificationStore.getState().addToast("error", "Cài đặt Plugin thất bại.");
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          onInstallSuccessRef.current?.();
          scheduleInstallReset();
        }
      }
    } catch (err: any) {
      // 401: token hết hạn — force session refresh và tiếp tục polling
      const httpStatus = err?.response?.status;
      if (httpStatus === 401) {
        logger.warn("[useMarketplace] 401 khi poll status — thử refresh session");
        try {
          await getSession(); // triggers next-auth token refresh
        } catch {
          // ignore — next poll sẽ thử lại tự động
        }
        return; // không dừng polling, thử lại lần sau
      }
      // Lỗi thực sự (5xx, network) → dừng polling
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setInstallStatus("failed");
      useNotificationStore.getState().addToast("error", "Không thể kiểm tra tiến trình cài đặt. Vui lòng kiểm tra lại Backend.");
      scheduleInstallReset();
    } finally {
      pollInFlightRef.current = false;
    }
  }, [scheduleInstallReset]);

  const pollUninstallStatus = useCallback(async (taskId: string, pluginId: string) => {
    if (pollInFlightRef.current) return;
    pollInFlightRef.current = true;
    try {
      const response = await api.get<InstallTaskStatus>(`/v1/plugins/install/${taskId}/status`);
      const statusData = response.data;
      if (statusData) {
        if (statusData.steps && statusData.steps.length > 0) {
          setInstallSteps(statusData.steps);
          const completedSteps = statusData.steps.filter((s) => s.status === "DONE").length;
          const realProgress = Math.round((completedSteps / statusData.steps.length) * 100);
          setInstallProgress((prev) => Math.max(prev, realProgress));
        } else {
          setInstallProgress((prev) => Math.min(prev + 10, 95));
        }

        const overallStatus = statusData.overall_status;
        if (overallStatus === "DELETED" || overallStatus === "COMPLETED") {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setInstallProgress(100);
          useNotificationStore.getState().addToast("success", "Đã gỡ cài đặt Plugin thành công.");
          setTrigger((t) => t + 1);
          onInstallSuccessRef.current?.();
          scheduleInstallReset();
        } else if (
          overallStatus === "FAILED_DIRTY" ||
          overallStatus === "FAILED" ||
          overallStatus === "ROLLING_BACK"
        ) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setInstallStatus("failed");
          useNotificationStore.getState().addToast("error", "Gỡ cài đặt Plugin thất bại.");
          onInstallSuccessRef.current?.();
          scheduleInstallReset();
        }
      }
    } catch (err: any) {
      const httpStatus = err?.response?.status;
      if (httpStatus === 401) {
        try {
          await getSession();
        } catch {
          // ignore
        }
        return;
      }
      if (httpStatus === 404) {
        // Bản ghi đã xóa khỏi DB → gỡ thành công
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        setInstallProgress(100);
        useNotificationStore.getState().addToast("success", "Đã gỡ cài đặt Plugin thành công.");
        setTrigger((t) => t + 1);
        onInstallSuccessRef.current?.();
        scheduleInstallReset();
        return;
      }
      // Fallback: kiểm tra danh sách installed xem plugin đã biến mất chưa
      try {
        const installedRes = await api.get<{ items: PluginInfo[] }>("/v1/plugins/installed");
        const stillInstalled = (installedRes.data?.items || []).some((p) => p.id === pluginId);
        if (!stillInstalled) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setInstallProgress(100);
          useNotificationStore.getState().addToast("success", "Đã gỡ cài đặt Plugin thành công.");
          setTrigger((t) => t + 1);
          onInstallSuccessRef.current?.();
          scheduleInstallReset();
          return;
        }
      } catch {
        // ignore fallback error
      }
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setInstallStatus("failed");
      useNotificationStore.getState().addToast("error", "Không thể kiểm tra tiến trình gỡ cài đặt.");
      onInstallSuccessRef.current?.();
      scheduleInstallReset();
    } finally {
      pollInFlightRef.current = false;
    }
  }, [scheduleInstallReset]);

  const installPlugin = useCallback(async (pluginId: string, credentials?: CredentialInput[]) => {
    // Clear interval và timeout cũ nếu có
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    clearResetTimer();
    pollInFlightRef.current = false;

    setInstallingId(pluginId);
    setInstallProgress(0);
    setInstallStatus("installing");
    setInstallSteps([]);

    try {
      const data = await install(pluginId, credentials);
      if (data?.task_id) {
        pollingRef.current = setInterval(() => {
          pollStatus(data.task_id, pluginId);
        }, 3000);
      } else {
        throw new Error("No task_id returned");
      }
    } catch (error) {
      if (process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
        // Simulate install progress locally
        let mockProgress = 0;
        pollingRef.current = setInterval(() => {
          mockProgress += 20;
          setInstallProgress(mockProgress);
          if (mockProgress >= 100) {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setInstallStatus("active");
            useNotificationStore.getState().addToast("success", "Cài đặt Plugin thành công (Mock).");
            onInstallSuccessRef.current?.();
            scheduleInstallReset();
          }
        }, 500);
      } else {
        setInstallStatus("failed");
        useNotificationStore.getState().addToast("error", "Không thể bắt đầu cài đặt Plugin.");
        setInstallingId(null);
      }
    }
  }, [install, pollStatus, clearResetTimer, scheduleInstallReset]);

  const uninstallPlugin = useCallback(async (pluginId: string, confirmName?: string) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    clearResetTimer();
    pollInFlightRef.current = false;

    const data = await uninstall(pluginId, confirmName);
    if (data?.task_id && !data.task_id.startsWith("mock-")) {
      setInstallingId(pluginId);
      setInstallProgress(0);
      setInstallStatus("uninstalling");
      setInstallSteps([]);
      onInstallSuccessRef.current?.();
      pollingRef.current = setInterval(() => {
        pollUninstallStatus(data.task_id, pluginId);
      }, 2500);
    } else {
      if (!data?.task_id) {
        useNotificationStore.getState().addToast("success", "Đã gỡ cài đặt Plugin thành công.");
      }
      setTrigger((t) => t + 1);
      onInstallSuccessRef.current?.();
    }
    return data;
  }, [uninstall, pollUninstallStatus, clearResetTimer]);

  const closeProgress = useCallback(() => {
    const isBusy =
      installStatus === "installing" ||
      installStatus === "uninstalling" ||
      installStatus === "upgrading";
    if (!isBusy) {
      clearResetTimer();
      setInstallingId(null);
      setInstallStatus(null);
      setInstallProgress(0);
      setInstallSteps([]);
    }
  }, [installStatus, clearResetTimer]);

  return {
    plugins,
    isLoading,
    error,
    refetch: () => setTrigger((t) => t + 1),
    installingId,
    installProgress,
    installStatus,
    installSteps,
    installPlugin,
    uninstallPlugin,
    closeProgress,
  };
}
