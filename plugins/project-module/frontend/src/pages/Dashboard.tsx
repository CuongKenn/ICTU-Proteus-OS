// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Project Module — Tổng quan: KPI dự án/task + tiến độ + task sắp hạn.
import React, { useEffect, useState } from 'react';
import { PROJECT_STATUS_LABEL, formatVND, type Milestone, type Project, type ProjectTask } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { C, DataSourceBar, InlineError, StatCard, TableWrap, td, th } from '../components/ui';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [p, t, m] = await Promise.all([
          store.listProjects(),
          store.listTasks(),
          store.listMilestones(),
        ]);
        if (!cancelled) {
          setProjects(p);
          setTasks(t);
          setMilestones(m);
        }
      } catch (e) {
        if (!cancelled) setError(errText(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [store]);

  if (!store || loading) return <p style={{ color: C.muted }}>Đang tải...</p>;

  const active = projects.filter((p) => p.status === 'ACTIVE').length;
  const doneTasks = tasks.filter((t) => t.status === 'DONE').length;
  const today = new Date().toISOString().slice(0, 10);
  const overdue = tasks.filter((t) => t.status !== 'DONE' && t.due_date && t.due_date < today);
  const totalBudget = projects
    .filter((p) => p.status !== 'CANCELLED')
    .reduce((s, p) => s + p.budget, 0);
  const byStatus = projects.reduce<Record<string, number>>((acc, p) => {
    acc[p.status] = (acc[p.status] ?? 0) + 1;
    return acc;
  }, {});
  const maxCount = Math.max(1, ...Object.values(byStatus));
  const upcomingMilestones = [...milestones].sort((a, b) => a.due_date.localeCompare(b.due_date)).slice(0, 5);
  const projName = (id: string) => projects.find((p) => p.id === id)?.code ?? '—';

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Tổng dự án" value={String(projects.length)} sub={`${active} đang triển khai`} />
        <StatCard label="Tổng ngân sách" value={formatVND(totalBudget)} sub="Dự án hiệu lực" />
        <StatCard label="Công việc hoàn thành" value={`${doneTasks}/${tasks.length}`} />
        <StatCard label="Công việc quá hạn" value={String(overdue.length)} sub="Chưa hoàn thành trễ hạn" />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Phân bổ trạng thái dự án</h4>
          {(Object.keys(PROJECT_STATUS_LABEL) as Array<keyof typeof PROJECT_STATUS_LABEL>).map((st) => (
            <div key={st} className="mfe-bar-row">
              <span style={{ width: 130, color: C.muted, fontSize: '.82rem' }}>{PROJECT_STATUS_LABEL[st]}</span>
              <div className="mfe-bar-track">
                <div
                  className="mfe-bar-fill"
                  style={{ width: `${(((byStatus[st] ?? 0) / maxCount) * 100).toFixed(0)}%` }}
                />
              </div>
              <span style={{ width: 32, textAlign: 'right', color: C.text, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                {byStatus[st] ?? 0}
              </span>
            </div>
          ))}
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Cột mốc sắp tới</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Dự án</th>
                <th style={th}>Cột mốc</th>
                <th style={th}>Tiến độ</th>
              </tr>
            </thead>
            <tbody>
              {upcomingMilestones.map((m) => (
                <tr key={m.id}>
                  <td style={td}>{projName(m.project_id)}</td>
                  <td style={td}>
                    {m.name}
                    <div style={{ color: C.muted, fontSize: '.78rem' }}>Hạn: {m.due_date}</div>
                  </td>
                  <td style={td}>{m.completion_pct}%</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          <p className="mfe-note">
            Hệ thống tự động gửi nhắc nhở trước thời hạn của từng cột mốc dự án.
          </p>
        </div>
      </div>
    </div>
  );
}
