// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertCircle, RefreshCw, Home } from "lucide-react";
import { extractErrorMessage } from "@/lib/api";
import { logger } from "@/lib/logger";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Unhandled client error in App Router:", error);
  }, [error]);

  const errorMessage = extractErrorMessage(error, "Hệ thống gặp sự cố trong quá trình xử lý yêu cầu.");

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-bg-base text-text-primary">
      <div className="max-w-md w-full bg-bg-surface border border-border rounded-2xl p-8 shadow-elevated text-center">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-error/10 border border-error/20 flex items-center justify-center text-error">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold font-grot mb-2">Đã xảy ra lỗi</h2>
        <p className="text-sm text-text-secondary mb-6">
          {errorMessage}
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={() => reset()}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white font-medium hover:bg-primary-hover transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Thử lại
          </button>
          <Link
            href="/launchpad"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-bg-base border border-border text-text-primary font-medium hover:bg-bg-surface transition-colors text-sm"
          >
            <Home className="w-4 h-4" />
            Về trang chủ
          </Link>
        </div>
      </div>
    </div>
  );
}
