// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { renderHook, act } from '@testing-library/react';
import { ChatMessage, useAICommand } from './useAICommand';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch
global.fetch = vi.fn();

describe('useAICommand', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'completed',
        result: 'Mock result',
      }),
    });
  });

  it('initializes with collapsed state and empty messages for SSR hydration safety', () => {
    const { result } = renderHook(() => useAICommand());
    expect(result.current.widgetState).toBe('collapsed');
    expect(result.current.messages).toHaveLength(0);
  });

  it('can open and close the widget', () => {
    const { result } = renderHook(() => useAICommand());
    
    act(() => {
      result.current.openWidget();
    });
    expect(result.current.widgetState).toBe('expanded');

    act(() => {
      result.current.resetAndClose();
    });

    expect(result.current.widgetState).toBe("collapsed");
  });

  it('sends command and updates state accordingly', async () => {
    const { result } = renderHook(() => useAICommand());
    
    act(() => {
      result.current.setInputValue('Hello AI');
    });

    await act(async () => {
      await result.current.sendCommand();
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/ai/command', expect.any(Object));
    expect(result.current.inputValue).toBe('');
    expect(result.current.messages.some(m => m.content === 'Hello AI' && m.role === 'user')).toBe(true);
    // Since mock fetch returns completed status:
    expect(result.current.messages.some(m => m.content === 'Mock result' && m.role === 'assistant')).toBe(true);
  });

  it('supports SSE stream from /api/ai/chat/stream and extracts Z3 verification (#874)', async () => {
    const sseFrames = [
      'event: started\ndata: {"session_id":"test-sse"}\n\n',
      'event: plan\ndata: {"total":1,"steps":[{"action":"ops.asset.transfer","effect":"write"}]}\n\n',
      'event: result\ndata: {"status":"FAILED","message":"Vi phạm ràng buộc Z3","result":{"z3_verification":{"status":"UNSAT","verified":false,"violated_constraint":"source_room != target_room"}}}\n\n',
    ];
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const f of sseFrames) {
          controller.enqueue(encoder.encode(f));
        }
        controller.close();
      },
    });

    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'Content-Type': 'text/event-stream' }),
      body: stream,
    });

    const { result } = renderHook(() => useAICommand({ enableStream: true }));

    await act(async () => {
      await result.current.sendCommand('Chuyển thiết bị từ Phòng C1-202 sang Phòng C1-202');
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/ai/chat/stream', expect.any(Object));
    const lastMsg = result.current.messages[result.current.messages.length - 1];
    expect(lastMsg.role).toBe('assistant');
    expect(lastMsg.z3_verification?.status).toBe('UNSAT');
    expect(lastMsg.z3_verification?.violated_constraint).toBe('source_room != target_room');
  });

  it('transitions out of awaiting_approval when polling returns APPROVED (#882)', async () => {
    vi.useFakeTimers();
    try {
      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            status: 'pending_approval',
            dsl_preview: {
              command_id: 'cmd-882',
              action: 'procurement.order.create',
              effect: 'write',
              approval_message: 'Cần duyệt đơn mua hàng',
            },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            command_id: 'cmd-882',
            status: 'APPROVED',
            action: 'procurement.order.create',
            effect: 'write',
          }),
        });

      const { result } = renderHook(() => useAICommand());

      await act(async () => {
        await result.current.sendCommand('Tạo đề xuất mua 5 màn hình Lab');
      });

      expect(result.current.widgetState).toBe('awaiting_approval');
      expect(result.current.dslPreview?.command_id).toBe('cmd-882');

      await act(async () => {
        vi.advanceTimersByTime(3000);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(result.current.widgetState).toBe('expanded');
      expect(result.current.dslPreview).toBeNull();
      const lastMsg = result.current.messages[result.current.messages.length - 1];
      expect(lastMsg.content).toContain('phê duyệt');
    } finally {
      vi.useRealTimers();
    }
  });

  it('cancels pending approval and clears stale dslPreview when externalSessionId changes (#882)', async () => {
    (global.fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'pending_approval',
          dsl_preview: {
            command_id: 'cmd-stale-1',
            action: 'hr.employee.update',
            effect: 'write',
            approval_message: 'Duyệt thay đổi',
          },
        }),
      })
      .mockResolvedValue({
        ok: true,
        json: async () => ({ cancelled: true }),
      });

    const { result, rerender } = renderHook(
      ({ extId, extMsgs }: { extId: string; extMsgs?: ChatMessage[] }) =>
        useAICommand({ externalSessionId: extId, externalMessages: extMsgs }),
      {
        initialProps: {
          extId: 'session-a',
          extMsgs: undefined as ChatMessage[] | undefined,
        },
      }
    );

    await act(async () => {
      await result.current.sendCommand('Cập nhật hồ sơ');
    });
    expect(result.current.widgetState).toBe('awaiting_approval');
    expect(result.current.dslPreview?.command_id).toBe('cmd-stale-1');

    act(() => {
      rerender({ extId: 'session-b', extMsgs: [] });
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/v1/ai/commands/cmd-stale-1/cancel',
      expect.objectContaining({ method: 'POST' })
    );
    expect(result.current.sessionId).toBe('session-b');
    expect(result.current.dslPreview).toBeNull();
    expect(result.current.widgetState).toBe('expanded');
    expect(result.current.messages).toHaveLength(0);
  });
});
