// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import { renderHook, act } from '@testing-library/react';
import { useAICommand } from './useAICommand';
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
});
