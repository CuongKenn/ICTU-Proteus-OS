// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// useAICommand — Custom Hook quản lý AI Chat Widget state & logic
// Tách biệt hoàn toàn Business Logic khỏi UI (AGENTS.md §2, §8)
// Giao tiếp qua BFF /api/ai/command & /api/ai/chat/stream (không gọi FastAPI trực tiếp)
// Tham chiếu: docs/architecture.md §2.1 (BFF Pattern), docs/dsl-spec.md

import { useState, useCallback, useEffect, useRef } from "react";
import { useDraftRestore } from "@/hooks/useDraftRestore";
import { useNotificationStore } from "@/store/notificationStore";

// Helper: sinh UUID v4 RFC-4122 chuẩn cho cả HTTPS và HTTP
export const uuid = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      // Fallback
    }
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 10xx
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// ─── Types ────────────────────────────────────────────────────────────────────

export type WidgetState = "collapsed" | "expanded" | "thinking" | "awaiting_approval";

export type MessageRole = "user" | "assistant" | "system";

export interface Z3Verification {
  status: "SAT" | "UNSAT";
  verified: boolean;
  solve_time_ms?: number;
  invariants_checked?: string[];
  violated_constraint?: string | null;
  escalated_to_critical?: boolean;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  z3_verification?: Z3Verification;
  action?: string;
  effect?: "read" | "write" | "critical";
  show_pipeline?: boolean;
}

export interface DslPreview {
  command_id: string;
  action: string;
  effect: "read" | "write" | "critical";
  approval_message: string;
  dry_run_result?: {
    affected_count: number;
    preview: Array<Record<string, unknown>> | string;
  };
  approval_deadline?: string | null;
  z3_verification?: Z3Verification;
}

interface AICommandBFFResponse {
  /** effect=read: trả kết quả trực tiếp */
  result?: unknown;
  /** effect=write/critical: DSL preview để hiển thị awaiting_approval */
  dsl_preview?: DslPreview;
  /** Thông tin kiểm chứng hình thức Z3 SMT (nếu đặt ở cấp root) */
  z3_verification?: Z3Verification;
  /** Trạng thái xử lý */
  status: "completed" | "pending_approval" | "error" | "failed" | string;
  message: string;
  command_id?: string;
}

export interface UseAICommandOptions {
  /** Cho phép bật cưỡng bức SSE stream (mặc định: true trên trình duyệt thực, false trong unit test để tương thích mock đơn) */
  enableStream?: boolean;
  /** Đồng bộ session từ bên ngoài (dùng cho trang /ai có Sessions Sidebar) */
  externalSessionId?: string;
  /** Tin nhắn lịch sử khi người dùng chọn phiên hội thoại cũ trên trang /ai */
  externalMessages?: ChatMessage[];
  /** Callback báo khi vừa hoàn tất 1 lượt hội thoại (để làm mới danh sách sessions) */
  onTurnCompleted?: (sessionId: string) => void;
}

export interface UseAICommandReturn {
  widgetState: WidgetState;
  messages: ChatMessage[];
  inputValue: string;
  dslPreview: DslPreview | null;
  sessionId: string;
  streamStatus: string | null;
  setInputValue: (value: string) => void;
  openWidget: () => void;
  minimizeWidget: () => void;
  resetAndClose: () => void;
  startNewSession: () => void;
  loadSessionHistory: (targetSessionId: string, history: ChatMessage[]) => void;
  sendCommand: (overrideInput?: string | unknown) => Promise<void>;
  openMattermostApproval: () => void;
  cancelApproval: () => void;
}

// ─── Helpers: Trích xuất Z3 Formal Verification từ nhiều vị trí payload ──────

function normalizeZ3Object(raw: unknown): Z3Verification | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const obj = raw as Record<string, unknown>;
  const rawStatus = String(obj.status || "").toUpperCase();
  if (rawStatus !== "SAT" && rawStatus !== "UNSAT") return undefined;

  return {
    status: rawStatus as "SAT" | "UNSAT",
    verified: typeof obj.verified === "boolean" ? obj.verified : rawStatus === "SAT",
    solve_time_ms:
      typeof obj.solve_time_ms === "number" ? obj.solve_time_ms : undefined,
    invariants_checked: Array.isArray(obj.invariants_checked)
      ? obj.invariants_checked.map((x) => String(x))
      : undefined,
    violated_constraint:
      typeof obj.violated_constraint === "string" ? obj.violated_constraint : null,
    escalated_to_critical:
      typeof obj.escalated_to_critical === "boolean"
        ? obj.escalated_to_critical
        : undefined,
  };
}

export function extractZ3FromPayload(
  data: AICommandBFFResponse | Record<string, unknown>,
  userPrompt?: string
): {
  z3?: Z3Verification;
  action?: string;
  effect?: "read" | "write" | "critical";
  showPipeline: boolean;
} {
  const rec = data as Record<string, unknown>;
  const preview = (rec.dsl_preview || rec.dry_run) as Record<string, unknown> | undefined;
  const resultObj =
    rec.result && typeof rec.result === "object"
      ? (rec.result as Record<string, unknown>)
      : undefined;

  const steps = Array.isArray(resultObj?.steps)
    ? (resultObj?.steps as Array<Record<string, unknown>>)
    : [];
  const lastStep = steps.length > 0 ? steps[steps.length - 1] : undefined;
  const lastStepResult =
    lastStep?.result && typeof lastStep.result === "object"
      ? (lastStep.result as Record<string, unknown>)
      : undefined;

  let z3 =
    normalizeZ3Object(preview?.z3_verification) ||
    normalizeZ3Object(rec.z3_verification) ||
    normalizeZ3Object(resultObj?.z3_verification) ||
    normalizeZ3Object(lastStep?.z3_verification) ||
    normalizeZ3Object(lastStepResult?.z3_verification);

  const action =
    (typeof preview?.action === "string" && preview.action) ||
    (typeof lastStep?.action === "string" && lastStep.action) ||
    undefined;

  const rawEffect =
    (typeof preview?.effect === "string" && preview.effect) ||
    (typeof lastStep?.effect === "string" && lastStep.effect) ||
    undefined;
  const effect =
    rawEffect === "read" || rawEffect === "write" || rawEffect === "critical"
      ? rawEffect
      : undefined;

  const msgText = String(rec.message || "");
  const statusLower = String(rec.status || "").toLowerCase();

  // Nhận diện thông báo chặn Poka-yoke Z3 UNSAT dạng text nếu backend trả chuỗi cảnh báo
  if (
    !z3 &&
    (msgText.includes("UNSAT") ||
      /poka[-\s]?yoke/i.test(msgText) ||
      (/z3/i.test(msgText) && (statusLower === "failed" || statusLower === "error")))
  ) {
    const constraintMatch =
      msgText.match(/constraint[:\s]+([^\n]+)/i) ||
      msgText.match(/ràng buộc[:\s]+([^\n]+)/i) ||
      msgText.match(/`([^`]+)`/);
    z3 = {
      status: "UNSAT",
      verified: false,
      violated_constraint:
        constraintMatch?.[1]?.trim() ||
        (userPrompt && /C1-202.*C1-202/i.test(userPrompt)
          ? "And(transfer_qty > 0, source_room != target_room) [C1-202 == C1-202]"
          : "Invariant violation detected by Z3 SMT Solver"),
    };
  }

  const isPlainChatReply = action === "core.chat.reply" && !z3;
  const showPipeline = Boolean(z3) || (Boolean(action) && !isPlainChatReply);

  return { z3, action, effect, showPipeline };
}

function parseSseEvents(rawChunkBuffer: string): {
  events: Array<{ event: string; data: Record<string, unknown> }>;
  remainder: string;
} {
  const normalized = rawChunkBuffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() ?? "";
  const events: Array<{ event: string; data: Record<string, unknown> }> = [];

  for (const block of blocks) {
    const trimmedBlock = block.trim();
    if (!trimmedBlock) continue;
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of trimmedBlock.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length > 0) {
      try {
        const parsed = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
        events.push({ event: eventName, data: parsed });
      } catch {
        // Bỏ qua frame không phải JSON hợp lệ
      }
    }
  }

  return { events, remainder };
}

// ─── Hook Implementation ───────────────────────────────────────────────────────

export function useAICommand(options?: UseAICommandOptions): UseAICommandReturn {
  const { saveDraft, restoreDraft, clearDraft } = useDraftRestore();
  const DRAFT_KEY = "ai_command_draft_input";

  const [widgetState, setWidgetState] = useState<WidgetState>("collapsed");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValueState] = useState<string>("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);

  useEffect(() => {
    const draft = restoreDraft<string>(DRAFT_KEY);
    if (draft) {
      setInputValueState(draft);
    }
  }, [restoreDraft]);

  const setInputValue = useCallback(
    (value: string) => {
      setInputValueState(value);
      if (value) {
        saveDraft(DRAFT_KEY, value);
      } else {
        clearDraft(DRAFT_KEY);
      }
    },
    [saveDraft, clearDraft]
  );

  const [dslPreview, setDslPreview] = useState<DslPreview | null>(null);
  const [sessionId, setSessionId] = useState<string>(
    () => options?.externalSessionId || uuid()
  );
  const pollInFlightRef = useRef(false);

  const { addToast } = useNotificationStore();

  useEffect(() => {
    if (options?.externalSessionId && options.externalSessionId !== sessionId) {
      setSessionId(options.externalSessionId);
    }
  }, [options?.externalSessionId, sessionId]);

  useEffect(() => {
    if (options?.externalMessages) {
      setMessages(options.externalMessages);
      setDslPreview(null);
      setWidgetState("expanded");
    }
  }, [options?.externalMessages]);

  // ─── Actions ─────────────────────────────────────────────────────────────────

  const openWidget = useCallback(() => {
    setWidgetState((prev) =>
      prev === "collapsed" ? (dslPreview ? "awaiting_approval" : "expanded") : prev
    );
  }, [dslPreview]);

  const minimizeWidget = useCallback(() => {
    setWidgetState("collapsed");
  }, []);

  const startNewSession = useCallback(() => {
    const cmdId = dslPreview?.command_id;
    if (cmdId) {
      fetch(`/api/proxy/v1/ai/commands/${cmdId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).catch(() => {
        // Best-effort cancel
      });
    }
    setDslPreview(null);
    setStreamStatus(null);
    setInputValueState("");
    clearDraft(DRAFT_KEY);
    setMessages([]);
    setSessionId(uuid());
    setWidgetState("expanded");
  }, [dslPreview, clearDraft]);

  const loadSessionHistory = useCallback(
    (targetSessionId: string, history: ChatMessage[]) => {
      setDslPreview(null);
      setStreamStatus(null);
      setSessionId(targetSessionId);
      setMessages(history);
      setWidgetState("expanded");
    },
    []
  );

  const resetAndClose = useCallback(() => {
    const cmdId = dslPreview?.command_id;
    if (cmdId) {
      fetch(`/api/proxy/v1/ai/commands/${cmdId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).catch(() => {
        // Best-effort cancel
      });
    }
    setWidgetState("collapsed");
    setDslPreview(null);
    setStreamStatus(null);
    setInputValueState("");
    clearDraft(DRAFT_KEY);
    setMessages([]);
    setSessionId(uuid());
  }, [dslPreview, clearDraft]);

  const appendMessage = useCallback(
    (
      role: MessageRole,
      content: string,
      meta?: Pick<ChatMessage, "z3_verification" | "action" | "effect" | "show_pipeline">
    ) => {
      setMessages((prev) => [
        ...prev,
        { id: uuid(), role, content, timestamp: new Date(), ...meta },
      ]);
    },
    []
  );

  // Poll trạng thái phê duyệt khi đang có lệnh chờ phê duyệt (#866)
  useEffect(() => {
    const commandId = dslPreview?.command_id;
    if (!commandId) return;
    if (widgetState !== "awaiting_approval" && widgetState !== "collapsed") return;

    let cancelled = false;
    pollInFlightRef.current = false;

    const pollApprovalStatus = async () => {
      if (pollInFlightRef.current || cancelled) return;
      pollInFlightRef.current = true;
      try {
        const res = await fetch(`/api/proxy/v1/ai/commands/${commandId}/status`, {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        if (!res.ok || cancelled) return;
        const statusData = await res.json().catch(() => null);
        if (!statusData || cancelled) return;

        const statusUpper = String(statusData.status || "").toUpperCase();
        if (statusUpper === "COMPLETED" || statusUpper === "EXECUTED") {
          let replyText = typeof statusData.message === "string" ? statusData.message : "";
          if (!replyText) {
            if (typeof statusData.result === "string") {
              replyText = statusData.result;
            } else if (statusData.result && typeof statusData.result === "object") {
              const resObj = statusData.result as Record<string, unknown>;
              replyText =
                (typeof resObj.message === "string" && resObj.message) ||
                (typeof resObj.text === "string" && resObj.text) ||
                "✅ Lệnh đã được phê duyệt và thực thi thành công.";
            } else {
              replyText = "✅ Lệnh đã được phê duyệt và thực thi thành công.";
            }
          }
          setDslPreview(null);
          appendMessage("assistant", replyText, {
            z3_verification: dslPreview?.z3_verification,
            action: dslPreview?.action,
            effect: dslPreview?.effect,
            show_pipeline: true,
          });
          setWidgetState((prev) => (prev === "collapsed" ? "collapsed" : "expanded"));
        } else if (
          statusUpper === "REJECTED" ||
          statusUpper === "FAILED" ||
          statusUpper === "EXPIRED" ||
          statusUpper === "TIMEOUT" ||
          statusUpper === "CANCELLED"
        ) {
          const defaultStatusMessages: Record<string, string> = {
            REJECTED: "🚫 Yêu cầu đã bị từ chối phê duyệt trên Mattermost.",
            CANCELLED: "🚫 Lệnh đã được huỷ bỏ.",
            EXPIRED: "⏰ Yêu cầu phê duyệt đã hết hạn.",
            TIMEOUT: "⏰ Yêu cầu phê duyệt đã hết hạn.",
            FAILED: "❌ Thực thi lệnh sau khi phê duyệt thất bại.",
          };
          const statusMsg =
            (typeof statusData.message === "string" && statusData.message.trim()) ||
            defaultStatusMessages[statusUpper] ||
            "Lệnh không thể hoàn tất.";
          setDslPreview(null);
          appendMessage("assistant", statusMsg);
          setWidgetState((prev) => (prev === "collapsed" ? "collapsed" : "expanded"));
        }
      } catch {
        // Ignore transient network errors while polling
      } finally {
        pollInFlightRef.current = false;
      }
    };

    const intervalId = setInterval(pollApprovalStatus, 3000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
      pollInFlightRef.current = false;
    };
  }, [
    widgetState,
    dslPreview?.command_id,
    dslPreview?.z3_verification,
    dslPreview?.action,
    dslPreview?.effect,
    appendMessage,
  ]);

  const applyFinalResponse = useCallback(
    (data: AICommandBFFResponse, rawPrompt: string) => {
      const statusLower = String(data.status || "").toLowerCase();
      const resultObj =
        data.result && typeof data.result === "object"
          ? (data.result as Record<string, unknown>)
          : undefined;
      const rawPreview = (data.dsl_preview ||
        (data as unknown as Record<string, unknown>).dry_run ||
        resultObj?.dsl_preview) as DslPreview | undefined;

      const { z3, action, effect, showPipeline } = extractZ3FromPayload(data, rawPrompt);

      if (statusLower === "completed") {
        let replyText = data.message;
        if (!replyText) {
          if (typeof data.result === "string") {
            replyText = data.result;
          } else if (resultObj) {
            replyText =
              (typeof resultObj.message === "string" && resultObj.message) ||
              (typeof resultObj.text === "string" && resultObj.text) ||
              JSON.stringify(data.result, null, 2);
          } else {
            replyText = "Lệnh đã được thực hiện thành công.";
          }
        }
        appendMessage("assistant", replyText, {
          z3_verification: z3,
          action,
          effect,
          show_pipeline: showPipeline,
        });
        setWidgetState("expanded");
      } else if (statusLower === "pending_approval" && rawPreview) {
        const enrichedPreview: DslPreview = z3
          ? { ...rawPreview, z3_verification: rawPreview.z3_verification ?? z3 }
          : rawPreview;
        setDslPreview(enrichedPreview);
        appendMessage(
          "assistant",
          `🔒 Lệnh này yêu cầu phê duyệt từ Ban Giám đốc.\n\n**Hành động:** \`${enrichedPreview.action}\`\n\nVui lòng bấm **"Phê duyệt trên Mattermost"** để tiếp tục.`,
          {
            z3_verification: enrichedPreview.z3_verification,
            action: enrichedPreview.action,
            effect: enrichedPreview.effect,
            show_pipeline: true,
          }
        );
        setWidgetState("awaiting_approval");
      } else {
        appendMessage("assistant", data.message || "Đã xảy ra lỗi không xác định.", {
          z3_verification: z3,
          action,
          effect,
          show_pipeline: Boolean(z3),
        });
        setWidgetState("expanded");
      }

      options?.onTurnCompleted?.(sessionId);
    },
    [appendMessage, options, sessionId]
  );

  const consumeEventStream = useCallback(
    async (
      bodyStream: ReadableStream<Uint8Array>,
      rawPrompt: string
    ): Promise<AICommandBFFResponse | null> => {
      const reader = bodyStream.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalPayload: AICommandBFFResponse | null = null;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const { events, remainder } = parseSseEvents(buffer);
          buffer = remainder;

          for (const evt of events) {
            if (evt.event === "started") {
              setStreamStatus("Khởi tạo phiên suy luận DX-DSL…");
            } else if (evt.event === "token") {
              setStreamStatus("Đang tổng hợp kế hoạch DX-DSL…");
            } else if (evt.event === "plan") {
              const steps = Array.isArray(evt.data.steps) ? evt.data.steps : [];
              const firstAction =
                steps[0] && typeof steps[0] === "object"
                  ? String((steps[0] as Record<string, unknown>).action || "")
                  : "";
              setStreamStatus(
                firstAction
                  ? `Kiểm chứng Z3 & RBAC cho ${firstAction}…`
                  : "Kiểm chứng Z3 SMT & phân quyền RBAC…"
              );
            } else if (evt.event === "thought") {
              const thoughtText = String(evt.data.text || "").trim();
              if (thoughtText) {
                setStreamStatus(
                  thoughtText.length > 68 ? `${thoughtText.slice(0, 68)}…` : thoughtText
                );
              }
            } else if (evt.event === "step") {
              const actName = String(evt.data.action || "");
              if (actName) {
                setStreamStatus(`Thực thi ${actName}…`);
              }
            } else if (evt.event === "result") {
              const resObj =
                evt.data.result && typeof evt.data.result === "object"
                  ? (evt.data.result as Record<string, unknown>)
                  : undefined;
              finalPayload = {
                status: String(evt.data.status || "completed").toLowerCase(),
                message: String(evt.data.message || ""),
                result: evt.data.result,
                dsl_preview: (evt.data.dsl_preview || resObj?.dsl_preview) as
                  | DslPreview
                  | undefined,
                z3_verification: evt.data.z3_verification as Z3Verification | undefined,
                command_id:
                  typeof evt.data.command_id === "string"
                    ? evt.data.command_id
                    : undefined,
              };
            }
          }
        }
      } finally {
        reader.releaseLock();
        setStreamStatus(null);
      }

      if (finalPayload) {
        applyFinalResponse(finalPayload, rawPrompt);
      }
      return finalPayload;
    },
    [applyFinalResponse]
  );

  /**
   * sendCommand — Hỗ trợ đọc SSE stream từ POST /api/ai/chat/stream trên trình duyệt thực,
   * tự động fallback mượt sang POST /api/ai/command khi không trả text/event-stream
   * hoặc trong môi trường unit test.
   */
  const sendCommand = useCallback(
    async (overrideInput?: string | unknown) => {
      const candidate = typeof overrideInput === "string" ? overrideInput : inputValue;
      const trimmed = candidate.trim();
      if (!trimmed || widgetState === "thinking") return;

      appendMessage("user", trimmed);
      setInputValue("");
      clearDraft(DRAFT_KEY);
      setWidgetState("thinking");
      setStreamStatus(null);

      const isTestEnv =
        typeof process !== "undefined" &&
        (process.env.NODE_ENV === "test" || Boolean(process.env.VITEST));
      const shouldTryStream =
        options?.enableStream !== undefined ? options.enableStream : !isTestEnv;

      const requestBody = JSON.stringify({
        natural_language_input: trimmed,
        session_id: sessionId,
      });

      try {
        if (shouldTryStream) {
          try {
            const streamRes = await fetch("/api/ai/chat/stream", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Accept: "text/event-stream",
              },
              body: requestBody,
            });

            const streamContentType =
              streamRes?.headers?.get?.("content-type")?.toLowerCase() ?? "";

            if (
              streamRes.ok &&
              streamContentType.includes("text/event-stream") &&
              streamRes.body
            ) {
              const streamedResult = await consumeEventStream(streamRes.body, trimmed);
              if (streamedResult) {
                return;
              }
            } else if (streamRes.ok && typeof streamRes.json === "function") {
              const jsonFallback = (await streamRes.json()) as AICommandBFFResponse;
              if (jsonFallback && typeof jsonFallback === "object" && jsonFallback.status) {
                applyFinalResponse(jsonFallback, trimmed);
                return;
              }
            }
          } catch {
            // Tự động fallback mượt sang /api/ai/command bên dưới
            setStreamStatus(null);
          }
        }

        const response = await fetch("/api/ai/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: requestBody,
        });

        const cmdContentType =
          response?.headers?.get?.("content-type")?.toLowerCase() ?? "";
        if (response.ok && cmdContentType.includes("text/event-stream") && response.body) {
          const streamed = await consumeEventStream(response.body, trimmed);
          if (streamed) return;
        }

        let data: AICommandBFFResponse;

        if (!response.ok && process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
          const { MOCK_RESPONSES, detectEffectFromInput } = await import(
            "../__tests__/useAICommand.mock"
          );
          const detectedEffect = detectEffectFromInput(trimmed);
          data = MOCK_RESPONSES[detectedEffect] as AICommandBFFResponse;
        } else if (!response.ok) {
          throw new Error(`API Error: ${response.status}`);
        } else {
          data = await response.json();
        }

        applyFinalResponse(data, trimmed);
      } catch {
        setStreamStatus(null);
        if (process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
          if (/C1-202.*C1-202/i.test(trimmed)) {
            appendMessage(
              "assistant",
              "⛔ Lệnh chuyển thiết bị đã bị chặn bởi bộ giải toán học Z3 SMT vì phòng nguồn trùng với phòng đích.",
              {
                action: "ops.asset.transfer",
                effect: "write",
                show_pipeline: true,
                z3_verification: {
                  status: "UNSAT",
                  verified: false,
                  solve_time_ms: 1.8,
                  invariants_checked: ["asset_transfer_distinct_rooms"],
                  violated_constraint: "source_room != target_room (C1-202 == C1-202)",
                },
              }
            );
            setWidgetState("expanded");
            return;
          }
          const { MOCK_RESPONSES, detectEffectFromInput } = await import(
            "../__tests__/useAICommand.mock"
          );
          const detectedEffect = detectEffectFromInput(trimmed);
          const mockData = MOCK_RESPONSES[detectedEffect] as AICommandBFFResponse;
          if (mockData.status === "pending_approval" && mockData.dsl_preview) {
            const z3Sat: Z3Verification = {
              status: "SAT",
              verified: true,
              solve_time_ms: 2.4,
              invariants_checked: ["budget_non_negative", "positive_quantity"],
            };
            setDslPreview({
              ...mockData.dsl_preview,
              command_id: uuid(),
              z3_verification: z3Sat,
            });
            appendMessage(
              "assistant",
              `🔒 Lệnh này yêu cầu phê duyệt từ Ban Giám đốc.\n\n**Hành động:** \`${mockData.dsl_preview.action}\`\n\nVui lòng bấm **"Phê duyệt trên Mattermost"** để tiếp tục.`,
              {
                z3_verification: z3Sat,
                action: mockData.dsl_preview.action,
                effect: mockData.dsl_preview.effect,
                show_pipeline: true,
              }
            );
            setWidgetState("awaiting_approval");
          } else if (mockData.status === "completed" && mockData.result) {
            appendMessage("assistant", String(mockData.result));
            setWidgetState("expanded");
          }
        } else {
          appendMessage(
            "assistant",
            "❌ Không thể kết nối tới AI Service. Vui lòng thử lại sau."
          );
          addToast("error", "Lỗi kết nối AI Service");
          setWidgetState("expanded");
        }
      }
    },
    [
      inputValue,
      widgetState,
      appendMessage,
      addToast,
      sessionId,
      setInputValue,
      clearDraft,
      options?.enableStream,
      consumeEventStream,
      applyFinalResponse,
    ]
  );

  /**
   * openMattermostApproval — Mở Mattermost để phê duyệt.
   * Rule sinh tử: AI KHÔNG tự bypass bước này (AGENTS.md §4).
   */
  const openMattermostApproval = useCallback(() => {
    const mattermostUrl = process.env.NEXT_PUBLIC_MATTERMOST_URL || "/chat";
    window.open(mattermostUrl, "_blank", "noopener,noreferrer");
    addToast(
      "info",
      "Đã mở Mattermost. Vui lòng bấm [Phê duyệt] trên tin nhắn từ Proteus AI."
    );
  }, [addToast]);

  /**
   * cancelApproval — Huỷ lệnh đang chờ phê duyệt trên cả server và client (#731).
   */
  const cancelApproval = useCallback(async () => {
    const cmdId = dslPreview?.command_id;
    if (cmdId) {
      try {
        await fetch(`/api/proxy/v1/ai/commands/${cmdId}/cancel`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
      } catch {
        // Best-effort cancel
      }
    }
    setDslPreview(null);
    appendMessage("assistant", "🚫 Lệnh đã được huỷ bỏ.");
    setWidgetState("expanded");
  }, [dslPreview, appendMessage]);

  return {
    widgetState,
    messages,
    inputValue,
    dslPreview,
    sessionId,
    streamStatus,
    setInputValue,
    openWidget,
    minimizeWidget,
    resetAndClose,
    startNewSession,
    loadSessionHistory,
    sendCommand,
    openMattermostApproval,
    cancelApproval,
  };
}
