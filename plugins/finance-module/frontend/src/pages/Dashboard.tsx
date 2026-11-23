// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Finance Module — Tổng quan: KPI thu/chi + chờ duyệt + hóa đơn sắp hạn.
import React, { useEffect, useState } from 'react';
import { INVOICE_STATUS_LABEL, formatVND, type ExpenseRequest, type FinanceInvoice, type FinanceTransaction } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { C, DataSourceBar, InlineError, SimpleBadge, StatCard, TableWrap, td, th } from '../components/ui';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [txns, setTxns] = useState<FinanceTransaction[]>([]);
  const [invoices, setInvoices] = useState<FinanceInvoice[]>([]);
  const [expenses, setExpenses] = useState<ExpenseRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [t, iv, ex] = await Promise.all([
          store.listTransactions(),
          store.listInvoices(),
          store.listExpenses(),
        ]);
        if (!cancelled) {
          setTxns(t);
          setInvoices(iv);
          setExpenses(ex);
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

  const totalIn = txns.filter((t) => t.type === 'CREDIT').reduce((s, t) => s + t.amount, 0);
  const totalOut = txns.filter((t) => t.type === 'DEBIT').reduce((s, t) => s + t.amount, 0);
  const pendingExpenses = expenses.filter((e) => e.status === 'PENDING');
  const pendingExpenseSum = pendingExpenses.reduce((s, e) => s + e.amount, 0);
  const overdue = invoices.filter((i) => i.status === 'OVERDUE');
  const recent = [...txns].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date)).slice(0, 5);
  const upcomingInvoices = [...invoices]
    .filter((i) => i.status === 'PENDING' || i.status === 'OVERDUE')
    .sort((a, b) => a.due_date.localeCompare(b.due_date))
    .slice(0, 5);

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Tổng thu" value={formatVND(totalIn)} sub={`${txns.filter((t) => t.type === 'CREDIT').length} giao dịch`} />
        <StatCard label="Tổng chi" value={formatVND(totalOut)} sub={`${txns.filter((t) => t.type === 'DEBIT').length} giao dịch`} />
        <StatCard label="Số dư (thu − chi)" value={formatVND(totalIn - totalOut)} />
        <StatCard label="Chờ duyệt chi" value={String(pendingExpenses.length)} sub={formatVND(pendingExpenseSum)} />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Giao dịch gần đây</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Ngày</th>
                <th style={th}>Nội dung</th>
                <th style={th}>Số tiền</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((t) => (
                <tr key={t.id}>
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>{t.transaction_date}</td>
                  <td style={td}>{t.description || t.category}</td>
                  <td style={{ ...td, color: t.type === 'CREDIT' ? C.green : C.red, fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {t.type === 'CREDIT' ? '+' : '−'}{formatVND(t.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Hóa đơn cần thanh toán ({overdue.length} quá hạn)</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Số HĐ</th>
                <th style={th}>Hạn TT</th>
                <th style={th}>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {upcomingInvoices.map((i) => (
                <tr key={i.id}>
                  <td style={td}>
                    <b style={{ color: C.text }}>{i.invoice_number}</b>
                    <div style={{ color: C.muted, fontSize: '.78rem' }}>{i.vendor_name}</div>
                  </td>
                  <td style={{ ...td, whiteSpace: 'nowrap' }}>{i.due_date}</td>
                  <td style={td}>
                    <SimpleBadge
                      text={INVOICE_STATUS_LABEL[i.status] ?? i.status}
                      color={i.status === 'OVERDUE' ? C.red : i.status === 'PAID' ? C.green : C.amber}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          <p className="mfe-note">
            Hệ thống theo dõi công nợ theo hạn thanh toán và gửi nhắc tự động trước kỳ hạn.
          </p>
        </div>
      </div>
    </div>
  );
}
