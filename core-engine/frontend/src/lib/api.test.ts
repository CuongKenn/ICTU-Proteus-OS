// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, it, expect } from "vitest";
import { extractErrorMessage } from "./api";

describe("extractErrorMessage helper (#746)", () => {
  it("returns fallback when input is null or undefined", () => {
    expect(extractErrorMessage(null)).toBe("Đã xảy ra lỗi không xác định.");
    expect(extractErrorMessage(undefined, "Custom fallback")).toBe("Custom fallback");
  });

  it("returns plain string when string is passed", () => {
    expect(extractErrorMessage("Lỗi kết nối")).toBe("Lỗi kết nối");
  });

  it("extracts message from standard JavaScript Error", () => {
    const err = new Error("Something broke");
    expect(extractErrorMessage(err)).toBe("Something broke");
  });

  it("extracts message from FastAPI 422 validation error array", () => {
    const fastapi422Error = {
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ["body", "admin_password"],
              msg: "Mật khẩu phải có ít nhất 1 chữ hoa.",
              type: "value_error",
            },
            {
              loc: ["body", "admin_password"],
              msg: "Mật khẩu phải có ít nhất 1 chữ số.",
              type: "value_error",
            },
          ],
        },
      },
    };

    const result = extractErrorMessage(fastapi422Error);
    expect(result).toBe("Mật khẩu phải có ít nhất 1 chữ hoa.; Mật khẩu phải có ít nhất 1 chữ số.");
    expect(typeof result).toBe("string");
  });

  it("handles FastAPI detail as string", () => {
    const error = {
      response: {
        data: {
          detail: "Tenant already exists",
        },
      },
    };
    expect(extractErrorMessage(error)).toBe("Tenant already exists");
  });

  it("handles detail as object by stringifying it", () => {
    const error = {
      response: {
        data: {
          detail: { code: "ERR_CONFLICT", reason: "Name taken" },
        },
      },
    };
    const result = extractErrorMessage(error);
    expect(result).toContain("ERR_CONFLICT");
    expect(typeof result).toBe("string");
  });

  it("sanitizes HTML string responses to prevent HTML leakage into UI", () => {
    const htmlResponse = {
      response: {
        data: "<!DOCTYPE html><html><head><title>Login</title></head><body>Login Page</body></html>",
      },
    };
    const result = extractErrorMessage(htmlResponse);
    expect(result).toBe("Phiên làm việc đã hết hạn hoặc không có quyền truy cập.");
  });

  it("handles error format with error property", () => {
    const error = {
      response: {
        data: {
          error: "Unauthorized access",
        },
      },
    };
    expect(extractErrorMessage(error)).toBe("Unauthorized access");
  });
});
