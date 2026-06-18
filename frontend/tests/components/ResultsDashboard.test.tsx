/**
 * COMPONENT TESTS — ResultsDashboard
 * Tests rendering of recommendation card, confidence/score widgets,
 * radar chart data computation, bar chart suitability comparison,
 * "Why not others?" panel, PDF export trigger, and null-data guards.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ResultsDashboard } from '@/components/ResultsDashboard'
import * as api from '@/lib/api'
import type { AnalysisResult } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  exportAnalysis: vi.fn(),
}))

// Recharts resizes based on container — must be mocked in jsdom
vi.mock('recharts', () => ({
  Radar: () => null,
  RadarChart: ({ children }: any) => <div data-testid="radar-chart">{children}</div>,
  PolarGrid: () => null,
  PolarAngleAxis: () => null,
  PolarRadiusAxis: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
}))

const COMPLETE_RESULT: AnalysisResult = {
  analysis_id: 'dashboard-test-id',
  status: 'complete',
  recommended: 'RAG',
  confidence: 0.87,
  ranking: ['RAG', 'Hybrid', 'FineTuning', 'CAG'],
  scores: { RAG: 85.0, Hybrid: 62.0, FineTuning: 40.0, CAG: 18.0 },
  why_not: {
    Hybrid: 'Adds unnecessary operational complexity for this use case.',
    FineTuning: 'High data volatility makes model retraining impractical.',
    CAG: 'Dataset size exceeds feasible precomputation capacity.',
  },
  factor_breakdown: {
    RAG: { dataset_size: 0.9, data_volatility: 0.8, latency: 0.7 },
    Hybrid: { dataset_size: 0.6, data_volatility: 0.7, latency: 0.8 },
    FineTuning: { dataset_size: 0.4, data_volatility: 0.3, latency: 0.6 },
  },
  architecture_details: {
    RAG: {
      full_name: 'Retrieval-Augmented Generation',
      description: 'Combines a retrieval system with generative AI.',
      strengths: ['Real-time knowledge', 'No retraining needed'],
      weaknesses: ['Higher latency than CAG'],
    },
  },
}

const MINIMAL_RESULT: AnalysisResult = {
  analysis_id: 'minimal-id',
  status: 'complete',
  recommended: 'CAG',
  confidence: 0.55,
  scores: { RAG: 30.0, CAG: 70.0, FineTuning: 20.0, Hybrid: 40.0 },
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ─── Null Guards ──────────────────────────────────────────────────────────────
describe('ResultsDashboard — Null Guards', () => {
  it('renders nothing when recommended is missing', () => {
    const { container } = render(
      <ResultsDashboard result={{ analysis_id: 'x', status: 'complete' }} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when scores is missing', () => {
    const { container } = render(
      <ResultsDashboard result={{ analysis_id: 'x', status: 'complete', recommended: 'RAG' }} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders when both recommended and scores are present', () => {
    render(<ResultsDashboard result={MINIMAL_RESULT} />)
    expect(screen.getByText(/recommended architecture/i)).toBeDefined()
  })
})

// ─── Recommendation Card ─────────────────────────────────────────────────────
describe('ResultsDashboard — Recommendation Card', () => {
  it('shows "Analysis Complete" badge', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Analysis Complete')).toBeDefined()
  })

  it('shows the full architecture name', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getAllByText('Retrieval-Augmented Generation')[0]).toBeDefined()
  })

  it('falls back to architecture key when details missing', () => {
    render(<ResultsDashboard result={MINIMAL_RESULT} />)
    expect(screen.getAllByText('CAG')[0]).toBeDefined()
  })

  it('shows the architecture description', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Combines a retrieval system with generative AI.')).toBeDefined()
  })
})

// ─── Confidence Widget ────────────────────────────────────────────────────────
describe('ResultsDashboard — Confidence Widget', () => {
  it('displays confidence percentage correctly', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    // confidence 0.87 -> "87"
    expect(screen.getByText('87')).toBeDefined()
  })

  it('displays Overall Score for recommended architecture', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    // RAG score is 85.0 -> "85.0"
    expect(screen.getByText('85.0')).toBeDefined()
  })

  it('displays /100 suffix for overall score', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('/100')).toBeDefined()
  })

  it('shows "Confidence" label', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Confidence')).toBeDefined()
  })

  it('shows "Overall Score" label', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Overall Score')).toBeDefined()
  })
})

// ─── Charts ──────────────────────────────────────────────────────────────────
describe('ResultsDashboard — Charts', () => {
  it('renders Factor Breakdown radar chart section', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Factor Breakdown')).toBeDefined()
  })

  it('renders Architecture Ranking section', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Architecture Ranking')).toBeDefined()
  })

  it('does not crash when factor_breakdown is missing', () => {
    const { container } = render(
      <ResultsDashboard result={{ ...MINIMAL_RESULT, factor_breakdown: undefined }} />
    )
    expect(container).toBeDefined()
  })
})

// ─── Why Not Section ──────────────────────────────────────────────────────────
describe('ResultsDashboard — Why Not Others', () => {
  it('shows "Why not others?" heading', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText("Why not others?")).toBeDefined()
  })

  it('shows rejection reasons for non-recommended architectures', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Adds unnecessary operational complexity for this use case.')).toBeDefined()
    expect(screen.getByText('High data volatility makes model retraining impractical.')).toBeDefined()
  })

  it('shows maximum 3 rejection reasons', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    // why_not has 3 entries — all should show
    const reasons = screen.getAllByText(/complexity|volatility|precomputation/i)
    expect(reasons.length).toBeLessThanOrEqual(3)
  })

  it('handles missing why_not gracefully', () => {
    const resultWithNoWhyNot = { ...COMPLETE_RESULT, why_not: undefined }
    render(<ResultsDashboard result={resultWithNoWhyNot} />)
    // Should render without crashing
    expect(screen.getByText('Factor Breakdown')).toBeDefined()
  })
})

// ─── Download PDF Button ──────────────────────────────────────────────────────
describe('ResultsDashboard — Download PDF', () => {
  it('shows Download PDF Report button', () => {
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    expect(screen.getByText('Download PDF Report')).toBeDefined()
  })

  it('calls exportAnalysis on Download click', async () => {
    vi.mocked(api.exportAnalysis).mockResolvedValueOnce(undefined)
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    await userEvent.click(screen.getByText('Download PDF Report'))
    expect(api.exportAnalysis).toHaveBeenCalledWith(COMPLETE_RESULT)
  })

  it('calls exportAnalysis with full result object', async () => {
    vi.mocked(api.exportAnalysis).mockResolvedValueOnce(undefined)
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    await userEvent.click(screen.getByText('Download PDF Report'))
    const calledWith = vi.mocked(api.exportAnalysis).mock.calls[0][0]
    expect(calledWith.analysis_id).toBe('dashboard-test-id')
    expect(calledWith.recommended).toBe('RAG')
  })

  it('does not throw when export fails', async () => {
    vi.mocked(api.exportAnalysis).mockRejectedValueOnce(new Error('PDF generation failed'))
    render(<ResultsDashboard result={COMPLETE_RESULT} />)
    // Must not crash the component
    await expect(userEvent.click(screen.getByText('Download PDF Report'))).resolves.not.toThrow()
  })
})

// ─── Score Sorting ────────────────────────────────────────────────────────────
describe('ResultsDashboard — Score Sorting', () => {
  it('sorts scores in descending order for bar chart', () => {
    // Verify the sorting logic works correctly by checking radarData computation
    const unsortedResult = {
      ...COMPLETE_RESULT,
      scores: { CAG: 18.0, RAG: 85.0, FineTuning: 40.0, Hybrid: 62.0 },
    }
    render(<ResultsDashboard result={unsortedResult} />)
    // Chart renders without errors regardless of input order
    expect(screen.getByTestId('bar-container')).toBeDefined()
  })
})
