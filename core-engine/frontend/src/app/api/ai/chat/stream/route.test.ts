// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { POST, GET } from "./route";

vi.mock("next-auth/jwt", () => ({
  getToken: vi.fn(),
  encode: vi.fn().mockResolvedValue("mocked-stream-rotated-session-token"),
}));

vi.mock("@/lib/tokenRefresh", () => ({
  refreshAccessToken: vi.fn(),
}));

import { getToken } from "next-auth/jwt";
import { refreshAccessToken } from "@/lib/tokenRefresh";
import { sessionCookieName } from "@/lib/sessionCookie";

describe("AI Chat Stream BFF Route Handler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 405 on GET request", async () => {
    const res = await GET();
    expect(res.status).toBe(405);
  });

  it("returns 401 when no token is present", async () => {
    vi.mocked(getToken).mockResolvedValue(null);
    const req = new NextRequest("http://localhost:3000/api/ai/chat/stream", {
      method: "POST",
      body: JSON.stringify({ natural_language_input: "hello" }),
    });

    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("pipes stream and persists rotated token cookie when token is expiring", async () => {
    vi.mocked(getToken).mockResolvedValue({
      sub: "user-stream",
      accessToken: "old-stream-token",
      accessTokenExpires: Date.now() + 2_000,
    } as any);

    vi.mocked(refreshAccessToken).mockResolvedValue({
      sub: "user-stream",
      accessToken: "new-stream-token",
      accessTokenExpires: Date.now() + 60_000,
    } as any);

    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: {\"chunk\": \"hi\"}\n\n"));
        controller.close();
      },
    });

    const mockFetch = vi.fn().mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      })
    );
    global.fetch = mockFetch;

    const req = new NextRequest("http://localhost:3000/api/ai/chat/stream", {
      method: "POST",
      body: JSON.stringify({
        session_id: "11111111-2222-3333-4444-555555555555",
        natural_language_input: "ping",
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/ai/chat/stream",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer new-stream-token",
        }),
      })
    );

    // Verify Set-Cookie header is persisted with rotated token (#730)
    const setCookie = res.headers.get("Set-Cookie");
    expect(setCookie).toBeDefined();
    expect(setCookie).toContain(`${sessionCookieName()}=mocked-stream-rotated-session-token`);
  });
});
