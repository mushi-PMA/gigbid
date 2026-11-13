import { expect, test } from '@playwright/test'
import { approvalItem, callsTo, ENCODED_THREAD_ID, mockApi, THREAD_ID } from './fixtures'

test('editing a draft sends action=edit with the edited text', async ({ page }) => {
  const calls = await mockApi(page, {
    [`GET /api/approvals/${THREAD_ID}`]: { json: approvalItem },
    [`POST /api/approvals/${THREAD_ID}`]: { status: 202, json: { thread_id: THREAD_ID, queued: true } },
  })

  await page.goto(`/studio/${ENCODED_THREAD_ID}`)
  await page.getByRole('button', { name: 'Edit draft' }).click()

  const editor = page.getByLabel('Cover letter text')
  await editor.fill('Hello, I would love to help with your churn model.')
  await expect(page.getByText('You changed the text')).toBeVisible()

  await page.getByRole('button', { name: 'Approve my edited version' }).click()
  await expect(page).toHaveURL(new RegExp(`/runs/${ENCODED_THREAD_ID}$`))

  const [decision] = callsTo(calls, 'POST', `/api/approvals/${THREAD_ID}`)
  expect(decision.body).toMatchObject({
    action: 'edit',
    edited_text: 'Hello, I would love to help with your churn model.',
    edited_answers: ['I have done this before.'],
  })
})
