import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

// A freelancer checks GigBid on a phone: pages must fit the screen with no sideways scrolling.
test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

const jobs = [
  { job_id: 'job-1', title: 'Churn prediction for a shop with a very long title that has to wrap on a small screen',
    status: 'awaiting_approval', first_seen: '2026-11-01T10:00:00Z', fit: 0.82, risk: 0.1, risk_flags: [], action: 'bid',
    price: 900, payment_type: 'fixed', connects_cost: 12, skills: ['Machine Learning', 'Python', 'Data Science'] },
]

async function noSidewaysScroll(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
}

test('the inbox and the main pages fit a phone screen', async ({ page }) => {
  await mockApi(page, { 'GET /api/jobs': { json: jobs }, 'GET /api/approvals': { json: [] } })
  await page.goto('/')
  await expect(page.getByRole('link', { name: /^Churn prediction for a shop/ })).toBeVisible()
  await noSidewaysScroll(page)

  // the top links fold into a menu on a phone
  await page.getByRole('button', { name: 'Menu' }).click()
  await page.getByRole('link', { name: 'Approvals' }).click()
  await expect(page).toHaveURL(/\/approvals$/)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await noSidewaysScroll(page)
})
