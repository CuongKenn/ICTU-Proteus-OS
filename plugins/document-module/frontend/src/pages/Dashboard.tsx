// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Document Module — Tổng quan: KPI + văn bản chờ xử lý + phê duyệt tồn.
import React, { useEffect, useState } from 'react';
import { INCOMING_LABEL, type ApprovalItem, type IncomingDoc, type OutgoingDoc } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { C, DataSourceBar, InlineError, StatCard, TableWrap, td, th } from '../components/ui';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [incoming, setIncoming] = useState<IncomingDoc[]>([]);
  const [outgoing, setOutgoing] = useState<OutgoingDoc[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [inc, out, app] = await Promise.all([
          store.listIncoming(),
          store.listOutgoing(),
          store.listApprovals(),
        ]);
        if (!cancelled) {
          setIncoming(inc);
          setOutgoing(out);
          setApprovals(app);
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

  const pendingApproval = approvals.filter((a) => a.status === 'pending').length;
  const byStatus = incoming.reduce<Record<string, number>>((acc, d) => {
    acc[d.status] = (acc[d.status] ?? 0) + 1;
    return acc;
  }, {});
  const waiting = [...incoming]
    .filter((d) => d.status !== 'done')
    .sort((a, b) => b.ngay_nhan.localeCompare(a.ngay_nhan))
    .slice(0, 5);
  const maxCount = Math.max(1, ...Object.values(byStatus));

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Văn bản đến" value={String(incoming.length)} sub={`${byStatus['received'] ?? 0} mới tiếp nhận`} />
        <StatCard label="Văn bản đi" value={String(outgoing.length)} sub={`${outgoing.filter((o) => o.status === 'draft').length} bản nháp`} />
        <StatCard label="Chờ phê duyệt" value={String(pendingApproval)} sub="Hồ sơ chờ ký duyệt" />
        <StatCard label="Đã hoàn tất" value={String(byStatus['done'] ?? 0)} sub="Văn bản đã xử lý" />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Văn bản đến theo trạng thái</h4>
          {(Object.keys(INCOMING_LABEL) as Array<keyof typeof INCOMING_LABEL>).map((st) => (
            <div key={st} className="mfe-bar-row">
              <span style={{ width: 118, color: C.muted, fontSize: '.82rem' }}>{INCOMING_LABEL[st]}</span>
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
          <p className="mfe-note">
            Trạng thái cập nhật theo thời gian thực khi tiếp nhận và phân công văn bản.
          </p>
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Văn bản đến cần xử lý</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Số văn bản</th>
                <th style={th}>Ngày nhận</th>
                <th style={th}>Người xử lý</th>
              </tr>
            </thead>
            <tbody>
              {waiting.map((d) => (
                <tr key={d.id}>
                  <td style={td}>{d.so_van_ban}</td>
                  <td style={td}>{d.ngay_nhan}</td>
                  <td style={td}>{d.assignee_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          <p className="mfe-note">
            Điều chuyển người phụ trách và phê duyệt ký số được lưu vết đầy đủ trong nhật ký xử lý.
          </p>
        </div>
      </div>
    </div>
  );
}
