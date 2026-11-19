// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { usePathname } from "next/navigation";
import { Bell, LogOut, ChevronDown, Menu, ChevronRight } from "lucide-react";
import { NotificationPanel } from "@/components/NotificationPanel";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LanguageToggle } from "@/components/i18n/LanguageToggle";
import { useNotificationStore } from "@/store/notificationStore";

interface TopbarProps {
  onOpenMobileMenu?: () => void;
}

export function Topbar({ onOpenMobileMenu }: TopbarProps) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const unreadCount = useNotificationStore((s) => s.unreadCount);

  const handleLogout = async () => {
    try {
      const res = await fetch("/api/auth/federated-logout");
      const data = await res.json();
      await signOut({ redirect: false });
      window.location.href = data.url || "/login";
    } catch {
      await signOut({ callbackUrl: "/login" });
    }
  };

  const pageTitle = (() => {
    if (pathname.startsWith("/launchpad")) return "Dashboard";
    if (pathname.startsWith("/ai")) return "Proteus AI";
    if (pathname.startsWith("/marketplace")) return "Marketplace";
    if (pathname.startsWith("/settings")) return "Settings";
    if (pathname.startsWith("/chat")) return "Mattermost";
    if (pathname.startsWith("/wiki")) return "Outline Wiki";
    if (pathname.startsWith("/apps")) return "Apps (Low-code)";
    if (pathname.startsWith("/plugins/")) {
      const slug = pathname.replace("/plugins/", "").split("/")[0];
      return slug ? slug.replace(/-/g, " ") : "Plugin";
    }
    return "Workspace";
  })();

  const userInitial = (session?.user?.name || session?.user?.email || "U")
    .trim()
    .charAt(0)
    .toUpperCase();

  return (
    <header className="h-14 flex items-center justify-between px-4 md:px-6 shrink-0 bg-paper-raised border-b border-line">
      {/* Left: Mobile drawer button + Clean Enterprise Breadcrumb */}
      <div className="flex items-center gap-2 min-w-0">
        {onOpenMobileMenu && (
          <button
            type="button"
            onClick={onOpenMobileMenu}
            className="icon-btn p-2 -ml-1 md:hidden"
            aria-label="Mở menu điều hướng"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm min-w-0">
          <span className="text-dim font-medium hidden sm:inline">Proteus OS</span>
          <ChevronRight className="w-3.5 h-3.5 text-ghost hidden sm:inline shrink-0" />
          <span className="font-semibold text-ink truncate capitalize">{pageTitle}</span>
        </nav>
      </div>

      {/* Right: Utility Controls */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        <LanguageToggle />
        <ThemeToggle />

        {/* Notifications */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setShowNotifications((v) => !v);
              setShowUserMenu(false);
            }}
            className="icon-btn p-2 relative"
            aria-label="Thông báo"
          >
            <Bell className="w-[18px] h-[18px]" />
            {unreadCount > 0 && (
              <span
                className="absolute top-1 right-1 min-w-[16px] h-4 px-1 text-[10px] font-semibold text-white rounded-full flex items-center justify-center pointer-events-none tabular-nums"
                style={{ background: "var(--rose)" }}
              >
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>
          {showNotifications && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowNotifications(false)} />
              <div className="absolute right-0 top-full mt-2 z-50">
                <NotificationPanel onClose={() => setShowNotifications(false)} />
              </div>
            </>
          )}
        </div>

        {/* Divider */}
        {session?.user && <div className="h-5 w-px bg-line mx-1 hidden sm:block" />}

        {/* User Menu */}
        {session?.user && (
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setShowUserMenu((v) => !v);
                setShowNotifications(false);
              }}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-paper-subtle transition-colors cursor-pointer"
              aria-expanded={showUserMenu}
              aria-haspopup="menu"
            >
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
                style={{ background: "var(--accent-solid)" }}
              >
                {userInitial}
              </div>
              <span className="text-[13px] font-medium text-ink hidden lg:inline max-w-[140px] truncate">
                {session.user.name}
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-dim transition-transform duration-150 ${showUserMenu ? "rotate-180" : ""}`}
              />
            </button>

            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                <div
                  role="menu"
                  className="absolute right-0 mt-2 w-56 rounded-xl py-1 z-50 bg-paper-white border border-line-hi shadow-elevated animate-scale-in origin-top-right"
                >
                  <div className="px-3.5 py-2.5 border-b border-line">
                    <p className="text-[13px] font-semibold text-ink truncate">
                      {session.user.name}
                    </p>
                    <p className="text-xs text-dim truncate mt-0.5">
                      {session.user.email}
                    </p>
                  </div>
                  <div className="p-1">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="w-full text-left px-3 py-2 text-[13px] font-medium rounded-lg transition-colors flex items-center gap-2 text-error hover:bg-error/10 cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      Đăng xuất
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
