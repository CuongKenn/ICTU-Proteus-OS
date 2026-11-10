// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, it } from "vitest";
import { authOptions } from "./authOptions";
import {
  isSecureCookies,
  sessionCookieDomain,
  sessionCookieName,
  SESSION_MAX_AGE,
} from "./sessionCookie";

describe("authOptions callbacks", () => {
  it("session callback never exposes accessToken (#685)", async () => {
    const sessionCallback = authOptions.callbacks?.session;
    expect(sessionCallback).toBeDefined();

    const mockSession = {
      user: { name: "Test User", email: "test@example.com" },
      expires: "2026-12-31T23:59:59Z",
    };
    const mockToken = {
      accessToken: "secret-bearer-token-keycloak",
      roles: ["admin"],
    };

    const result = await sessionCallback!({
      session: mockSession as any,
      token: mockToken as any,
      user: {} as any,
      newSession: {} as any,
      trigger: "update",
    });

    expect((result as any).accessToken).toBeUndefined();
    expect((result as any).user?.roles).toEqual(["admin"]);
  });

  it("configures sessionToken cookie matching sessionCookie helpers (#730)", () => {
    const sessionTokenCookie = authOptions.cookies?.sessionToken;
    expect(sessionTokenCookie).toBeDefined();
    expect(sessionTokenCookie?.name).toBe(sessionCookieName());
    expect(sessionTokenCookie?.options?.httpOnly).toBe(true);
    expect(sessionTokenCookie?.options?.sameSite).toBe("lax");
    expect(sessionTokenCookie?.options?.path).toBe("/");
    expect(sessionTokenCookie?.options?.secure).toBe(isSecureCookies());
    expect(sessionTokenCookie?.options?.domain).toBe(sessionCookieDomain());
    expect(sessionTokenCookie?.options?.maxAge).toBe(SESSION_MAX_AGE);
  });
});
