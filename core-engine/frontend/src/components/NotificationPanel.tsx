// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { Bell, Check, X } from "lucide-react";
import { useNotificationStore } from "@/store/notificationStore";

interface NotificationPanelProps {
  onClose: () => void;
}

export function NotificationPanel({ onClose }: NotificationPanelProps) {
  const { notifications, markAllAsRead } = useNotificationStore();
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  return (
    <div className="w-80 rounded-xl bg-paper-white border border-line-hi shadow-elevated animate-scale-in origin-top-right overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-accent" />
          <span className="text-sm font-semibold text-ink">Thông báo</span>
          {unreadCount > 0 && (
            <span
              className="px-1.5 py-0.5 rounded-full text-[11px] font-semibold text-white tabular-nums"
              style={{ background: "var(--accent-solid)" }}
            >
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={markAllAsRead}
              className="icon-btn p-1.5"
              title="Đánh dấu tất cả đã đọc"
              aria-label="Đánh dấu tất cả đã đọc"
            >
              <Check className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="icon-btn p-1.5"
            aria-label="Đóng bảng thông báo"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="max-h-[360px] overflow-y-auto divide-y divide-line">
        {notifications.length === 0 ? (
          <div className="py-10 px-4 text-center text-dim">
            <Bell className="w-7 h-7 mx-auto mb-2.5 opacity-40" />
            <p className="text-sm font-medium text-muted">Không có thông báo mới</p>
            <p className="text-xs text-dim mt-1">Các cập nhật hệ thống sẽ xuất hiện tại đây.</p>
          </div>
        ) : (
          notifications.slice(0, 10).map((n) => (
            <div
              key={n.id}
              className="px-4 py-3 transition-colors hover:bg-paper-subtle/70"
              style={{
                background: n.isRead ? "transparent" : "var(--accent-soft)",
              }}
            >
              <p className={`text-[13px] leading-relaxed ${n.isRead ? "text-muted" : "text-ink font-medium"}`}>
                {n.message}
              </p>
              <span className="text-[11px] text-dim mt-1 block tabular-nums">
                {new Date(n.createdAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
