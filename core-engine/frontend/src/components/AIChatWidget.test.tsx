// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AIChatWidget } from './AIChatWidget';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAICommand } from '@/hooks/useAICommand';

// Mock the hook
vi.mock('@/hooks/useAICommand', () => ({
  useAICommand: vi.fn(),
}));

describe('AIChatWidget', () => {
  const mockOpenWidget = vi.fn();
  const mockMinimizeWidget = vi.fn();
  const mockResetAndClose = vi.fn();
  const mockStartNewSession = vi.fn();
  const mockLoadSessionHistory = vi.fn();
  const mockSendCommand = vi.fn();
  const mockSetInputValue = vi.fn();
  const mockOpenMattermostApproval = vi.fn();
  const mockCancelApproval = vi.fn();

  const defaultMockReturn = {
    widgetState: 'collapsed' as const,
    messages: [],
    inputValue: '',
    dslPreview: null,
    sessionId: 'test-session',
    streamStatus: null,
    setInputValue: mockSetInputValue,
    openWidget: mockOpenWidget,
    minimizeWidget: mockMinimizeWidget,
    resetAndClose: mockResetAndClose,
    startNewSession: mockStartNewSession,
    loadSessionHistory: mockLoadSessionHistory,
    sendCommand: mockSendCommand,
    openMattermostApproval: mockOpenMattermostApproval,
    cancelApproval: mockCancelApproval,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue(defaultMockReturn);

    // Mock scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('renders floating button initially', () => {
    render(<AIChatWidget />);
    const fab = screen.getByRole('button', { name: /Mở Proteus AI/i });
    expect(fab).toBeInTheDocument();
  });

  it('calls openWidget when fab is clicked in collapsed state', () => {
    render(<AIChatWidget />);
    const fab = screen.getByRole('button', { name: /Mở Proteus AI/i });
    fireEvent.click(fab);
    expect(mockOpenWidget).toHaveBeenCalled();
  });

  it('calls minimizeWidget (not resetAndClose) when fab is clicked in expanded state (#866)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'expanded',
    });

    render(<AIChatWidget />);
    const fab = screen.getByRole('button', { name: /Thu nhỏ Proteus AI/i });
    fireEvent.click(fab);
    expect(mockMinimizeWidget).toHaveBeenCalled();
    expect(mockResetAndClose).not.toHaveBeenCalled();
  });

  it('renders fallback deadline text when approval_deadline is missing or invalid (#866)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'awaiting_approval',
      dslPreview: {
        command_id: 'cmd-no-deadline',
        action: 'hr.leave.approve',
        effect: 'write',
        approval_message: 'Cần duyệt đơn',
        approval_deadline: undefined,
      },
    });

    render(<AIChatWidget />);
    expect(screen.getByText(/30 phút/i)).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument();
  });

  it('shows input and messages when expanded', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'expanded',
      messages: [{ id: '1', role: 'assistant', content: 'Hello there', timestamp: new Date() }],
    });

    render(<AIChatWidget />);
    expect(screen.getByText('Hello there')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Nhập lệnh bằng tiếng Việt/i)).toBeInTheDocument();
  });

  it('disables input when thinking', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'thinking',
    });

    render(<AIChatWidget />);
    const input = screen.getByPlaceholderText(/Nhập lệnh bằng tiếng Việt/i);
    expect(input).toBeDisabled();
    expect(screen.getByText('Đang phân tích')).toBeInTheDocument();
  });

  it('renders awaiting_approval with string preview without crashing (#731)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'awaiting_approval',
      dslPreview: {
        command_id: 'cmd-string-preview',
        action: 'hr.leave.reject',
        effect: 'write',
        approval_message: 'Cần duyệt đơn',
        dry_run_result: {
          affected_count: 1,
          preview: 'Không thể thực hiện dry run',
        },
        approval_deadline: '2026-12-31T23:59:59Z',
      },
    });

    render(<AIChatWidget />);
    expect(screen.getByText('hr.leave.reject')).toBeInTheDocument();
    expect(screen.getByText('Không thể thực hiện dry run')).toBeInTheDocument();
  });

  it('renders 4 quick action starter chips on welcome screen and triggers sendCommand (#874)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'expanded',
      messages: [],
    });

    render(<AIChatWidget />);
    const pokaChip = screen.getByText(/Chuyển thiết bị từ Phòng C1-202 sang Phòng C1-202/i);
    expect(pokaChip).toBeInTheDocument();
    fireEvent.click(pokaChip);
    expect(mockSendCommand).toHaveBeenCalledWith(
      'Chuyển thiết bị từ Phòng C1-202 sang Phòng C1-202'
    );
  });

  it('renders Z3 Formal Proof SAT badge & dual-approval tag when escalated (#874)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'awaiting_approval',
      dslPreview: {
        command_id: 'cmd-z3-sat',
        action: 'finance.purchase.create',
        effect: 'critical',
        approval_message: 'Mua thiết bị Lab',
        z3_verification: {
          status: 'SAT',
          verified: true,
          solve_time_ms: 3.2,
          invariants_checked: ['budget_non_negative', 'amount_gt_zero'],
          escalated_to_critical: true,
        },
      },
    });

    render(<AIChatWidget />);
    expect(screen.getByText(/Z3 Formal Proof: SAT \(3\.2ms\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Phê duyệt kép 2 cấp/i)).toBeInTheDocument();
    expect(screen.getByText(/NL → DX-DSL/i)).toBeInTheDocument();
  });

  it('renders POKA-YOKE Z3 BLOCKED (UNSAT) alert with violated constraint (#874)', () => {
    (useAICommand as ReturnType<typeof vi.fn>).mockReturnValue({
      ...defaultMockReturn,
      widgetState: 'expanded',
      messages: [
        {
          id: 'msg-unsat',
          role: 'assistant',
          content: 'Lệnh bị chặn bởi Z3 SMT Solver.',
          timestamp: new Date(),
          show_pipeline: true,
          z3_verification: {
            status: 'UNSAT',
            verified: false,
            violated_constraint: 'source_room != target_room (C1-202 == C1-202)',
          },
        },
      ],
    });

    render(<AIChatWidget />);
    expect(screen.getByText(/POKA-YOKE Z3 BLOCKED \(UNSAT\)/i)).toBeInTheDocument();
    expect(
      screen.getByText(/source_room != target_room \(C1-202 == C1-202\)/i)
    ).toBeInTheDocument();
  });
});
