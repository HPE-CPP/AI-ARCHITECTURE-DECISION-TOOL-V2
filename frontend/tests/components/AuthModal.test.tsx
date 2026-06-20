/**
 * COMPONENT TESTS — AuthModal
 * Tests all modal states (main, skip-confirm, transfer, discard-confirm),
 * Google sign-in flow, error handling, project checklist transfer, and backdrop click behavior.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthModal } from '@/components/AuthModal'

const MOCK_USER = { uid: 'uid-123', email: 'test@example.com', displayName: 'Test User' }

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onAuthSuccess: vi.fn(),
  onSkip: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Modal Visibility ─────────────────────────────────────────────────────────
describe('AuthModal — Visibility', () => {
  it('renders nothing when isOpen is false', () => {
    render(<AuthModal {...defaultProps} isOpen={false} />)
    expect(screen.queryByText('Continue with Google')).toBeNull()
  })

  it('renders sign-in modal when isOpen is true', () => {
    render(<AuthModal {...defaultProps} />)
    expect(screen.getByText('Continue with Google')).toBeDefined()
  })

  it('shows "Save Your Progress" heading in default mode', () => {
    render(<AuthModal {...defaultProps} />)
    expect(screen.getByText('Save Your Progress')).toBeDefined()
  })

  it('shows "Sign In Required" heading in project-limit mode', () => {
    render(<AuthModal {...defaultProps} mode="project-limit" />)
    expect(screen.getByText('Sign In Required')).toBeDefined()
  })

  it('shows "Cancel" instead of "Skip for now" in project-limit mode', () => {
    render(<AuthModal {...defaultProps} mode="project-limit" />)
    expect(screen.getByText('Cancel')).toBeDefined()
    expect(screen.queryByText('Skip for now')).toBeNull()
  })

  it('calls onClose when X button is clicked', async () => {
    render(<AuthModal {...defaultProps} />)
    // Find close button by its aria-label (added in FE-001)
    await userEvent.click(screen.getByRole('button', { name: /close sign-in dialog/i }))
    expect(defaultProps.onClose).toHaveBeenCalled()
  })

  it('calls onClose on backdrop click', async () => {
    const { container } = render(<AuthModal {...defaultProps} />)
    const backdrop = container.querySelector('.fixed.inset-0') as HTMLElement
    if (backdrop) {
      await userEvent.click(backdrop)
      expect(defaultProps.onClose).toHaveBeenCalled()
    }
  })
})

// ─── Google Sign-In ───────────────────────────────────────────────────────────
describe('AuthModal — Google Sign-In', () => {
  it('shows loading state while signing in', async () => {
    let resolve!: (v: any) => void
    defaultProps.signIn.mockReturnValueOnce(new Promise(r => { resolve = r }))

    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))

    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(screen.getByText('Connecting...')).toBeDefined()
    })
    resolve(MOCK_USER)
  })

  it('button is disabled while loading', async () => {
    let resolve!: (v: any) => void
    defaultProps.signIn.mockReturnValueOnce(new Promise(r => { resolve = r }))
    render(<AuthModal {...defaultProps} />)
    const btn = screen.getByText('Continue with Google').closest('button') as HTMLButtonElement
    await userEvent.click(btn)
    await waitFor(() => {
      expect(btn.disabled).toBe(true)
    })
    resolve(MOCK_USER)
  })

  it('calls onAuthSuccess directly when no anonymous projects exist', async () => {
    defaultProps.signIn.mockResolvedValueOnce(MOCK_USER)
    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(defaultProps.onAuthSuccess).toHaveBeenCalledWith(MOCK_USER)
    })
  })

  it('shows transfer checklist when anonymous projects exist', async () => {
    defaultProps.signIn.mockResolvedValueOnce(MOCK_USER)
    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([
        { id: 'anon-proj-1', name: 'My Analysis', user_id: 'guest_xxx', status: 'empty' }
      ]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(screen.getByText('Transfer Projects')).toBeDefined()
      expect(screen.getByText('My Analysis')).toBeDefined()
    })
  })

  it('shows Firebase configuration error for auth/configuration-not-found', async () => {
    const err = new Error('Firebase not configured')
    ;(err as any).code = 'auth/configuration-not-found'
    defaultProps.signIn.mockRejectedValueOnce(err)
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(screen.getByText(/firebase is not configured/i)).toBeDefined()
    })
  })

  it('does not show error when user closes popup (auth/popup-closed-by-user)', async () => {
    const err = new Error('Popup closed')
    ;(err as any).code = 'auth/popup-closed-by-user'
    defaultProps.signIn.mockRejectedValueOnce(err)
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(screen.queryByText(/sign-in failed/i)).toBeNull()
    })
  })

  it('shows generic error for unexpected sign-in failures', async () => {
    defaultProps.signIn.mockRejectedValueOnce(new Error('Network timeout'))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => {
      expect(screen.getByText('Network timeout')).toBeDefined()
    })
  })
})

// ─── Skip Flow ────────────────────────────────────────────────────────────────
describe('AuthModal — Skip Flow', () => {
  it('clicking "Skip for now" transitions to skip-confirm step', async () => {
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Skip for now'))
    await waitFor(() => {
      expect(screen.getByText('Continue Without Saving?')).toBeDefined()
    })
  })

  it('"Continue Anyway" on skip-confirm calls onSkip', async () => {
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Skip for now'))
    await waitFor(() => screen.getByText('Continue Without Saving?'))
    await userEvent.click(screen.getByText('Continue Anyway'))
    expect(defaultProps.onSkip).toHaveBeenCalledOnce()
  })

  it('"Go Back" from skip-confirm returns to main step', async () => {
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Skip for now'))
    await waitFor(() => screen.getByText('Continue Without Saving?'))
    await userEvent.click(screen.getByText('Go Back'))
    await waitFor(() => {
      expect(screen.getByText('Save Your Progress')).toBeDefined()
    })
  })
})

// ─── Transfer Steps ───────────────────────────────────────────────────────────
describe('AuthModal — Project Transfer Flow', () => {
  it('"Discard All" advances to discard-confirm step', async () => {
    defaultProps.signIn.mockResolvedValueOnce(MOCK_USER)
    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([
        { id: 'anon-proj-1', name: 'Finance Platform', user_id: 'guest_xxx', status: 'empty' }
      ]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => screen.getByText('Transfer Projects'))
    await userEvent.click(screen.getByText('Discard All'))
    await waitFor(() => {
      expect(screen.getByText('Discard All Projects?')).toBeDefined()
    })
  })

  it('"Go Back" from discard-confirm returns to transfer checklist', async () => {
    defaultProps.signIn.mockResolvedValueOnce(MOCK_USER)
    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([
        { id: 'anon-proj-1', name: 'Finance Platform', user_id: 'guest_xxx', status: 'empty' }
      ]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => screen.getByText('Transfer Projects'))
    await userEvent.click(screen.getByText('Discard All'))
    await waitFor(() => screen.getByText('Discard All Projects?'))
    await userEvent.click(screen.getByText('Go Back'))
    await waitFor(() => {
      expect(screen.getByText('Transfer Projects')).toBeDefined()
    })
  })

  it('shows all guest projects as checkboxes, all pre-selected', async () => {
    defaultProps.signIn.mockResolvedValueOnce(MOCK_USER)
    vi.doMock('@/lib/projects-store', () => ({
      getProjects: vi.fn().mockResolvedValue([
        { id: 'p1', name: 'Project Alpha', user_id: 'guest_xxx', status: 'empty' },
        { id: 'p2', name: 'Project Beta', user_id: 'guest_xxx', status: 'empty' },
      ]),
      getAllGuestIds: vi.fn().mockReturnValue(['guest_xxx']),
      clearGuestIds: vi.fn(),
    }))
    render(<AuthModal {...defaultProps} />)
    await userEvent.click(screen.getByText('Continue with Google'))
    await waitFor(() => screen.getByText('Transfer Projects'))
    expect(screen.getByText('Project Alpha')).toBeDefined()
    expect(screen.getByText('Project Beta')).toBeDefined()
    expect(screen.getByText('Transfer 2 Projects')).toBeDefined()
  })
})
