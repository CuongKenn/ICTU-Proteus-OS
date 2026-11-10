// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// BFF API Route — POST /api/ai/chat/stream
// Pipe SSE từ FastAPI POST /api/v1/ai/chat/stream về browser.
// Auth + refresh inline giống /api/ai/command (token không bao giờ xuống browser).

import { NextRequest } from "next/server";
import { getBffAuth } from "@/lib/bffAuth";
import { withRotatedCookie } from "@/lib/sessionCookie";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest): Promise<Response> {
  const auth = await getBffAuth(request);
  if (!auth.success) {
    return auth.response;
  }

  const { accessToken, rotatedCookieValue } = auth;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "Bad Request", message: "Request body không hợp lệ." },
      { status: 400 }
    );
  }

  const bodyAny = body as any;
  const backendPayload = {
    session_id: (bodyAny.session_id && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(bodyAny.session_id))
                ? bodyAny.session_id
                : crypto.randomUUID(),
    natural_language_input: bodyAny.natural_language_input || ""
  };

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/api/v1/ai/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify(backendPayload),
      signal: AbortSignal.timeout(180_000),
    });
  } catch (err) {
    if (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) {
      return Response.json(
        { error: "Gateway Timeout", message: "AI Service mất quá nhiều thời gian phản hồi." },
        { status: 504 }
      );
    }
    return Response.json(
      { error: "Service Unavailable", message: "Không thể kết nối tới AI Service." },
      { status: 503 }
    );
  }

  if (!upstream.ok || !upstream.body) {
    let text = "";
    try {
      text = await upstream.text();
    } catch {
      text = "";
    }
    return Response.json(
      { error: "Upstream Error", message: text || "Backend trả về response không hợp lệ." },
      { status: upstream.status || 502 }
    );
  }

  // Pipe nguyên stream SSE về browser (không buffer).
  const streamRes = new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });

  return withRotatedCookie(streamRes, rotatedCookieValue);
}

export async function GET(): Promise<Response> {
  return Response.json({ error: "Method Not Allowed" }, { status: 405 });
}
