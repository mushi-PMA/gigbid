import { expect, test } from '@playwright/test'
import { callsTo, defaultSettings, mockApi, user } from './fixtures'

test('a new user registers, picks a persona, sets a budget and saves settings', async ({ page }) => {
  const calls = await mockApi(page, {
    'GET /api/auth/me': { status: 401, json: { detail: 'not signed in' } },
    'POST /api/auth/register': { status: 201, json: { user, token: 'tok-123' } },
    'PUT /api/settings': (request) => ({ json: request.postDataJSON() }),
  })

  await page.goto('/')
  await expect(page).toHaveURL(/\/sign-in$/)

  await page.getByRole('button', { name: 'Create account' }).first().click()
  await page.getByLabel('Your name').fill('Sam')
  await page.getByLabel('Email').fill('sam@example.com')
  await page.getByLabel('Password').fill('correct-horse-battery')
  await page.getByRole('button', { name: 'Create account' }).last().click()

  await expect(page).toHaveURL(/\/onboarding$/)
  expect(callsTo(calls, 'POST', '/api/auth/register')).toHaveLength(1)

  await page.getByRole('radio', { name: /AI and ML engineer/ }).check()
  await page.getByLabel('Weekly Connects budget').fill('45')
  await page.getByRole('button', { name: 'Save settings' }).click()

  await expect(page.getByText('Settings saved.')).toBeVisible()
  const [save] = callsTo(calls, 'PUT', '/api/settings')
  expect(save.body).toMatchObject({ persona: 'ai_ml_engineer', weekly_connects_budget: 45, rates: defaultSettings.rates })
})
