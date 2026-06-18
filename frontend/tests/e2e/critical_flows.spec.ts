import { test, expect } from '@playwright/test'
import path from 'path'

// Mocking external API responses for reliable E2E tests
test.beforeEach(async ({ page }) => {
  // Mock questionnaire options
  await page.route('**/api/v1/questionnaire/options', async route => {
    const json = {
      signals: {
        dataset_size: {
          description: "Size of the primary dataset",
          required: true,
          options: [
            { value: "small", label: "Small (< 10GB)" },
            { value: "medium", label: "Medium (10GB - 1TB)" },
            { value: "large", label: "Large (> 1TB)" }
          ]
        },
        data_volatility: {
          description: "How frequently the data changes",
          required: true,
          options: [
            { value: "low", label: "Low (Static, updated rarely)" },
            { value: "high", label: "High (Real-time, frequent updates)" }
          ]
        }
      }
    }
    await route.fulfill({ json })
  })

  // Mock questionnaire submit
  await page.route('**/api/v1/questionnaire', async route => {
    const json = { analysis_id: 'e2e-mock-id-1234', status: 'complete' }
    // small delay to simulate processing
    await new Promise(r => setTimeout(r, 500))
    await route.fulfill({ json })
  })

  // Mock analysis result
  await page.route('**/api/v1/analysis/e2e-mock-id-1234', async route => {
    const json = {
      analysis_id: 'e2e-mock-id-1234',
      status: 'complete',
      recommended: 'RAG',
      confidence: 0.85,
      ranking: ['RAG', 'Hybrid', 'FineTuning', 'CAG'],
      scores: { RAG: 85, Hybrid: 60, FineTuning: 45, CAG: 20 },
      signals: {
        dataset_size: { value: 'large', confidence: 0.9, source_verified: true },
        data_volatility: { value: 'high', confidence: 0.8, source_verified: true }
      },
      followup_questions: [],
      factor_breakdown: {},
      why_not: {},
      suitability: {},
      decision_trace: [],
      architecture_details: {}
    }
    await route.fulfill({ json })
  })
})

test.describe('Critical User Flows', () => {

  test('User can complete the manual questionnaire and see results', async ({ page }) => {
    // Navigate to homepage
    await page.goto('/')

    // Click Manual Input button
    await page.click('text="Manual Input"')
    await expect(page).toHaveURL(/.*mode=questionnaire/)

    // Step 1: Dataset Size
    await expect(page.locator('h2')).toContainText('Dataset Size', { ignoreCase: true })
    await page.click('text="Large"') // Select large
    await page.click('button:has-text("Next")')

    // Step 2: Data Volatility
    await expect(page.locator('h2')).toContainText('Data Volatility', { ignoreCase: true })
    await page.click('text="High"') // Select high
    
    // Last step -> Analyze
    await page.click('button:has-text("Analyze")')

    // Should redirect to results page
    await expect(page).toHaveURL(/\/results\/e2e-mock-id-1234/)

    // Verify results page content
    await expect(page.locator('h1')).toContainText('RAG') // Recommended architecture
    await expect(page.locator('text="Confidence"')).toBeVisible()
    
    // Check signals panel
    await expect(page.locator('text="Extracted Signals"')).toBeVisible()
    await expect(page.locator('text="large"')).toBeVisible()
    await expect(page.locator('text="high"')).toBeVisible()
  })

  test('Homepage renders correctly', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveTitle(/AI Architecture Decision Platform|Vite \+ React/) // depending on what index.html says
    await expect(page.locator('text="Enterprise AI Architecture"')).toBeVisible()
  })

})
