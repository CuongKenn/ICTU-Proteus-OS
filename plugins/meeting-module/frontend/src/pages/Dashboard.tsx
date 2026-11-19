// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Meeting Module — Tổng quan: KPI + lịch sắp tới + việc quá hạn.
import React, { useEffect, useState } from 'react';
import { fmtTime, type ActionItem, type Booking, type MeetingRoom } from '../types';
import { errText, reasonText, useStore } from '../lib/useStore';
import { C, DataSourceBar, InlineError, StatCard, TableWrap, td, th } from '../components/ui';

export function Dashboard() {
  const { mode, store, reason, message } = useStore();
  const [rooms, setRooms] = useState<MeetingRoom[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [rm, bk, ac] = await Promise.all([
          store.listRooms(),
          store.listBookings(),
          store.listActions(),
        ]);
        if (!cancelled) {
          setRooms(rm);
          setBookings(bk);
          setActions(ac);
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

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = [...bookings]
    .filter((b) => b.status === 'SCHEDULED')
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
    .slice(0, 5);
  const overdue = actions.filter(
    (a) => a.status !== 'COMPLETED' && a.status !== 'CANCELLED' && a.due_date && a.due_date < today,
  );
  const roomName = (id: string) => rooms.find((r) => r.id === id)?.name ?? '—';

  return (
    <div>
      <DataSourceBar mode={mode} reasonText={reasonText(reason)} message={message} />
      <InlineError text={error} onClose={() => setError(null)} />
      <div className="mfe-kpi-grid">
        <StatCard label="Phòng họp" value={String(rooms.filter((r) => r.is_active).length)} sub={`Tổng ${rooms.length} phòng`} />
        <StatCard label="Lịch đã đặt" value={String(bookings.filter((b) => b.status === 'SCHEDULED').length)} sub="Sắp diễn ra" />
        <StatCard label="Việc cần làm" value={String(actions.filter((a) => a.status === 'PENDING' || a.status === 'IN_PROGRESS').length)} sub="Đang triển khai" />
        <StatCard label="Quá hạn" value={String(overdue.length)} sub="Đầu việc trễ hạn" />
      </div>

      <div className="mfe-panel-grid">
        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Lịch họp sắp tới</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Cuộc họp</th>
                <th style={th}>Phòng</th>
                <th style={th}>Bắt đầu</th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((b) => (
                <tr key={b.id}>
                  <td style={td}>{b.title}</td>
                  <td style={td}>{roomName(b.room_id)}</td>
                  <td style={td}>{fmtTime(b.start_time)}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          {upcoming.length === 0 && <p className="mfe-empty">Chưa có lịch họp sắp tới.</p>}
          <p className="mfe-note">
            Lịch họp tự động gửi thư mời và thông báo nhắc lịch trước giờ bắt đầu.
          </p>
        </div>

        <div className="mfe-panel">
          <h4 className="mfe-panel-title">Đầu việc quá hạn</h4>
          <TableWrap>
            <thead>
              <tr>
                <th style={th}>Công việc</th>
                <th style={th}>Người phụ trách</th>
                <th style={th}>Hạn</th>
              </tr>
            </thead>
            <tbody>
              {overdue.slice(0, 5).map((a) => (
                <tr key={a.id}>
                  <td style={td}>{a.task_desc}</td>
                  <td style={td}>{a.owner_id}</td>
                  <td style={{ ...td, color: C.red, fontWeight: 500 }}>{a.due_date}</td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
          {overdue.length === 0 && <p className="mfe-empty">Không có đầu việc quá hạn.</p>}
          <p className="mfe-note">
            Hệ thống tự động nhắc nhở định kỳ đối với các đầu việc sau cuộc họp sắp đến hạn.
          </p>
        </div>
      </div>
    </div>
  );
}
