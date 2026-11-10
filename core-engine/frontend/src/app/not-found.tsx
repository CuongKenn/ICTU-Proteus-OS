// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import React from "react";
import Link from "next/link";
import { FileQuestion, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg-base text-text-primary">
      <div className="max-w-md w-full bg-bg-surface border border-border rounded-2xl p-8 shadow-elevated text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
          <FileQuestion className="w-8 h-8" />
        </div>
        <h1 className="text-3xl font-bold font-grot mb-2">404</h1>
        <h2 className="text-lg font-semibold mb-2">Không tìm thấy trang</h2>
        <p className="text-sm text-text-secondary mb-6">
          Trang bạn đang tìm kiếm không tồn tại hoặc đã được di chuyển.
        </p>
        <Link
          href="/launchpad"
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-white font-medium hover:bg-primary-hover transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Về trang chủ
        </Link>
      </div>
    </div>
  );
}
