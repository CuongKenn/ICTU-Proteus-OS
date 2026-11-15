// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Session cookie helpers — single source of truth cho tên/domain cookie.
// Dùng chung giữa authOptions (lúc sign-in) và BFF proxy (lúc persist token
// sau inline refresh). Lệch nhau là browser gửi cookie mà server không đọc.

import { NextRequest, NextResponse } from "next/server";

export const SESSION_MAX_AGE = 8 * 60 * 60; // 8 giờ, khớp session.maxAge

// Đổi tên cookie (+.v2) để bỏ lại phía sau các cookie rác của bản cũ: trước đây
// BFF ghi 1 cookie đơn >4KB (browser bỏ qua) và lệch domain host-only/.nttspace.online
// với NextAuth → session hỏng, refresh_token bị reuse. Tên mới tách hẳn khỏi các
// chunk cũ (.0/.1) nên không bị SessionStore ghép nhầm. User login lại 1 lần.
const SESSION_COOKIE_BASE = "next-auth.session-token.v2";

export function isSecureCookies(): boolean {
  return (process.env.NEXTAUTH_URL ?? "").startsWith("https://");
}

export function sessionCookieName(): string {
  return isSecureCookies()
    ? `__Secure-${SESSION_COOKIE_BASE}`
    : SESSION_COOKIE_BASE;
}

/**
 * Domain chia sẻ *.proteus.local; localhost dev giữ host-only.
 * LƯU Ý: hiện KHÔNG dùng domain cho session cookie (host-only) để tránh trùng
 * tên cookie giữa domain và host-only khiến SessionStore ghép nhầm. MFE đã
 * chuyển sang same-origin (/plugins-mfe) nên host-only là đủ.
 */
export function sessionCookieDomain(): string | undefined {
  try {
    const host = new URL(process.env.NEXTAUTH_URL ?? "").hostname;
    if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
      return undefined;
    }
    const parts = host.split(".");
    if (parts.length < 2) return undefined;
    return "." + parts.slice(-2).join(".");
  } catch {
    return undefined;
  }
}

const CHUNK_SIZE = 4096 - 163;

/** Gắn cookie session mới sau khi xoay vòng token cho cả NextResponse và Response thường (có chia chunk >4KB) */
export function withRotatedCookie<T extends Response | NextResponse>(
  res: T,
  rotatedCookieValue: string | null,
  req?: NextRequest
): T {
  if (rotatedCookieValue) {
    const baseName = sessionCookieName();
    const domain = sessionCookieDomain();
    const chunkCount = Math.max(1, Math.ceil(rotatedCookieValue.length / CHUNK_SIZE));
    const entries: Array<[string, string]> = [];
    if (chunkCount === 1) {
      entries.push([baseName, rotatedCookieValue]);
    } else {
      for (let i = 0; i < chunkCount; i++) {
        entries.push([`${baseName}.${i}`, rotatedCookieValue.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE)]);
      }
    }

    const activeNames = new Set(entries.map(([name]) => name));
    const expireCookie = (cookieName: string) => {
      if ("cookies" in res && typeof (res as any).cookies?.set === "function") {
        const opts: any = {
          name: cookieName,
          value: "",
          httpOnly: true,
          secure: isSecureCookies(),
          sameSite: "lax",
          path: "/",
          maxAge: 0,
        };
        if (domain) opts.domain = domain;
        (res as NextResponse).cookies.set(opts);
      } else {
        const parts = [
          `${cookieName}=`,
          `Path=/`,
          `Max-Age=0`,
          `SameSite=Lax`,
          `HttpOnly`,
        ];
        if (isSecureCookies()) parts.push("Secure");
        if (domain) parts.push(`Domain=${domain}`);
        res.headers.append("Set-Cookie", parts.join("; "));
      }
    };

    if (req) {
      for (const c of req.cookies.getAll()) {
        if ((c.name === baseName || c.name.startsWith(`${baseName}.`)) && !activeNames.has(c.name)) {
          expireCookie(c.name);
        }
      }
    }

    for (const [cookieName, cookieVal] of entries) {
      if ("cookies" in res && typeof (res as any).cookies?.set === "function") {
        const cookieOptions: any = {
          name: cookieName,
          value: cookieVal,
          httpOnly: true,
          secure: isSecureCookies(),
          sameSite: "lax",
          path: "/",
          maxAge: SESSION_MAX_AGE,
        };
        if (domain) {
          cookieOptions.domain = domain;
        }
        (res as NextResponse).cookies.set(cookieOptions);
      } else {
        const parts = [
          `${cookieName}=${cookieVal}`,
          `Path=/`,
          `Max-Age=${SESSION_MAX_AGE}`,
          `SameSite=Lax`,
          `HttpOnly`,
        ];
        if (isSecureCookies()) parts.push("Secure");
        if (domain) parts.push(`Domain=${domain}`);
        res.headers.append("Set-Cookie", parts.join("; "));
      }
    }
  }
  return res;
}

/**
 * Base URL public mà browser thấy (https://proteus.local).
 * Chạy sau Traefik nên req.url chứa hostname container — phải đọc
 * X-Forwarded-Host do Traefik gắn, fallback NEXTAUTH_URL.
 */
export function publicBaseUrl(req: {
  url: string;
  headers: { get(name: string): string | null };
}): string {
  const forwardedHost = req.headers
    .get("x-forwarded-host")
    ?.split(",")[0]
    .trim();
  if (forwardedHost) {
    const proto =
      req.headers.get("x-forwarded-proto")?.split(",")[0].trim() || "http";
    return `${proto}://${forwardedHost}`;
  }
  if (process.env.NEXTAUTH_URL) return process.env.NEXTAUTH_URL;
  return new URL(req.url).origin;
}
