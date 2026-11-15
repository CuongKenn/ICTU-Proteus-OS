// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { NextRequest, NextResponse } from "next/server";
import { publicBaseUrl } from "@/lib/sessionCookie";
import { readSessionToken } from "@/lib/sessionJwt";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const token = await readSessionToken(req);
    if (!token) {
      return NextResponse.json({ url: "/login" });
    }

    const idToken = token.idToken as string;
    if (!idToken) {
      return NextResponse.json({ url: "/login" });
    }

    const issuerUrl = process.env.KEYCLOAK_ISSUER;
    if (!issuerUrl) {
      logger.warn("Missing KEYCLOAK_ISSUER for federated logout");
      return NextResponse.json({ url: "/login" });
    }

    const publicBase = publicBaseUrl(req).replace(/\/+$/, "");
    const postLogoutRedirectUri = `${publicBase}/login`;
    const logoutUrl = `${issuerUrl}/protocol/openid-connect/logout?id_token_hint=${encodeURIComponent(
      idToken
    )}&post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUri)}`;

    return NextResponse.json({ url: logoutUrl });
  } catch (error) {
    logger.error("Federated logout error:", error);
    return NextResponse.json({ url: "/login" });
  }
}
