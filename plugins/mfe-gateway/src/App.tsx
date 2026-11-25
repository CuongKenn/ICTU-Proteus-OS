// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// MFE Gateway shell — Enterprise Swiss Slate theme (light/dark), synchronized with core-engine.
// Supports seamless embed mode (?embed=1) hiding redundant topbar while preserving sub-tabs & postMessage theme sync.
import React, { useCallback, useEffect, useState } from 'react';
import { registry } from './plugins/registry';
import {
  applyTheme,
  isThemeMessage,
  isTrustedThemeOrigin,
  resolveInitialTheme,
  syncThemeUrlParam,
  toggleTheme,
  type Theme,
} from './theme';

const BASE = '/plugins-mfe';

function stripBase(pathname: string): string {
  if (pathname === BASE || pathname === `${BASE}/`) return '/';
  if (pathname.startsWith(`${BASE}/`)) return pathname.slice(BASE.length);
  return pathname;
}

function parsePath(): { pluginId: string; subPath: string } {
  const parts = stripBase(window.location.pathname).split('/').filter(Boolean);
  if (parts.length === 0) return { pluginId: '', subPath: '' };
  const [pluginId, ...rest] = parts;
  return { pluginId, subPath: rest.length ? `/${rest.join('/')}` : '' };
}

function detectEmbedMode(): boolean {
  try {
    return new URLSearchParams(window.location.search).get('embed') === '1';
  } catch {
    return false;
  }
}

/* Crisp inline SVG icons (zero emojis) */
const IconArrowLeft = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M19 12H5" />
    <path d="m12 19-7-7 7-7" />
  </svg>
);

const IconSun = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
  </svg>
);

const IconMoon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
  </svg>
);

const IconArrowUpRight = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7 7h10v10" />
    <path d="M7 17 17 7" />
  </svg>
);

const App = () => {
  const [route, setRoute] = useState(parsePath);
  const [isEmbedded] = useState<boolean>(detectEmbedMode);
  const [theme, setThemeState] = useState<Theme>(() => resolveInitialTheme());
  const [busy, setBusy] = useState(0);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    const onBusy = (e: Event) => setBusy(Number((e as CustomEvent).detail) || 0);
    window.addEventListener('mfe-busy', onBusy as EventListener);
    return () => window.removeEventListener('mfe-busy', onBusy as EventListener);
  }, []);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'proteus-theme' && (e.newValue === 'dark' || e.newValue === 'light')) {
        setThemeState(e.newValue);
      }
    };
    const onMessage = (e: MessageEvent) => {
      if (!isTrustedThemeOrigin(e.origin)) return;
      if (isThemeMessage(e.data)) {
        setThemeState(e.data.theme);
        try {
          localStorage.setItem('proteus-theme', e.data.theme);
        } catch {
          /* ignore */
        }
        syncThemeUrlParam(e.data.theme);
      }
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener('message', onMessage);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('message', onMessage);
    };
  }, []);

  useEffect(() => {
    const onNav = () => setRoute(parsePath());
    window.addEventListener('popstate', onNav);
    return () => window.removeEventListener('popstate', onNav);
  }, []);

  const navigate = useCallback(
    (to: string) => {
      const useBasePrefix =
        window.location.pathname === BASE ||
        window.location.pathname.startsWith(`${BASE}/`);

      const parsedTarget = new URL(to, window.location.origin);
      let targetPathname = parsedTarget.pathname;

      if (useBasePrefix) {
        if (targetPathname === '/') {
          targetPathname = `${BASE}/`;
        } else if (
          targetPathname !== BASE &&
          !targetPathname.startsWith(`${BASE}/`)
        ) {
          targetPathname = `${BASE}${targetPathname.startsWith('/') ? '' : '/'}${targetPathname}`;
        }
      } else if (targetPathname === BASE || targetPathname === `${BASE}/`) {
        targetPathname = '/';
      } else if (targetPathname.startsWith(`${BASE}/`)) {
        targetPathname = targetPathname.slice(BASE.length);
      }

      const currentParams = new URLSearchParams(window.location.search);
      const nextParams = new URLSearchParams(parsedTarget.search);

      if (isEmbedded || currentParams.get('embed') === '1') {
        nextParams.set('embed', '1');
      }

      const attrTheme = document.documentElement.getAttribute('data-theme');
      const urlTheme = currentParams.get('theme');
      const activeTheme =
        attrTheme === 'dark' || attrTheme === 'light'
          ? attrTheme
          : urlTheme === 'dark' || urlTheme === 'light'
            ? urlTheme
            : null;
      if (activeTheme && (isEmbedded || currentParams.has('theme'))) {
        nextParams.set('theme', activeTheme);
      }

      const queryStr = nextParams.toString();
      const finalUrl = `${targetPathname}${queryStr ? `?${queryStr}` : ''}${parsedTarget.hash}`;
      window.history.pushState(null, '', finalUrl);
      setRoute(parsePath());
    },
    [isEmbedded],
  );

  const navigateSub = useCallback(
    (sub: string) => {
      navigate(`/${route.pluginId}${sub}`);
    },
    [navigate, route.pluginId],
  );

  const onToggleTheme = () => setThemeState((t) => toggleTheme(t));

  const entry = route.pluginId ? registry.find((p) => p.code === route.pluginId) : undefined;

  return (
    <div style={{ background: 'var(--mfe-bg)', color: 'var(--mfe-text)', minHeight: '100vh' }}>
      {/* Global busy progress bar */}
      <div className="mfe-busy-track">
        {busy > 0 && <div className="mfe-busy-bar" />}
      </div>

      {/* Executive Shell Topbar — ẩn khi nhúng mượt ?embed=1 bên trong Core Engine */}
      {!isEmbedded && (
        <header className="mfe-topbar">
          {route.pluginId ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0 }}>
              <button type="button" onClick={() => navigate('/')} className="mfe-back-btn">
                <IconArrowLeft />
                <span>Tất cả phân hệ</span>
              </button>
              {entry && (
                <>
                  <span style={{ color: 'var(--mfe-line-hi)' }}>/</span>
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: '0.875rem',
                      color: 'var(--mfe-text)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {entry.displayName}
                  </span>
                </>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              <div
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: 7,
                  background: 'var(--mfe-primary)',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: 'var(--mfe-font-heading)',
                  fontWeight: 700,
                  fontSize: '0.78rem',
                }}
              >
                P
              </div>
              <span
                style={{
                  fontFamily: 'var(--mfe-font-heading)',
                  fontWeight: 700,
                  fontSize: '0.94rem',
                  letterSpacing: '-0.015em',
                }}
              >
                Proteus <span style={{ color: 'var(--mfe-accent)' }}>Modules</span>
              </span>
            </div>
          )}

          <span style={{ flex: 1 }} />

          <button
            type="button"
            className="mfe-theme-toggle"
            onClick={onToggleTheme}
            aria-label="Đổi chế độ sáng/tối"
            title={theme === 'dark' ? 'Chuyển sang sáng' : 'Chuyển sang tối'}
          >
            {theme === 'dark' ? <IconSun /> : <IconMoon />}
            <span>{theme === 'dark' ? 'Sáng' : 'Tối'}</span>
          </button>
        </header>
      )}

      {!route.pluginId && <Catalog navigate={navigate} />}
      {route.pluginId && !entry && <NotFound pluginId={route.pluginId} navigate={navigate} />}
      {route.pluginId && entry && !entry.ready && (
        <ComingSoon code={entry.code} name={entry.displayName} desc={entry.description} navigate={navigate} />
      )}
      {route.pluginId && entry && entry.ready && entry.render({ subPath: route.subPath, navigate: navigateSub })}
    </div>
  );
};

function Catalog(props: { navigate: (to: string) => void }) {
  return (
    <div className="mfe-module-shell">
      <div style={{ paddingBottom: '1.25rem', borderBottom: '1px solid var(--mfe-line)' }}>
        <h1 className="mfe-module-title" style={{ fontSize: '1.5rem' }}>
          Danh mục Phân hệ Nghiệp vụ
        </h1>
        <p className="mfe-module-desc">
          Các ứng dụng Micro-Frontend vận hành đồng bộ trên kiến trúc Proteus OS Multi-Tenant.
        </p>
      </div>

      <div className="mfe-catalog-grid">
        {registry.map((p) => (
          <button
            key={p.code}
            type="button"
            onClick={() => p.ready && props.navigate(`/${p.code}`)}
            disabled={!p.ready}
            className="mfe-catalog-card"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: '0.65rem' }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 9,
                  background: 'var(--mfe-accent-soft)',
                  color: 'var(--mfe-accent)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: 'var(--mfe-font-heading)',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                }}
              >
                {p.displayName.charAt(0)}
              </div>
              <span style={{ color: 'var(--mfe-dim)' }}>
                <IconArrowUpRight />
              </span>
            </div>

            <div style={{ fontWeight: 600, fontSize: '0.95rem', fontFamily: 'var(--mfe-font-heading)' }}>
              {p.displayName}
            </div>
            <div
              style={{
                color: 'var(--mfe-muted)',
                fontSize: '0.82rem',
                margin: '0.3rem 0 0.85rem',
                lineHeight: 1.45,
                flex: 1,
              }}
            >
              {p.description || p.code}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', paddingTop: '0.7rem', borderTop: '1px solid var(--mfe-line-soft)' }}>
              <span style={{ fontFamily: 'var(--mfe-font-mono)', fontSize: '0.72rem', color: 'var(--mfe-dim)' }}>
                {p.code}
              </span>
              <span
                className="mfe-badge"
                style={{ color: p.ready ? 'var(--mfe-success)' : 'var(--mfe-warning)' }}
              >
                <span className="mfe-badge-dot" />
                {p.ready ? 'Sẵn sàng' : 'Đang phát triển'}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function ComingSoon(props: {
  code: string;
  name: string;
  desc: string;
  navigate: (to: string) => void;
}) {
  return (
    <div style={{ padding: '4rem 1.25rem', display: 'flex', justifyContent: 'center' }}>
      <div
        style={{
          background: 'var(--mfe-panel)',
          border: '1px solid var(--mfe-line)',
          borderRadius: 12,
          padding: '2rem',
          maxWidth: 520,
          boxShadow: 'var(--mfe-shadow)',
        }}
      >
        <h2 style={{ marginTop: 0, fontFamily: 'var(--mfe-font-heading)', fontSize: '1.2rem' }}>{props.name}</h2>
        <p style={{ color: 'var(--mfe-muted)', fontSize: '0.9rem' }}>{props.desc}</p>
        <p style={{ color: 'var(--mfe-warning)', fontSize: '0.85rem' }}>
          Phân hệ <code>{props.code}</code> hiện đang trong quá trình hoàn thiện giao diện.
        </p>
        <button type="button" onClick={() => props.navigate('/')} className="mfe-btn" style={{ marginTop: '0.5rem' }}>
          <IconArrowLeft /> Quay lại danh mục
        </button>
      </div>
    </div>
  );
}

function NotFound(props: { pluginId: string; navigate: (to: string) => void }) {
  return (
    <div style={{ padding: '4rem 1.25rem', textAlign: 'center', color: 'var(--mfe-text)' }}>
      <h2 style={{ fontFamily: 'var(--mfe-font-heading)' }}>Không tìm thấy phân hệ: {props.pluginId}</h2>
      <button type="button" onClick={() => props.navigate('/')} className="mfe-btn" style={{ marginTop: '0.75rem' }}>
        <IconArrowLeft /> Về danh mục phân hệ
      </button>
    </div>
  );
}

export default App;
