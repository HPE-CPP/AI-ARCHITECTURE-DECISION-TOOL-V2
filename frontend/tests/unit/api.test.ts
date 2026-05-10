/**
 * UNIT TESTS — API Client (src/lib/api.ts)
 * Tests API contract, error handling, response parsing,
 * and the broken PDF export URL (INTEG-001 regression test).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  uploadDocument,
  getAnalysis,
  submitQuestionnaire,
  submitFollowUp,
  exportAnalysis,
  getQuestionnaireOptions,
} from '@/lib/api'

const MOCK_ANALYSIS_RESULT = {
  analysis_id: 'test-analysis-uuid-1234',
  status: 'complete',
  recommended: 'RAG',
  confidence: 0.85,
  scores: { RAG: 78.5, FineTuning: 52.0, CAG: 35.0, Hybrid: 64.0 },
  ranking: ['RAG', 'Hybrid', 'FineTuning', 'CAG'],
  signals: {
    dataset_size: { value: 'large', confidence: 0.9, source_text: 'test', page_number: 1, source_verified: true },
  },
  factor_breakdown: {},
  why_not: {},
  suitability: {},
  followup_questions: [],
  sensitivity: { is_stable: true, stability_score: 0.9, instabilities: [] },
  decision_trace: [],
  architecture_details: {},
}

beforeEach(() => {
  vi.mocked(fetch).mockReset()
})

// ─── uploadDocument ────────────────────────────────────────────────────────
describe('uploadDocument', () => {
  it('sends POST to /api/v1/upload with multipart form', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    const file = new File(['content for analysis here'], 'req.txt', { type: 'text/plain' })
    const result = await uploadDocument(file, 'openai')

    expect(fetch).toHaveBeenCalledOnce()
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(url).toContain('/api/v1/upload')
    expect(options?.method).toBe('POST')
    expect(result.analysis_id).toBe('test-analysis-uuid-1234')
  })

  it('includes provider query param', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    const file = new File(['long enough content for testing purposes'], 'req.txt', { type: 'text/plain' })
    await uploadDocument(file, 'ollama')
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('provider=ollama')
  })

  it('includes project_id when provided', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    const file = new File(['enough content for analysis testing here'], 'req.txt', { type: 'text/plain' })
    await uploadDocument(file, 'openai', 'proj-123')
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('project_id=proj-123')
  })

  it('throws on non-200 response with detail message', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'File too large' }), { status: 400 })
    )
    const file = new File(['x'], 'r.txt', { type: 'text/plain' })
    await expect(uploadDocument(file, 'openai')).rejects.toThrow('File too large')
  })

  it('throws on network failure', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network unreachable'))
    const file = new File(['content'], 'r.txt', { type: 'text/plain' })
    await expect(uploadDocument(file, 'openai')).rejects.toThrow('Network unreachable')
  })
})

// ─── getAnalysis ───────────────────────────────────────────────────────────
describe('getAnalysis', () => {
  it('calls GET /api/v1/analysis/{id}', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    const result = await getAnalysis('test-analysis-uuid-1234')
    const [url] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/analysis/test-analysis-uuid-1234')
    expect(result.recommended).toBe('RAG')
  })

  it('returns processing status without throwing', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ analysis_id: 'abc', status: 'processing' }), { status: 200 })
    )
    const result = await getAnalysis('abc')
    expect(result.status).toBe('processing')
  })

  it('throws on 404', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Analysis not found' }), { status: 404 })
    )
    await expect(getAnalysis('nonexistent')).rejects.toThrow()
  })
})

// ─── submitQuestionnaire ───────────────────────────────────────────────────
describe('submitQuestionnaire', () => {
  it('sends answers wrapped in { answers: {} } JSON body (FIX FE-005)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    const answers = { dataset_size: 'large', data_volatility: 'high' }
    await submitQuestionnaire(answers, 'ollama')
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(options?.method).toBe('POST')
    // Provider goes as query param, not in body
    expect(String(url)).toContain('provider=ollama')
    // Body must be wrapped: { answers: {...} }
    const body = JSON.parse(options?.body as string)
    expect(body).toHaveProperty('answers')
    expect(body.answers.dataset_size).toBe('large')
    // Provider must NOT be in the body
    expect(body).not.toHaveProperty('provider')
  })

  it('handles empty answers gracefully', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    await expect(submitQuestionnaire({}, 'ollama')).resolves.toBeDefined()
  })
})

// ─── submitFollowUp ────────────────────────────────────────────────────────
describe('submitFollowUp', () => {
  it('sends analysis_id and answers to /api/v1/followup', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(MOCK_ANALYSIS_RESULT), { status: 200 })
    )
    await submitFollowUp('analysis-123', { dataset_size: 'medium' })
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    expect(String(url)).toContain('/api/v1/followup')
    const body = JSON.parse(options?.body as string)
    expect(body.analysis_id).toBe('analysis-123')
    expect(body.answers.dataset_size).toBe('medium')
  })
})

// ─── exportAnalysis (INTEG-001 regression) ────────────────────────────────
describe('exportAnalysis', () => {
  it('calls POST /api/v1/export/pdf — not GET /export/{id}', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(new ArrayBuffer(100), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      })
    )
    // exportAnalysis triggers a download — mock URL.createObjectURL
    globalThis.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
    globalThis.URL.revokeObjectURL = vi.fn()
    await exportAnalysis(MOCK_ANALYSIS_RESULT as any)
    const [url, options] = vi.mocked(fetch).mock.calls[0]
    // CRITICAL: Must be POST not GET
    expect(options?.method).toBe('POST')
    // CRITICAL: Must hit /export/pdf not a per-id endpoint
    expect(String(url)).toContain('/api/v1/export/pdf')
    expect(String(url)).not.toMatch(/\/export\/[0-9a-f-]{36}$/)
  })

  it('sends full result object as JSON body', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(new ArrayBuffer(100), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      })
    )
    globalThis.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
    await exportAnalysis(MOCK_ANALYSIS_RESULT as any)
    const [, options] = vi.mocked(fetch).mock.calls[0]
    const body = JSON.parse(options?.body as string)
    expect(body.recommended).toBe('RAG')
  })

  it('throws on non-200 response', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'PDF generation failed' }), { status: 500 })
    )
    await expect(exportAnalysis(MOCK_ANALYSIS_RESULT as any)).rejects.toThrow()
  })
})

// ─── getQuestionnaireOptions ───────────────────────────────────────────────
describe('getQuestionnaireOptions', () => {
  it('fetches from /api/v1/questionnaire/options', async () => {
    const mockOptions = {
      signals: {
        dataset_size: {
          description: 'Size of dataset',
          required: true,
          options: [{ value: 'small', label: 'Small (< 10k records)' }],
        },
      },
    }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(mockOptions), { status: 200 })
    )
    const result = await getQuestionnaireOptions()
    expect(result.signals).toBeDefined()
    expect(result.signals.dataset_size.required).toBe(true)
  })
})
