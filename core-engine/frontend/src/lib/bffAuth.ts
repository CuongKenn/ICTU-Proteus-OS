// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// BFF Authentication Helper — Single source of truth cho xác thực & inline token refresh
// Dùng chung cho: /api/proxy/[...path], /api/ai/chat/stream, /api/ai/command, /api/embed/metabase

import { encode, getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";
import { refreshAccessToken } from "@/lib/tokenRefresh";
import { logger } from "@/lib/logger";
import { SESSION_MAX_AGE } from "@/lib/sessionCookie";

export interface BffAuthSuccess {
  success: true;
  accessToken: string;
  rotatedCookieValue: string | null;
}

export interface BffAuthFailure {
  success: false;
  response: NextResponse;
}

export type BffAuthResult = BffAuthSuccess | BffAuthFailure;

export async function getBffAuth(request: NextRequest): Promise<BffAuthResult> {
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });

  if (!token?.accessToken) {
    logger.error("[BFF] 401: no session token or accessToken found");
    return {
      success: false,
      response: NextResponse.json(
        { error: "Unauthorized", message: "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại." },
        { status: 401 }
      ),
    };
  }

  let accessToken = token.accessToken as string;
  let rotatedCookieValue: string | null = null;
  const expires = token.accessTokenExpires as number | undefined;

  if (expires && Date.now() > expires - 10_000) {
    logger.info("[BFF] access_token sắp/đã hết hạn — thử refresh inline");
    try {
      const refreshed = await refreshAccessToken(token as Parameters<typeof refreshAccessToken>[0]);
      if (refreshed.error) {
        logger.error("[BFF] Refresh token thất bại:", refreshed.error);
        return {
          success: false,
          response: NextResponse.json(
            { error: "AccessTokenExpired", message: "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại." },
            { status: 401 }
          ),
        };
      }
      accessToken = refreshed.accessToken as string;
      logger.info("[BFF] Refresh token thành công");

      try {
        rotatedCookieValue = await encode({
          token: refreshed,
          secret: process.env.NEXTAUTH_SECRET ?? "default-secret",
          maxAge: SESSION_MAX_AGE,
        });
      } catch (encodeErr) {
        logger.error("[BFF] Lỗi encode session cookie sau refresh:", encodeErr);
      }
    } catch (err) {
      logger.error("[BFF] Lỗi khi refresh token:", err);
      return {
        success: false,
        response: NextResponse.json(
          { error: "AccessTokenExpired", message: "Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại." },
          { status: 401 }
        ),
      };
    }
  }

  return {
    success: true,
    accessToken,
    rotatedCookieValue,
  };
}
