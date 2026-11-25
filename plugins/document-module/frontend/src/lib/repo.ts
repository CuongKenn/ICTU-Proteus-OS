// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later
// Document Module — DATA LAYER.
// Hai chế độ sau cùng 1 interface async DocumentStore:
// - DEMO: mock sync (seed + localStorage, offline, không cần login).
// - LIVE: API thật (records CRUD + dispatcher → n8n), cần login ở Launchpad.
// getStore() tự dò: gọi thử API, rớt (401/offline/chưa cài) → DEMO + lý do.
// Mọi gọi API qua BffClient tới /api/proxy; KHÔNG BAO GIỜ gửi tenant_id.
import type {
  ApprovalItem,
  ApprovalStatus,
  DistributionItem,
  DocumentCategory,
  IncomingDoc,
  IncomingStatus,
  OutgoingDoc,
} from '../types';
import {
  seedApprovals,
  seedCategories,
  seedDistributions,
  seedIncoming,
  seedOutgoing,
} from '../data/seed';

const LS_KEY = 'proteus:document-module:v1';

interface Persisted {
  incoming: IncomingDoc[];
  outgoing: OutgoingDoc[];
  approvals: ApprovalItem[];
  distributions: DistributionItem[];
}

function load(): Persisted {
  const fallback: Persisted = {
    incoming: seedIncoming,
    outgoing: seedOutgoing,
    approvals: seedApprovals,
    distributions: seedDistributions,
  };
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      incoming: parsed.incoming ?? fallback.incoming,
      outgoing: parsed.outgoing ?? fallback.outgoing,
      approvals: parsed.approvals ?? fallback.approvals,
      distributions: parsed.distributions ?? fallback.distributions,
    };
  } catch {
    return fallback;
  }
}

function save(s: Persisted) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(s));
  } catch {
    /* ignore quota */
  }
}

export function uid(): string {
  return 'xxxxxxxx-xxxx-4xxx'.replace(/x/g, () =>
    Math.floor(Math.random() * 16).toString(16),
  );
}

export interface DocumentRepo {
  listIncoming(): IncomingDoc[];
  createIncoming(input: Omit<IncomingDoc, 'id' | 'status'>): IncomingDoc;
  updateIncoming(id: string, patch: Partial<IncomingDoc>): IncomingDoc;
  reassignIncoming(id: string, assignee: string): void;
  listOutgoing(): OutgoingDoc[];
  createOutgoing(input: Omit<OutgoingDoc, 'id'>): OutgoingDoc;
  updateOutgoing(id: string, patch: Partial<OutgoingDoc>): OutgoingDoc;
  listApprovals(): ApprovalItem[];
  reviewApproval(id: string, status: ApprovalStatus, note: string): void;
  listDistributions(): DistributionItem[];
  reset(): void;
}

export function createMockRepo(): DocumentRepo {
  return {
    listIncoming: () => load().incoming,
    createIncoming(input) {
      const s = load();
      const row: IncomingDoc = { ...input, id: uid(), status: 'received' };
      s.incoming = [row, ...s.incoming];
      save(s);
      return row;
    },
    updateIncoming(id, patch) {
      const s = load();
      const row = s.incoming.find((d) => d.id === id);
      if (!row) throw new Error('Không tìm thấy văn bản đến');
      Object.assign(row, patch);
      save(s);
      return row;
    },
    reassignIncoming(id, assignee) {
      const s = load();
      const row = s.incoming.find((d) => d.id === id);
      if (!row) throw new Error('Không tìm thấy văn bản đến');
      row.assignee_id = assignee;
      if (row.status === 'received') row.status = 'processing' as IncomingStatus;
      save(s);
    },
    listOutgoing: () => load().outgoing,
    createOutgoing(input) {
      const s = load();
      const row: OutgoingDoc = { ...input, id: uid() };
      s.outgoing = [row, ...s.outgoing];
      save(s);
      return row;
    },
    updateOutgoing(id, patch) {
      const s = load();
      const row = s.outgoing.find((d) => d.id === id);
      if (!row) throw new Error('Không tìm thấy văn bản đi');
      Object.assign(row, patch);
      if (patch.status === 'pending') {
        const existing = s.approvals.filter((a) => a.document_id === id && a.document_type === 'outgoing');
        if (existing.length === 0) {
          s.approvals = [
            {
              id: uid(),
              document_id: id,
              document_type: 'outgoing',
              approver_id: row.nguoi_ky || 'Ban Giám đốc',
              order_no: 1,
              status: 'pending',
              signed_at: null,
              note: '',
            },
            ...s.approvals,
          ];
        } else if (!existing.some((a) => a.status === 'pending')) {
          for (const a of existing) {
            if (a.status === 'rejected') {
              a.status = 'pending';
              a.signed_at = null;
            }
          }
          if (!existing.some((a) => a.status === 'pending')) {
            existing[existing.length - 1].status = 'pending';
            existing[existing.length - 1].signed_at = null;
          }
        }
      }
      save(s);
      return row;
    },
    listApprovals: () => load().approvals,
    reviewApproval(id, status, note) {
      const s = load();
      const req = s.approvals.find((a) => a.id === id);
      if (!req) throw new Error('Không tìm thấy yêu cầu phê duyệt');
      req.status = status;
      req.note = note;
      req.signed_at = status === 'pending' ? null : new Date().toISOString();
      if (req.document_type === 'outgoing') {
        const doc = s.outgoing.find((d) => d.id === req.document_id);
        if (doc) {
          if (status === 'rejected') {
            doc.status = 'draft';
          } else if (status === 'approved') {
            const docApprovals = s.approvals.filter(
              (a) => a.document_id === req.document_id && a.document_type === 'outgoing',
            );
            if (docApprovals.length > 0 && docApprovals.every((a) => a.status === 'approved')) {
              doc.status = 'signed';
            }
          }
        }
      }
      save(s);
    },
    listDistributions: () => load().distributions,
    reset() {
      localStorage.removeItem(LS_KEY);
    },
  };
}

// ─── Async Store (DEMO + LIVE chung interface) ──────────────
import { ApiError, createBffClient, type BffClient } from './api';

export type StoreMode = 'live' | 'demo';
export type DemoReason =
  | 'unauthenticated' // 401: chưa login ở Launchpad
  | 'not-installed' // plugin chưa ACTIVE / bảng chưa có
  | 'offline'; // không tới được BFF

export interface DocumentStore {
  listCategories(): Promise<DocumentCategory[]>;
  listIncoming(): Promise<IncomingDoc[]>;
  createIncoming(input: Omit<IncomingDoc, 'id' | 'status'>): Promise<IncomingDoc>;
  updateIncoming(id: string, patch: Partial<IncomingDoc>): Promise<IncomingDoc>;
  reassignIncoming(id: string, assignee: string, reason?: string): Promise<void>;
  listOutgoing(): Promise<OutgoingDoc[]>;
  createOutgoing(input: Omit<OutgoingDoc, 'id'>): Promise<OutgoingDoc>;
  updateOutgoing(id: string, patch: Partial<OutgoingDoc>): Promise<OutgoingDoc>;
  submitForApproval(id: string): Promise<OutgoingDoc>;
  listApprovals(document_id?: string): Promise<ApprovalItem[]>;
  reviewApproval(id: string, status: ApprovalStatus, note: string): Promise<void>;
  listDistributions(): Promise<DistributionItem[]>;
  reset(): Promise<void>;
}

const R = '/v1/plugins/document-module/records';
const A = '/v1/plugins/document-module/actions';
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isUuid = (val?: string | null): boolean => !!val && UUID_RE.test(val.trim());

function toIncoming(r: Record<string, unknown>): IncomingDoc {
  return {
    id: String(r.id ?? ''),
    so_van_ban: String(r.so_van_ban ?? ''),
    noi_gui: String(r.noi_gui ?? ''),
    ngay_nhan: String(r.ngay_nhan ?? '').slice(0, 10),
    trich_yeu: String(r.trich_yeu ?? ''),
    file_url: String(r.file_url ?? ''),
    assignee_id: r.assignee_id == null ? null : String(r.assignee_id),
    status: (r.status as IncomingStatus) ?? 'received',
  };
}

function toOutgoing(r: Record<string, unknown>): OutgoingDoc {
  const title = String(r.trich_yeu ?? r.tieu_de ?? '');
  return {
    id: String(r.id ?? ''),
    so_van_ban: String(r.so_van_ban ?? ''),
    loai_vb: String(r.loai_vb ?? ''),
    nguoi_ky: r.nguoi_ky == null ? null : String(r.nguoi_ky),
    ngay_phat_hanh: String(r.ngay_phat_hanh ?? '').slice(0, 10),
    file_url: String(r.file_url ?? ''),
    status: (r.status as OutgoingDoc['status']) ?? 'draft',
    trich_yeu: title,
    tieu_de: title,
  };
}

function toApproval(r: Record<string, unknown>): ApprovalItem {
  return {
    id: String(r.id ?? ''),
    document_id: String(r.document_id ?? ''),
    document_type: (r.document_type as ApprovalItem['document_type']) ?? 'outgoing',
    approver_id: String(r.approver_id ?? ''),
    order_no: Number(r.order_no ?? 0),
    status: (r.status as ApprovalStatus) ?? 'pending',
    signed_at: r.signed_at == null ? null : String(r.signed_at),
    note: String(r.note ?? ''),
  };
}

/** Demo store: bọc mock sync thành async (giữ nguyên localStorage). */
export function createDemoStore(): DocumentStore {
  const m = createMockRepo();
  return {
    async listCategories() { return seedCategories; },
    async listIncoming() { return m.listIncoming(); },
    async createIncoming(i) { return m.createIncoming(i); },
    async updateIncoming(id, p) { return m.updateIncoming(id, p); },
    async reassignIncoming(id, a) { m.reassignIncoming(id, a); },
    async listOutgoing() { return m.listOutgoing(); },
    async createOutgoing(i) { return m.createOutgoing(i); },
    async updateOutgoing(id, p) { return m.updateOutgoing(id, p); },
    async submitForApproval(id) { return m.updateOutgoing(id, { status: 'pending' }); },
    async listApprovals(doc) {
      const all = m.listApprovals();
      return doc ? all.filter((a) => a.document_id === doc) : all;
    },
    async reviewApproval(id, s, n) { m.reviewApproval(id, s, n); },
    async listDistributions() { return m.listDistributions(); },
    async reset() { m.reset(); },
  };
}

/** Live store: records CRUD + dispatcher → n8n webhook. */
export function createLiveStore(client: BffClient): DocumentStore {
  const rows = async <T>(table: string): Promise<T[]> => {
    const res = await client.get<{ rows: T[] }>(`${R}/${table}?limit=100`);
    return res.rows ?? [];
  };
  return {
    async listCategories() {
      try {
        const cats = await rows<Record<string, unknown>>('document_categories');
        return cats.map((c) => ({
          id: String(c.id),
          name: String(c.name),
          description: String(c.description ?? ''),
        }));
      } catch {
        return seedCategories;
      }
    },
    async listIncoming() {
      const [incRows, dists] = await Promise.all([
        rows<Record<string, unknown>>('document_incoming'),
        rows<Record<string, unknown>>('document_distributions').catch(() => []),
      ]);
      const latestDeptByDoc = new Map<string, string>();
      for (const d of dists) {
        const docId = String(d.document_id ?? '');
        const dept = String(d.recipient_dept ?? '').trim();
        if (docId && dept && !latestDeptByDoc.has(docId)) {
          latestDeptByDoc.set(docId, dept);
        }
      }
      return incRows.map((r) => {
        const doc = toIncoming(r);
        if (!doc.assignee_id && latestDeptByDoc.has(doc.id)) {
          doc.assignee_id = latestDeptByDoc.get(doc.id) ?? null;
        }
        return doc;
      });
    },
    // Tạo văn bản đến: ghi DB trước rồi bắn workflow wf_incoming_document
    async createIncoming(i) {
      const validAssigneeUuid = isUuid(i.assignee_id) ? i.assignee_id!.trim() : null;
      const recipientDept = !validAssigneeUuid && i.assignee_id?.trim() ? i.assignee_id.trim() : null;
      const createdRaw = await client.post<any>(
        `${R}/document_incoming`,
        {
          so_van_ban: i.so_van_ban,
          noi_gui: i.noi_gui,
          ngay_nhan: i.ngay_nhan,
          trich_yeu: i.trich_yeu || (i as any).tieu_de || '',
          file_url: i.file_url || null,
          assignee_id: validAssigneeUuid,
          status: 'received',
        },
      );
      const created = createdRaw?.data ?? createdRaw;
      if (recipientDept && created?.id) {
        try {
          await client.post(`${R}/document_distributions`, {
            document_id: created.id,
            document_type: 'incoming',
            recipient_dept: recipientDept,
          });
        } catch {
          // best-effort distribution record
        }
      }
      try {
        await client.post(`${A}/wf_incoming_document`, {
          payload: {
            id: created.id,
            so_van_ban: i.so_van_ban,
            noi_gui: i.noi_gui,
            ngay_nhan: i.ngay_nhan,
            trich_yeu: i.trich_yeu,
            file_url: i.file_url || undefined,
            assignee_id: validAssigneeUuid || undefined,
            recipient_dept: recipientDept || undefined,
          },
        });
      } catch {
        // best-effort workflow trigger
      }
      const doc = toIncoming(created);
      if (!doc.assignee_id && recipientDept) doc.assignee_id = recipientDept;
      return doc;
    },
    async updateIncoming(id, p) {
      const payload: Record<string, unknown> = { ...p };
      if ('assignee_id' in payload) {
        payload.assignee_id = isUuid(payload.assignee_id as string) ? payload.assignee_id : null;
      }
      return toIncoming(await client.patch(`${R}/document_incoming/${id}`, payload));
    },
    // Điều chuyển văn bản đi qua workflow wf_reassign_document (tránh ép chuỗi phòng ban vào UUID).
    async reassignIncoming(id, assignee, reason) {
      const trimmed = assignee.trim();
      const validUuid = isUuid(trimmed) ? trimmed : null;
      const recipientDept = validUuid ? null : trimmed;
      try {
        await client.post(`${A}/wf_reassign_document`, {
          payload: {
            document_id: id,
            new_assignee_id: validUuid,
            assignee_id: validUuid,
            recipient_dept: recipientDept,
            reason: reason || (recipientDept ? `Điều chuyển tới ${recipientDept}` : 'Điều chuyển xử lý'),
          },
        });
      } catch {
        await client.patch(`${R}/document_incoming/${id}`, {
          ...(validUuid ? { assignee_id: validUuid } : {}),
          status: 'processing',
        });
        if (recipientDept) {
          await client.post(`${R}/document_distributions`, {
            document_id: id,
            document_type: 'incoming',
            recipient_dept: recipientDept,
          });
        }
      }
    },
    async listOutgoing() {
      return (await rows<Record<string, unknown>>('document_outgoing')).map(toOutgoing);
    },
    async createOutgoing(i) {
      const { tieu_de, ...rest } = i;
      const body = {
        ...rest,
        trich_yeu: rest.trich_yeu ?? tieu_de ?? '',
        loai_vb: isUuid(rest.loai_vb) ? rest.loai_vb : null,
        nguoi_ky: isUuid(rest.nguoi_ky) ? rest.nguoi_ky : null,
        ngay_phat_hanh: rest.ngay_phat_hanh || null,
      };
      const res = await client.post<any>(`${R}/document_outgoing`, body);
      return toOutgoing(res?.data ?? res);
    },
    async updateOutgoing(id, p) {
      const { tieu_de, ...rest } = p;
      const body: Record<string, unknown> = { ...rest };
      if (tieu_de !== undefined && body.trich_yeu === undefined) {
        body.trich_yeu = tieu_de;
      }
      if ('loai_vb' in body) {
        body.loai_vb = isUuid(body.loai_vb as string) ? body.loai_vb : null;
      }
      if ('nguoi_ky' in body) {
        body.nguoi_ky = isUuid(body.nguoi_ky as string) ? body.nguoi_ky : null;
      }
      const res = await client.patch<any>(`${R}/document_outgoing/${id}`, body);
      const updated = toOutgoing(res?.data ?? res);
      if (p.status === 'pending') {
        const approverUuid = isUuid(updated.nguoi_ky)
          ? updated.nguoi_ky!.trim()
          : '00000000-0000-0000-0000-000000000001';
        try {
          const existing = await this.listApprovals(id);
          const outgoingSteps = existing.filter((a) => a.document_type === 'outgoing');
          if (outgoingSteps.length === 0) {
            await client.post(`${R}/document_approvals`, {
              document_id: id,
              document_type: 'outgoing',
              approver_id: approverUuid,
              order_no: 1,
              status: 'pending',
              note: null,
            });
          } else if (!outgoingSteps.some((a) => a.status === 'pending')) {
            const rejectedSteps = outgoingSteps.filter((a) => a.status === 'rejected');
            if (rejectedSteps.length > 0) {
              for (const step of rejectedSteps) {
                await client.patch(`${R}/document_approvals/${step.id}`, {
                  status: 'pending',
                  signed_at: null,
                });
              }
            } else {
              await client.post(`${R}/document_approvals`, {
                document_id: id,
                document_type: 'outgoing',
                approver_id: approverUuid,
                order_no: outgoingSteps.length + 1,
                status: 'pending',
                note: null,
              });
            }
          }
        } catch {
          // best-effort đảm bảo bước ký duyệt tồn tại
        }
        try {
          await client.post(`${A}/wf_document_approval`, {
            payload: { document_id: id },
          });
        } catch {
          // best-effort kích hoạt workflow thông báo người duyệt
        }
      }
      return updated;
    },
    async submitForApproval(id) {
      return this.updateOutgoing(id, { status: 'pending' });
    },
    async listApprovals(document_id) {
      const all = (await rows<Record<string, unknown>>('document_approvals')).map(toApproval);
      return document_id ? all.filter((a) => a.document_id === document_id) : all;
    },
    // Duyệt văn bản: cập nhật trực tiếp bản ghi trên bảng document_approvals qua REST PATCH
    // và đồng bộ trạng thái văn bản đi liên quan.
    async reviewApproval(id, status, note) {
      const signed_at = status === 'pending' ? null : new Date().toISOString();
      const updatedRaw = await client.patch<any>(`${R}/document_approvals/${id}`, {
        status,
        note: note || null,
        signed_at,
      });
      const updated = toApproval(updatedRaw?.data ?? updatedRaw);
      if (updated.document_id && updated.document_type === 'outgoing') {
        try {
          if (status === 'rejected') {
            await client.patch(`${R}/document_outgoing/${updated.document_id}`, { status: 'draft' });
          } else if (status === 'approved') {
            const docApprovals = await this.listApprovals(updated.document_id);
            const allApproved =
              docApprovals.length > 0 && docApprovals.every((a) => a.status === 'approved');
            if (allApproved) {
              await client.patch(`${R}/document_outgoing/${updated.document_id}`, { status: 'signed' });
            }
          }
        } catch {
          // best-effort cập nhật trạng thái văn bản đi
        }
      }
    },
    async listDistributions() {
      const all = await rows<DistributionItem>('document_distributions');
      return all;
    },
    async reset() { /* live: không reset DB từ UI */ },
  };
}

export interface ResolvedStore {
  mode: StoreMode;
  store: DocumentStore;
  reason?: DemoReason;
  message?: string;
}

let cached: Promise<ResolvedStore> | null = null;

/** Dò API thật, rớt → demo + lý do để UI hiển thị banner trung thực. */
export function getStore(): Promise<ResolvedStore> {
  if (!cached) {
    cached = (async () => {
      const client = createBffClient();
      try {
        await client.get(`${R}/document_incoming?limit=1`);
        return { mode: 'live' as const, store: createLiveStore(client) };
      } catch (e) {
        const st = e instanceof ApiError ? e.status : 0;
        const detail = e instanceof ApiError ? e.detail : String(e);
        const reason: DemoReason =
          st === 401 ? 'unauthenticated'
          : st === 400 || st === 404 ? 'not-installed'
          : 'offline';
        return { mode: 'demo' as const, store: createDemoStore(), reason, message: detail };
      }
    })();
  }
  return cached;
}

export function resetStoreCache() {
  cached = null;
}
