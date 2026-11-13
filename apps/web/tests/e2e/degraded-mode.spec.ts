import { expect, test } from '@playwright/test'
import { healthyHealth, mockApi } from './fixtures'

const bannerText = 'Marketplace unavailable: new work is queued and will resume automatically'

test('the degraded banner appears when the marketplace is down', async ({ page }) => {
  await mockApi(page, {
    'GET /api/health': { json: { ...healthyHealth, marketplace: false, degraded: true, queued_jobs: 3 } },
  })
  await page.goto('/')
  await expect(page.getByRole('status').filter({ hasText: bannerText })).toBeVisible()
})

test('there is no banner when everything is healthy', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Job inbox' })).toBeVisible()
  await expect(page.getByText(bannerText)).toHaveCount(0)
})

test('the messages page shows a clear state when the marketplace answers 503', async ({ page }) => {
  await mockApi(page, { 'GET /api/threads': { status: 503, json: { detail: 'marketplace unavailable' } } })
  await page.goto('/messages')
  await expect(page.getByRole('alert')).toContainText('Marketplace unavailable')
})
