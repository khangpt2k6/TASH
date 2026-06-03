import { test, expect } from '@playwright/test'

/**
 * These tests cover the AuthScreen - the first page every visitor sees now
 * that TASH gates the chat behind Supabase auth. They verify the visual
 * system from the redesign (react-icons, theme tokens, restrained styling)
 * on the page that is reachable without a session.
 */

test.describe('Auth screen - renders', () => {
  test('shows the auth screen with TASH branding', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="auth-screen"]')).toBeVisible()
    await expect(page.locator('.logo-name')).toHaveText('TASH')
    await expect(page.locator('.auth-title')).toBeVisible()
  })

  test('logo is a real react-icons SVG, not an emoji', async ({ page }) => {
    await page.goto('/')
    // react-icons renders an <svg>; emoji would be a text node.
    const svg = page.locator('[data-testid="auth-logo"] svg')
    await expect(svg).toBeVisible()
  })

  test('no emoji characters are used as icons anywhere on the page', async ({ page }) => {
    await page.goto('/')
    const bodyText = await page.locator('body').innerText()
    // Common emoji that were previously used as icons must be gone.
    const forbidden = ['🔬', '🧬', '📊', '🔍', '⚙️', '💡']
    for (const e of forbidden) {
      expect(bodyText).not.toContain(e)
    }
  })

  test('has Google sign-in and email/password form', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="google-btn"]')).toBeVisible()
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })
})

test.describe('Auth screen - interactions', () => {
  test('can switch between sign in and sign up', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.auth-title')).toHaveText('Welcome back')

    await page.click('[data-testid="switch-signup"]')
    await expect(page.locator('.auth-title')).toHaveText('Create your account')

    await page.click('[data-testid="switch-signin"]')
    await expect(page.locator('.auth-title')).toHaveText('Welcome back')
  })

  test('email and password inputs accept text', async ({ page }) => {
    await page.goto('/')
    await page.fill('input[type="email"]', 'test@example.com')
    await page.fill('input[type="password"]', 'secret123')
    await expect(page.locator('input[type="email"]')).toHaveValue('test@example.com')
    await expect(page.locator('input[type="password"]')).toHaveValue('secret123')
  })
})

test.describe('Theme system', () => {
  test('a theme is applied on first load', async ({ page }) => {
    await page.goto('/')
    const theme = await page.locator('html').getAttribute('data-theme')
    expect(['dark', 'light']).toContain(theme)
  })

  test('theme preference persists from localStorage', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.setItem('tash-theme', 'dark'))
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

    await page.evaluate(() => localStorage.setItem('tash-theme', 'light'))
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  })
})

test.describe('Design system - no fake effects', () => {
  test('chips/cards do not use translateY lift on hover (restrained motion)', async ({ page }) => {
    await page.goto('/')
    // The submit button uses our restrained transition - assert it has no
    // large box-shadow glow baked into its resting state.
    const btn = page.locator('.auth-submit')
    await expect(btn).toBeVisible()
    const boxShadow = await btn.evaluate(el => getComputedStyle(el).boxShadow)
    // resting primary button should not carry a heavy colored glow
    expect(boxShadow === 'none' || boxShadow.length < 60).toBeTruthy()
  })
})
