// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Procurement Module — Tổng quan: KPI + đề xuất chờ duyệt + hợp đồng sắp hết hạn.
import React, { useEffect, useState } from 'react';
import { REQUEST_STATUS_LABEL, formatVND, type Contract, type PurchaseOrder, type PurchaseRequest, type Vendor } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { Badge, C, DataSourceBar, InlineError, StatCard, TableWrap, td, th } from '../components/ui';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [pos, setPOs] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [rq, vd, ct, po] = await Promise.all([
          store.listRequests(),
          store.listVendors(),
          store.listContracts(),
          store.listPOs(),
        ]);
        if (!cancelled) {
          setRequests(rq);
          setVendors(vd);
          setContracts(ct);
          setPOs(po);
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

  const pendingReq = requests.filter((r) => r.status === 'submitted');
  const pendingPO = pos.filter((p) => p.status === 'pending');
  const approvedValue = pos
    .filter((p) => p.status === 'approved' || p.status === 'delivered')
    .reduce((s, p) => s + p.total_amount, 0);
  const now = new Date().toISOString().slice(0, 10);
  const soonEnd = (d: string) => d >= now && d <= addDays(now, 30);
  const expiring = contracts.filter((c) => c.status === 'active' && soonEnd(c.end_date));
  const vendorName = (id: string) => vendors.find((v) => v.id === id)?.name ?? '—';

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Đề xuất chờ duyệt" value={String(pendingReq.length)} sub={`Tổng ${requests.length} đề xuất`} />
        <StatCard label="PO chờ duyệt" value={String(pendingPO.length)} sub={`Tổng ${pos.length} đơn hàng`} />
        <StatCard label="Giá trị PO đã duyệt" value={formatVND(approvedValue)} sub="Đã duyệt & đã bàn giao" />
        <StatCard label="Hợp đồng sắp hết hạn" value={String(expiring.length)} sub="Hết hạn trong 30 ngày" />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Đề xuất chờ duyệt</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Hạng mục</th>
                <th style={th}>Ước tính</th>
                <th style={th}>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {pendingReq.slice(0, 5).map((r) => (
                <tr key={r.id}>
                  <td style={td}>
                    <b>{r.item_name}</b>
                    <div style={{ color: C.muted, fontSize: '.78rem' }}>{r.requester_name}</div>
                  </td>
                  <td style={td}>{formatVND(r.estimated_cost)}</td>
                  <td style={td}><Badge text={REQUEST_STATUS_LABEL[r.status]} status={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          {pendingReq.length === 0 && <p className="mfe-empty">Không có đề xuất chờ duyệt.</p>}
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Hợp đồng sắp hết hạn</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Nhà cung cấp</th>
                <th style={th}>Hết hạn</th>
                <th style={th}>Giá trị</th>
              </tr>
            </thead>
            <tbody>
              {expiring.map((c) => (
                <tr key={c.id}>
                  <td style={td}>{vendorName(c.vendor_id)}</td>
                  <td style={td}>{c.end_date}</td>
                  <td style={td}>{formatVND(c.value)}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          {expiring.length === 0 && <p className="mfe-empty">Không có hợp đồng nào sắp hết hạn.</p>}
          <p className="mfe-note">
            Cảnh báo gia hạn hợp đồng được rà soát và gửi định kỳ vào thứ Hai hàng tuần.
          </p>
        </div>
      </div>
    </div>
  );
}

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
