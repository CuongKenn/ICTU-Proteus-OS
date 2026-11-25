// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  Bot,
  Network,
  Store,
  Settings,
  MessageSquare,
  FileText,
  LayoutGrid,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";

interface NavGroup {
  title: string;
  items: {
    id: string;
    label: string;
    icon: React.ElementType;
    href: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Không gian làm việc",
    items: [
      { id: "launchpad", label: "Dashboard", icon: LayoutDashboard, href: "/launchpad" },
      { id: "digital-twin", label: "Bản sao số (Digital Twin)", icon: Network, href: "/digital-twin" },
      { id: "ai", label: "Proteus AI", icon: Bot, href: "/ai" },
      { id: "marketplace", label: "Marketplace", icon: Store, href: "/marketplace" },
    ],
  },
  {
    title: "Cộng tác & Ứng dụng",
    items: [
      { id: "chat", label: "Mattermost", icon: MessageSquare, href: "/chat" },
      { id: "wiki", label: "Outline Wiki", icon: FileText, href: "/wiki" },
      { id: "apps", label: "Apps (Low-code)", icon: LayoutGrid, href: "/apps" },
    ],
  },
  {
    title: "Quản trị hệ thống",
    items: [
      { id: "settings", label: "Settings", icon: Settings, href: "/settings" },
    ],
  },
];

interface SidebarProps {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export function Sidebar({ mobileOpen = false, onCloseMobile }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  const renderNavContent = (isCompact: boolean, closeOnNav: boolean) => (
    <>
      {/* Brand Lockup */}
      <div className="h-14 flex items-center justify-between px-4 shrink-0 border-b border-line">
        <Link
          href="/launchpad"
          onClick={closeOnNav ? onCloseMobile : undefined}
          className="flex items-center gap-2.5 overflow-hidden"
        >
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center font-heading font-bold text-white text-xs shrink-0 shadow-sm"
            style={{ background: "var(--accent-solid)" }}
          >
            P
          </div>
          {!isCompact && (
            <div className="flex flex-col leading-none">
              <span className="font-heading text-[15px] font-bold tracking-tight text-ink whitespace-nowrap">
                Proteus <span className="text-accent">OS</span>
              </span>
              <span className="text-[11px] text-dim mt-0.5 whitespace-nowrap">
                Enterprise Edition
              </span>
            </div>
          )}
        </Link>
        {closeOnNav && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="icon-btn p-1.5 md:hidden"
            aria-label="Đóng thanh điều hướng"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Grouped Navigation */}
      <nav aria-label="Điều hướng chính" className="flex-1 py-4 px-2.5 space-y-5 overflow-y-auto">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="space-y-1">
            {!isCompact ? (
              <div className="px-2.5 pb-1 text-[11px] font-semibold text-dim tracking-wide">
                {group.title}
              </div>
            ) : (
              <div className="mx-2 my-1 h-px bg-line" />
            )}
            {group.items.map((item) => {
              const isActive =
                pathname === item.href || pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  onClick={closeOnNav ? onCloseMobile : undefined}
                  className={clsx(
                    "nav-item",
                    isActive && "nav-item--active",
                    isCompact ? "justify-center px-2 py-2.5" : "px-2.5 py-2"
                  )}
                  title={isCompact ? item.label : undefined}
                  aria-current={isActive ? "page" : undefined}
                >
                  <item.icon className="w-[17px] h-[17px] shrink-0" strokeWidth={isActive ? 2.1 : 1.75} />
                  {!isCompact && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={clsx(
          "hidden md:flex flex-col h-full shrink-0 bg-paper-raised border-r border-line transition-[width] duration-200",
          collapsed ? "w-[64px]" : "w-[236px]"
        )}
      >
        {renderNavContent(collapsed, false)}

        {/* Footer Collapse Control */}
        <div className="p-2 border-t border-line shrink-0">
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className={clsx(
              "icon-btn w-full h-9 text-xs font-medium gap-2",
              collapsed ? "justify-center px-0" : "justify-start px-2.5"
            )}
            aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
          >
            {collapsed ? (
              <PanelLeftOpen className="w-4 h-4 shrink-0" />
            ) : (
              <>
                <PanelLeftClose className="w-4 h-4 shrink-0" />
                <span>Thu gọn</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/40 backdrop-blur-[2px] animate-fade-in"
            onClick={onCloseMobile}
          />
          <aside className="relative z-10 flex flex-col w-[264px] max-w-[82vw] h-full bg-paper-raised border-r border-line shadow-modal animate-fade-in">
            {renderNavContent(false, true)}
          </aside>
        </div>
      )}
    </>
  );
}
