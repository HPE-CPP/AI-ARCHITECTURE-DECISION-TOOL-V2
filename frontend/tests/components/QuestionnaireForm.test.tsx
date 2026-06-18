/**
 * COMPONENT TESTS — QuestionnaireForm
 * Tests multi-step form navigation, validation, answer persistence,
 * skip logic, required vs optional signals, submission flow,
 * error handling, loading state, and localStorage persistence.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuestionnaireForm from '@/components/QuestionnaireForm'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getQuestionnaireOptions: vi.fn(),
  submitQuestionnaire: vi.fn(),
}))

const mockRouter = { push: vi.fn() }
vi.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
  useSearchParams: () => new URLSearchParams(),
}))

const MOCK_OPTIONS: api.QuestionnaireOptions = {
  signals: {
    dataset_size: {
      description: 'Size of the primary dataset',
      required: true,
      options: [
        { value: 'small', label: 'Small (< 10GB)' },
        { value: 'medium', label: 'Medium (10GB - 1TB)' },
        { value: 'large', label: 'Large (> 1TB)' },
      ],
    },
    data_volatility: {
      description: 'How frequently the data changes',
      required: true,
      options: [
        { value: 'low', label: 'Low (Static)' },
        { value: 'high', label: 'High (Real-time)' },
      ],
    },
    cost_sensitivity: {
      description: 'Budget constraints',
      required: false,
      options: [
        { value: 'low', label: 'Low (Cost is critical)' },
        { value: 'moderate', label: 'Moderate' },
        { value: 'high', label: 'High (Quality over cost)' },
      ],
    },
  },
}

const MOCK_RESULT: api.AnalysisResult = {
  analysis_id: 'form-test-analysis-id',
  status: 'complete',
  recommended: 'RAG',
  confidence: 0.85,
  ranking: ['RAG', 'Hybrid', 'FineTuning', 'CAG'],
  scores: { RAG: 80, Hybrid: 60, FineTuning: 40, CAG: 20 },
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getQuestionnaireOptions).mockResolvedValue(MOCK_OPTIONS)
})

// ─── Initial Loading ─────────────────────────────────────────────────────────
describe('QuestionnaireForm — Loading State', () => {
  it('shows loading spinner initially', async () => {
    render(<QuestionnaireForm />)
    expect(document.querySelector('.animate-spin')).toBeTruthy()
    // Wait for the async effect to settle to prevent "not wrapped in act(...)" warnings
    await waitFor(() => screen.getByText('Dataset Size'))
  })

  it('renders first question after options load', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => {
      expect(screen.getByText('Dataset Size')).toBeDefined()
    })
  })

  it('shows error when options fail to load', async () => {
    vi.mocked(api.getQuestionnaireOptions).mockRejectedValueOnce(
      new Error('Network error')
    )
    render(<QuestionnaireForm />)
    await waitFor(() => {
      expect(screen.getByText(/backend is running|failed to load/i)).toBeDefined()
    })
  })
})

// ─── Step Display ────────────────────────────────────────────────────────────
describe('QuestionnaireForm — Step Rendering', () => {
  it('shows step 1 of 3 progress indicator', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    expect(screen.getByText(/1 \/ 3/i)).toBeDefined()
  })

  it('shows "Required" badge for required signal', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    expect(screen.getByText('Required')).toBeDefined()
  })

  it('shows description text for current signal', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    expect(screen.getByText('Size of the primary dataset')).toBeDefined()
  })

  it('shows all options for dataset_size', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    expect(screen.getByText('Small')).toBeDefined()
    expect(screen.getByText('Medium')).toBeDefined()
    expect(screen.getByText('Large')).toBeDefined()
  })

  it('Back button is invisible on step 1', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    const backBtn = screen.getByRole('button', { name: /back/i }) as HTMLButtonElement
    // Back button is invisible (disabled/hidden) on step 1
    expect(backBtn.className).toContain('invisible')
  })

  it('Next button is present on step 1', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    expect(screen.getByRole('button', { name: /next/i })).toBeDefined()
  })
})

// ─── Required Field Validation ───────────────────────────────────────────────
describe('QuestionnaireForm — Required Field Validation', () => {
  it('shows error when Next is clicked without answering required signal', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(screen.getByText('This information is required to proceed.')).toBeDefined()
    })
  })

  it('clears error after user selects an option', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('This information is required to proceed.'))
    await userEvent.click(screen.getByText('Large'))
    await waitFor(() => {
      expect(screen.queryByText('This information is required to proceed.')).toBeNull()
    })
  })

  it('does not advance to step 2 without answering required step 1', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      // Still on step 1
      expect(screen.getByText(/1 \/ 3/i)).toBeDefined()
    })
  })
})

// ─── Navigation ──────────────────────────────────────────────────────────────
describe('QuestionnaireForm — Multi-Step Navigation', () => {
  it('advances to step 2 after answering required step 1', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(screen.getByText('Data Volatility')).toBeDefined()
      expect(screen.getByText(/2 \/ 3/i)).toBeDefined()
    })
  })

  it('Back button navigates to previous step', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    await waitFor(() => {
      expect(screen.getByText('Dataset Size')).toBeDefined()
      expect(screen.getByText(/1 \/ 3/i)).toBeDefined()
    })
  })

  it('progress bar advances with each step', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    // Step 1: ~33%
    expect(screen.getByText(/33%/i)).toBeDefined()
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      // Step 2: ~67%
      expect(screen.getByText(/67%/i)).toBeDefined()
    })
  })

  it('last step shows "Analyze" button instead of "Next"', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    // Step 1
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    // Step 2
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    // Step 3 (optional) — Analyze button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /analyze/i })).toBeDefined()
    })
  })
})

// ─── Skip Logic ──────────────────────────────────────────────────────────────
describe('QuestionnaireForm — Skip Behavior', () => {
  it('Skip button appears for optional signals', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    // Navigate to step 3 (cost_sensitivity is optional)
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Cost Sensitivity'))
    expect(screen.getByRole('button', { name: /skip/i })).toBeDefined()
  })

  it('Skip button not shown when option is already selected', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Cost Sensitivity'))
    await userEvent.click(screen.getByText('Moderate'))
    // Once selected, Skip button should be gone
    expect(screen.queryByRole('button', { name: /skip/i })).toBeNull()
  })

  it('clicking same option deselects it (toggle)', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    // Click again to deselect
    await userEvent.click(screen.getByText('Large'))
    // Now Next should show error (required field unselected)
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => {
      expect(screen.getByText('This information is required to proceed.')).toBeDefined()
    })
  })
})

// ─── localStorage Persistence ────────────────────────────────────────────────
describe('QuestionnaireForm — Persistence', () => {
  it('saves answers to localStorage on selection', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    const saved = localStorage.getItem('questionnaire_answers')
    expect(saved).not.toBeNull()
    const parsed = JSON.parse(saved!)
    expect(parsed.dataset_size).toBe('large')
  })

  it('restores saved answers from localStorage on mount', async () => {
    localStorage.setItem('questionnaire_answers', JSON.stringify({ dataset_size: 'medium' }))
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    // "Medium" button should appear selected
    const mediumBtn = screen.getByText('Medium').closest('button')
    expect(mediumBtn?.className).toContain('bg-[color:var(--text-primary)]')
  })

  it('uses projectId-scoped key when projectId provided', async () => {
    render(<QuestionnaireForm projectId="proj-123" />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Small'))
    expect(localStorage.getItem('project_proj-123_answers')).not.toBeNull()
  })
})

// ─── Submission ──────────────────────────────────────────────────────────────
describe('QuestionnaireForm — Submission', () => {
  async function fillAndReachAnalyze() {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByRole('button', { name: /analyze/i }))
  }

  it('calls submitQuestionnaire on Analyze click', async () => {
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      expect(api.submitQuestionnaire).toHaveBeenCalledOnce()
    })
  })

  it('passes correct answers to submitQuestionnaire', async () => {
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      const [answers] = vi.mocked(api.submitQuestionnaire).mock.calls[0]
      expect(answers.dataset_size).toBe('large')
      expect(answers.data_volatility).toBe('high')
    })
  })

  it('passes projectId to submitQuestionnaire', async () => {
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    render(<QuestionnaireForm projectId="proj-456" />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByRole('button', { name: /analyze/i }))
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      const callArgs = vi.mocked(api.submitQuestionnaire).mock.calls[0]
      expect(callArgs[2]).toBe('proj-456')
    })
  })

  it('shows Analyzing spinner while submission is pending', async () => {
    let resolve!: (v: any) => void
    vi.mocked(api.submitQuestionnaire).mockReturnValueOnce(
      new Promise(r => { resolve = r })
    )
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      expect(screen.getByText(/analyzing/i)).toBeDefined()
    })
    resolve(MOCK_RESULT)
  })

  it('navigates to results after successful submission', async () => {
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      expect(mockRouter.push).toHaveBeenCalledWith(
        expect.stringContaining('/results/form-test-analysis-id')
      )
    }, { timeout: 2000 })
  })

  it('shows error message when submission fails', async () => {
    vi.mocked(api.submitQuestionnaire).mockRejectedValueOnce(
      new Error('Backend unavailable')
    )
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      expect(screen.getByText(/unable to submit your answers/i)).toBeDefined()
    })
  })

  it('calls onAnalysisStart with analysis_id on success', async () => {
    const onStart = vi.fn()
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    render(<QuestionnaireForm onAnalysisStart={onStart} />)
    await waitFor(() => screen.getByText('Dataset Size'))
    await userEvent.click(screen.getByText('Large'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByText('Data Volatility'))
    await userEvent.click(screen.getByText('High'))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => screen.getByRole('button', { name: /analyze/i }))
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      expect(onStart).toHaveBeenCalledWith('form-test-analysis-id')
    })
  })

  it('reads llm_provider from localStorage for submission', async () => {
    localStorage.setItem('llm_provider', 'openai')
    vi.mocked(api.submitQuestionnaire).mockResolvedValueOnce(MOCK_RESULT)
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      const [, provider] = vi.mocked(api.submitQuestionnaire).mock.calls[0]
      expect(provider).toBe('openai')
    })
  })

  it('button is disabled during submission', async () => {
    let resolve!: (v: any) => void
    vi.mocked(api.submitQuestionnaire).mockReturnValueOnce(
      new Promise(r => { resolve = r })
    )
    await fillAndReachAnalyze()
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }))
    await waitFor(() => {
      const btn = document.getElementById('questionnaire-next-btn') as HTMLButtonElement
      expect(btn?.disabled).toBe(true)
    })
    resolve(MOCK_RESULT)
  })
})

// ─── Accessibility ───────────────────────────────────────────────────────────
describe('QuestionnaireForm — Accessibility', () => {
  it('Next/Analyze button has id for test targeting', async () => {
    render(<QuestionnaireForm />)
    await waitFor(() => screen.getByText('Dataset Size'))
    const btn = document.getElementById('questionnaire-next-btn')
    expect(btn).toBeTruthy()
  })
})
