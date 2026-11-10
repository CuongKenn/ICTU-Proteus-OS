// Copyright (c) 2026 CuongKenn & ICTU Team
// SPDX-License-Identifier: AGPL-3.0-or-later

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Toast } from './Toast';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';

describe('Toast', () => {
  it('renders message correctly', () => {
    render(<Toast type="success" message="Success message" />);
    expect(screen.getByText('Success message')).toBeInTheDocument();
  });

  it('safely renders FastAPI 422 error array without crashing React (#746)', () => {
    const errorArray = [
      { loc: ['body', 'admin_password'], msg: 'Password must have uppercase' },
      { loc: ['body', 'admin_password'], msg: 'Password must have number' },
    ];
    render(<Toast type="error" message={errorArray as any} />);
    expect(screen.getByText('Password must have uppercase; Password must have number')).toBeInTheDocument();
  });

  it('safely renders object message without crashing React (#746)', () => {
    const errorObj = { msg: 'Specific object error' };
    render(<Toast type="error" message={errorObj as any} />);
    expect(screen.getByText('Specific object error')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const handleClose = vi.fn();
    render(<Toast type="success" message="Success" onClose={handleClose} />);
    const button = screen.getByRole('button');
    await userEvent.click(button);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
