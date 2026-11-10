// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// BFF API Route — POST /api/ai/command
// Nhận lệnh ngôn ngữ tự nhiên từ AIChatWidget → forward tới FastAPI AI Orchestrator.
// BFF inject JWT Token từ HttpOnly Cookie (Browser KHÔNG bao giờ gọi FastAPI trực tiếp).
//
// Luồng xử lý:
//   1. Validate session (Keycloak JWT)
//   2. Forward request tới POST /api/v1/ai/command (FastAPI)
//   3. FastAPI trả về AICommandResponse:
//      - effect=read  → status=completed, result=<kết quả>
//      - effect=write → status=pending_approval, dsl_preview=<DSL JSON>
//
// Tham chiếu:
//   - docs/architecture.md §2.1 (BFF Pattern)
//   - docs/architecture.md §2.3 (AI Orchestrator & DX-DSL)
//   - docs/dsl-spec.md §4 (Effect Levels)
//   - docs/api-swagger.yaml POST /ai/command

import { NextRequest, NextResponse } from "next/server";
import { getBffAuth } from "@/lib/bffAuth";
import { withRotatedCookie } from "@/lib/sessionCookie";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest): Promise<NextResponse> {
  // 1. Xác thực session — Token được đọc từ HttpOnly Cookie phía server & tự động refresh inline
  const auth = await getBffAuth(request);
  if (!auth.success) {
    return auth.response;
  }

  const { accessToken, rotatedCookieValue } = auth;

  let body: any;
  try {
    body = await request.json();
  } catch {
    return withRotatedCookie(
      NextResponse.json(
        { error: "Bad Request", message: "Request body không hợp lệ." },
        { status: 400 }
      ),
      rotatedCookieValue
    );
  }

  const isNaturalLanguage = typeof body?.natural_language_input === "string" && !body?.action;
  if (isNaturalLanguage && (!body?.session_id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(body.session_id))) {
    body = { ...body, session_id: crypto.randomUUID() };
  }

  const targetUrl = isNaturalLanguage
    ? `${BACKEND_URL}/api/v1/ai/chat`
    : `${BACKEND_URL}/api/v1/ai/command`;

  try {
    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // BFF inject Bearer Token — browser không biết token này
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      // Timeout 30s cho AI inference
      signal: AbortSignal.timeout(30_000),
    });

    const contentType = backendResponse.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const data = await backendResponse.json();
      if (data && typeof data === "object") {
        // Chuẩn hóa status enum sang lowercase cho Frontend
        const rawStatus = String(data.status || "");
        data.status = rawStatus.toLowerCase();
        if (data.status === "pending_approval" && !data.dsl_preview && data.result) {
          data.dsl_preview = data.result;
        }
      }
      return withRotatedCookie(
        NextResponse.json(data, { status: backendResponse.status }),
        rotatedCookieValue
      );
    }

    // Trường hợp Backend trả non-JSON (unexpected)
    return withRotatedCookie(
      NextResponse.json(
        { error: "Upstream Error", message: "Backend trả về response không hợp lệ." },
        { status: 502 }
      ),
      rotatedCookieValue
    );
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") {
      return withRotatedCookie(
        NextResponse.json(
          { error: "Gateway Timeout", message: "AI Service mất quá nhiều thời gian phản hồi." },
          { status: 504 }
        ),
        rotatedCookieValue
      );
    }

    // Không thể kết nối tới Backend (network error, Backend down)
    return withRotatedCookie(
      NextResponse.json(
        { error: "Service Unavailable", message: "Không thể kết nối tới AI Service." },
        { status: 503 }
      ),
      rotatedCookieValue
    );
  }
}
