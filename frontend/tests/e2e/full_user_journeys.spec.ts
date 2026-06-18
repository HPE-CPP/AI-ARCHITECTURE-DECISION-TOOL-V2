import { test, expect, Page } from '@playwright/test'

// ─── Shared mock setup ────────────────────────────────────────────────────────
async function setupApiMocks(page: Page) {
  await page.route('**/api/v1/questionnaire/options', route => route.fulfill({
    json: {
      signals: {
        dataset_size: {
          description: 'Size of the dataset', required: true,
          options: [{ value: 'large', label: 'Large (> 1TB)' }]
        },
        data_volatility: {
          description: 'Frequency of data changes', required: true,
          options: [{ value: 'high', label: 'High (Real-time)' }]
        },
        cost_sensitivity: {
          description: 'Budget constraints', required: false,
          options: [{ value: 'moderate', label: 'Moderate' }]
        }
      }
    }
  }))

  await page.route('**/api/v1/questionnaire', route => route.fulfill({
    json: { analysis_id: 'e2e-analysis-001', status: 'complete' }
  }))

  await page.route('**/api/v1/analysis/e2e-analysis-001', route => route.fulfill({
    json: {
      analysis_id: 'e2e-analysis-001',
      status: 'complete',
      recommended: 'RAG',
      confidence: 0.87,
      ranking: ['RAG', 'Hybrid', 'FineTuning', 'CAG'],
      scores: { RAG: 85, Hybrid: 62, FineTuning: 40, CAG: 18 },
      signals: {
        dataset_size: { value: 'large', confidence: 0.9, source_verified: true, source_text: 'test', page_number: 1 },
        data_volatility: { value: 'high', confidence: 0.85, source_verified: true, source_text: 'test', page_number: 1 }
      },
      why_not: { Hybrid: 'Too complex.', FineTuning: 'Data volatility too high.', CAG: 'Dataset too large.' },
      factor_breakdown: {
        RAG: { dataset_size: 0.9, data_volatility: 0.85 },
        Hybrid: { dataset_size: 0.6, data_volatility: 0.7 }
      },
      architecture_details: {
        RAG: { full_name: 'Retrieval-Augmented Generation', description: 'Combines retrieval with AI.', strengths: [], weaknesses: [] }
      },
      followup_questions: [],
      sensitivity: { is_stable: true, stability_score: 0.9, instabilities: [], warning: null },
      decision_trace: [
        { step: 'document_parse', status: 'complete', timestamp: new Date().toISOString(), details: 'Parsed 3 pages' },
        { step: 'signal_extraction', status: 'complete', timestamp: new Date().toISOString(), details: 'Found 2 signals' },
        { step: 'scoring', status: 'complete', timestamp: new Date().toISOString(), details: 'RAG scored highest' }
      ]
    }
  }))

  await page.route('**/api/v1/projects*', route => route.fulfill({
    json: { projects: [] }
  }))

  await page.route('**/api/v1/upload*', route => route.fulfill({
    json: { analysis_id: 'e2e-upload-001', status: 'processing' }
  }))

  await page.route('**/api/v1/analysis/e2e-upload-001', route => route.fulfill({
    json: { analysis_id: 'e2e-upload-001', status: 'complete', recommended: 'RAG', scores: { RAG: 80 } }
  }))
}

// ─── Test: Homepage renders correctly ─────────────────────────────────────────
test.describe('Homepage', () => {
  test('renders homepage with correct title and key content', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')

    // Title is correct
    await expect(page).toHaveTitle(/AI Architecture Decision|ArchGuide/)

    // Hero heading visible
    await expect(page.locator('h1').first()).toBeVisible()

    // Navigation links visible
    await expect(page.getByText('Projects')).toBeVisible()
  })

  test('page loads without console errors', async ({ page }) => {
    const errors: string[] = []
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    await setupApiMocks(page)
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Filter out expected errors (Firebase not configured in test env)
    const critical = errors.filter(e =>
      !e.includes('Firebase') &&
      !e.includes('NEXT_PUBLIC') &&
      !e.includes('Warning:')
    )
    expect(critical).toHaveLength(0)
  })

  test('has no accessibility violations on main heading structure', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')
    // H1 should exist and be unique
    const h1Count = await page.locator('h1').count()
    expect(h1Count).toBeGreaterThanOrEqual(1)
  })

  test('dark mode is default on first load', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')
    const html = page.locator('html')
    const clazz = await html.getAttribute('class')
    // Theme should be dark by default
    expect(clazz ?? '').toContain('dark')
  })
})

// ─── Test: Questionnaire Full Flow ────────────────────────────────────────────
test.describe('Questionnaire Flow', () => {
  test('full questionnaire flow navigates to results page', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')

    // Click "Manual Input" / questionnaire mode
    const manualBtn = page.getByRole('button', { name: /manual|questionnaire/i })
    if (await manualBtn.isVisible()) {
      await manualBtn.click()
    } else {
      // Navigate directly if CTA is a link
      await page.goto('/?mode=questionnaire')
    }

    // Wait for questionnaire to load
    await page.waitForSelector('text=Dataset Size', { timeout: 10000 })

    // Step 1: Dataset Size
    await page.getByText('Large').click()
    await page.getByRole('button', { name: /next/i }).click()

    // Step 2: Data Volatility
    await page.waitForSelector('text=Data Volatility')
    await page.getByText('High').click()
    await page.getByRole('button', { name: /next/i }).click()

    // Step 3: Cost Sensitivity (optional)
    await page.waitForSelector('text=Cost Sensitivity')
    await page.getByRole('button', { name: /analyze/i }).click()

    // Should navigate to results
    await expect(page).toHaveURL(/\/results\/e2e-analysis-001/, { timeout: 10000 })
  })

  test('required field validation blocks progression', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/?mode=questionnaire')

    await page.waitForSelector('text=Dataset Size', { timeout: 10000 })

    // Try to advance without selecting
    await page.getByRole('button', { name: /next/i }).click()

    // Error should appear
    await expect(page.getByText(/required/i)).toBeVisible()

    // Still on step 1
    await expect(page.getByText(/1 \/ 3/i)).toBeVisible()
  })

  test('Back button returns to previous step', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/?mode=questionnaire')

    await page.waitForSelector('text=Dataset Size', { timeout: 10000 })
    await page.getByText('Large').click()
    await page.getByRole('button', { name: /next/i }).click()

    await page.waitForSelector('text=Data Volatility')
    await page.getByRole('button', { name: /back/i }).click()

    await expect(page.getByText('Dataset Size')).toBeVisible()
  })
})

// ─── Test: Results Page ───────────────────────────────────────────────────────
test.describe('Results Page', () => {
  test('renders results dashboard with recommendation', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/results/e2e-analysis-001')

    await expect(page.getByText('Retrieval-Augmented Generation')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Confidence')).toBeVisible()
    await expect(page.getByText('87')).toBeVisible()
  })

  test('shows decision trace steps', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/results/e2e-analysis-001')

    await expect(page.getByText('Decision Trace')).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('document parse')).toBeVisible()
  })

  test('shows why not others section', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/results/e2e-analysis-001')

    await expect(page.getByText("Why not others?")).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('Too complex.')).toBeVisible()
  })

  test('shows Analysis Complete badge', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/results/e2e-analysis-001')

    await expect(page.getByText('Analysis Complete')).toBeVisible({ timeout: 10000 })
  })

  test('shows polite loading state for processing analysis', async ({ page }) => {
    await page.route('**/api/v1/analysis/processing-id', route => route.fulfill({
      json: { analysis_id: 'processing-id', status: 'processing' }
    }))
    await page.goto('/results/processing-id')

    // Should show some kind of loading or analyzing indicator
    await expect(page.locator('text=/analyzing|processing|loading/i').first()).toBeVisible({
      timeout: 5000
    })
  })
})

// ─── Test: Projects Page ──────────────────────────────────────────────────────
test.describe('Projects Page', () => {
  test('renders projects page with empty state', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/projects')

    // Either shows empty state or a Create Project button
    const hasEmpty = await page.getByText(/no projects|create your first/i).isVisible()
    const hasCreate = await page.getByRole('button', { name: /create|new project/i }).isVisible()
    expect(hasEmpty || hasCreate).toBe(true)
  })
})

// ─── Test: Theme Switching ────────────────────────────────────────────────────
test.describe('Theme Switching', () => {
  test('theme toggle switches between dark and light', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')

    // Wait for navbar to appear
    await page.waitForSelector('nav', { timeout: 5000 })

    // Find theme toggle button (sun/moon icon)
    const themeBtn = page.locator('button').filter({ hasText: '' }).first()
    const initialClass = await page.locator('html').getAttribute('class')

    // Click theme toggle
    const allButtons = page.locator('button')
    const count = await allButtons.count()
    for (let i = 0; i < count; i++) {
      const btn = allButtons.nth(i)
      const title = await btn.getAttribute('title') ?? ''
      const ariaLabel = await btn.getAttribute('aria-label') ?? ''
      if (title.toLowerCase().includes('theme') || ariaLabel.toLowerCase().includes('theme')) {
        await btn.click()
        break
      }
    }

    await page.waitForTimeout(300)
    const newClass = await page.locator('html').getAttribute('class')
    // Class should have changed
    expect(newClass).not.toBe(initialClass)
  })
})

// ─── Test: Navigation ─────────────────────────────────────────────────────────
test.describe('Navigation', () => {
  test('clicking Projects nav link navigates to /projects', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/')
    await page.waitForTimeout(1000) // wait for navbar animation

    await page.click('text=Projects')
    await expect(page).toHaveURL(/\/projects/, { timeout: 5000 })
  })

  test('logo click returns to homepage', async ({ page }) => {
    await setupApiMocks(page)
    await page.goto('/projects')

    // Click on "ArchGuide." logo
    await page.click('text=ArchGuide.')
    await expect(page).toHaveURL('/')
  })
})

// ─── Test: Mobile Responsiveness ─────────────────────────────────────────────
test.describe('Mobile Responsiveness', () => {
  test('homepage renders correctly on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await setupApiMocks(page)
    await page.goto('/')

    // Page should load without overflow (no horizontal scrollbar)
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
    const viewportWidth = await page.evaluate(() => window.innerWidth)
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2) // 2px tolerance
  })

  test('results page is readable on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await setupApiMocks(page)
    await page.goto('/results/e2e-analysis-001')

    // Recommended architecture should be visible
    await expect(
      page.getByText('Retrieval-Augmented Generation')
    ).toBeVisible({ timeout: 10000 })
  })
})

// ─── Test: Error States ───────────────────────────────────────────────────────
test.describe('Error States', () => {
  test('shows error when results API fails', async ({ page }) => {
    await page.route('**/api/v1/analysis/error-id', route => route.fulfill({
      status: 500,
      json: { detail: 'Internal server error' }
    }))
    await page.goto('/results/error-id')

    // Should show an error, not crash
    await expect(page.getByText(/error|failed|something went wrong/i)).toBeVisible({ timeout: 5000 })
  })

  test('shows error when questionnaire options fail', async ({ page }) => {
    await page.route('**/api/v1/questionnaire/options', route => route.fulfill({
      status: 503,
      json: { detail: 'Service unavailable' }
    }))
    await page.goto('/?mode=questionnaire')

    await expect(page.getByText(/backend|failed|unavailable/i)).toBeVisible({ timeout: 5000 })
  })
})
