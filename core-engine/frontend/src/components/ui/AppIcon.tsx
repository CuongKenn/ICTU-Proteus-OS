// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";
import { clsx } from "clsx";
import { ArrowUpRight } from "lucide-react";

interface AppIconProps {
  appName: string;
  subtitle?: string;
  icon: React.ReactNode;
  onClick?: () => void;
  isActive?: boolean;
}

export const AppIcon: React.FC<AppIconProps> = ({
  appName,
  subtitle,
  icon,
  onClick,
  isActive = true,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!isActive}
      className={clsx(
        "card-interactive text-left p-4 flex-row items-center gap-3.5 group w-full",
        isActive ? "cursor-pointer" : "opacity-55 cursor-not-allowed grayscale-[40%]"
      )}
    >
      <div className="w-11 h-11 rounded-lg flex items-center justify-center shrink-0 bg-paper-subtle border border-line group-hover:border-line-hi transition-colors">
        {icon}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink truncate">
            {appName}
          </span>
        </div>
        {subtitle && (
          <p className="text-xs text-muted truncate mt-0.5">{subtitle}</p>
        )}
      </div>

      <ArrowUpRight className="w-4 h-4 text-ghost group-hover:text-accent shrink-0 transition-colors" />
    </button>
  );
};
