import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ShareButton from '../../src/components/ShareButton';

describe('ShareButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the share button and toggles the popover', () => {
    render(<ShareButton analysisId="test-123" />);
    
    const shareBtn = screen.getByRole('button', { name: /share/i });
    expect(shareBtn).toBeInTheDocument();
    
    // Open popover
    fireEvent.click(shareBtn);
    expect(screen.getByText(/Share this analysis/i)).toBeInTheDocument();
    
    // Close popover using the close button
    const closeBtn = screen.getAllByRole('button')[1]; // The X button
    fireEvent.click(closeBtn);
  });

  it('copies the url to clipboard', async () => {
    vi.useFakeTimers();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    render(<ShareButton analysisId="test-123" />);
    fireEvent.click(screen.getByRole('button', { name: /share/i }));

    const copyBtn = screen.getByRole('button', { name: /copy/i });
    
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('/r/test-123'));
    
    expect(screen.getByText(/Copied!/i)).toBeInTheDocument();
    
    act(() => {
      vi.advanceTimersByTime(2600);
    });
    
    expect(screen.getByText(/Copy/i)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('handles clipboard fallback when navigator.clipboard fails', async () => {
    vi.useFakeTimers();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockRejectedValue(new Error('clipboard disabled')),
      },
    });

    document.execCommand = vi.fn();

    render(<ShareButton analysisId="test-123" />);
    fireEvent.click(screen.getByRole('button', { name: /share/i }));

    const copyBtn = screen.getByRole('button', { name: /copy/i });
    
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(document.execCommand).toHaveBeenCalledWith('copy');
    expect(screen.getByText(/Copied!/i)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2600);
    });
    vi.useRealTimers();
  });
});
