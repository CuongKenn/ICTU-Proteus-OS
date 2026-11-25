// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// HR Core — Tổng quan: KPI headcount + phân bổ phòng ban + đơn nghỉ gần đây.
import React, { useEffect, useState } from 'react';
import { LEAVE_STATUS_COLOR, LEAVE_STATUS_LABEL, formatVND, isPendingLeave, type Employee, type LeaveRequest, type PayrollRecord } from '../types';
import type { Department } from '../types';
import { useStore, errText } from '../lib/useStore';
import { C, DataSourceBar, InlineError, SimpleBadge, StatCard, TableWrap, td, th } from '../components/ui';
import { reasonText } from '../lib/useStore';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [depts, setDepts] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [leaves, setLeaves] = useState<LeaveRequest[]>([]);
  const [payroll, setPayroll] = useState<PayrollRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [dp, em, lv, pr] = await Promise.all([
          store.listDepartments(),
          store.listEmployees(),
          store.listLeaveRequests(),
          store.listPayroll().catch(() => [] as PayrollRecord[]),
        ]);
        if (!cancelled) {
          setDepts(dp);
          setEmployees(em);
          setLeaves(lv);
          setPayroll(pr);
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

  const active = employees.filter((e) => e.status === 'active').length;
  const pending = leaves.filter((l) => isPendingLeave(l.status)).length;
  const totalPayroll = payroll.reduce((s, p) => s + Number(p.amount ?? 0), 0);
  const nameOf = (id: string) => employees.find((e) => e.id === id)?.full_name ?? '—';

  const byDept = depts.map((d) => ({
    dept: d,
    count: employees.filter((e) => e.department_id === d.id && e.status === 'active').length,
  }));
  const maxCount = Math.max(1, ...byDept.map((b) => b.count));
  const recent = [...leaves]
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
    .slice(0, 5);

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Tổng nhân viên" value={String(employees.length)} sub={`${active} đang làm việc`} />
        <StatCard label="Phòng ban" value={String(depts.length)} />
        <StatCard label="Đơn chờ duyệt" value={String(pending)} sub="Đơn nghỉ phép chờ duyệt" />
        <StatCard label="Tổng lương kỳ này" value={formatVND(totalPayroll)} sub={`${payroll.length} phiếu lương`} />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Nhân sự theo phòng ban</h4>
          {byDept.map((b) => (
            <div key={b.dept.id} className="mfe-bar-row">
              <span style={{ width: 170, color: C.muted, fontSize: '.82rem' }}>{b.dept.name}</span>
              <div className="mfe-bar-track">
                <div
                  className="mfe-bar-fill"
                  style={{ width: `${((b.count / maxCount) * 100).toFixed(0)}%` }}
                />
              </div>
              <span style={{ width: 32, textAlign: 'right', color: C.text, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                {b.count}
              </span>
            </div>
          ))}
          <p className="mfe-note">
            Thống kê chỉ tính nhân sự đang trong trạng thái làm việc chính thức.
          </p>
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Đơn nghỉ gần đây</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Nhân viên</th>
                <th style={th}>Khoảng nghỉ</th>
                <th style={th}>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((l) => (
                <tr key={l.id}>
                  <td style={td}>{nameOf(l.employee_id)}</td>
                  <td style={td}>{l.start_date} → {l.end_date} ({l.duration_days} ngày)</td>
                  <td style={td}>
                    <SimpleBadge text={LEAVE_STATUS_LABEL[l.status]} color={LEAVE_STATUS_COLOR[l.status]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          <p className="mfe-note">
            Đơn nghỉ phép tự động gửi yêu cầu phê duyệt tới quản lý trực tiếp.
          </p>
        </div>
      </div>
    </div>
  );
}
