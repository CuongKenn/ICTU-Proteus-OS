// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// BFF API Route — Metabase Embed URL
// Lấy Signed URL từ Backend Python hoặc giả lập (mock) nếu Backend chưa sẵn sàng.

import { NextRequest, NextResponse } from "next/server";
import { getBffAuth } from "@/lib/bffAuth";
import { withRotatedCookie } from "@/lib/sessionCookie";
import { logger } from "@/lib/logger";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// Helper function giải mã Payload của JWT mà không cần thư viện
function decodeJwtPayload(token: string) {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    return null;
  }
}

export async function GET(request: NextRequest) {
  // 1. Xác thực session từ HttpOnly Cookie với inline auto refresh
  const auth = await getBffAuth(request);
  if (!auth.success) {
    return auth.response;
  }

  const { accessToken, rotatedCookieValue } = auth;

  // 2. Trích xuất dashboard_id từ Query Parameters & chặn SSRF / Path Traversal (#734)
  const dashboardId =
    request.nextUrl.searchParams.get("dashboard_id") ||
    request.nextUrl.searchParams.get("dashboardId");
  if (!dashboardId) {
    return withRotatedCookie(
      NextResponse.json(
        { error: "Thiếu tham số dashboard_id" },
        { status: 400 }
      ),
      rotatedCookieValue
    );
  }
  if (!/^\d+$/.test(dashboardId)) {
    return withRotatedCookie(
      NextResponse.json(
        { error: "dashboard_id không hợp lệ (phải là số nguyên dương)" },
        { status: 400 }
      ),
      rotatedCookieValue
    );
  }

  // 3. Giải mã accessToken (Keycloak JWT) để lấy tenant_id
  const payload = decodeJwtPayload(accessToken);
  const tenantId = payload?.tenant_id || payload?.groups?.[0] || "unknown_tenant";

  try {
    // 4. Gọi Python Backend API để lấy Signed URL
    const targetUrl = `${BACKEND_URL}/api/v1/embed/metabase/${dashboardId}`;
    const response = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();
      return withRotatedCookie(NextResponse.json(data), rotatedCookieValue);
    }
    
    // Nếu Backend trả về lỗi (có thể do chưa implement), throw để chuyển sang luồng Mock
    throw new Error(`Backend error: ${response.status}`);
  } catch (error) {
    // 5. MOCK: Khi Python Backend chưa có API này hoặc đang sập
    if (process.env.NODE_ENV === "development") {
      logger.warn("[Metabase BFF] Backend chưa sẵn sàng, trả về MOCK Signed URL.");
      
      const mockMetabaseUrl = process.env.METABASE_URL || "http://localhost:3000";
      // Giả lập 1 chuỗi token ngẫu nhiên
      const mockToken = Buffer.from(`mock_token_${tenantId}_${dashboardId}_${Date.now()}`).toString("base64");
      
      return withRotatedCookie(
        NextResponse.json({
          url: `${mockMetabaseUrl}/embed/dashboard/${mockToken}#bordered=true&titled=false`,
        }),
        rotatedCookieValue
      );
    }

    // Trên production không trả về mock
    return withRotatedCookie(
      NextResponse.json(
        { error: "Không thể kết nối đến hệ thống báo cáo (Backend Error)" },
        { status: 500 }
      ),
      rotatedCookieValue
    );
  }
}
