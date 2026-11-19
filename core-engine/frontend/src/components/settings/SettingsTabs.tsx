// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { clsx } from "clsx";
import { User, Building2, Palette, Blocks, Shield, KeyRound, Info, Users, BookOpen } from "lucide-react";
import type { SettingsTabId } from "@/app/settings/SettingsClient";

interface SettingsTabsProps {
  activeTab: SettingsTabId;
  onChangeTab: (tab: SettingsTabId) => void;
}

const TAB_GROUPS: {
  label: string;
  tabs: { id: SettingsTabId; label: string; icon: React.ElementType }[];
}[] = [
  {
    label: "Tài khoản & Giao diện",
    tabs: [
      { id: "profile", label: "Hồ sơ cá nhân", icon: User },
      { id: "appearance", label: "Giao diện", icon: Palette },
      { id: "security", label: "Bảo mật", icon: KeyRound },
    ],
  },
  {
    label: "Tổ chức & Phân quyền",
    tabs: [
      { id: "tenant", label: "Tổ chức (Tenant)", icon: Building2 },
      { id: "users", label: "Người dùng", icon: Users },
      { id: "roles", label: "Vai trò & Quyền", icon: Shield },
    ],
  },
  {
    label: "Nền tảng & Tri thức",
    tabs: [
      { id: "integrations", label: "Kết nối tích hợp", icon: Blocks },
      { id: "knowledge", label: "Kho tri thức AI", icon: BookOpen },
      { id: "about", label: "Thông tin hệ thống", icon: Info },
    ],
  },
];

export const SettingsTabs: React.FC<SettingsTabsProps> = ({ activeTab, onChangeTab }) => {
  return (
    <nav aria-label="Danh mục cài đặt" className="card p-3 space-y-4">
      {TAB_GROUPS.map((group) => (
        <div key={group.label} className="space-y-1">
          <div className="px-2.5 pb-1 text-[11px] font-semibold text-dim">
            {group.label}
          </div>
          {group.tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onChangeTab(tab.id)}
                className={clsx(
                  "nav-item w-full text-left px-2.5 py-2 cursor-pointer",
                  isActive && "nav-item--active"
                )}
                aria-current={isActive ? "page" : undefined}
              >
                <tab.icon className="w-4 h-4 shrink-0" strokeWidth={isActive ? 2.1 : 1.75} />
                <span className="truncate">{tab.label}</span>
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
};
