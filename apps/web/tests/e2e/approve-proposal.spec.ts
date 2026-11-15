import { expect, test } from '@playwright/test'
import { approvalItem, callsTo, ENCODED_THREAD_ID, mockApi, THREAD_ID } from './fixtures'

test('approving a proposal shows evidence on hover and sends action=approve', async ({ page }) => {
  const calls = await mockApi(page, {
    [`GET /api/approvals/${THREAD_ID}`]: { json: approvalItem },
    [`POST /api/approvals/${THREAD_ID}`]: { status: 202, json: { thread_id: THREAD_ID, queued: true } },
  })

  await page.goto(`/studio/${ENCODED_THREAD_ID}`)
  await expect(page.getByRole('heading', { name: /Proposal for Churn prediction/ })).toBeVisible()

  // Hover on a citation shows the evidence behind it.
  await page.getByText('cs-aiml-03', { exact: true }).hover()
  const tooltip = page.getByRole('tooltip')
  await expect(tooltip).toBeVisible()
  await expect(tooltip).toContainText('Churn model for a retailer')
  await expect(tooltip).toContainText('cut customer churn by 18 percent')

  // The same evidence shows on keyboard focus of a claim.
  await page.mouse.move(0, 0)
  await page.locator('.claim').first().focus()
  await expect(page.getByRole('tooltip')).toContainText('Churn model for a retailer')

  // The dry run shows what will be sent and the Connects cost.
  await expect(page.getByText('Connects cost:')).toContainText('12')

  await page.getByRole('button', { name: 'Approve and send' }).click()
  await expect(page).toHaveURL(new RegExp(`/runs/${ENCODED_THREAD_ID}$`))
  const [decision] = callsTo(calls, 'POST', `/api/approvals/${THREAD_ID}`)
  expect(decision.body).toMatchObject({ action: 'approve' })
  await expect(page.getByText('Run started')).toBeVisible()
})
