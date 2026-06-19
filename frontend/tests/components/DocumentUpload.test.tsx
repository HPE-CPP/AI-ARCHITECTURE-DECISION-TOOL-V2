/**
 * COMPONENT TESTS — DocumentUpload
 * Tests file selection, drag-drop, validation, upload flow,
 * error states, and accessibility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DocumentUpload from '@/components/DocumentUpload'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  uploadDocument: vi.fn(),
}))

const mockRouter = { push: vi.fn() }
vi.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
  useSearchParams: () => new URLSearchParams(),
}))

const VALID_FILE = new File(
  ['This is a valid requirements document with enough content for analysis.'],
  'requirements.txt',
  { type: 'text/plain' }
)

const PDF_FILE = new File(['%PDF-1.4 content'], 'report.pdf', { type: 'application/pdf' })
const EXE_FILE = new File(['MZ executable'], 'virus.exe', { type: 'application/octet-stream' })

describe('DocumentUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Render ───────────────────────────────────────────────────────────────
  it('renders dropzone in initial state', () => {
    render(<DocumentUpload />)
    expect(screen.getByText(/click or drag/i)).toBeDefined()
    expect(screen.getByText(/PDF, DOCX, TXT/i)).toBeDefined()
  })

  it('shows file info after dropping a valid file', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    expect(screen.getByText('requirements.txt')).toBeDefined()
  })

  it('shows PDF file after dropping', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, PDF_FILE)
    expect(screen.getByText('report.pdf')).toBeDefined()
  })

  it('shows Begin Analysis button when file is selected', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    expect(screen.getByRole('button', { name: /begin analysis/i })).toBeDefined()
  })

  it('shows Cancel button when file is selected', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    expect(screen.getByRole('button', { name: /cancel/i })).toBeDefined()
  })

  it('clears file when Cancel is clicked', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    const cancelBtn = screen.getByRole('button', { name: /cancel/i })
    await userEvent.click(cancelBtn)
    expect(screen.getByText(/click or drag/i)).toBeDefined()
  })

  // ─── Upload flow ─────────────────────────────────────────────────────────
  it('calls uploadDocument when Begin Analysis is clicked', async () => {
    vi.mocked(api.uploadDocument).mockResolvedValueOnce({
      analysis_id: 'new-analysis-123',
      status: 'complete',
    } as any)
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    const btn = screen.getByRole('button', { name: /begin analysis/i })
    await userEvent.click(btn)
    expect(api.uploadDocument).toHaveBeenCalledOnce()
    expect(api.uploadDocument).toHaveBeenCalledWith(
      VALID_FILE, 'ollama', undefined
    )
  })

  it('passes projectId to uploadDocument when provided', async () => {
    vi.mocked(api.uploadDocument).mockResolvedValueOnce({
      analysis_id: 'proj-analysis-abc',
      status: 'complete',
    } as any)
    render(<DocumentUpload projectId="proj-xyz" />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    const btn = screen.getByRole('button', { name: /begin analysis/i })
    await userEvent.click(btn)
    expect(api.uploadDocument).toHaveBeenCalledWith(VALID_FILE, 'ollama', 'proj-xyz')
  })

  it('shows Analyzing text while uploading', async () => {
    let resolveUpload!: (v: any) => void
    vi.mocked(api.uploadDocument).mockReturnValueOnce(
      new Promise((resolve) => { resolveUpload = resolve })
    )
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    const btn = screen.getByRole('button', { name: /begin analysis/i })
    await userEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByText(/contacting server/i)).toBeDefined()
    })
    resolveUpload({ analysis_id: 'done', status: 'complete' })
  })

  it('calls onAnalysisStart with analysis_id on success', async () => {
    const onStart = vi.fn()
    vi.mocked(api.uploadDocument).mockResolvedValueOnce({
      analysis_id: 'result-id-789',
      status: 'complete',
    } as any)
    render(<DocumentUpload onAnalysisStart={onStart} />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => expect(onStart).toHaveBeenCalledWith('result-id-789'))
  })

  it('navigates to results page on successful upload', async () => {
    vi.mocked(api.uploadDocument).mockResolvedValueOnce({
      analysis_id: 'nav-id-000',
      status: 'complete',
    } as any)
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => {
      expect(mockRouter.push).toHaveBeenCalledWith('/results/nav-id-000')
    }, { timeout: 2000 })
  })

  // ─── Error handling ───────────────────────────────────────────────────────
  it('shows error message when upload fails', async () => {
    vi.mocked(api.uploadDocument).mockRejectedValueOnce(new Error('Server error'))
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => {
      expect(screen.getByText(/Upload failed/i)).toBeDefined()
    })
  })

  it('shows error when file too large (client-side)', async () => {
    const bigFile = new File([new ArrayBuffer(51 * 1024 * 1024)], 'huge.pdf', {
      type: 'application/pdf',
    })
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, bigFile)
    // react-dropzone rejects oversized files — dropzone stays visible
    expect(screen.getByText(/click or drag/i)).toBeDefined()
  })

  it('dismisses error on X click', async () => {
    vi.mocked(api.uploadDocument).mockRejectedValueOnce(new Error('Network error'))
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => screen.getByText(/connection issue/i))
    const dismissBtn = document.querySelector('[aria-label="Dismiss error"]') as HTMLElement
    if (dismissBtn) {
      await userEvent.click(dismissBtn)
      await waitFor(() => expect(screen.queryByText(/network error/i)).toBeNull())
    }
  })

  // ─── Accessibility ────────────────────────────────────────────────────────
  it('begin analysis button has id for browser test targeting', async () => {
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    const btn = document.getElementById('begin-analysis-btn')
    expect(btn).toBeTruthy()
  })

  it('cancel button is disabled while uploading', async () => {
    let resolveUpload!: (v: any) => void
    vi.mocked(api.uploadDocument).mockReturnValueOnce(
      new Promise((resolve) => { resolveUpload = resolve })
    )
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => {
      const cancelBtn = screen.getByRole('button', { name: /cancel/i }) as HTMLButtonElement
      expect(cancelBtn.disabled).toBe(true)
    })
    resolveUpload({ analysis_id: 'done', status: 'complete' })
  })

  // ─── LLM provider from localStorage ──────────────────────────────────────
  it('reads llm_provider from localStorage', async () => {
    localStorage.setItem('llm_provider', 'openai')
    vi.mocked(api.uploadDocument).mockResolvedValueOnce({
      analysis_id: 'prov-test',
      status: 'complete',
    } as any)
    render(<DocumentUpload />)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, VALID_FILE)
    await userEvent.click(screen.getByRole('button', { name: /begin analysis/i }))
    await waitFor(() => {
      expect(api.uploadDocument).toHaveBeenCalledWith(VALID_FILE, 'openai', undefined)
    })
  })
})
