// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// AIChatWidget — Enterprise Glass-box AI Assistant (Floating & Full-Page Inline)
// Theme-aware (Light & Dark), Z3 Formal Proof Governance, 4-Step Pipeline & HITL DSL preview.

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
  ShieldCheck,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { clsx } from "clsx";
import {
  useAICommand,
  ChatMessage,
  DslPreview,
  Z3Verification,
  UseAICommandOptions,
} from "@/hooks/useAICommand";
import { logger } from "@/lib/logger";

// ─── Prompt Starters (4 năng lực cốt lõi) ────────────────────────────────────

export interface PromptStarterItem {
  id: string;
  label: string;
  tag: string;
  prompt: string;
}

export const PROMPT_STARTERS: PromptStarterItem[] = [
  {
    id: "starter-rag",
    label: "Tra cứu quy định nghỉ phép năm",
    tag: "RAG Tri thức",
    prompt: "Tra cứu quy định nghỉ phép năm",
  },
  {
    id: "starter-read",
    label: "Thống kê nhân sự theo phòng ban",
    tag: "Truy vấn read",
    prompt: "Thống kê nhân sự theo phòng ban",
  },
  {
    id: "starter-write",
    label: "Tạo đề xuất mua 5 màn hình Lab giá 35 triệu",
    tag: "Write + HITL",
    prompt: "Tạo đề xuất mua 5 màn hình Lab giá 35 triệu",
  },
  {
    id: "starter-z3-unsat",
    label: "Chuyển thiết bị từ Phòng C1-202 sang Phòng C1-202",
    tag: "Poka-yoke Z3",
    prompt: "Chuyển thiết bị từ Phòng C1-202 sang Phòng C1-202",
  },
];

// ─── Glass-box Governance Sub-components ──────────────────────────────────────

const PIPELINE_STEPS = [
  { num: "①", label: "NL → DX-DSL" },
  { num: "②", label: "RBAC & RLS" },
  { num: "③", label: "Z3 SMT Proof" },
  { num: "④", label: "Dry-Run / HITL" },
] as const;

const GlassboxPipelineBar: React.FC<{
  z3Status?: "SAT" | "UNSAT";
  awaitingHitl?: boolean;
}> = ({ z3Status, awaitingHitl }) => {
  const isBlockedAtZ3 = z3Status === "UNSAT";

  return (
    <div
      className="flex flex-wrap items-center gap-1 py-1.5 px-2.5 rounded-lg bg-paper-white/80 border border-line text-[10.5px] font-medium"
      aria-label="Chuỗi kiểm định Glass-box AI 4 bước"
    >
      {PIPELINE_STEPS.map((step, idx) => {
        const isZ3Step = idx === 2;
        const isHitlStep = idx === 3;

        let stepStyle = "text-emerald-700 dark:text-emerald-400";
        if (isBlockedAtZ3 && isZ3Step) {
          stepStyle = "text-rose-700 dark:text-rose-400 font-semibold";
        } else if (isBlockedAtZ3 && isHitlStep) {
          stepStyle = "text-dim line-through";
        } else if (awaitingHitl && isHitlStep) {
          stepStyle = "text-amber-700 dark:text-amber-400 font-semibold";
        }

        return (
          <React.Fragment key={step.label}>
            <span className={clsx("inline-flex items-center gap-1", stepStyle)}>
              <span>{step.num}</span>
              <span>{step.label}</span>
            </span>
            {idx < PIPELINE_STEPS.length - 1 && (
              <span className="text-ghost select-none px-0.5">·</span>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

const Z3VerificationBadge: React.FC<{
  z3?: Z3Verification;
  fallbackSat?: boolean;
  effect?: "read" | "write" | "critical";
}> = ({ z3, fallbackSat = false, effect }) => {
  if (!z3 && !fallbackSat) return null;

  if (z3?.status === "UNSAT") {
    return (
      <div
        role="alert"
        className="mt-2 rounded-lg border p-2.5 text-xs"
        style={{
          background: "var(--rose-fill)",
          borderColor: "rgba(190, 18, 60, 0.35)",
          color: "var(--rose)",
        }}
      >
        <div className="flex items-center gap-1.5 font-bold tracking-tight">
          <ShieldAlert className="w-4 h-4 shrink-0" />
          <span>⛔ POKA-YOKE Z3 BLOCKED (UNSAT)</span>
        </div>
        {z3.violated_constraint && (
          <div className="mt-1.5 px-2 py-1.5 rounded bg-paper-white/90 border border-rose-500/25 font-mono text-[11px] text-ink break-words">
            <span className="text-muted mr-1">∀ Vi phạm bất biến:</span>
            <code>{z3.violated_constraint}</code>
          </div>
        )}
        {z3.invariants_checked && z3.invariants_checked.length > 0 && (
          <div className="mt-1 text-[10.5px] opacity-90">
            Ràng buộc đã quét: {z3.invariants_checked.join(", ")}
          </div>
        )}
      </div>
    );
  }

  const solveTimeSuffix =
    z3?.solve_time_ms !== undefined ? ` (${z3.solve_time_ms}ms)` : "";
  const invariantsTooltip =
    z3?.invariants_checked && z3.invariants_checked.length > 0
      ? `Bất biến đã kiểm chứng: ${z3.invariants_checked.join(", ")}`
      : "Đã kiểm chứng tính đúng đắn hình thức qua Z3 Theorem Prover";
  const isDualApproval = Boolean(z3?.escalated_to_critical || effect === "critical");

  return (
    <div className="mt-2 flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          title={invariantsTooltip}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold border"
          style={{
            background: "var(--emerald-fill)",
            borderColor: "rgba(5, 150, 105, 0.3)",
            color: "var(--emerald)",
          }}
        >
          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
          <span>{`🛡️ Z3 Formal Proof: SAT${solveTimeSuffix}`}</span>
        </span>

        {isDualApproval && (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10.5px] font-semibold border"
            style={{
              background: "var(--rose-fill)",
              borderColor: "rgba(190, 18, 60, 0.28)",
              color: "var(--rose)",
            }}
          >
            Phê duyệt kép 2 cấp
          </span>
        )}
      </div>

      {z3?.invariants_checked && z3.invariants_checked.length > 0 && (
        <div className="text-[10.5px] text-muted font-mono truncate" title={invariantsTooltip}>
          ✓ Bất biến: {z3.invariants_checked.join(" · ")}
        </div>
      )}
    </div>
  );
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const ThinkingIndicator: React.FC<{ statusText?: string | null }> = ({ statusText }) => (
  <div className="flex items-center gap-1.5 px-3 py-2.5">
    <span className="text-xs mr-1.5 font-medium text-dim">
      {statusText || "Đang phân tích"}
    </span>
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
  const showGovernance = !isUser && Boolean(message.show_pipeline || message.z3_verification);

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
          "max-w-[85%] rounded-xl px-3.5 py-2.5 text-[13.5px] leading-relaxed",
          isUser
            ? "text-white rounded-tr-sm"
            : "bg-paper-subtle border border-line text-ink rounded-tl-sm"
        )}
        style={isUser ? { background: "var(--accent-solid)" } : undefined}
      >
        {showGovernance && (
          <div className="mb-2">
            <GlassboxPipelineBar
              z3Status={message.z3_verification?.status ?? "SAT"}
              awaitingHitl={
                (message.effect === "write" || message.effect === "critical") &&
                message.z3_verification?.status !== "UNSAT"
              }
            />
          </div>
        )}

        {renderMessageContent(message.content, isUser)}

        {showGovernance && (
          <Z3VerificationBadge
            z3={message.z3_verification}
            fallbackSat={!message.z3_verification}
            effect={message.effect}
          />
        )}

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
  const hasValidDeadline =
    Boolean(preview.approval_deadline) &&
    !Number.isNaN(new Date(preview.approval_deadline as string).getTime());
  const deadlineText = hasValidDeadline
    ? new Date(preview.approval_deadline as string).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "30 phút";
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

      {/* Pipeline 4 bước & Huy hiệu Z3 */}
      <div className="px-3.5 pt-3">
        <GlassboxPipelineBar
          z3Status={preview.z3_verification?.status ?? "SAT"}
          awaitingHitl={preview.z3_verification?.status !== "UNSAT"}
        />
        <Z3VerificationBadge
          z3={preview.z3_verification}
          fallbackSat={!preview.z3_verification}
          effect={preview.effect}
        />

        <div className="flex items-center gap-1.5 mt-2.5 mb-2">
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
          {hasValidDeadline ? `Hết hạn: ${deadlineText}` : `Thời hạn phê duyệt: ${deadlineText}`}
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

export interface AIChatWidgetProps extends UseAICommandOptions {
  mode?: "floating" | "inline";
}

const AIChatWidgetInner: React.FC<AIChatWidgetProps> = ({
  mode = "floating",
  enableStream,
  externalSessionId,
  externalMessages,
  onTurnCompleted,
}) => {
  const {
    widgetState,
    messages,
    inputValue,
    dslPreview,
    streamStatus,
    setInputValue,
    openWidget,
    minimizeWidget,
    resetAndClose,
    sendCommand,
    openMattermostApproval,
    cancelApproval,
  } = useAICommand({
    enableStream,
    externalSessionId,
    externalMessages,
    onTurnCompleted,
  });

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

  const handleStarterClick = (prompt: string) => {
    if (isInputDisabled) return;
    sendCommand(prompt);
  };

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
                "w-[395px] max-w-[calc(100vw-2.5rem)] rounded-xl shadow-modal",
                "transition-all duration-200 ease-out origin-bottom-right",
                isExpanded
                  ? "opacity-100 scale-100 translate-y-0"
                  : "opacity-0 scale-95 translate-y-3 pointer-events-none"
              )
        )}
        style={{
          height: isInline ? "100%" : isExpanded ? "530px" : "0px",
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
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-semibold text-ink leading-tight font-heading">
                  Proteus AI
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-paper-subtle border border-line text-muted">
                  Z3 Glass-box
                </span>
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
            <div className="min-h-full flex flex-col items-center justify-center text-center px-2 py-5">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-3 border border-line"
                style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
              >
                <Bot className="w-5 h-5" />
              </div>
              <p className="text-sm font-semibold text-ink">Trợ lý Điều hành Proteus AI</p>
              <p className="text-xs text-muted mt-1 max-w-[300px] leading-relaxed">
                Mọi yêu cầu đều được kiểm chứng qua 4 lớp: NL → DX-DSL · RBAC/RLS · Z3 SMT Proof · Dry-Run/HITL.
              </p>

              {/* 4 Prompt Starters (1-chạm) */}
              <div
                className={clsx(
                  "w-full mt-4 grid gap-2 text-left",
                  isInline ? "grid-cols-1 sm:grid-cols-2 max-w-2xl" : "grid-cols-1"
                )}
              >
                {PROMPT_STARTERS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleStarterClick(item.prompt)}
                    className="group flex flex-col gap-1 p-2.5 rounded-xl bg-paper-white hover:bg-paper-subtle border border-line hover:border-accent/40 transition-all text-left cursor-pointer"
                  >
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-accent uppercase tracking-wider">
                      <Sparkles className="w-3 h-3 shrink-0" />
                      {item.tag}
                    </span>
                    <span className="text-xs font-medium text-ink group-hover:text-accent transition-colors leading-snug">
                      {item.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {widgetState === "thinking" && (
            <div aria-hidden="true">
              <ThinkingIndicator statusText={streamStatus} />
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

        {/* Compact Quick Action Strip when conversation is active */}
        {messages.length > 0 && !isInputDisabled && (
          <div className="px-3.5 py-1.5 flex items-center gap-1.5 overflow-x-auto border-t border-line bg-paper-subtle/50 shrink-0">
            {PROMPT_STARTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => handleStarterClick(item.prompt)}
                title={item.label}
                className="shrink-0 text-[11px] px-2.5 py-1 rounded-full bg-paper-white border border-line hover:border-accent/50 text-ink-soft hover:text-accent transition-colors cursor-pointer"
              >
                {item.tag}
              </button>
            ))}
          </div>
        )}

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
            onClick={() => sendCommand()}
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
          onClick={isExpanded ? minimizeWidget : openWidget}
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

interface AIChatErrorBoundaryProps {
  children: React.ReactNode;
  mode?: "floating" | "inline";
}

class AIChatErrorBoundary extends React.Component<
  AIChatErrorBoundaryProps,
  { hasError: boolean }
> {
  constructor(props: AIChatErrorBoundaryProps) {
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
      const isInline = this.props.mode === "inline";
      return (
        <div
          className={clsx(
            "rounded-xl flex flex-col items-center justify-center gap-2 p-5 bg-paper-white border border-error/40 shadow-elevated",
            isInline
              ? "w-full max-w-md mx-auto my-8"
              : "fixed bottom-5 right-5 z-[90] w-[300px]"
          )}
        >
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

export const AIChatWidget: React.FC<AIChatWidgetProps> = (props) => (
  <AIChatErrorBoundary mode={props.mode ?? "floating"}>
    <AIChatWidgetInner {...props} mode={props.mode ?? "floating"} />
  </AIChatErrorBoundary>
);

export const AIChatPanel: React.FC<AIChatWidgetProps> = (props) => (
  <AIChatErrorBoundary mode={props.mode ?? "inline"}>
    <AIChatWidgetInner {...props} mode={props.mode ?? "inline"} />
  </AIChatErrorBoundary>
);
