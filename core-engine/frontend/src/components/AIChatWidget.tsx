// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// AIChatWidget — Enterprise AI Assistant (Floating & Full-Page Inline)
// Theme-aware (Light & Dark), Human-in-the-loop DSL approval preview.

"use client";

import React, { useRef, useEffect, KeyboardEvent } from "react";
import {
  Bot,
  X,
  Send,
  Loader2,
  AlertTriangle,
  ExternalLink,
  XCircle,
  ChevronDown,
  Clock,
  Terminal,
} from "lucide-react";
import { clsx } from "clsx";
import { useAICommand, ChatMessage, DslPreview } from "@/hooks/useAICommand";
import { logger } from "@/lib/logger";

// ─── Sub-components ───────────────────────────────────────────────────────────

const ThinkingIndicator: React.FC = () => (
  <div className="flex items-center gap-1.5 px-3 py-2.5">
    <span className="text-xs mr-1.5 font-medium text-dim">Đang phân tích</span>
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        className="w-1.5 h-1.5 rounded-full animate-bounce"
        style={{
          background: "var(--accent)",
          animationDelay: `${i * 180}ms`,
          animationDuration: "650ms",
        }}
      />
    ))}
  </div>
);

function renderMessageContent(content: string, isUser: boolean): React.ReactNode {
  const parts = content.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={idx} className={isUser ? "font-semibold text-white" : "font-semibold text-ink"}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={idx}
          className={clsx(
            "px-1.5 py-0.5 rounded font-mono text-xs",
            isUser
              ? "bg-white/15 text-white"
              : "bg-paper-subtle text-accent border border-line"
          )}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part.split("\n").map((line, li, arr) => (
      <React.Fragment key={`${idx}-${li}`}>
        {line}
        {li < arr.length - 1 && <br />}
      </React.Fragment>
    ));
  });
}

const MessageBubble: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const isUser = message.role === "user";
  return (
    <div className={clsx("flex gap-2.5 mb-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {!isUser && (
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 border border-line"
          style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
        >
          <Bot className="w-3.5 h-3.5" />
        </div>
      )}

      <div
        className={clsx(
          "max-w-[82%] rounded-xl px-3.5 py-2.5 text-[13.5px] leading-relaxed",
          isUser
            ? "text-white rounded-tr-sm"
            : "bg-paper-subtle border border-line text-ink rounded-tl-sm"
        )}
        style={isUser ? { background: "var(--accent-solid)" } : undefined}
      >
        {renderMessageContent(message.content, isUser)}
        <div
          className={clsx(
            "text-[10.5px] mt-1 tabular-nums",
            isUser ? "text-right text-white/75" : "text-left text-dim"
          )}
        >
          {message.timestamp.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
};

const DslPreviewPanel: React.FC<{
  preview: DslPreview;
  onApprove: () => void;
  onCancel: () => void;
}> = ({ preview, onApprove, onCancel }) => {
  const deadline = new Date(preview.approval_deadline);
  const isWrite = preview.effect === "write";

  return (
    <div
      className="mx-1 mb-3 rounded-xl border overflow-hidden"
      style={{
        background: "var(--amber-fill)",
        borderColor: "rgba(180, 83, 9, 0.28)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3.5 py-2.5 border-b"
        style={{ borderColor: "rgba(180, 83, 9, 0.2)" }}
      >
        <AlertTriangle className="w-4 h-4 shrink-0" style={{ color: "var(--amber)" }} />
        <span className="text-xs font-semibold" style={{ color: "var(--amber)" }}>
          Chờ phê duyệt Mattermost
        </span>
        <span
          className={clsx(
            "ml-auto text-[10.5px] font-semibold font-mono px-2 py-0.5 rounded-full",
            isWrite ? "status-badge--warning" : "status-badge--failed"
          )}
        >
          {preview.effect.toUpperCase()}
        </span>
      </div>

      {/* Action & Preview */}
      <div className="px-3.5 pt-3">
        <div className="flex items-center gap-1.5 mb-2">
          <Terminal className="w-3.5 h-3.5 text-accent shrink-0" />
          <span className="text-xs font-mono font-medium text-ink">{preview.action}</span>
        </div>

        {preview.dry_run_result && (
          <div className="mb-2.5 p-2.5 rounded-lg bg-paper-white border border-line">
            {preview.dry_run_result.affected_count !== undefined && (
              <div className="text-xs font-medium text-muted mb-1.5 tabular-nums">
                Ảnh hưởng đến{" "}
                <strong className="text-ink font-semibold">
                  {preview.dry_run_result.affected_count}
                </strong>{" "}
                bản ghi:
              </div>
            )}
            <div className="space-y-1 max-h-[84px] overflow-y-auto">
              {Array.isArray(preview.dry_run_result?.preview) ? (
                <>
                  {preview.dry_run_result.preview.slice(0, 3).map((item, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-ink-soft">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ background: "var(--amber)" }}
                      />
                      <span className="truncate">
                        {String(item.employee_name || item.id || JSON.stringify(item))}
                      </span>
                    </div>
                  ))}
                  {preview.dry_run_result.preview.length > 3 && (
                    <div className="text-[11px] text-dim pl-3.5">
                      +{preview.dry_run_result.preview.length - 3} bản ghi khác…
                    </div>
                  )}
                </>
              ) : (
                <div className="text-xs text-muted italic">
                  {String(preview.dry_run_result?.preview || "Không có bản ghi xem trước")}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex items-center gap-1.5 text-[11px] text-muted mb-3 tabular-nums">
          <Clock className="w-3 h-3" />
          Hết hạn:{" "}
          {deadline.toLocaleTimeString("vi-VN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 px-3.5 pb-3">
        <button
          id="ai-widget-approve-mattermost-btn"
          type="button"
          onClick={onApprove}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-white text-xs font-semibold transition-opacity hover:opacity-90 cursor-pointer"
          style={{ background: "var(--amber)" }}
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Phê duyệt trên Mattermost
        </button>
        <button
          id="ai-widget-cancel-approval-btn"
          type="button"
          onClick={onCancel}
          className="btn-ghost btn-sm hover:!text-error hover:!border-error/40"
        >
          <XCircle className="w-3.5 h-3.5" />
          Huỷ
        </button>
      </div>
    </div>
  );
};

// ─── Main Widget Component ────────────────────────────────────────────────────

export interface AIChatWidgetProps {
  mode?: "floating" | "inline";
}

const AIChatWidgetInner: React.FC<AIChatWidgetProps> = ({ mode = "floating" }) => {
  const {
    widgetState,
    messages,
    inputValue,
    dslPreview,
    setInputValue,
    openWidget,
    minimizeWidget,
    resetAndClose,
    sendCommand,
    openMattermostApproval,
    cancelApproval,
  } = useAICommand();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isInline = mode === "inline";
  const isExpanded = isInline || widgetState !== "collapsed";

  useEffect(() => {
    if (isInline && widgetState === "collapsed") {
      openWidget();
    }
  }, [isInline, widgetState, openWidget]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, widgetState]);

  useEffect(() => {
    if (widgetState === "expanded") {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [widgetState]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendCommand();
    } else if (e.key === "Escape") {
      e.preventDefault();
      minimizeWidget();
    }
  };

  useEffect(() => {
    if (isInline) return;
    const handleGlobalKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        if (isExpanded) {
          minimizeWidget();
        } else {
          openWidget();
        }
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [isExpanded, openWidget, minimizeWidget, isInline]);

  const isInputDisabled = widgetState === "thinking" || widgetState === "awaiting_approval";
  const canSend = inputValue.trim().length > 0 && !isInputDisabled;

  return (
    <div
      id={isInline ? "ai-chat-inline-root" : "ai-chat-widget-root"}
      className={clsx(
        isInline
          ? "w-full h-full flex flex-col flex-1"
          : "fixed bottom-5 right-5 z-[90] flex flex-col items-end gap-2.5"
      )}
      role={isInline ? "region" : "complementary"}
      aria-label="Proteus AI Chat"
    >
      {/* Chat Panel */}
      <div
        id="ai-chat-panel"
        aria-hidden={!isExpanded}
        className={clsx(
          "bg-paper-white border border-line-hi overflow-hidden flex flex-col",
          isInline
            ? "w-full h-full flex-1 rounded-xl shadow-card"
            : clsx(
                "w-[380px] max-w-[calc(100vw-2.5rem)] rounded-xl shadow-modal",
                "transition-all duration-200 ease-out origin-bottom-right",
                isExpanded
                  ? "opacity-100 scale-100 translate-y-0"
                  : "opacity-0 scale-95 translate-y-3 pointer-events-none"
              )
        )}
        style={{
          height: isInline ? "100%" : isExpanded ? "500px" : "0px",
        }}
      >
        {/* Header */}
        <div className="h-[54px] flex items-center justify-between px-4 shrink-0 border-b border-line bg-paper-raised">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center border border-line"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-semibold text-ink leading-tight font-heading">
                Proteus AI
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span
                  className={clsx(
                    "w-1.5 h-1.5 rounded-full",
                    widgetState === "thinking" ? "animate-pulse" : ""
                  )}
                  style={{
                    background:
                      widgetState === "thinking" || widgetState === "awaiting_approval"
                        ? "var(--amber)"
                        : "var(--emerald)",
                  }}
                />
                <span className="text-[11px] text-dim font-medium">
                  {widgetState === "thinking"
                    ? "Đang xử lý"
                    : widgetState === "awaiting_approval"
                    ? "Chờ phê duyệt"
                    : "Sẵn sàng"}
                </span>
              </div>
            </div>
          </div>

          {!isInline && (
            <div className="flex items-center gap-1">
              <button
                id="ai-widget-minimize-btn"
                type="button"
                aria-label="Thu nhỏ widget"
                onClick={minimizeWidget}
                className="icon-btn p-1.5"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
              <button
                id="ai-widget-close-btn"
                type="button"
                aria-label="Đóng widget"
                onClick={resetAndClose}
                className="icon-btn p-1.5 hover:!text-error hover:!bg-error/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Messages Area */}
        <div
          id="ai-chat-messages"
          role="log"
          aria-live="polite"
          aria-atomic="false"
          aria-label="Lịch sử hội thoại với Proteus AI"
          className="flex-1 overflow-y-auto px-4 pt-4 pb-2 bg-paper/40"
        >
          {messages.length === 0 && widgetState !== "thinking" && !dslPreview && (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 py-8">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-3 border border-line"
                style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
              >
                <Bot className="w-5 h-5" />
              </div>
              <p className="text-sm font-semibold text-ink">Trợ lý Điều hành Proteus AI</p>
              <p className="text-xs text-muted mt-1 max-w-[260px] leading-relaxed">
                Hỏi đáp tài liệu nội bộ hoặc ra lệnh nghiệp vụ bằng tiếng Việt. Các thao tác ghi dữ liệu luôn yêu cầu phê duyệt.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {widgetState === "thinking" && (
            <div aria-hidden="true">
              <ThinkingIndicator />
            </div>
          )}

          {widgetState === "awaiting_approval" && dslPreview && (
            <DslPreviewPanel
              preview={dslPreview}
              onApprove={openMattermostApproval}
              onCancel={cancelApproval}
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="px-3.5 py-2.5 flex items-center gap-2 shrink-0 border-t border-line bg-paper-white">
          <textarea
            ref={inputRef}
            id="ai-chat-input"
            rows={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isInputDisabled}
            placeholder={
              widgetState === "awaiting_approval"
                ? "Đang chờ phê duyệt…"
                : "Nhập lệnh bằng tiếng Việt… (Enter để gửi)"
            }
            aria-label="Nhập lệnh cho AI"
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-dim resize-none outline-none leading-5 py-1.5 max-h-[60px] overflow-y-auto disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            id="ai-chat-send-btn"
            type="button"
            aria-label="Gửi lệnh"
            onClick={sendCommand}
            disabled={!canSend}
            className={clsx(
              "w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-colors",
              canSend ? "text-white cursor-pointer" : "bg-paper-subtle text-dim cursor-not-allowed"
            )}
            style={canSend ? { background: "var(--accent-solid)" } : undefined}
          >
            {widgetState === "thinking" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Floating Launcher Button */}
      {!isInline && (
        <button
          id="ai-widget-fab"
          type="button"
          aria-label={isExpanded ? "Thu nhỏ Proteus AI" : "Mở Proteus AI"}
          aria-expanded={isExpanded}
          title={isExpanded ? "Thu nhỏ" : "Mở Proteus AI (Ctrl+K)"}
          onClick={isExpanded ? resetAndClose : openWidget}
          className={clsx(
            "w-12 h-12 rounded-xl flex items-center justify-center cursor-pointer transition-all duration-150 shadow-elevated",
            isExpanded
              ? "bg-paper-white border border-line-hi text-muted hover:text-ink"
              : "text-white hover:brightness-110"
          )}
          style={!isExpanded ? { background: "var(--accent-solid)" } : undefined}
        >
          {isExpanded ? <ChevronDown className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
        </button>
      )}
    </div>
  );
};

// ─── Error Boundary ───────────────────────────────────────────────────────────

class AIChatErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logger.error("AIChatWidget Error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="fixed bottom-5 right-5 z-[90] w-[300px] rounded-xl flex flex-col items-center justify-center gap-2 p-5 bg-paper-white border border-error/40 shadow-elevated">
          <AlertTriangle className="w-7 h-7 mb-1 text-error" />
          <div className="text-sm font-semibold text-center font-heading text-ink">
            AI Chat gặp lỗi
          </div>
          <div className="text-xs text-center mb-2 text-muted">
            Đã có lỗi xảy ra trong quá trình hiển thị.
          </div>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false })}
            className="btn-ghost btn-sm"
          >
            Thử lại
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export const AIChatWidget: React.FC<AIChatWidgetProps> = ({ mode = "floating" }) => (
  <AIChatErrorBoundary>
    <AIChatWidgetInner mode={mode} />
  </AIChatErrorBoundary>
);

export const AIChatPanel: React.FC<AIChatWidgetProps> = ({ mode = "inline" }) => (
  <AIChatErrorBoundary>
    <AIChatWidgetInner mode={mode} />
  </AIChatErrorBoundary>
);
