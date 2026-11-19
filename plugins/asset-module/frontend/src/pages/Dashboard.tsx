// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Asset Module — Dashboard: KPI + phân bổ trạng thái + bảo trì sắp tới.
import React, { useEffect, useState } from 'react';
import { STATUS_LABEL, formatVND, type AssetItem } from '../types';
import type { DisposalRequest, MaintenanceLog } from '../types';
import { useStore, errText } from '../lib/useStore';
import { C, DataSourceBar, InlineError, StatCard, td, th, TableWrap } from '../components/ui';
import { reasonText } from '../lib/useStore';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [items, setItems] = useState<AssetItem[]>([]);
  const [maintenance, setMaintenance] = useState<MaintenanceLog[]>([]);
  const [disposals, setDisposals] = useState<DisposalRequest[]>([]);
  const [cats, setCats] = useState<{ id: string; name: string; code: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [it, mt, dp, ct] = await Promise.all([
          store.listItems(),
          store.listMaintenance(),
          store.listDisposals(),
          store.listCategories(),
        ]);
        if (!cancelled) {
          setItems(it);
          setMaintenance(mt);
          setDisposals(dp);
          setCats(ct);
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

  const totalValue = items
    .filter((i) => i.status !== 'DISPOSED')
    .reduce((s, i) => s + i.book_value_remaining, 0);
  const byStatus = items.reduce<Record<string, number>>((acc, i) => {
    acc[i.status] = (acc[i.status] ?? 0) + 1;
    return acc;
  }, {});
  const upcoming = [...maintenance]
    .sort((a, b) => a.next_due.localeCompare(b.next_due))
    .slice(0, 5);
  const pendingDisposals = disposals.filter((d) => d.status === 'PENDING').length;

  const maxCount = Math.max(1, ...Object.values(byStatus));

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Tổng tài sản" value={String(items.length)} sub={`${items.filter((i) => i.status === 'AVAILABLE').length} sẵn sàng`} />
        <StatCard label="Giá trị còn lại" value={formatVND(totalValue)} sub="Chưa thanh lý" />
        <StatCard label="Đang cấp phát" value={String(byStatus['ASSIGNED'] ?? 0)} />
        <StatCard label="Chờ thanh lý" value={String(pendingDisposals)} sub="Đề xuất chờ duyệt" />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Phân bổ trạng thái</h4>
          {(Object.keys(STATUS_LABEL) as Array<keyof typeof STATUS_LABEL>).map((st) => (
            <div key={st} className="mfe-bar-row">
              <span style={{ width: 118, color: C.muted, fontSize: '.82rem' }}>{STATUS_LABEL[st]}</span>
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
            Giá trị còn lại được tính theo phương pháp khấu hao đường thẳng định kỳ.
          </p>
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Bảo trì sắp tới</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Mã</th>
                <th style={th}>Hạn</th>
                <th style={th}>Loại</th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((m) => {
                const item = items.find((i) => i.id === m.asset_id);
                return (
                  <tr key={m.id}>
                    <td style={td}>{item?.code ?? '—'}</td>
                    <td style={td}>{m.next_due}</td>
                    <td style={td}>{m.type}</td>
                  </tr>
                );
              })}
            </tbody>
          </TableWrap>
          <p className="mfe-note">
            Hệ thống tự động gửi thông báo nhắc lịch khi tài sản sắp đến kỳ bảo trì.
          </p>
        </div>
      </div>

      <div className="mfe-note" style={{ marginTop: '1rem' }}>
        Danh mục tài sản: {cats.map((c) => `${c.code} (${c.name})`).join(' · ')}
      </div>
    </div>
  );
}
