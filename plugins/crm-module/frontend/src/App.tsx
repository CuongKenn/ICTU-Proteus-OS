// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// crm-module — Enterprise Micro-Frontend root shell.
import React from 'react';
import { crmMeta } from './meta';
import { Dashboard } from './pages/Dashboard';
import { LeadsPage } from './pages/LeadsPage';
import { OpportunitiesPage } from './pages/OpportunitiesPage';
import { CustomersPage } from './pages/CustomersPage';
import { TicketsPage } from './pages/TicketsPage';
import { resetStoreCache } from './lib/repo';
import { useStore } from './lib/useStore';

export function CrmModuleApp(props: { subPath: string; navigate: (sub: string) => void }) {
  const route = (props.subPath || '').replace(/^\/+|\/+$/g, '');
  const { mode } = useStore();
  return (
    <div className="mfe-module-shell">
      <header className="mfe-module-header">
        <div className="mfe-module-header-top">
          <div>
            <h2 className="mfe-module-title">{crmMeta.displayName}</h2>
            <p className="mfe-module-desc">{crmMeta.description}</p>
          </div>
          {mode !== 'live' && (
            <button
              type="button"
              onClick={() => {
                resetStoreCache();
                window.location.reload();
              }}
              title="Xóa localStorage demo, dò lại API"
              className="mfe-reset-btn"
            >
              Reset demo
            </button>
          )}
        </div>
        <nav className="mfe-tabs" aria-label={crmMeta.displayName}>
          {crmMeta.routes.map((r) => {
            const active = route === r.path;
            return (
              <button
                key={r.path}
                type="button"
                onClick={() => props.navigate(r.path ? `/${r.path}` : '')}
                className={active ? 'mfe-tab mfe-tab--active' : 'mfe-tab'}
                aria-current={active ? 'page' : undefined}
              >
                {r.label}
              </button>
            );
          })}
        </nav>
      </header>
      {route === '' && <Dashboard />}
      {route === 'leads' && <LeadsPage />}
      {route === 'opportunities' && <OpportunitiesPage />}
      {route === 'customers' && <CustomersPage />}
      {route === 'tickets' && <TicketsPage />}
      {!['', 'leads', 'opportunities', 'customers', 'tickets'].includes(route) && (
        <p style={{ color: 'var(--mfe-muted)' }}>Trang không tồn tại: /{route}</p>
      )}
    </div>
  );
}

export default CrmModuleApp;
