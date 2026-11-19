// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// CRM Dashboard: pipeline weighted + lead source + SLA.
import React, { useEffect, useState } from 'react';
import type { Lead, Opportunity, Ticket } from '../types';
import { formatVND } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { C, DataSourceBar, InlineError, StatCard } from '../components/ui';

const OPEN_STAGES = ['PROSPECTING', 'QUALIFICATION', 'PROPOSAL', 'NEGOTIATION'];

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [o, l, t] = await Promise.all([
          store.listOpportunities(),
          store.listLeads(),
          store.listTickets(),
        ]);
        if (!cancelled) {
          setOpps(o);
          setLeads(l);
          setTickets(t);
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

  const open = opps.filter((o) => OPEN_STAGES.includes(o.stage));
  const weighted = open.reduce((s, o) => s + (o.value * o.probability_pct) / 100, 0);
  const won = opps.filter((o) => o.stage === 'CLOSED_WON').reduce((s, o) => s + o.value, 0);
  const breached = tickets.filter((t) => t.sla_deadline < new Date().toISOString() && !['RESOLVED', 'CLOSED'].includes(t.status)).length;

  const bySource = leads.reduce<Record<string, number>>((a, l) => {
    a[l.source] = (a[l.source] ?? 0) + 1;
    return a;
  }, {});

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Giá trị kỳ vọng" value={formatVND(weighted)} sub={`${open.length} cơ hội đang mở`} />
        <StatCard label="Đã chốt thành công" value={formatVND(won)} />
        <StatCard label="Lead mới" value={String(leads.filter((l) => l.stage === 'NEW').length)} sub={`Tổng ${leads.length} tiềm năng`} />
        <StatCard label="Ticket quá SLA" value={String(breached)} sub={`Tổng ${tickets.length} yêu cầu`} />
      </div>
      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Phễu cơ hội đang mở</h4>
          {OPEN_STAGES.map((st) => {
            const rows = open.filter((o) => o.stage === st);
            const sum = rows.reduce((s, o) => s + o.value, 0);
            return (
              <div key={st} className="mfe-list-row">
                <span>{st} ({rows.length})</span>
                <b>{formatVND(sum)}</b>
              </div>
            );
          })}
        </div>
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Khách hàng tiềm năng theo nguồn</h4>
          {Object.entries(bySource).map(([k, v]) => (
            <div key={k} className="mfe-list-row">
              <span>{k}</span><b>{v}</b>
            </div>
          ))}
          <p className="mfe-note">
            Dữ liệu được đồng bộ tự động từ kênh tiếp nhận khách hàng tiềm năng và bảng theo dõi doanh số.
          </p>
        </div>
      </div>
    </div>
  );
}
