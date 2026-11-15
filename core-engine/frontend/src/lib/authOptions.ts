// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// NextAuth options — BFF Security Pattern
// Browser KHÔNG bao giờ nhận JWT trực tiếp.
// Token được lưu trong HttpOnly session cookie do Next.js quản lý.
// Tham chiếu: docs/architecture.md (BFF Pattern), docs/clarification.md §8

import type { NextAuthOptions } from "next-auth";
import {
  isSecureCookies,
  sessionCookieDomain,
  sessionCookieName,
  SESSION_MAX_AGE,
} from "./sessionCookie";
import { refreshAccessToken } from "./tokenRefresh";

const publicIssuer = process.env.KEYCLOAK_ISSUER || "";
const realm = publicIssuer.split("/realms/")[1] || "proteus";
const internalBase = process.env.KEYCLOAK_INTERNAL_URL
  ? `${process.env.KEYCLOAK_INTERNAL_URL}/realms/${realm}`
  : publicIssuer;

// ─── NextAuth Config ──────────────────────────────────────────
export const authOptions: NextAuthOptions = {
  debug: process.env.NODE_ENV === "development",
  providers: [
    // Manual OAuth provider — Keycloak luôn trả id_token nên phải dùng idToken:true
    // Dùng wellKnown để NextAuth lấy jwks_uri (cho ID token verification)
    // Tất cả endpoints được hardcode để tránh dependency vào discovery cho routing
    {
      id: "keycloak",
      name: "Keycloak SSO",
      type: "oauth",
      // wellKnown cần để lấy JWKS cho ID token verification
      // Nhưng discovery chỉ xảy ra 1 lần và được cache
      wellKnown: `${internalBase}/.well-known/openid-configuration`,
      // Hardcode authorization endpoint — không phụ thuộc vào discovery cho redirect
      authorization: {
        url: `${publicIssuer}/protocol/openid-connect/auth`,
        params: { scope: "openid email profile", response_type: "code" },
      },
      // Hardcode token và userinfo endpoints
      token: `${internalBase}/protocol/openid-connect/token`,
      userinfo: `${internalBase}/protocol/openid-connect/userinfo`,
      // Thêm issuer để tránh lỗi issuer mismatch
      issuer: publicIssuer,
      // idToken: true — Keycloak luôn trả id_token, phải dùng client.callback()
      idToken: true,
      checks: ["pkce", "state"],
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      profile(profile: any) {
        return {
          id: profile.sub,
          name: profile.name ?? profile.preferred_username,
          email: profile.email,
          image: profile.picture ?? null,
        };
      },
    },
  ],

  callbacks: {
    async signIn() {
      // Allow any user authenticated by Keycloak — role-based access is handled by RBAC middleware
      return true;
    },

    async jwt({ token, account, profile }) {
      // Lần đầu login — lưu access_token, refresh_token và expiry vào JWT session
      if (account) {
        let roles: string[] = [];
        let tenantId = (profile as any)?.tenant_id as string | undefined;

        // Ưu tiên decode access_token để lấy realm_access.roles và tenant_id
        // vì Keycloak đảm bảo realm_access luôn có trong access_token.
        // id_token (profile) chỉ chứa roles nếu đã cấu hình Protocol Mapper riêng.
        if (account.access_token) {
          try {
            const payloadBase64 = account.access_token.split(".")[1];
            const decoded = JSON.parse(
              Buffer.from(payloadBase64, "base64url").toString("utf-8")
            );
            if (decoded?.realm_access?.roles) {
              roles = decoded.realm_access.roles;
            }
            if (decoded?.tenant_id) {
              tenantId = decoded.tenant_id;
            }
          } catch {
            // Fallback: thử lấy từ profile (id_token)
            const kcProfile = profile as any;
            if (kcProfile?.realm_access?.roles) {
              roles = kcProfile.realm_access.roles;
            }
          }
        } else {
          // Fallback: thử lấy từ profile (id_token)
          const kcProfile = profile as any;
          if (kcProfile?.realm_access?.roles) {
            roles = kcProfile.realm_access.roles;
          }
        }

        return {
          ...token,
          accessToken: account.access_token,
          idToken: account.id_token,       // ← BẮT BUỘC cho federated logout
          refreshToken: account.refresh_token,
          accessTokenExpires: account.expires_at
            ? account.expires_at * 1000
            : Date.now() + 60 * 60 * 1000, // Fallback: 1 giờ
          roles,
          tenant_id: tenantId,
        };
      }

      // Token vẫn còn hạn (thêm buffer 30s để tránh edge case)
      if (Date.now() < (token.accessTokenExpires as number) - 30_000) {
        return token;
      }

      // Token sắp/đã hết hạn → Silent refresh
      return refreshAccessToken(token);
    },

    async session({ session, token }) {
      // KHÔNG expose access token vào session (#685).
      // NextAuth serialize session về client qua /api/auth/session nên token không được nằm ở đây.
      // Các BFF routes lấy accessToken qua getToken({ req }) ở server-side.
      session.user.roles = (token.roles as string[]) ?? [];
      if (token.tenant_id) {
        (session.user as any).tenant_id = token.tenant_id;
      }
      if (token.sub) {
        (session.user as any).id = token.sub;
      }

      // Truyền lỗi refresh lên client để hiển thị thông báo (vd: RefreshAccessTokenError)
      if (token.error) {
        (session as any).error = token.error;
      }

      return session;
    },
  },

  cookies: {
    sessionToken: {
      name: sessionCookieName(),
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: isSecureCookies(),
        domain: sessionCookieDomain(),
        maxAge: SESSION_MAX_AGE,
      },
    },
  },

  session: {
    strategy: "jwt",
    maxAge: SESSION_MAX_AGE, // 8 giờ (session tối đa, kể cả refresh)
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },
};
