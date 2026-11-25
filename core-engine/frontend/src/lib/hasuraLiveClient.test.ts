// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  computeBackoffDelayMs,
  GRAPHQL_TRANSPORT_WS_PROTOCOL,
  HasuraClientStatus,
  HasuraLiveClient,
  sanitizeHasuraWsUrl,
} from "./hasuraLiveClient";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  public readonly url: string;
  public readonly protocol: string;
  public readyState = MockWebSocket.CONNECTING;
  public sentFrames: Record<string, any>[] = [];

  public onopen: ((ev: Event) => void) | null = null;
  public onmessage: ((ev: MessageEvent) => void) | null = null;
  public onerror: ((ev: Event) => void) | null = null;
  public onclose: ((ev: CloseEvent) => void) | null = null;

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = String(url);
    this.protocol = Array.isArray(protocols) ? protocols[0] ?? "" : protocols ?? "";
    MockWebSocket.instances.push(this);
  }

  public send(data: string): void {
    this.sentFrames.push(JSON.parse(data));
  }

  public close(code = 1000, reason = ""): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code, reason } as CloseEvent);
  }

  public simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  public simulateServerMessage(payload: Record<string, unknown>): void {
    this.onmessage?.({
      data: JSON.stringify(payload),
    } as MessageEvent);
  }

  public simulateAbnormalClose(code = 1006, reason = "Abnormal Closure"): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code, reason } as CloseEvent);
  }
}

describe("HasuraLiveClient (graphql-transport-ws)", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("strips sensitive query params from URL and completes connection_init -> connection_ack -> subscribe handshake", async () => {
    const statuses: HasuraClientStatus[] = [];
    const client = new HasuraLiveClient({
      url: "wss://hasura.ictu.edu.vn/v1/graphql?token=super-secret-jwt&x-hasura-admin-secret=leak&keep=1",
      tenantId: "tenant-ictu-001",
      authToken: "jwt-session-token",
      webSocketImpl: MockWebSocket as unknown as typeof WebSocket,
      onStatusChange: (st) => statuses.push(st),
    });

    expect(client.getSanitizedUrl()).toBe(
      "wss://hasura.ictu.edu.vn/v1/graphql?keep=1"
    );
    expect(client.getSanitizedUrl()).not.toContain("super-secret-jwt");
    expect(client.getSanitizedUrl()).not.toContain("admin-secret");

    const onNext = vi.fn();
    const unsubscribe = client.subscribe({
      id: "sub_entities",
      query: "subscription WatchEntities($tenant_id: uuid!) { context_entity_state { entity_id } }",
      onNext,
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    const ws = MockWebSocket.instances[0];
    expect(ws.protocol).toBe(GRAPHQL_TRANSPORT_WS_PROTOCOL);

    ws.simulateOpen();
    await Promise.resolve();

    // 1. Kiểm tra gửi connection_init chứa auth payload (không nằm trên URL)
    expect(ws.sentFrames).toHaveLength(1);
    expect(ws.sentFrames[0]).toEqual({
      type: "connection_init",
      payload: {
        headers: {
          Authorization: "Bearer jwt-session-token",
          "X-Hasura-Tenant-Id": "tenant-ictu-001",
        },
        tenant_id: "tenant-ictu-001",
      },
    });

    // 2. Server phản hồi connection_ack -> Client tự động gửi subscribe kèm tenant_id
    ws.simulateServerMessage({ type: "connection_ack" });
    expect(statuses).toContain("connected");
    expect(ws.sentFrames).toHaveLength(2);
    expect(ws.sentFrames[1]).toEqual({
      id: "sub_entities",
      type: "subscribe",
      payload: {
        query:
          "subscription WatchEntities($tenant_id: uuid!) { context_entity_state { entity_id } }",
        variables: {
          tenant_id: "tenant-ictu-001",
        },
      },
    });

    unsubscribe();
  });

  it("delivers `next` payloads isolated by tenant_id and responds to server `ping` with `pong`", async () => {
    const client = new HasuraLiveClient({
      url: "ws://localhost:8080/v1/graphql",
      tenantId: "tenant-alpha",
      webSocketImpl: MockWebSocket as unknown as typeof WebSocket,
    });

    const received: unknown[] = [];
    const unsubscribe = client.subscribe({
      id: "sub_live",
      query: "subscription { context_entity_state { entity_id tenant_id } }",
      onNext: (data) => received.push(data),
    });

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();
    await Promise.resolve();
    ws.simulateServerMessage({ type: "connection_ack" });

    // Server ping -> client pong
    ws.simulateServerMessage({ type: "ping" });
    expect(ws.sentFrames[ws.sentFrames.length - 1]).toEqual({ type: "pong" });

    // Server gửi `next` có trộn thực thể khác tenant -> client lọc sạch chỉ giữ đúng tenant-alpha
    ws.simulateServerMessage({
      id: "sub_live",
      type: "next",
      payload: {
        data: {
          context_entity_state: [
            {
              entity_id: "urn:ngsi-ld:Room:tenant-alpha:C1-202",
              tenant_id: "tenant-alpha",
            },
            {
              entity_id: "urn:ngsi-ld:Room:tenant-other:X9-999",
              tenant_id: "tenant-other",
            },
          ],
        },
      },
    });

    expect(received).toHaveLength(1);
    expect(received[0]).toEqual({
      context_entity_state: [
        {
          entity_id: "urn:ngsi-ld:Room:tenant-alpha:C1-202",
          tenant_id: "tenant-alpha",
        },
      ],
    });

    unsubscribe();
    expect(client.getStatus()).toBe("closed");
  });

  it("reconnects automatically with exponential backoff (1s -> 2s -> 4s -> max 15s) and cleans up on unsubscribe", async () => {
    expect(computeBackoffDelayMs(0)).toBe(1000);
    expect(computeBackoffDelayMs(1)).toBe(2000);
    expect(computeBackoffDelayMs(2)).toBe(4000);
    expect(computeBackoffDelayMs(3)).toBe(8000);
    expect(computeBackoffDelayMs(4)).toBe(15000);
    expect(computeBackoffDelayMs(8)).toBe(15000);

    const statusHistory: Array<{ status: HasuraClientStatus; delayMs?: number }> = [];
    const client = new HasuraLiveClient({
      url: "wss://hasura.ictu.edu.vn/v1/graphql",
      tenantId: "tenant-ictu",
      webSocketImpl: MockWebSocket as unknown as typeof WebSocket,
      onStatusChange: (status, meta) =>
        statusHistory.push({ status, delayMs: meta?.delayMs }),
    });

    const onNext = vi.fn();
    const unsubscribe = client.subscribe({
      id: "sub_1",
      query: "subscription { context_entity_state { entity_id } }",
      onNext,
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    const ws1 = MockWebSocket.instances[0];
    ws1.simulateOpen();
    await Promise.resolve();
    ws1.simulateServerMessage({ type: "connection_ack" });

    // Đóng bất thường lần 1 -> hẹn reconnect sau 1000ms
    ws1.simulateAbnormalClose(1006);
    expect(statusHistory[statusHistory.length - 1]).toEqual({
      status: "reconnecting",
      delayMs: 1000,
    });
    expect(MockWebSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(999);
    expect(MockWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances).toHaveLength(2);

    // Đóng bất thường lần 2 trước khi ack -> hẹn reconnect sau 2000ms
    const ws2 = MockWebSocket.instances[1];
    ws2.simulateAbnormalClose(1006);
    expect(statusHistory[statusHistory.length - 1]).toEqual({
      status: "reconnecting",
      delayMs: 2000,
    });

    vi.advanceTimersByTime(2000);
    expect(MockWebSocket.instances).toHaveLength(3);

    // Kết nối thứ 3 thành công -> reset bộ đếm và nhận dữ liệu tiếp
    const ws3 = MockWebSocket.instances[2];
    ws3.simulateOpen();
    await Promise.resolve();
    ws3.simulateServerMessage({ type: "connection_ack" });
    ws3.simulateServerMessage({
      id: "sub_1",
      type: "next",
      payload: {
        data: {
          context_entity_state: [
            { entity_id: "urn:ngsi-ld:Asset:tenant-ictu:Maxhub-01" },
          ],
        },
      },
    });
    expect(onNext).toHaveBeenCalledTimes(1);

    // Hủy đăng ký -> gửi complete, đóng socket và không bao giờ tự reconnect nữa
    unsubscribe();
    vi.advanceTimersByTime(20_000);
    expect(MockWebSocket.instances).toHaveLength(3);
    expect(client.getStatus()).toBe("closed");
  });

  it("converts http/https schemes gracefully in sanitizeHasuraWsUrl", () => {
    expect(sanitizeHasuraWsUrl("https://live.example.com/v1/graphql?token=abc")).toBe(
      "wss://live.example.com/v1/graphql"
    );
    expect(sanitizeHasuraWsUrl("http://localhost:8080/v1/graphql")).toBe(
      "ws://localhost:8080/v1/graphql"
    );
  });
});
