// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Enterprise MFE UI primitives for crm-module (powered by theme.css v4.0).
import React, { useEffect } from 'react';

const IconSearch = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const IconClose = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
);

export const C = {
  bg: 'var(--mfe-bg)',
  panel: 'var(--mfe-panel)',
  line: 'var(--mfe-line)',
  text: 'var(--mfe-text)',
  muted: 'var(--mfe-muted)',
  accent: 'var(--mfe-accent)',
  green: 'var(--mfe-success)',
  amber: 'var(--mfe-warning)',
  red: 'var(--mfe-danger)',
};

export function StatCard(props: { label: string; value: string; sub?: string }) {
  return (
    <div className="mfe-stat">
      <div className="mfe-stat-label">{props.label}</div>
      <div className="mfe-stat-value">{props.value}</div>
      {props.sub && <div className="mfe-stat-sub">{props.sub}</div>}
    </div>
  );
}

export function Pill(props: { text: string; color: string }) {
  return (
    <span className="mfe-badge" style={{ color: props.color }}>
      <span className="mfe-badge-dot" />
      {props.text}
    </span>
  );
}

export function SimpleBadge(props: { text: string; color: string }) {
  return <Pill text={props.text} color={props.color} />;
}

export function Toolbar(props: {
  search: string;
  onSearch: (v: string) => void;
  children?: React.ReactNode;
  placeholder?: string;
}) {
  return (
    <div className="mfe-toolbar">
      <div className="mfe-search-wrap">
        <span className="mfe-search-icon">
          <IconSearch />
        </span>
        <input
          value={props.search}
          onChange={(e) => props.onSearch(e.target.value)}
          placeholder={props.placeholder ?? 'Tìm kiếm...'}
          className="mfe-input mfe-input--search"
        />
      </div>
      {props.children}
    </div>
  );
}

export function Btn(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean }) {
  const { primary, className, style, type, ...rest } = props;
  const cls = [primary ? 'mfe-btn mfe-btn--primary' : 'mfe-btn', className].filter(Boolean).join(' ');
  return <button type={type ?? 'button'} {...rest} className={cls} style={style} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className, style, ...rest } = props;
  const cls = ['mfe-select', className].filter(Boolean).join(' ');
  return <select {...rest} className={cls} style={style} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className, style, ...rest } = props;
  const cls = ['mfe-input', className].filter(Boolean).join(' ');
  return <input {...rest} className={cls} style={style} />;
}

export function Modal(props: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') props.onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [props]);

  return (
    <div onClick={props.onClose} className="mfe-modal-overlay" role="dialog" aria-modal="true" aria-label={props.title}>
      <div onClick={(e) => e.stopPropagation()} className="mfe-modal">
        <div className="mfe-modal-header">
          <h3 className="mfe-modal-title">{props.title}</h3>
          <button type="button" onClick={props.onClose} className="mfe-modal-close" aria-label="Đóng">
            <IconClose />
          </button>
        </div>
        <div className="mfe-modal-body">{props.children}</div>
      </div>
    </div>
  );
}

export function TableWrap(props: { children: React.ReactNode }) {
  return (
    <div className="mfe-table-wrap">
      <table className="mfe-table">{props.children}</table>
    </div>
  );
}

export function DataSourceBar(props: {
  mode: 'live' | 'demo' | null;
  reasonText: string | null;
  message?: string;
}) {
  if (props.mode !== 'demo') return null;
  return (
    <div className="mfe-demo-banner">
      <span className="mfe-badge-dot" />
      <span>
        Dữ liệu mẫu{props.reasonText ? ' · ' + props.reasonText : ''}
        {props.message ? ' (' + props.message + ')' : ''}
      </span>
    </div>
  );
}

export function InlineError(props: { text: string | null; onClose?: () => void }) {
  if (!props.text) return null;
  return (
    <div className="mfe-alert-error" role="alert">
      <span>{props.text}</span>
      {props.onClose && (
        <button
          type="button"
          onClick={props.onClose}
          className="mfe-modal-close"
          style={{ color: 'var(--mfe-danger)' }}
          aria-label="Đóng thông báo lỗi"
        >
          <IconClose />
        </button>
      )}
    </div>
  );
}

export const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.7rem 0.95rem',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--mfe-muted)',
  borderBottom: '1px solid var(--mfe-line)',
  background: 'var(--mfe-bg-soft)',
  whiteSpace: 'nowrap',
};

export const td: React.CSSProperties = {
  padding: '0.75rem 0.95rem',
  borderBottom: '1px solid var(--mfe-line-soft)',
  verticalAlign: 'middle',
};
