// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import { useSession } from "@/hooks/useSession";
import { HasuraLiveClient } from "@/lib/hasuraLiveClient";
import {
  HASURA_ENTITY_SUBSCRIPTION,
  useDigitalTwinLive,
} from "./useDigitalTwinLive";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
  },
  extractErrorMessage: (_err: unknown, fallback: string) => fallback,
}));

vi.mock("@/hooks/useSession");

describe("useDigitalTwinLive (#881)", () => {
  const originalEnv = process.env.NEXT_PUBLIC_HASURA_WS_URL;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_HASURA_WS_URL = "";
    (useSession as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      user: { tenant_id: "11111111-1111-4111-8111-111111111111" },
      status: "authenticated",
    });
  });

  afterEach(() => {
    process.env.NEXT_PUBLIC_HASURA_WS_URL = originalEnv;
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("omits restricted tenant_id column and filter from HASURA_ENTITY_SUBSCRIPTION for role:user", () => {
    expect(HASURA_ENTITY_SUBSCRIPTION).not.toContain("tenant_id");
    expect(HASURA_ENTITY_SUBSCRIPTION).toContain("context_entity_state");
    expect(HASURA_ENTITY_SUBSCRIPTION).toContain("entity_id");
    expect(HASURA_ENTITY_SUBSCRIPTION).toContain("payload");
  });

  it("reads entities from backend { entities: [...] } payload shape (#881)", async () => {
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        tenant_id: "11111111-1111-4111-8111-111111111111",
        source: "context.entity_state",
        center: [105.8058, 21.5858],
        total: 1,
        entities: [
          {
            entity_id:
              "urn:ngsi-ld:Room:11111111-1111-4111-8111-111111111111:C1-202",
            type: "Room",
            tenant_id: "11111111-1111-4111-8111-111111111111",
            coordinates: [105.8058, 21.5858],
            payload: {
              name: { type: "Property", value: "Phòng C1-202" },
              status: { type: "Property", value: "occupied" },
            },
            updated_at: "2026-11-25T12:00:00Z",
          },
        ],
      },
    });

    const { result } = renderHook(() => useDigitalTwinLive());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.entities).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.entities[0].type).toBe("Room");
    expect(result.current.entities[0].status_indicator).toBe("busy");
  });

  it("tears down WS and resumes 4s live_poll immediately when Hasura subscription emits error (#881)", async () => {
    vi.useFakeTimers();
    process.env.NEXT_PUBLIC_HASURA_WS_URL = "ws://localhost:8080/v1/graphql";

    const mockGet = vi.fn().mockResolvedValue({
      data: {
        source: "context.entity_state",
        total: 1,
        entities: [
          {
            entity_id:
              "urn:ngsi-ld:Room:11111111-1111-4111-8111-111111111111:C1-202",
            type: "Room",
            payload: {},
          },
        ],
      },
    });
    (api.get as unknown as ReturnType<typeof vi.fn>) = mockGet;

    let capturedOnStatusChange:
      | ((st: "connected" | "reconnecting" | "closed") => void)
      | undefined;
    let capturedOnError: ((err: unknown) => void) | undefined;
    const unsubscribeSpy = vi.fn();
    const disposeSpy = vi
      .spyOn(HasuraLiveClient.prototype, "dispose")
      .mockImplementation(() => {
        capturedOnStatusChange?.("closed");
      });

    vi.spyOn(HasuraLiveClient.prototype, "subscribe").mockImplementation(
      function (this: HasuraLiveClient, opts) {
        // Capture callbacks via instance options & subscribe options
        const internal = this as unknown as {
          onStatusChange?: (st: "connected" | "reconnecting" | "closed") => void;
        };
        capturedOnStatusChange = internal.onStatusChange;
        capturedOnError = opts.onError;
        return unsubscribeSpy;
      }
    );

    const { result } = renderHook(() => useDigitalTwinLive());

    await act(async () => {
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(1);

    // Hasura sends connection_ack -> status connected
    act(() => {
      capturedOnStatusChange?.("connected");
    });
    expect(result.current.connectionMode).toBe("hasura_ws");

    // Hasura rejects anonymous/unpermitted subscription -> emits error frame
    act(() => {
      capturedOnError?.([{ message: "field 'context_entity_state' not found" }]);
    });

    expect(result.current.connectionMode).toBe("live_poll");
    expect(unsubscribeSpy).toHaveBeenCalledTimes(1);
    expect(disposeSpy).toHaveBeenCalled();

    // Advance 4s -> live polling is NOT deadlocked and fetches fresh snapshot
    await act(async () => {
      vi.advanceTimersByTime(4_000);
      await Promise.resolve();
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
