// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { Moon, Sun, Check } from "lucide-react";
import { useTheme } from "@/components/ui/ThemeToggleProvider";

export const AppearanceTab = () => {
  const { theme, setTheme } = useTheme();

  const options = [
    {
      id: "light" as const,
      label: "Giao diện Sáng (Light)",
      desc: "Nền sáng sắc nét, độ tương phản cao, tối ưu cho môi trường văn phòng.",
      icon: Sun,
      previewBg: "#F8FAFC",
      previewCard: "#FFFFFF",
      previewBorder: "#E2E8F0",
      previewAccent: "#0369A1",
    },
    {
      id: "dark" as const,
      label: "Giao diện Tối (Dark)",
      desc: "Nền xanh than dịu mắt, giảm chói khi làm việc ban đêm hoặc giám sát dài giờ.",
      icon: Moon,
      previewBg: "#0B1120",
      previewCard: "#131C31",
      previewBorder: "#1E293B",
      previewAccent: "#38BDF8",
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="pb-5 border-b border-line">
        <h2 className="text-lg font-heading font-semibold text-ink">Giao diện hiển thị</h2>
        <p className="text-sm text-muted mt-1">
          Tùy chỉnh chế độ hiển thị cho toàn bộ Core Engine và các phân hệ Micro-Frontend.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {options.map((opt) => {
          const isSelected = theme === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => setTheme(opt.id)}
              className="text-left p-4 rounded-xl transition-all cursor-pointer border-2 bg-paper-white"
              style={{
                borderColor: isSelected ? "var(--accent)" : "var(--line)",
              }}
            >
              {/* Mini UI Preview */}
              <div
                className="h-24 rounded-lg p-3 mb-3.5 border flex gap-2.5 overflow-hidden"
                style={{
                  background: opt.previewBg,
                  borderColor: opt.previewBorder,
                }}
              >
                <div
                  className="w-12 rounded-md border flex flex-col gap-1.5 p-1.5"
                  style={{ background: opt.previewCard, borderColor: opt.previewBorder }}
                >
                  <div className="h-2 w-6 rounded-sm" style={{ background: opt.previewAccent }} />
                  <div className="h-1.5 w-8 rounded-sm opacity-30" style={{ background: opt.previewAccent }} />
                  <div className="h-1.5 w-7 rounded-sm opacity-20" style={{ background: opt.previewAccent }} />
                </div>
                <div className="flex-1 flex flex-col gap-2">
                  <div
                    className="h-5 rounded-md border"
                    style={{ background: opt.previewCard, borderColor: opt.previewBorder }}
                  />
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <div
                      className="rounded-md border"
                      style={{ background: opt.previewCard, borderColor: opt.previewBorder }}
                    />
                    <div
                      className="rounded-md border"
                      style={{ background: opt.previewCard, borderColor: opt.previewBorder }}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <opt.icon className="w-4 h-4 text-accent" />
                  <span className="font-semibold text-sm text-ink">{opt.label}</span>
                </div>
                {isSelected && (
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-white"
                    style={{ background: "var(--accent-solid)" }}
                  >
                    <Check className="w-3 h-3" />
                  </span>
                )}
              </div>
              <p className="text-xs text-muted mt-1.5 leading-relaxed">{opt.desc}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
