// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// hr-module — Enterprise Micro-Frontend root shell.
import React from 'react';
import { hrMeta } from './meta';
import { Dashboard } from './pages/Dashboard';
import { EmployeesPage } from './pages/EmployeesPage';
import { LeavesPage } from './pages/LeavesPage';
import { DepartmentsPage } from './pages/DepartmentsPage';
import { RecruitmentPage } from './pages/RecruitmentPage';
import { resetStoreCache } from './lib/repo';
import { useStore } from './lib/useStore';

export function HrModuleApp(props: { subPath: string; navigate: (sub: string) => void }) {
  const route = (props.subPath || '').replace(/^\/+|\/+$/g, '');
  const { mode } = useStore();
  return (
    <div className="mfe-module-shell">
      <header className="mfe-module-header">
        <div className="mfe-module-header-top">
          <div>
            <h2 className="mfe-module-title">{hrMeta.displayName}</h2>
            <p className="mfe-module-desc">{hrMeta.description}</p>
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
        <nav className="mfe-tabs" aria-label={hrMeta.displayName}>
          {hrMeta.routes.map((r) => {
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
      {route === 'employees' && <EmployeesPage />}
      {route === 'leaves' && <LeavesPage />}
      {route === 'departments' && <DepartmentsPage />}
      {route === 'recruitment' && <RecruitmentPage />}
      {!['', 'employees', 'leaves', 'departments', 'recruitment'].includes(route) && (
        <p style={{ color: 'var(--mfe-muted)' }}>Trang không tồn tại: /{route}</p>
      )}
    </div>
  );
}

export default HrModuleApp;
