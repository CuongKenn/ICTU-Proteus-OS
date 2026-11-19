// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";

interface ProgressBarProps {
  progress: number;
  label?: string;
  status?: "installing" | "default";
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ progress, label }) => {
  return (
    <div className="w-full space-y-1.5">
      {label && (
        <div className="flex justify-between text-xs font-medium text-accent tabular-nums">
          <span>{label}</span>
          <span>{progress}%</span>
        </div>
      )}
      <div className="w-full h-1.5 rounded-full overflow-hidden bg-paper-subtle">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${Math.min(Math.max(progress, 0), 100)}%`,
            background: "var(--accent-solid)",
          }}
        />
      </div>
    </div>
  );
};
