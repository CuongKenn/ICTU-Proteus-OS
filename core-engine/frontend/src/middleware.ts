// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { withAuth } from "next-auth/middleware";
import { NextRequest, NextResponse } from "next/server";

const authMiddleware = withAuth({
  pages: {
    signIn: "/login",
  },
});

export default function middleware(req: NextRequest) {
  // CORS Preflight requests không mang cookie và không được redirect 307 (#732)
  if (req.method === "OPTIONS") {
    return NextResponse.next();
  }

  // Cho các BFF routes: để route handler tự kiểm tra token & trả JSON 401 thay vì redirect 307 HTML (#732, #746)
  const pathname = req.nextUrl.pathname;
  if (
    pathname.startsWith("/api/proxy/") ||
    pathname.startsWith("/api/ai/") ||
    pathname.startsWith("/api/embed/")
  ) {
    return NextResponse.next();
  }

  return (authMiddleware as any)(req);
}

export const config = {
  matcher: [
    "/((?!$|login|signup|api/auth|api/onboarding|_next/static|_next/image|favicon.ico).*)",
  ],
};
