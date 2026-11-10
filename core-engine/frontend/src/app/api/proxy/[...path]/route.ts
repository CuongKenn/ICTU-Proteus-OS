// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// BFF API Route — Backend Proxy
// Tất cả request từ Client → BFF Proxy → FastAPI Backend.
// Token được inject và tự động refresh. Browser KHÔNG bao giờ gọi Backend trực tiếp.
// Dùng getToken() + manual refresh thay vì getServerSession() (gây 500 trong App Router).
// Tham chiếu: docs/architecture.md (BFF Pattern)

import { NextRequest, NextResponse } from "next/server";
import { getBffAuth } from "@/lib/bffAuth";
import { withRotatedCookie } from "@/lib/sessionCookie";
import { logger } from "@/lib/logger";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxyHandler(
  request: NextRequest,
  { params }: { params: { path: string[] } }
): Promise<NextResponse> {
  const auth = await getBffAuth(request);
  if (!auth.success) {
    return auth.response;
  }

  const { accessToken, rotatedCookieValue } = auth;

  const targetPath = params.path.join("/");
  // Frontend calls api.get("/v1/roles") → params.path = ["v1","roles"] → targetPath = "v1/roles"
  // Dùng /api/ (không thêm v1) để tránh double prefix: /api/v1/v1/roles (404)
  const targetUrl = `${BACKEND_URL}/api/${targetPath}${request.nextUrl.search}`;

  // Forward headers có chọn lọc — không forward cookie, host, x-forwarded-* từ client
  const headers = new Headers({
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": request.headers.get("Content-Type") ?? "application/json",
    Accept: request.headers.get("Accept") ?? "application/json",
    "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
  });

  // Đọc body một lần — request.text() không thể gọi 2 lần
  let body: string | undefined = undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    try {
      body = await request.text();
    } catch (error) {
      logger.error("[BFF] Lỗi đọc request body:", error);
      return withRotatedCookie(
        NextResponse.json(
          { error: "Invalid request body format or stream interrupted" },
          { status: 400 }
        ),
        rotatedCookieValue
      );
    }
  }

  let response: Response;
  try {
    response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });
  } catch (err: any) {
    logger.error(`[BFF] Fetch to backend failed: ${err.message}`);
    return withRotatedCookie(
      NextResponse.json({ error: "Backend unavailable" }, { status: 502 }),
      rotatedCookieValue
    );
  }

  logger.info(`[BFF] ${request.method} ${targetUrl} → ${response.status}`);

  if (response.status === 401) {
    const txt = await response.text();
    logger.error(`[BFF] Backend returned 401 for ${targetUrl}: ${txt}`);
    return withRotatedCookie(
      NextResponse.json({ error: "Unauthorized from backend", detail: txt }, { status: 401 }),
      rotatedCookieValue
    );
  }

  // Proxy status code và response body nguyên vẹn
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const data = await response.json().catch(() => null);
    return withRotatedCookie(
      NextResponse.json(data, { status: response.status }),
      rotatedCookieValue
    );
  }

  // Non-JSON response (ví dụ: file download)
  const blob = await response.blob();
  return withRotatedCookie(
    new NextResponse(blob, {
      status: response.status,
      headers: { "Content-Type": contentType },
    }),
    rotatedCookieValue
  );
}

export const GET = proxyHandler;
export const POST = proxyHandler;
export const PUT = proxyHandler;
export const PATCH = proxyHandler;
export const DELETE = proxyHandler;
