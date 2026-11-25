// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// useAICommand — Custom Hook quản lý AI Chat Widget state & logic
// Tách biệt hoàn toàn Business Logic khỏi UI (AGENTS.md §2, §8)
// Giao tiếp qua BFF /api/ai/command (không gọi FastAPI trực tiếp)
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

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

export interface DslPreview {
  command_id: string;
  action: string;
  effect: "read" | "write" | "critical";
  approval_message: string;
  dry_run_result?: {
    affected_count: number;
    preview: Array<Record<string, unknown>>;
  };
  approval_deadline?: string | null;
}

interface AICommandBFFResponse {
  /** effect=read: trả kết quả trực tiếp */
  result?: string;
  /** effect=write/critical: DSL preview để hiển thị awaiting_approval */
  dsl_preview?: DslPreview;
  /** Trạng thái xử lý */
  status: "completed" | "pending_approval" | "error" | string;
  message: string;
}

interface UseAICommandReturn {
  widgetState: WidgetState;
  messages: ChatMessage[];
  inputValue: string;
  dslPreview: DslPreview | null;
  sessionId: string;
  setInputValue: (value: string) => void;
  openWidget: () => void;
  minimizeWidget: () => void;
  resetAndClose: () => void;
  sendCommand: () => Promise<void>;
  openMattermostApproval: () => void;
  cancelApproval: () => void;
}

// ─── Hook Implementation ───────────────────────────────────────────────────────

export function useAICommand(): UseAICommandReturn {
  const { saveDraft, restoreDraft, clearDraft } = useDraftRestore();
  const DRAFT_KEY = "ai_command_draft_input";

  const [widgetState, setWidgetState] = useState<WidgetState>("collapsed");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValueState] = useState<string>("");

  useEffect(() => {
    const draft = restoreDraft<string>(DRAFT_KEY);
    if (draft) {
      setInputValueState(draft);
    }
  }, [restoreDraft]);

  const setInputValue = useCallback((value: string) => {
    setInputValueState(value);
    if (value) {
      saveDraft(DRAFT_KEY, value);
    } else {
      clearDraft(DRAFT_KEY);
    }
  }, [saveDraft, clearDraft]);
  const [dslPreview, setDslPreview] = useState<DslPreview | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => uuid());
  const pollInFlightRef = useRef(false);

  const { addToast } = useNotificationStore();

  // ─── Actions ─────────────────────────────────────────────────────────────────

  const openWidget = useCallback(() => {
    setWidgetState((prev) =>
      prev === "collapsed" ? (dslPreview ? "awaiting_approval" : "expanded") : prev
    );
  }, [dslPreview]);

  const minimizeWidget = useCallback(() => {
    setWidgetState("collapsed");
  }, []);

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
    setInputValueState("");
    clearDraft(DRAFT_KEY);
    setMessages([]);
    setSessionId(uuid());
  }, [dslPreview, clearDraft]);

  const appendMessage = useCallback((role: MessageRole, content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: uuid(), role, content, timestamp: new Date() },
    ]);
  }, []);

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
          appendMessage("assistant", replyText);
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
  }, [widgetState, dslPreview?.command_id, appendMessage]);

  /**
   * sendCommand — Gửi lệnh tới BFF /api/ai/command
   * BFF sẽ inject JWT Token từ HttpOnly Cookie và forward tới FastAPI.
   * effect=read → hiển thị kết quả ngay.
   * effect=write/critical → chuyển sang state awaiting_approval + hiện DSL preview.
   */
  const sendCommand = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || widgetState === "thinking") return;

    // Thêm tin nhắn người dùng
    appendMessage("user", trimmed);
    setInputValue("");
    clearDraft(DRAFT_KEY);
    setWidgetState("thinking");

    try {
      const response = await fetch("/api/ai/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          natural_language_input: trimmed,
          session_id: sessionId,
        }),
      });

      let data: AICommandBFFResponse;

      if (!response.ok && process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
        // Dev fallback: mock response khi API chưa có
        const { MOCK_RESPONSES, detectEffectFromInput } = await import("../__tests__/useAICommand.mock");
        const detectedEffect = detectEffectFromInput(trimmed);
        data = MOCK_RESPONSES[detectedEffect] as AICommandBFFResponse;
      } else if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      } else {
        data = await response.json();
      }

      const statusLower = String(data.status || "").toLowerCase();
      const preview = data.dsl_preview || (data as any).dry_run;
      if (statusLower === "completed") {
        // Ưu tiên hiển thị data.message (câu trả lời tự nhiên từ AI) (#731)
        let replyText = data.message;
        if (!replyText) {
          if (typeof data.result === "string") {
            replyText = data.result;
          } else if (data.result && typeof data.result === "object") {
            const resAny = data.result as any;
            replyText = resAny.message || resAny.text || JSON.stringify(data.result, null, 2);
          } else {
            replyText = "Lệnh đã được thực hiện thành công.";
          }
        }
        appendMessage("assistant", replyText);
        setWidgetState("expanded");
      } else if (statusLower === "pending_approval" && preview) {
        // effect=write/critical: chờ phê duyệt
        setDslPreview(preview);
        appendMessage(
          "assistant",
          `🔒 Lệnh này yêu cầu phê duyệt từ Ban Giám đốc.\n\n**Hành động:** \`${preview.action}\`\n\nVui lòng bấm **"Phê duyệt trên Mattermost"** để tiếp tục.`
        );
        setWidgetState("awaiting_approval");
      } else {
        appendMessage("assistant", data.message || "Đã xảy ra lỗi không xác định.");
        setWidgetState("expanded");
      }
    } catch (error) {
      if (process.env.NEXT_PUBLIC_ENABLE_MOCKS === "true") {
        // Dev fallback
        const { MOCK_RESPONSES, detectEffectFromInput } = await import("../__tests__/useAICommand.mock");
        const detectedEffect = detectEffectFromInput(trimmed);
        const mockData = MOCK_RESPONSES[detectedEffect] as AICommandBFFResponse;
        if (mockData.status === "pending_approval" && mockData.dsl_preview) {
          setDslPreview({ ...mockData.dsl_preview, command_id: uuid() });
          appendMessage(
            "assistant",
            `🔒 Lệnh này yêu cầu phê duyệt từ Ban Giám đốc.\n\n**Hành động:** \`${mockData.dsl_preview.action}\`\n\nVui lòng bấm **"Phê duyệt trên Mattermost"** để tiếp tục.`
          );
          setWidgetState("awaiting_approval");
        } else if (mockData.status === "completed" && mockData.result) {
          appendMessage("assistant", mockData.result);
          setWidgetState("expanded");
        }
      } else {
        appendMessage("assistant", "❌ Không thể kết nối tới AI Service. Vui lòng thử lại sau.");
        addToast("error", "Lỗi kết nối AI Service");
        setWidgetState("expanded");
      }
    }
  }, [inputValue, widgetState, appendMessage, addToast, sessionId, setInputValue, clearDraft]);

  /**
   * openMattermostApproval — Mở Mattermost để phê duyệt.
   * Widget ở trạng thái awaiting_approval, người dùng bấm nút này để
   * chuyển sang Mattermost bấm [Phê duyệt].
   * Rule sinh tử: AI KHÔNG tự bypass bước này (AGENTS.md §4).
   */
  const openMattermostApproval = useCallback(() => {
    // Mở Mattermost — trong production, URL này từ env config
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
      } catch (err) {
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
    setInputValue,
    openWidget,
    minimizeWidget,
    resetAndClose,
    sendCommand,
    openMattermostApproval,
    cancelApproval,
  };
}
