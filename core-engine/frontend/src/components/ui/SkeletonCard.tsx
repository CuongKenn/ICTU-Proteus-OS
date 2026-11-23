// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React from "react";

export const SkeletonCard: React.FC = () => (
  <div className="card p-5 animate-pulse">
    <div className="flex items-start gap-3.5">
      <div className="plugin-icon bg-paper-subtle" />
      <div className="flex-1 space-y-2">
        <div className="h-4 rounded bg-paper-subtle w-3/4" />
        <div className="h-3 rounded bg-paper-subtle w-1/3" />
        <div className="flex gap-1.5 pt-1">
          <div className="h-5 rounded bg-paper-subtle w-12" />
          <div className="h-5 rounded bg-paper-subtle w-16" />
        </div>
      </div>
    </div>
    <div className="mt-4 space-y-2">
      <div className="h-3 rounded bg-paper-subtle w-full" />
      <div className="h-3 rounded bg-paper-subtle w-2/3" />
    </div>
    <div className="separator mt-4" />
    <div className="mt-3.5 h-9 rounded-lg bg-paper-subtle" />
  </div>
);
