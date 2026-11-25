// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// AIWorkspaceClient — Trung tâm Điều hành Glass-box AI & Lịch sử Phiên hội thoại (#874)

"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Plus,
  MessageSquare,
  ShieldCheck,
  Terminal,
  Lock,
  GitBranch,
  RefreshCw,
  Clock,
} from "lucide-react";
import { clsx } from "clsx";
import { AIChatPanel } from "@/components/AIChatWidget";
import { ChatMessage, uuid } from "@/hooks/useAICommand";

interface SessionSummary {
  id: string;
  title?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface RawSessionMessage {
  id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  created_at?: string | null;
}

function formatSafeSessionTime(raw?: string | null): string {
  if (!raw) return "Vừa xong";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "Gần đây";
  return d.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const AIWorkspaceClient: React.FC = () => {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState<boolean>(true);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => uuid());
  const [loadedMessages, setLoadedMessages] = useState<ChatMessage[] | undefined>(
    undefined
  );
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  const fetchSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const res = await fetch("/api/proxy/v1/ai/sessions", {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setSessions(data);
        }
      }
    } catch {
      // Giữ danh sách hiện tại nếu offline
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleNewSession = () => {
    const nextId = uuid();
    setActiveSessionId(nextId);
    setLoadedMessages([]);
  };

  const handleSelectSession = async (session: SessionSummary) => {
    setActiveSessionId(session.id);
    setIsLoadingHistory(true);
    try {
      const res = await fetch(
        `/api/proxy/v1/ai/sessions/${encodeURIComponent(session.id)}/messages`,
        {
          method: "GET",
          headers: { Accept: "application/json" },
        }
      );
      if (res.ok) {
        const rows = (await res.json()) as RawSessionMessage[];
        if (Array.isArray(rows)) {
          const mapped: ChatMessage[] = rows.map((r) => {
            const parsedDate = r.created_at ? new Date(r.created_at) : new Date();
            const safeDate = Number.isNaN(parsedDate.getTime())
              ? new Date()
              : parsedDate;
            const normalizedRole =
              r.role === "user" || r.role === "assistant" || r.role === "system"
                ? r.role
                : "assistant";
            return {
              id: r.id || uuid(),
              role: normalizedRole,
              content: r.content || "",
              timestamp: safeDate,
            };
          });
          setLoadedMessages(mapped);
        }
      }
    } catch {
      // Bỏ qua nếu không tải được lịch sử chi tiết
    } finally {
      setIsLoadingHistory(false);
    }
  };

  return (
    <div className="w-full h-[calc(100vh-76px)] p-4 md:p-6 max-w-[1380px] mx-auto flex flex-col lg:flex-row gap-4">
      {/* Left Column: Sessions Sidebar & Glass-box Governance Card */}
      <aside
        aria-label="Danh sách phiên hội thoại AI"
        className="w-full lg:w-[300px] xl:w-[320px] shrink-0 flex flex-col gap-3 lg:h-full max-h-[280px] lg:max-h-none"
      >
        <div className="bg-paper-white border border-line-hi rounded-xl shadow-card flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Sidebar Header */}
          <div className="p-3.5 border-b border-line bg-paper-raised flex items-center justify-between gap-2">
            <div>
              <h1 className="text-sm font-heading font-semibold text-ink">
                Phiên hội thoại
              </h1>
              <p className="text-[11px] text-dim">Bộ nhớ ngữ cảnh theo Tenant</p>
            </div>
            <button
              type="button"
              onClick={fetchSessions}
              title="Làm mới danh sách phiên"
              className="icon-btn p-1.5"
            >
              <RefreshCw
                className={clsx("w-3.5 h-3.5", isLoadingSessions && "animate-spin")}
              />
            </button>
          </div>

          {/* New Session Button */}
          <div className="p-3 border-b border-line">
            <button
              type="button"
              onClick={handleNewSession}
              className="w-full btn-accent justify-center text-xs py-2"
            >
              <Plus className="w-4 h-4" />
              + Phiên hội thoại mới
            </button>
          </div>

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {isLoadingSessions && sessions.length === 0 ? (
              <div className="space-y-2 p-2">
                {[0, 1, 2].map((idx) => (
                  <div
                    key={idx}
                    className="h-12 rounded-lg bg-paper-subtle animate-pulse"
                  />
                ))}
              </div>
            ) : sessions.length === 0 ? (
              <div className="px-3 py-6 text-center">
                <MessageSquare className="w-6 h-6 text-dim mx-auto mb-2" />
                <p className="text-xs font-medium text-ink-soft">
                  Chưa có phiên lưu trữ
                </p>
                <p className="text-[11px] text-dim mt-0.5 leading-relaxed">
                  Gửi câu hỏi đầu tiên hoặc chọn gợi ý bên phải để khởi tạo bộ nhớ phiên.
                </p>
              </div>
            ) : (
              sessions.map((session) => {
                const isSelected = session.id === activeSessionId;
                const displayTitle =
                  session.title?.trim() ||
                  `Phiên #${String(session.id).slice(0, 8)}`;
                return (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => handleSelectSession(session)}
                    className={clsx(
                      "w-full text-left px-3 py-2.5 rounded-lg border transition-all cursor-pointer flex flex-col gap-1",
                      isSelected
                        ? "bg-accent-soft border-accent/35 text-ink"
                        : "bg-transparent border-transparent hover:bg-paper-subtle hover:border-line text-ink-soft"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquare
                        className={clsx(
                          "w-3.5 h-3.5 shrink-0",
                          isSelected ? "text-accent" : "text-dim"
                        )}
                      />
                      <span className="text-xs font-medium truncate">
                        {displayTitle}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 pl-5 text-[10.5px] text-dim tabular-nums">
                      <Clock className="w-3 h-3" />
                      <span>
                        {formatSafeSessionTime(
                          session.updated_at || session.created_at
                        )}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Glass-box AI / Z3 Poka-yoke Summary Card */}
        <div className="hidden lg:flex flex-col gap-2.5 p-3.5 rounded-xl bg-paper-white border border-line-hi shadow-card shrink-0">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center border border-line"
              style={{
                background: "var(--emerald-fill)",
                color: "var(--emerald)",
              }}
            >
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-heading font-semibold text-ink">
                Glass-box AI Governance
              </div>
              <div className="text-[10.5px] text-dim">
                Kiểm chứng toán học Z3 Poka-yoke
              </div>
            </div>
          </div>

          <div className="space-y-1.5 text-[11px] text-ink-soft pt-1 border-t border-line">
            <div className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-accent shrink-0" />
              <span>
                <strong>NL → DX-DSL:</strong> Chuẩn hóa ý định tường minh
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Lock className="w-3.5 h-3.5 text-accent shrink-0" />
              <span>
                <strong>RBAC & RLS:</strong> Cô lập tuyệt đối theo Tenant
              </span>
            </div>
            <div className="flex items-center gap-2">
              <ShieldCheck
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: "var(--emerald)" }}
              />
              <span>
                <strong>Z3 SMT Solver:</strong> Chặn lệnh vi phạm bất biến
              </span>
            </div>
            <div className="flex items-center gap-2">
              <GitBranch
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: "var(--amber)" }}
              />
              <span>
                <strong>HITL Mattermost:</strong> Con người giữ quyền phê duyệt
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Right Column: Main Inline AI Console */}
      <main className="flex-1 min-w-0 h-full flex flex-col relative">
        {isLoadingHistory && (
          <div className="absolute inset-0 z-10 bg-paper/60 backdrop-blur-[1px] rounded-xl flex items-center justify-center">
            <span className="text-xs font-medium text-muted px-3 py-1.5 rounded-lg bg-paper-white border border-line shadow-card">
              Đang nạp lịch sử phiên hội thoại…
            </span>
          </div>
        )}
        <AIChatPanel
          mode="inline"
          externalSessionId={activeSessionId}
          externalMessages={loadedMessages}
          onTurnCompleted={() => fetchSessions()}
        />
      </main>
    </div>
  );
};
