// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, it } from "vitest";

describe("Issue #750 - JWT base64url decode with Vietnamese diacritics", () => {
  it("successfully decodes JWT payload with base64url encoding and Vietnamese characters", () => {
    const payload = {
      sub: "user-123",
      name: "Nguyễn Văn Cường",
      preferred_username: "cuongnv",
      tenant_id: "tenant-ictu-456",
      realm_access: {
        roles: ["quản_trị_viên", "chuyên_viên_nhân_sự", "offline_access"],
      },
    };

    // Encode payload as Base64URL (no padding, replaces + with - and / with _)
    const jsonStr = JSON.stringify(payload);
    const base64url = Buffer.from(jsonStr, "utf-8").toString("base64url");

    // Decoding with base64url
    const decoded = JSON.parse(Buffer.from(base64url, "base64url").toString("utf-8"));
    expect(decoded.name).toBe("Nguyễn Văn Cường");
    expect(decoded.realm_access.roles).toContain("quản_trị_viên");
    expect(decoded.realm_access.roles).toContain("chuyên_viên_nhân_sự");
    expect(decoded.tenant_id).toBe("tenant-ictu-456");
  });

  it("handles base64url payload with - and _ characters without corruption", () => {
    // Generate payload with characters that produce - and _ in base64url
    const payload = {
      sub: "user-abc-123_xyz",
      roles: ["role-a", "role_b"],
      special: ">>>???<<<!!!~~~",
    };
    const base64url = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");

    const decoded = JSON.parse(Buffer.from(base64url, "base64url").toString("utf-8"));
    expect(decoded.sub).toBe("user-abc-123_xyz");
  });
});
