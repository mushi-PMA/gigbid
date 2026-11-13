import { expect, test } from '@playwright/test'
import { approvalItem, callsTo, ENCODED_THREAD_ID, mockApi, THREAD_ID } from './fixtures'

test('rejecting needs a reason and then sends action=reject', async ({ page }) => {
  const calls = await mockApi(page, {
    [`GET /api/approvals/${THREAD_ID}`]: { json: approvalItem },
    [`POST /api/approvals/${THREAD_ID}`]: { status: 202, json: { thread_id: THREAD_ID, queued: true } },
  })

  await page.goto(`/studio/${ENCODED_THREAD_ID}`)
  await page.getByRole('button', { name: 'Reject', exact: true }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Confirm rejection' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Please say why')
  expect(callsTo(calls, 'POST', `/api/approvals/${THREAD_ID}`)).toHaveLength(0)

  await dialog.getByLabel('Reason (required)').fill('The client budget is too low.')
  await dialog.getByRole('button', { name: 'Confirm rejection' }).click()

  await expect(page).toHaveURL(new RegExp(`/runs/${ENCODED_THREAD_ID}$`))
  const [decision] = callsTo(calls, 'POST', `/api/approvals/${THREAD_ID}`)
  expect(decision.body).toMatchObject({ action: 'reject', reason: 'The client budget is too low.' })
})
