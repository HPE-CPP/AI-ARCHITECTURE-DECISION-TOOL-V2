/**
 * UNIT TESTS — projects-store.ts
 * Tests getGuestId persistence, API contract for all CRUD operations,
 * updateProject payload mapping bugs, duplicateProject behavior,
 * localStorage helpers, and event dispatch.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getGuestId,
  getProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
  duplicateProject,
  getLastActiveProjectId,
  setLastActiveProjectId,
} from '@/lib/projects-store'

const MOCK_PROJECT = {
  id: 'proj-001',
  user_id: 'user-001',
  name: 'Test Project',
  description: 'Test description',
  status: 'empty' as const,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

beforeEach(() => {
  vi.mocked(fetch).mockReset()
  localStorage.clear()
})

// ─── getGuestId ───────────────────────────────────────────────────────────────
describe('getGuestId', () => {
  it('generates a guest ID prefixed with "guest_"', () => {
    const id = getGuestId()
    expect(id).toMatch(/^guest_/)
  })

  it('persists the same ID across calls (localStorage)', () => {
    const id1 = getGuestId()
    const id2 = getGuestId()
    expect(id1).toBe(id2)
  })

  it('returns existing ID if already in localStorage', () => {
    localStorage.setItem('archguide_guest_id', 'guest_existing-id')
    expect(getGuestId()).toBe('guest_existing-id')
  })

  it('does not generate a new ID if one already exists', () => {
    const first = getGuestId()
    // Clear the mock reset but keep localStorage
    const second = getGuestId()
    expect(first).toBe(second)
  })
})

// ─── getProjects ──────────────────────────────────────────────────────────────
describe('getProjects', () => {
  it('fetches with user_id query param', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ projects: [MOCK_PROJECT] }), { status: 200 })
    )
    await getProjects('user-001')
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('user_id=user-001')
  })

  it('uses guest ID when no userId provided', async () => {
    localStorage.setItem('archguide_guest_id', 'guest_test-123')
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ projects: [] }), { status: 200 })
    )
    await getProjects()
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('user_id=guest_test-123')
  })

  it('returns empty array on network failure', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network down'))
    const result = await getProjects('user-001')
    expect(result).toEqual([])
  })

  it('returns empty array on non-200 response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    )
    const result = await getProjects('user-001')
    expect(result).toEqual([])
  })

  it('returns projects array from response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ projects: [MOCK_PROJECT] }), { status: 200 })
    )
    const result = await getProjects('user-001')
    expect(result).toHaveLength(1)
    expect(result[0].id).toBe('proj-001')
  })
})

// ─── getProject ───────────────────────────────────────────────────────────────
describe('getProject', () => {
  it('fetches the correct project endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await getProject('proj-001')
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/projects/proj-001')
  })

  it('returns undefined on 404', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    )
    const result = await getProject('nonexistent')
    expect(result).toBeUndefined()
  })

  it('returns undefined on network failure', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Timeout'))
    const result = await getProject('proj-001')
    expect(result).toBeUndefined()
  })
})

// ─── createProject ────────────────────────────────────────────────────────────
describe('createProject', () => {
  it('sends POST to /api/v1/projects with correct body', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await createProject({ name: 'New Project', description: 'Test desc', userId: 'user-001' })
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/projects')
    expect(options?.method).toBe('POST')
    const body = JSON.parse(options?.body as string)
    expect(body.name).toBe('New Project')
    expect(body.user_id).toBe('user-001')
  })

  it('trims whitespace from name and description', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await createProject({ name: '  Padded Name  ', description: '  Desc  ', userId: 'user-001' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.name).toBe('Padded Name')
    expect(body.description).toBe('Desc')
  })

  it('uses guest ID when no userId provided', async () => {
    localStorage.setItem('archguide_guest_id', 'guest_abc')
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await createProject({ name: 'Guest Project', description: '' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.user_id).toBe('guest_abc')
  })

  it('throws when API returns an error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Name already taken' }), { status: 400 })
    )
    await expect(
      createProject({ name: 'Dup', description: '' })
    ).rejects.toThrow('Name already taken')
  })

  it('dispatches "projects-updated" event after creation', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    const listener = vi.fn()
    window.addEventListener('projects-updated', listener)
    await createProject({ name: 'Test', description: '', userId: 'user-001' })
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener('projects-updated', listener)
  })
})

// ─── updateProject (BUG TRACKING) ─────────────────────────────────────────────
describe('updateProject — Payload Mapping', () => {
  it('maps analysisId to analysis_id in payload', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await updateProject('proj-001', { analysisId: 'analysis-123' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.analysis_id).toBe('analysis-123')
  })

  it('maps userId to user_id in payload', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await updateProject('proj-001', { userId: 'user-new' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.user_id).toBe('user-new')
  })

  it('FE-002 FIXED: falsy description IS now sent (empty string clears description)', async () => {
    // FIX FE-002: Now uses !== undefined check, so empty string is correctly sent
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await updateProject('proj-001', { description: '' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    // Empty string should now be included — user can clear a description
    expect(Object.keys(body)).toContain('description')
    expect(body.description).toBe('')
  })

  it('sends correct fields for status update', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await updateProject('proj-001', { status: 'completed' })
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.status).toBe('completed')
  })

  it('returns null on API failure', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    )
    const result = await updateProject('nonexistent', { name: 'New' })
    expect(result).toBeNull()
  })

  it('uses PUT method', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    await updateProject('proj-001', { name: 'Updated' })
    const [, options] = vi.mocked(fetch).mock.calls[0]
    expect(options?.method).toBe('PUT')
  })
})

// ─── deleteProject ────────────────────────────────────────────────────────────
describe('deleteProject', () => {
  it('sends DELETE to correct endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteProject('proj-001')
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/projects/proj-001')
    expect(options?.method).toBe('DELETE')
  })

  it('dispatches "projects-updated" event after deletion', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }))
    const listener = vi.fn()
    window.addEventListener('projects-updated', listener)
    await deleteProject('proj-001')
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener('projects-updated', listener)
  })
})

// ─── duplicateProject ──────────────────────────────────────────────────────────
describe('duplicateProject', () => {
  it('creates copy with "(Copy)" appended to name', async () => {
    // First call: getProject
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_PROJECT), { status: 200 })
    )
    // Second call: createProject
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ...MOCK_PROJECT, id: 'proj-002', name: 'Test Project (Copy)' }), { status: 200 })
    )
    const result = await duplicateProject('proj-001', 'user-001')
    expect(result?.name).toBe('Test Project (Copy)')
  })

  it('returns null when original project not found', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
    )
    const result = await duplicateProject('nonexistent')
    expect(result).toBeNull()
  })
})

// ─── localStorage Helpers ──────────────────────────────────────────────────────
describe('localStorage Helpers', () => {
  it('getLastActiveProjectId returns null when not set', () => {
    expect(getLastActiveProjectId()).toBeNull()
  })

  it('setLastActiveProjectId persists to localStorage', () => {
    setLastActiveProjectId('proj-xyz')
    expect(localStorage.getItem('archguide_last_project')).toBe('proj-xyz')
  })

  it('getLastActiveProjectId returns stored value', () => {
    localStorage.setItem('archguide_last_project', 'proj-abc')
    expect(getLastActiveProjectId()).toBe('proj-abc')
  })
})
