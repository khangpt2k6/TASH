import { test, expect } from '@playwright/test'

test.describe('TASH - Page load', () => {
  test('loads homepage with logo and sidebar', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.logo-name')).toHaveText('TASH')
    await expect(page.locator('.sidebar')).toBeVisible()
    await expect(page.locator('.welcome-title')).toContainText('TASH')
  })

  test('shows welcome chips', async ({ page }) => {
    await page.goto('/')
    const chips = page.locator('.chip')
    await expect(chips).toHaveCount(6)
  })

  test('input area is visible and enabled', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="send-btn"]')).toBeDisabled()
  })
})

test.describe('TASH - Theme toggle', () => {
  test('starts with a theme (dark or light)', async ({ page }) => {
    await page.goto('/')
    const html = page.locator('html')
    const theme = await html.getAttribute('data-theme')
    expect(['dark', 'light']).toContain(theme)
  })

  test('toggles between dark and light mode', async ({ page }) => {
    await page.goto('/')
    const html = page.locator('html')
    const before = await html.getAttribute('data-theme')

    await page.click('[data-testid="theme-toggle"]')
    const after = await html.getAttribute('data-theme')

    expect(after).not.toBe(before)
    expect(['dark', 'light']).toContain(after)
  })

  test('persists theme after reload', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="theme-toggle"]')
    const theme = await page.locator('html').getAttribute('data-theme')

    await page.reload()
    const themeAfter = await page.locator('html').getAttribute('data-theme')
    expect(themeAfter).toBe(theme)
  })
})

test.describe('TASH - New chat', () => {
  test('clicking New Chat button shows chat interface', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')
    await expect(page.locator('.chat-header')).toBeVisible()
  })

  test('new chat appears in sidebar after sending a message', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')

    await page.fill('[data-testid="chat-input"]', 'What is scRNA-seq?')
    await page.click('[data-testid="send-btn"]')

    await expect(page.locator('[data-testid="conv-item"]').first()).toBeVisible({ timeout: 8000 })
  })
})

test.describe('TASH - Sending messages', () => {
  test('send button enables when text is typed', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')

    const input = page.locator('[data-testid="chat-input"]')
    const btn = page.locator('[data-testid="send-btn"]')

    await input.fill('Hello')
    await expect(btn).toBeEnabled()
  })

  test('can send a message and user bubble appears', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')

    await page.fill('[data-testid="chat-input"]', 'What is aging in single-cell biology?')
    await page.click('[data-testid="send-btn"]')

    await expect(page.locator('[data-testid="user-message"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="user-message"]')).toContainText('What is aging')
  })

  test('input clears after sending', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')

    await page.fill('[data-testid="chat-input"]', 'Test message')
    await page.click('[data-testid="send-btn"]')

    await expect(page.locator('[data-testid="chat-input"]')).toHaveValue('')
  })

  test('assistant responds after user sends message', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')

    await page.fill('[data-testid="chat-input"]', 'What is Scanpy?')
    await page.click('[data-testid="send-btn"]')

    await expect(page.locator('[data-testid="assistant-message"]')).toBeVisible({ timeout: 20000 })
  })

  test('welcome chip triggers a message send', async ({ page }) => {
    await page.goto('/')
    await page.click('.chip >> nth=0')

    await expect(page.locator('[data-testid="user-message"]')).toBeVisible({ timeout: 5000 })
  })
})

test.describe('TASH - Conversations', () => {
  test('conversation can be deleted', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'Test')
    await page.click('[data-testid="send-btn"]')

    await expect(page.locator('[data-testid="conv-item"]').first()).toBeVisible({ timeout: 8000 })

    await page.hover('[data-testid="conv-item"] >> nth=0')
    await page.click('[data-testid="conv-delete"] >> nth=0')

    await expect(page.locator('.empty-list')).toBeVisible({ timeout: 3000 })
  })
})

test.describe('TASH - Settings modal', () => {
  test('opens and closes settings modal', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="settings-btn"]')
    await expect(page.locator('.modal')).toBeVisible()
    await page.click('.modal-close')
    await expect(page.locator('.modal')).not.toBeVisible()
  })

  test('settings modal has provider selector', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="settings-btn"]')
    await expect(page.locator('.fsel')).toBeVisible()
    const options = await page.locator('.fsel option').count()
    expect(options).toBeGreaterThanOrEqual(4)
  })
})
