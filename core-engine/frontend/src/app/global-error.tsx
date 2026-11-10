// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { extractErrorMessage } from "@/lib/api";
import { logger } from "@/lib/logger";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    logger.error("Fatal root error in App Router:", error);
  }, [error]);

  const errorMessage = extractErrorMessage(error, "Đã xảy ra lỗi không thể phục hồi tại tầng giao diện gốc.");

  return (
    <html lang="vi">
      <body className="min-h-screen flex items-center justify-center p-6 bg-neutral-900 text-white font-sans">
        <div className="max-w-md w-full bg-neutral-800 border border-neutral-700 rounded-2xl p-8 text-center shadow-xl">
          <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Sự cố hệ thống nghiêm trọng</h1>
          <p className="text-sm text-neutral-400 mb-6">
            {errorMessage}
          </p>
          <button
            onClick={() => reset()}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition-colors text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Tải lại ứng dụng
          </button>
        </div>
      </body>
    </html>
  );
}
