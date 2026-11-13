import { expect, test } from '@playwright/test'
import { callsTo, mockApi } from './fixtures'

const jobs = [
  { job_id: 'job-1', title: 'Churn prediction for a shop', status: 'awaiting_approval', first_seen: '2026-11-01T10:00:00Z',
    fit: 0.82, risk: 0.1, risk_flags: [], action: 'bid', price: 900, payment_type: 'fixed', connects_cost: 12, skills: ['Machine Learning'] },
  { job_id: 'job-2', title: 'Send gift cards first', status: 'analysed', first_seen: '2026-11-01T11:00:00Z',
    fit: 0.4, risk: 0.9, risk_flags: ['off_platform_payment'], action: 'skip', price: null, payment_type: 'fixed', connects_cost: 8, skills: [] },
]

test('the inbox lists ranked jobs, filters them and skips one', async ({ page }) => {
  const calls = await mockApi(page, {
    'GET /api/jobs': { json: jobs },
    'POST /api/jobs/job-2/skip': { status: 204 },
  })
  await page.goto('/')

  await expect(page.getByRole('link', { name: 'Churn prediction for a shop', exact: true })).toBeVisible()
  await expect(page.getByText('Risk high (90%)')).toBeVisible()
  await expect(page.getByText('off platform payment')).toBeVisible()

  await page.getByLabel('Recommended action').selectOption('skip')
  await expect(page.getByRole('link', { name: 'Churn prediction for a shop', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: /Skip Send gift cards first/ }).click()
  await expect(page.getByText('Skipped "Send gift cards first".')).toBeVisible()
  expect(callsTo(calls, 'POST', '/api/jobs/job-2/skip')).toHaveLength(1)
})
