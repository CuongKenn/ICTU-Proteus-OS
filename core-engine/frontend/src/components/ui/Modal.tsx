// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

"use client";

import React, { useEffect, useState } from "react";
import { X, Loader2 } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
  /** Optional confirm action */
  onConfirm?: () => void;
  confirmLabel?: string;
  confirmVariant?: string;
  isConfirmLoading?: boolean;
  /** If set, user must type this keyword to enable confirm */
  confirmKeyword?: string;
}

const MAX_WIDTH_MAP: Record<string, string> = {
  sm: "384px",
  md: "448px",
  lg: "512px",
  xl: "576px",
  "2xl": "672px",
  "3xl": "768px",
  "4xl": "896px",
  "5xl": "1024px",
  "6xl": "1152px",
  "7xl": "1280px",
  full: "100%",
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = "480px",
  onConfirm,
  confirmLabel = "Xác nhận",
  confirmVariant = "accent",
  isConfirmLoading = false,
  confirmKeyword,
}) => {
  const [keywordInput, setKeywordInput] = useState("");

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) setKeywordInput("");
  }, [isOpen]);

  if (!isOpen) return null;

  const isConfirmEnabled = confirmKeyword ? keywordInput === confirmKeyword : true;
  const btnClass = confirmVariant === "danger" ? "btn-danger" : "btn-accent";

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-slate-950/45 backdrop-blur-[2px] animate-fade-in"
        onClick={onClose}
      />

      {/* Dialog Surface */}
      <div
        className="relative w-full rounded-xl bg-paper-white border border-line-hi shadow-modal animate-scale-in overflow-hidden flex flex-col max-h-[90vh]"
        style={{ maxWidth: MAX_WIDTH_MAP[maxWidth] || maxWidth }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line shrink-0">
          <h2 className="text-base font-heading font-semibold text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="icon-btn p-1.5 -mr-1.5"
            aria-label="Đóng hộp thoại"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 text-sm text-ink-soft overflow-y-auto">
          {children}
        </div>

        {/* Footer */}
        {onConfirm && (
          <div className="px-6 py-4 flex flex-col sm:flex-row sm:items-end justify-end gap-3 border-t border-line bg-paper-subtle/40 shrink-0">
            {confirmKeyword && (
              <div className="flex-1 w-full">
                <p className="text-xs text-muted mb-1.5">
                  Nhập <strong className="text-ink font-mono">{confirmKeyword}</strong> để xác nhận:
                </p>
                <input
                  type="text"
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  className="input-field text-sm"
                  placeholder={confirmKeyword}
                />
              </div>
            )}
            <div className="flex items-center justify-end gap-2 shrink-0">
              <button type="button" onClick={onClose} className="btn-ghost">
                Hủy
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={!isConfirmEnabled || isConfirmLoading}
                className={btnClass}
                style={!isConfirmEnabled ? { opacity: 0.5, cursor: "not-allowed" } : undefined}
              >
                {isConfirmLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : confirmLabel}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
