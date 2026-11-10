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

function isAllowedCorsOrigin(origin: string): boolean {
  if (!origin) return false;
  try {
    const url = new URL(origin);
    const host = url.hostname;
    if (host === "localhost" || host === "127.0.0.1" || host === "::1") return true;
    if (host === "proteus.local" || host.endsWith(".proteus.local")) return true;
    const baseHost = new URL(process.env.NEXTAUTH_URL ?? "http://localhost:3000").hostname;
    if (host === baseHost || host.endsWith(`.${baseHost}`)) return true;
  } catch {
    return false;
  }
  return false;
}

function withCorsHeaders(res: NextResponse, req: NextRequest): NextResponse {
  const origin = req.headers.get("origin");
  if (origin && isAllowedCorsOrigin(origin)) {
    res.headers.set("Access-Control-Allow-Origin", origin);
    res.headers.set("Access-Control-Allow-Credentials", "true");
    res.headers.set(
      "Access-Control-Allow-Methods",
      "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
    );
    res.headers.set(
      "Access-Control-Allow-Headers",
      "Content-Type, Authorization, Accept, X-Requested-With, X-Forwarded-Host, X-Tenant-ID"
    );
    res.headers.set("Access-Control-Max-Age", "86400");
  }
  return res;
}

export async function OPTIONS(request: NextRequest): Promise<NextResponse> {
  const origin = request.headers.get("origin");
  const headers = new Headers();
  if (origin && isAllowedCorsOrigin(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Access-Control-Allow-Credentials", "true");
    headers.set(
      "Access-Control-Allow-Methods",
      "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD"
    );
    headers.set(
      "Access-Control-Allow-Headers",
      "Content-Type, Authorization, Accept, X-Requested-With, X-Forwarded-Host, X-Tenant-ID"
    );
    headers.set("Access-Control-Max-Age", "86400");
  }
  return new NextResponse(null, { status: 204, headers });
}

async function proxyHandler(
  request: NextRequest,
  { params }: { params: { path: string[] } }
): Promise<NextResponse> {
  const auth = await getBffAuth(request);
  if (!auth.success) {
    return withCorsHeaders(auth.response, request);
  }

  const { accessToken, rotatedCookieValue } = auth;

  const rawPath = params.path.join("/");
  let decodedPath = rawPath;
  try {
    decodedPath = decodeURIComponent(rawPath);
  } catch (e) {
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json({ error: "Invalid path encoding" }, { status: 400 }),
        rotatedCookieValue
      ),
      request
    );
  }

  // Chặn Path traversal (#734)
  if (
    decodedPath.includes("..") ||
    params.path.some((seg) => seg.includes("..") || seg.includes("%2e") || seg.includes("%2E"))
  ) {
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json({ error: "Path traversal forbidden" }, { status: 400 }),
        rotatedCookieValue
      ),
      request
    );
  }

  // Chặn route nội bộ (#734)
  const normalizedPath = decodedPath.replace(/^\/+/, "");
  if (
    normalizedPath.startsWith("v1/webhooks") ||
    normalizedPath.startsWith("webhooks") ||
    normalizedPath.startsWith("internal")
  ) {
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json(
          { error: "Access to internal routes is forbidden" },
          { status: 403 }
        ),
        rotatedCookieValue
      ),
      request
    );
  }

  const targetPath = rawPath;
  // Frontend calls api.get("/v1/roles") → params.path = ["v1","roles"] → targetPath = "v1/roles"
  // Dùng /api/ (không thêm v1) để tránh double prefix: /api/v1/v1/roles (404)
  // Backend /health route mount ở root thay vì /api/health
  const targetUrl = targetPath === "health"
    ? `${BACKEND_URL}/health${request.nextUrl.search}`
    : `${BACKEND_URL}/api/${targetPath}${request.nextUrl.search}`;

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
      return withCorsHeaders(
        withRotatedCookie(
          NextResponse.json(
            { error: "Invalid request body format or stream interrupted" },
            { status: 400 }
          ),
          rotatedCookieValue
        ),
        request
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
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json({ error: "Backend unavailable" }, { status: 502 }),
        rotatedCookieValue
      ),
      request
    );
  }

  logger.info(`[BFF] ${request.method} ${targetUrl} → ${response.status}`);

  if (response.status === 401) {
    const txt = await response.text();
    logger.error(`[BFF] Backend returned 401 for ${targetUrl}: ${txt}`);
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json({ error: "Unauthorized from backend", detail: txt }, { status: 401 }),
        rotatedCookieValue
      ),
      request
    );
  }

  // Proxy status code và response body nguyên vẹn
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const data = await response.json().catch(() => null);
    return withCorsHeaders(
      withRotatedCookie(
        NextResponse.json(data, { status: response.status }),
        rotatedCookieValue
      ),
      request
    );
  }

  // Non-JSON response (ví dụ: file download)
  const blob = await response.blob();
  return withCorsHeaders(
    withRotatedCookie(
      new NextResponse(blob, {
        status: response.status,
        headers: { "Content-Type": contentType },
      }),
      rotatedCookieValue
    ),
    request
  );
}

export const GET = proxyHandler;
export const POST = proxyHandler;
export const PUT = proxyHandler;
export const PATCH = proxyHandler;
export const DELETE = proxyHandler;
export const HEAD = proxyHandler;
