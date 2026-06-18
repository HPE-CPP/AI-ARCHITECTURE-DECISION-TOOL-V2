/**
 * COMPONENT TESTS — ProjectCard
 * Tests status badges, relative timestamps, card click routing,
 * delete confirmation dialog, action button isolation, edit/duplicate callbacks,
 * and empty description display.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ProjectCard } from '@/components/ProjectCard'
import type { Project } from '@/lib/projects-store'

const mockRouter = { push: vi.fn() }
vi.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
}))

const BASE_PROJECT: Project = {
  id: 'proj-test-001',
  user_id: 'user-001',
  name: 'Financial Services Platform',
  description: 'AI architecture analysis for banking domain',
  status: 'empty',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const onEdit = vi.fn()
const onDelete = vi.fn()
const onDuplicate = vi.fn()

function renderCard(overrides: Partial<Project> = {}) {
  return render(
    <ProjectCard
      project={{ ...BASE_PROJECT, ...overrides }}
      onEdit={onEdit}
      onDelete={onDelete}
      onDuplicate={onDuplicate}
    />
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Rendering ────────────────────────────────────────────────────────────────
describe('ProjectCard — Render', () => {
  it('renders project name', () => {
    renderCard()
    expect(screen.getByText('Financial Services Platform')).toBeDefined()
  })

  it('renders project description', () => {
    renderCard()
    expect(screen.getByText('AI architecture analysis for banking domain')).toBeDefined()
  })

  it('shows placeholder when description is empty', () => {
    renderCard({ description: '' })
    expect(screen.getByText(/no description/i)).toBeDefined()
  })

  it('shows relative time in footer', () => {
    renderCard()
    // "just now" since created at current time
    expect(screen.getByText(/just now/i)).toBeDefined()
  })

  it('shows date for old timestamps', () => {
    const oldDate = new Date(Date.now() - 10 * 24 * 3600 * 1000).toISOString()
    renderCard({ updated_at: oldDate })
    // Should show formatted date, not "just now"
    expect(screen.queryByText(/just now/i)).toBeNull()
  })
})

// ─── Status Badges ────────────────────────────────────────────────────────────
describe('ProjectCard — Status Badges', () => {
  it('shows "Draft" badge for empty status', () => {
    renderCard({ status: 'empty' })
    expect(screen.getByText('Draft')).toBeDefined()
  })

  it('shows "In Progress" badge for in_progress status', () => {
    renderCard({ status: 'in_progress' })
    expect(screen.getByText('In Progress')).toBeDefined()
  })

  it('shows "Completed" badge for completed status', () => {
    renderCard({ status: 'completed' })
    expect(screen.getByText('Completed')).toBeDefined()
  })

  it('shows "Start" CTA for empty status', () => {
    renderCard({ status: 'empty' })
    expect(screen.getByText(/start/i)).toBeDefined()
  })

  it('shows "View" CTA for completed status', () => {
    renderCard({ status: 'completed', analysis_id: 'analysis-xyz' })
    expect(screen.getByText(/view/i)).toBeDefined()
  })
})

// ─── Card Click Routing ───────────────────────────────────────────────────────
describe('ProjectCard — Click Routing', () => {
  it('routes to /analyze for empty status project', async () => {
    renderCard({ status: 'empty' })
    await userEvent.click(screen.getByText('Financial Services Platform'))
    expect(mockRouter.push).toHaveBeenCalledWith('/projects/proj-test-001/analyze')
  })

  it('routes to /analyze for in_progress project', async () => {
    renderCard({ status: 'in_progress' })
    await userEvent.click(screen.getByText('Financial Services Platform'))
    expect(mockRouter.push).toHaveBeenCalledWith('/projects/proj-test-001/analyze')
  })

  it('routes to /results for completed project with analysis_id', async () => {
    renderCard({ status: 'completed', analysis_id: 'analysis-xyz' })
    await userEvent.click(screen.getByText('Financial Services Platform'))
    expect(mockRouter.push).toHaveBeenCalledWith(
      '/results/analysis-xyz?projectId=proj-test-001'
    )
  })

  it('routes to /analyze for completed project without analysis_id', async () => {
    renderCard({ status: 'completed', analysis_id: undefined })
    await userEvent.click(screen.getByText('Financial Services Platform'))
    expect(mockRouter.push).toHaveBeenCalledWith('/projects/proj-test-001/analyze')
  })
})

// ─── Action Buttons ───────────────────────────────────────────────────────────
describe('ProjectCard — Action Buttons', () => {
  it('calls onEdit with project when edit button clicked', async () => {
    renderCard()
    const editBtn = screen.getByTitle('Edit project')
    await userEvent.click(editBtn)
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: 'proj-test-001' }))
  })

  it('calls onDuplicate with project id when duplicate clicked', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Duplicate project'))
    expect(onDuplicate).toHaveBeenCalledWith('proj-test-001')
  })

  it('action button clicks do not trigger card navigation', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Edit project'))
    expect(mockRouter.push).not.toHaveBeenCalled()
  })

  it('edit button click does not trigger card navigation', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Duplicate project'))
    expect(mockRouter.push).not.toHaveBeenCalled()
  })
})

// ─── Delete Confirmation ──────────────────────────────────────────────────────
describe('ProjectCard — Delete Confirmation', () => {
  it('shows delete confirmation overlay on trash click', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Delete project'))
    await waitFor(() => {
      expect(screen.getByText('Delete this project?')).toBeDefined()
    })
  })

  it('"Cancel" hides the confirmation overlay', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Delete project'))
    await waitFor(() => screen.getByText('Delete this project?'))
    await userEvent.click(screen.getByText('Cancel'))
    await waitFor(() => {
      expect(screen.queryByText('Delete this project?')).toBeNull()
    })
  })

  it('"Delete" button calls onDelete with project id', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Delete project'))
    await waitFor(() => screen.getByText('Delete this project?'))
    await userEvent.click(screen.getByText('Delete'))
    expect(onDelete).toHaveBeenCalledWith('proj-test-001')
  })

  it('delete confirmation click does not bubble to card', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Delete project'))
    await waitFor(() => screen.getByText('Delete this project?'))
    await userEvent.click(screen.getByText('Delete'))
    // onDelete called, but NOT card navigation
    expect(mockRouter.push).not.toHaveBeenCalled()
  })

  it('"Cannot be undone" warning text is visible', async () => {
    renderCard()
    await userEvent.click(screen.getByTitle('Delete project'))
    await waitFor(() => {
      expect(screen.getByText(/cannot be undone/i)).toBeDefined()
    })
  })
})

// ─── formatRelativeTime Edge Cases ────────────────────────────────────────────
describe('ProjectCard — Relative Time Formatting', () => {
  it('shows "just now" for timestamps < 1 minute ago', () => {
    const recent = new Date(Date.now() - 30 * 1000).toISOString()
    renderCard({ updated_at: recent })
    expect(screen.getByText('just now')).toBeDefined()
  })

  it('shows "Xm ago" for timestamps 1-60 minutes ago', () => {
    const mins5 = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    renderCard({ updated_at: mins5 })
    expect(screen.getByText('5m ago')).toBeDefined()
  })

  it('shows "Xh ago" for timestamps 1-24 hours ago', () => {
    const hrs3 = new Date(Date.now() - 3 * 3600 * 1000).toISOString()
    renderCard({ updated_at: hrs3 })
    expect(screen.getByText('3h ago')).toBeDefined()
  })

  it('shows "Xd ago" for timestamps 1-7 days ago', () => {
    const days2 = new Date(Date.now() - 2 * 86400 * 1000).toISOString()
    renderCard({ updated_at: days2 })
    expect(screen.getByText('2d ago')).toBeDefined()
  })

  it('shows formatted date for timestamps > 7 days ago', () => {
    const old = new Date(2025, 0, 1).toISOString() // Jan 1, 2025
    renderCard({ updated_at: old })
    // Should show a proper date string, not relative
    expect(screen.queryByText(/ago/)).toBeNull()
  })
})
