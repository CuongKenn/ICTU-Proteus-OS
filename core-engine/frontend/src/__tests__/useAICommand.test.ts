// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAICommand, uuid } from "@/hooks/useAICommand";

vi.mock("@/store/notificationStore", () => ({
  useNotificationStore: () => ({
    addToast: vi.fn(),
  }),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("useAICommand", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    mockFetch.mockReset();
  });

  it("should initialize with default state and valid UUID sessionId", () => {
    const { result } = renderHook(() => useAICommand());

    expect(result.current.widgetState).toBe("collapsed");
    expect(result.current.messages.length).toBe(1);
    expect(result.current.messages[0].role).toBe("assistant");
    expect(result.current.inputValue).toBe("");
    expect(result.current.dslPreview).toBeNull();
    // Validate RFC-4122 UUID v4 format
    expect(result.current.sessionId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );
  });

  it("uuid() helper produces valid RFC-4122 UUID even without crypto.randomUUID", () => {
    const spy = vi.spyOn(crypto, "randomUUID").mockImplementation(() => {
      throw new Error("HTTP context - randomUUID not available");
    });
    try {
      const id = uuid();
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    } finally {
      spy.mockRestore();
    }
  });

  it("should handle widget open/close", () => {
    const { result } = renderHook(() => useAICommand());

    act(() => {
      result.current.openWidget();
    });
    expect(result.current.widgetState).toBe("expanded");

    act(() => {
      result.current.resetAndClose();
    });

    expect(result.current.widgetState).toBe("collapsed");
  });

  it("should process a read command successfully and prioritize message", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "completed",
        message: "Câu trả lời tiếng Việt từ AI",
        result: { plan_total: 1, steps: [] },
      }),
    });

    const { result } = renderHook(() => useAICommand());

    act(() => {
      result.current.setInputValue("Lấy dữ liệu");
    });

    await act(async () => {
      await result.current.sendCommand();
    });

    expect(result.current.widgetState).toBe("expanded");
    expect(result.current.messages[result.current.messages.length - 1].content).toBe(
      "Câu trả lời tiếng Việt từ AI"
    );
    expect(result.current.messages[result.current.messages.length - 1].role).toBe("assistant");
    expect(result.current.inputValue).toBe("");
  });

  it("should process a write command and transition to awaiting_approval", async () => {
    const dsl_preview = {
      command_id: "cmd-1",
      action: "test.action",
      effect: "write",
      approval_message: "Need approval",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "pending_approval",
        dsl_preview,
      }),
    });

    const { result } = renderHook(() => useAICommand());

    act(() => {
      result.current.setInputValue("Duyệt lệnh này");
    });

    await act(async () => {
      await result.current.sendCommand();
    });

    expect(result.current.widgetState).toBe("awaiting_approval");
    expect(result.current.dslPreview).toEqual(dsl_preview);

    // Test cancelApproval calls cancel endpoint on backend
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: "CANCELLED" }) });
    await act(async () => {
      await result.current.cancelApproval();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/proxy/v1/ai/commands/cmd-1/cancel",
      expect.objectContaining({ method: "POST" })
    );
    expect(result.current.dslPreview).toBeNull();
    expect(result.current.widgetState).toBe("expanded");
  });
});
