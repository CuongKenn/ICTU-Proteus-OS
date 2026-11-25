// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Hasura GraphQL Subscription Client — Chuẩn giao thức `graphql-transport-ws` (Issue #849)
// Bảo mật: Không bao giờ truyền token trên URL query; gửi auth & tenant_id qua `connection_init`
// và lọc cô lập dữ liệu theo `tenant_id` ở tầng client (Defense-in-depth).

import { logger } from "@/lib/logger";

export const GRAPHQL_TRANSPORT_WS_PROTOCOL = "graphql-transport-ws";

const SENSITIVE_QUERY_KEYS = new Set([
  "token",
  "access_token",
  "id_token",
  "refresh_token",
  "auth",
  "authorization",
  "jwt",
  "secret",
  "api_key",
  "apikey",
  "x-hasura-admin-secret",
  "admin_secret",
  "password",
  "key",
]);

export type HasuraClientStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "closed";

export interface HasuraStatusMeta {
  attempt?: number;
  delayMs?: number;
  reason?: string;
}

export interface HasuraLiveClientOptions {
  url: string;
  tenantId?: string | null;
  authToken?: string | null;
  getConnectionParams?: () =>
    | Promise<Record<string, unknown>>
    | Record<string, unknown>;
  onStatusChange?: (status: HasuraClientStatus, meta?: HasuraStatusMeta) => void;
  webSocketImpl?: typeof WebSocket;
  connectionAckTimeoutMs?: number;
}

export interface SubscribeOptions<TData = Record<string, unknown>> {
  id?: string;
  query: string;
  variables?: Record<string, unknown>;
  onNext: (data: TData) => void;
  onError?: (err: unknown) => void;
  onComplete?: () => void;
}

interface ActiveSubscription {
  id: string;
  query: string;
  variables?: Record<string, unknown>;
  onNext: (data: any) => void;
  onError?: (err: unknown) => void;
  onComplete?: () => void;
}

/**
 * Tính thời gian chờ kết nối lại theo Exponential Backoff:
 * attempt 0 -> 1000ms (1s)
 * attempt 1 -> 2000ms (2s)
 * attempt 2 -> 4000ms (4s)
 * attempt 3 -> 8000ms (8s)
 * attempt >= 4 -> 15000ms (tối đa 15s)
 */
export function computeBackoffDelayMs(attempt: number): number {
  const safeAttempt = Math.max(0, Math.floor(attempt));
  return Math.min(1000 * Math.pow(2, safeAttempt), 15_000);
}

/**
 * Chuẩn hóa URL WebSocket và loại bỏ triệt để mọi query param nhạy cảm (token, secret, jwt...)
 * để không bao giờ rò rỉ thông tin xác thực trên URL hoặc access logs.
 */
export function sanitizeHasuraWsUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim();
  if (!trimmed) {
    throw new Error("Hasura WebSocket URL must not be empty.");
  }

  const parsed = new URL(trimmed);
  if (parsed.protocol === "http:") {
    parsed.protocol = "ws:";
  } else if (parsed.protocol === "https:") {
    parsed.protocol = "wss:";
  } else if (parsed.protocol !== "ws:" && parsed.protocol !== "wss:") {
    throw new Error(`Unsupported WebSocket protocol: ${parsed.protocol}`);
  }

  // Xóa credentials nhúng trong URL (ws://user:pass@host) nếu có
  parsed.username = "";
  parsed.password = "";

  // Loại bỏ các query parameter nhạy cảm
  const keysToDelete: string[] = [];
  parsed.searchParams.forEach((_val, key) => {
    if (SENSITIVE_QUERY_KEYS.has(key.toLowerCase())) {
      keysToDelete.push(key);
    }
  });
  for (const k of keysToDelete) {
    parsed.searchParams.delete(k);
  }

  return parsed.toString();
}

/**
 * Lọc dữ liệu GraphQL `next` theo `tenantId` để đảm bảo cô lập đa thuê bao ở phía client.
 */
export function filterPayloadByTenant<T>(data: T, tenantId?: string | null): T {
  if (!tenantId || !data || typeof data !== "object") {
    return data;
  }

  if (Array.isArray(data)) {
    return data
      .filter((item) => {
        if (item && typeof item === "object" && "tenant_id" in item) {
          const itemTenant = (item as Record<string, unknown>).tenant_id;
          return !itemTenant || String(itemTenant) === String(tenantId);
        }
        return true;
      })
      .map((item) => filterPayloadByTenant(item, tenantId)) as unknown as T;
  }

  const record = data as Record<string, unknown>;
  if ("tenant_id" in record && record.tenant_id) {
    if (String(record.tenant_id) !== String(tenantId)) {
      return null as unknown as T;
    }
  }

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(record)) {
    result[key] = filterPayloadByTenant(value, tenantId);
  }
  return result as T;
}

export class HasuraLiveClient {
  private readonly url: string;
  private tenantId: string | null;
  private authToken: string | null;
  private readonly getConnectionParams?: HasuraLiveClientOptions["getConnectionParams"];
  private readonly onStatusChange?: HasuraLiveClientOptions["onStatusChange"];
  private readonly WebSocketCtor: typeof WebSocket;
  private readonly ackTimeoutMs: number;

  private ws: WebSocket | null = null;
  private status: HasuraClientStatus = "idle";
  private acknowledged = false;
  private manualClose = false;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private ackTimer: ReturnType<typeof setTimeout> | null = null;
  private nextSubSeq = 1;
  private readonly subscriptions = new Map<string, ActiveSubscription>();

  constructor(options: HasuraLiveClientOptions) {
    this.url = sanitizeHasuraWsUrl(options.url);
    this.tenantId = options.tenantId ?? null;
    this.authToken = options.authToken ?? null;
    this.getConnectionParams = options.getConnectionParams;
    this.onStatusChange = options.onStatusChange;
    this.ackTimeoutMs = options.connectionAckTimeoutMs ?? 10_000;

    const wsCtor =
      options.webSocketImpl ??
      (typeof WebSocket !== "undefined" ? WebSocket : undefined);
    if (!wsCtor) {
      throw new Error("WebSocket implementation is not available in this environment.");
    }
    this.WebSocketCtor = wsCtor;
  }

  public getStatus(): HasuraClientStatus {
    return this.status;
  }

  public getSanitizedUrl(): string {
    return this.url;
  }

  public updateSessionContext(params: {
    tenantId?: string | null;
    authToken?: string | null;
  }): void {
    const nextTenant = params.tenantId ?? null;
    const nextToken = params.authToken ?? null;
    const changed =
      nextTenant !== this.tenantId || nextToken !== this.authToken;
    this.tenantId = nextTenant;
    this.authToken = nextToken;

    if (changed && this.subscriptions.size > 0 && !this.manualClose) {
      this.teardownSocket(false);
      this.connect();
    }
  }

  public subscribe<TData = Record<string, unknown>>(
    opts: SubscribeOptions<TData>
  ): () => void {
    const id = opts.id ?? `sub_${this.nextSubSeq++}`;
    this.manualClose = false;

    const sub: ActiveSubscription = {
      id,
      query: opts.query,
      variables: opts.variables,
      onNext: opts.onNext,
      onError: opts.onError,
      onComplete: opts.onComplete,
    };
    this.subscriptions.set(id, sub);

    if (!this.ws) {
      this.connect();
    } else if (this.acknowledged && this.ws.readyState === this.WebSocketCtor.OPEN) {
      this.sendSubscribe(sub);
    }

    let active = true;
    return () => {
      if (!active) return;
      active = false;
      this.unsubscribe(id);
    };
  }

  public unsubscribe(id: string): void {
    const existed = this.subscriptions.delete(id);
    if (!existed) return;

    if (
      this.ws &&
      this.acknowledged &&
      this.ws.readyState === this.WebSocketCtor.OPEN
    ) {
      this.safeSend({ id, type: "complete" });
    }

    if (this.subscriptions.size === 0) {
      this.dispose();
    }
  }

  public dispose(): void {
    this.manualClose = true;
    this.clearTimers();
    this.subscriptions.clear();
    this.reconnectAttempt = 0;
    this.teardownSocket(true);
    this.setStatus("closed");
  }

  private setStatus(next: HasuraClientStatus, meta?: HasuraStatusMeta): void {
    if (this.status === next && next !== "reconnecting") return;
    this.status = next;
    try {
      this.onStatusChange?.(next, meta);
    } catch (err) {
      logger.warn("HasuraLiveClient onStatusChange callback error", err);
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ackTimer !== null) {
      clearTimeout(this.ackTimer);
      this.ackTimer = null;
    }
  }

  private teardownSocket(normalClose: boolean): void {
    this.acknowledged = false;
    if (this.ackTimer !== null) {
      clearTimeout(this.ackTimer);
      this.ackTimer = null;
    }
    if (!this.ws) return;

    const socket = this.ws;
    this.ws = null;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onerror = null;
    socket.onclose = null;

    try {
      if (
        socket.readyState === this.WebSocketCtor.OPEN ||
        socket.readyState === this.WebSocketCtor.CONNECTING
      ) {
        socket.close(normalClose ? 1000 : 4000, normalClose ? "Normal Closure" : "Reconnect");
      }
    } catch {
      /* Bỏ qua lỗi khi đóng socket đang ở trạng thái chuyển tiếp */
    }
  }

  private connect(): void {
    if (this.manualClose || this.subscriptions.size === 0) return;
    if (this.ws) return;

    this.clearTimers();
    this.acknowledged = false;
    if (this.reconnectAttempt === 0) {
      this.setStatus("connecting");
    }

    let socket: WebSocket;
    try {
      socket = new this.WebSocketCtor(this.url, GRAPHQL_TRANSPORT_WS_PROTOCOL);
    } catch (err) {
      logger.warn("HasuraLiveClient failed to create WebSocket", err);
      this.scheduleReconnect("socket_init_error");
      return;
    }

    this.ws = socket;

    socket.onopen = () => {
      if (this.ws !== socket || this.manualClose) return;
      void this.sendConnectionInit(socket);
    };

    socket.onmessage = (event: MessageEvent) => {
      if (this.ws !== socket || this.manualClose) return;
      this.handleMessage(event.data);
    };

    socket.onerror = () => {
      // Trình duyệt sẽ phát sự kiện `onclose` ngay sau `onerror`
      logger.debug("HasuraLiveClient WebSocket error encountered");
    };

    socket.onclose = (event: CloseEvent) => {
      if (this.ws === socket) {
        this.ws = null;
      }
      this.acknowledged = false;
      if (this.ackTimer !== null) {
        clearTimeout(this.ackTimer);
        this.ackTimer = null;
      }

      if (this.manualClose || this.subscriptions.size === 0) {
        this.setStatus("closed");
        return;
      }

      this.scheduleReconnect(event.reason || `close_${event.code}`);
    };
  }

  private async sendConnectionInit(socket: WebSocket): Promise<void> {
    try {
      const headers: Record<string, string> = {};
      if (this.authToken) {
        headers.Authorization = this.authToken.startsWith("Bearer ")
          ? this.authToken
          : `Bearer ${this.authToken}`;
      }
      if (this.tenantId) {
        headers["X-Hasura-Tenant-Id"] = this.tenantId;
      }

      let extraParams: Record<string, unknown> = {};
      if (this.getConnectionParams) {
        extraParams = (await this.getConnectionParams()) ?? {};
      }

      const extraHeaders =
        extraParams.headers && typeof extraParams.headers === "object"
          ? (extraParams.headers as Record<string, string>)
          : {};

      const payload: Record<string, unknown> = {
        ...extraParams,
        headers: {
          ...headers,
          ...extraHeaders,
        },
      };
      if (this.tenantId) {
        payload.tenant_id = this.tenantId;
      }

      if (this.ws !== socket || this.manualClose) return;

      this.safeSend({
        type: "connection_init",
        payload,
      });

      if (this.ackTimer !== null) {
        clearTimeout(this.ackTimer);
      }
      this.ackTimer = setTimeout(() => {
        if (!this.acknowledged && this.ws === socket && !this.manualClose) {
          logger.warn("HasuraLiveClient connection_ack timed out");
          this.teardownSocket(false);
          this.scheduleReconnect("ack_timeout");
        }
      }, this.ackTimeoutMs);
    } catch (err) {
      logger.warn("HasuraLiveClient failed to build connection_init payload", err);
      this.teardownSocket(false);
      this.scheduleReconnect("init_payload_error");
    }
  }

  private handleMessage(rawData: unknown): void {
    if (typeof rawData !== "string") return;

    let message: Record<string, any>;
    try {
      message = JSON.parse(rawData);
    } catch {
      logger.warn("HasuraLiveClient received invalid JSON frame");
      return;
    }

    switch (message.type) {
      case "connection_ack": {
        if (this.ackTimer !== null) {
          clearTimeout(this.ackTimer);
          this.ackTimer = null;
        }
        this.acknowledged = true;
        this.reconnectAttempt = 0;
        this.setStatus("connected");
        this.subscriptions.forEach((sub) => {
          this.sendSubscribe(sub);
        });
        break;
      }

      case "ping": {
        this.safeSend({ type: "pong" });
        break;
      }

      case "pong": {
        break;
      }

      case "next": {
        const subId = typeof message.id === "string" ? message.id : "";
        const sub = this.subscriptions.get(subId);
        if (!sub) break;

        const rawPayloadData = message.payload?.data;
        if (rawPayloadData !== undefined) {
          const filtered = filterPayloadByTenant(rawPayloadData, this.tenantId);
          if (filtered !== null) {
            sub.onNext(filtered);
          }
        }
        break;
      }

      case "error": {
        const subId = typeof message.id === "string" ? message.id : "";
        const sub = this.subscriptions.get(subId);
        sub?.onError?.(message.payload);
        break;
      }

      case "complete": {
        const subId = typeof message.id === "string" ? message.id : "";
        const sub = this.subscriptions.get(subId);
        if (sub) {
          this.subscriptions.delete(subId);
          sub.onComplete?.();
        }
        break;
      }

      default:
        break;
    }
  }

  private sendSubscribe(sub: ActiveSubscription): void {
    const mergedVariables: Record<string, unknown> = {
      ...(sub.variables ?? {}),
    };
    if (this.tenantId && mergedVariables.tenant_id === undefined) {
      mergedVariables.tenant_id = this.tenantId;
    }

    this.safeSend({
      id: sub.id,
      type: "subscribe",
      payload: {
        query: sub.query,
        variables: mergedVariables,
      },
    });
  }

  private scheduleReconnect(reason: string): void {
    if (this.manualClose || this.subscriptions.size === 0) return;
    if (this.reconnectTimer !== null) return;

    const attempt = this.reconnectAttempt;
    const delayMs = computeBackoffDelayMs(attempt);
    this.reconnectAttempt += 1;

    this.setStatus("reconnecting", { attempt: attempt + 1, delayMs, reason });

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.manualClose && this.subscriptions.size > 0) {
        this.connect();
      }
    }, delayMs);
  }

  private safeSend(frame: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== this.WebSocketCtor.OPEN) return;
    try {
      this.ws.send(JSON.stringify(frame));
    } catch (err) {
      logger.warn("HasuraLiveClient failed to send WebSocket frame", err);
    }
  }
}
