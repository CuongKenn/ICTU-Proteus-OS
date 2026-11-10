// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Axios API Client — Gọi BFF Proxy (không gọi Backend trực tiếp)
// Tất cả request đi qua /api/proxy/* (Next.js BFF route).
// Tham chiếu: docs/architecture.md (BFF Pattern)

import axios from "axios";

/**
 * Trích xuất thông báo lỗi an toàn từ response hoặc error object (đặc biệt là lỗi HTTP 422 của FastAPI).
 * Tránh lỗi React invariant: "Objects are not valid as a React child" (#746).
 */
export function extractErrorMessage(err: unknown, fallback: string = "Đã xảy ra lỗi không xác định."): string {
  if (!err) return fallback;

  if (typeof err === "string") return err;

  // Trường hợp Axios error: err.response?.data hoặc object mang data
  const data = (err as any)?.response?.data ?? (err as any)?.data ?? err;

  if (typeof data === "string") {
    // Tránh trả về HTML nguyên khối nếu lỡ nhận được trang HTML (#746)
    if (data.trim().startsWith("<!DOCTYPE html") || data.includes("<html")) {
      return "Phiên làm việc đã hết hạn hoặc không có quyền truy cập.";
    }
    return data;
  }

  // Nếu data là mảng (ví dụ mảng lỗi validation trực tiếp)
  if (Array.isArray(data)) {
    const messages = data
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          return item.msg || item.message || JSON.stringify(item);
        }
        return String(item);
      })
      .filter(Boolean);
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  // FastAPI validation error: {"detail": [...]} hoặc detail là chuỗi/object, hoặc msg/message/error
  const detail = data?.detail ?? data?.message ?? data?.msg ?? data?.error;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    // detail là mảng validation errors từ Pydantic: [{ loc: [...], msg: "...", type: "..." }]
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          return item.msg || item.message || JSON.stringify(item);
        }
        return String(item);
      })
      .filter(Boolean);
    if (messages.length > 0) {
      return messages.join("; ");
    }
  } else if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  // Trường hợp err là Error thông thường
  if ((err as any)?.message && typeof (err as any).message === "string") {
    return (err as any).message;
  }

  return fallback;
}

const api = axios.create({
  baseURL: "/api/proxy", // BFF Proxy — không dùng BACKEND_URL trực tiếp
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30_000,
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

async function handleAuthFailure(err: any) {
  processQueue(err, null);
  // Bắt buộc đăng xuất và chuyển hướng đến trang login thông báo hết hạn
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    const { signOut } = await import("next-auth/react");
    await signOut({ callbackUrl: "/login?expired=true" });
  }
}

async function handle401Retry(originalRequest: any) {
  if (isRefreshing) {
    return new Promise(function (resolve, reject) {
      failedQueue.push({ resolve, reject });
    })
      .then(() => {
        return api(originalRequest);
      })
      .catch((err) => {
        return Promise.reject(err);
      });
  }

  originalRequest._retry = true;
  isRefreshing = true;

  try {
    const { getSession } = await import("next-auth/react");
    const session = await getSession();

    if (!session || (session as any).error === "RefreshAccessTokenError") {
      throw new Error("Refresh token expired or no session");
    }

    processQueue(null, "Success");
    return api(originalRequest);
  } catch (err) {
    await handleAuthFailure(err);
    return Promise.reject(err);
  } finally {
    isRefreshing = false;
  }
}

// Response interceptor — xử lý token refresh và lỗi global
api.interceptors.response.use(
  async (response) => {
    // Phòng vệ: Nếu BFF trả về HTML (do redirect 307 tới /login khi cookie session hết hạn) (#746)
    if (
      typeof response.data === "string" &&
      (response.data.trim().startsWith("<!DOCTYPE html") || response.data.includes("<html"))
    ) {
      const originalRequest = response.config;
      if (originalRequest && !(originalRequest as any)._retry) {
        return handle401Retry(originalRequest);
      }
      const error: any = new Error("Session expired (HTML received)");
      error.response = { status: 401, data: { detail: "Session expired" } };
      await handleAuthFailure(error);
      return Promise.reject(error);
    }
    return response;
  },
  async (error) => {
    const originalRequest = error?.config;

    // Nếu BFF trả về 401 (AccessTokenExpired hoặc token hết hạn)
    if (error?.response?.status === 401) {
      if (originalRequest && !originalRequest._retry) {
        return handle401Retry(originalRequest);
      }
      await handleAuthFailure(error);
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

export default api;
