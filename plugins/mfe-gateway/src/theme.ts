// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Theme bootstrap cho MFE gateway. Dùng CHUNG key localStorage với core-engine
// ("proteus-theme") nên khi gateway chạy same-origin ( /plugins-mfe ) nó tự
// đồng bộ theo theme của app chính. Hỗ trợ thêm:
//   - ?theme=dark|light trên URL (khi nhúng iframe)
//   - postMessage { type: "proteus-theme", theme }
//   - storage event (đổi theme ở tab/app chính cùng origin)
//   - prefers-color-scheme lần đầu

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'proteus-theme';

function isTheme(v: unknown): v is Theme {
  return v === 'dark' || v === 'light';
}

function fromQuery(): Theme | null {
  try {
    const v = new URLSearchParams(window.location.search).get('theme');
    return isTheme(v) ? v : null;
  } catch {
    return null;
  }
}

function fromStorage(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return isTheme(v) ? v : null;
  } catch {
    return null;
  }
}

export function resolveInitialTheme(): Theme {
  return (
    fromQuery() ??
    fromStorage() ??
    (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  );
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.style.backgroundColor =
    theme === 'dark' ? '#0B1120' : '#F8FAFC';
  document.documentElement.style.colorScheme = theme;
}

export function syncThemeUrlParam(theme: Theme): void {
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get('theme') !== theme) {
      url.searchParams.set('theme', theme);
      window.history.replaceState(
        window.history.state,
        '',
        `${url.pathname}${url.search}${url.hash}`
      );
    }
  } catch {
    /* ignore */
  }
}

export function isTrustedThemeOrigin(origin: string): boolean {
  if (!origin || origin === window.location.origin) return true;
  try {
    const incomingHost = new URL(origin).hostname;
    const currentHost = window.location.hostname;
    if (incomingHost === currentHost) return true;
    if (
      `plugins.${incomingHost}` === currentHost ||
      incomingHost === `plugins.${currentHost}`
    ) {
      return true;
    }
    if (
      (incomingHost === 'localhost' || incomingHost === '127.0.0.1') &&
      (currentHost === 'localhost' || currentHost === '127.0.0.1')
    ) {
      return true;
    }
    if (
      incomingHost.endsWith('.proteus.local') ||
      incomingHost === 'proteus.local'
    ) {
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

export function isThemeMessage(
  data: unknown
): data is { type: string; theme: Theme } {
  if (!data || typeof data !== 'object') return false;
  const msg = data as { type?: unknown; theme?: unknown };
  return (
    (msg.type === 'proteus-theme' || msg.type === 'PROTEUS_THEME_CHANGE') &&
    isTheme(msg.theme)
  );
}

/** Đổi theme + phát cho app chính (postMessage) để đồng bộ 2 chiều. */
export function setTheme(theme: Theme): void {
  applyTheme(theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
  try {
    const currentSearch = new URLSearchParams(window.location.search);
    if (currentSearch.get('embed') === '1' || currentSearch.has('theme')) {
      syncThemeUrlParam(theme);
    }
  } catch {
    /* ignore */
  }
  try {
    window.parent?.postMessage({ type: 'proteus-theme', theme }, '*');
  } catch {
    /* ignore */
  }
}

export function toggleTheme(current: Theme): Theme {
  const next: Theme = current === 'dark' ? 'light' : 'dark';
  setTheme(next);
  return next;
}

/** Khởi tạo theme + lắng nghe thay đổi từ ngoài (storage/message). */
export function initTheme(): Theme {
  const queryTheme = fromQuery();
  const initial = resolveInitialTheme();
  applyTheme(initial);
  if (queryTheme) {
    try {
      localStorage.setItem(STORAGE_KEY, queryTheme);
    } catch {
      /* ignore */
    }
  }

  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY && isTheme(e.newValue)) applyTheme(e.newValue);
  });

  window.addEventListener('message', (e) => {
    if (!isTrustedThemeOrigin(e.origin)) return;
    if (isThemeMessage(e.data)) {
      applyTheme(e.data.theme);
      try {
        localStorage.setItem(STORAGE_KEY, e.data.theme);
      } catch {
        /* ignore */
      }
      syncThemeUrlParam(e.data.theme);
    }
  });

  return initial;
}
