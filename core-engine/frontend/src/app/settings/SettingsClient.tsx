// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState } from "react";
import { SettingsTabs } from "@/components/settings/SettingsTabs";
import { ProfileTab } from "@/components/settings/ProfileTab";
import { Settings } from "lucide-react";
import { AppearanceTab } from "@/components/settings/AppearanceTab";
import { TenantTab } from "@/components/settings/TenantTab";
import { IntegrationsTab } from "@/components/settings/IntegrationsTab";
import { KnowledgeTab } from "@/components/settings/KnowledgeTab";
import { SecurityTab } from "@/components/settings/SecurityTab";
import { AboutTab } from "@/components/settings/AboutTab";
import { UsersTab } from "@/components/settings/UsersTab";
import { RolesTab } from "@/components/settings/RolesTab";
import { useSession } from "next-auth/react";

export type SettingsTabId =
  | "profile"
  | "tenant"
  | "users"
  | "roles"
  | "appearance"
  | "integrations"
  | "knowledge"
  | "security"
  | "about";

export const SettingsClient = () => {
  const [activeTab, setActiveTab] = useState<SettingsTabId>("profile");
  const { data: session } = useSession();

  const renderActiveTab = () => {
    switch (activeTab) {
      case "profile":
        return <ProfileTab session={session} />;
      case "tenant":
        return <TenantTab />;
      case "users":
        return <UsersTab />;
      case "roles":
        return <RolesTab />;
      case "integrations":
        return <IntegrationsTab />;
      case "knowledge":
        return <KnowledgeTab />;
      case "appearance":
        return <AppearanceTab />;
      case "security":
        return <SecurityTab />;
      case "about":
        return <AboutTab />;
      default:
        return (
          <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-dashed border-line-hi">
            <Settings className="w-10 h-10 mb-3 text-ghost" />
            <p className="text-sm text-muted">Tính năng này đang trong quá trình phát triển.</p>
          </div>
        );
    }
  };

  return (
    <div className="w-full max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-heading font-bold tracking-tight text-ink">Cài đặt hệ thống</h1>
        <p className="text-sm text-muted mt-1">
          Quản lý hồ sơ, thành viên, phân quyền RBAC, kết nối dịch vụ và kho tri thức AI của tổ chức.
        </p>
      </div>
      <div className="flex flex-col md:flex-row gap-6 items-start">
        <div className="w-full md:w-60 shrink-0 md:sticky md:top-6">
          <SettingsTabs activeTab={activeTab} onChangeTab={setActiveTab} />
        </div>
        <div className="flex-1 min-w-0 w-full">
          <div className="card p-6 md:p-7 min-h-[520px]">{renderActiveTab()}</div>
        </div>
      </div>
    </div>
  );
};
