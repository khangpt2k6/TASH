import { test, expect } from '@playwright/test'

/**
 * Chat-flow E2E tests.
 *
 * TASH now gates the chat UI behind Supabase auth. Without a configured test
 * user + session these tests cannot reach the chat surface, so each one is
 * skipped (with a clear reason) when the auth screen is present. Once a
 * Supabase test session is wired up, they run automatically - no edits needed.
 *
 * Reachable-page coverage (auth screen, theme, react-icons, restrained motion)
 * lives in auth.spec.ts and runs unconditionally.
 */

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  const authGated = await page
    .locator('[data-testid="auth-screen"]')
    .isVisible()
    .catch(() => false)
  test.skip(
    authGated,
    'Chat flow requires an authenticated Supabase session (test user not configured yet)'
  )
})

test.describe('Chat - new chat', () => {
  test('clicking New Chat shows the chat interface', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await expect(page.locator('.chat-header')).toBeVisible()
  })

  test('new chat appears in sidebar after sending a message', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'What is scRNA-seq?')
    await page.click('[data-testid="send-btn"]')
    await expect(page.locator('[data-testid="conv-item"]').first()).toBeVisible({ timeout: 8000 })
  })
})

test.describe('Chat - sending messages', () => {
  test('send button enables when text is typed', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'Hello')
    await expect(page.locator('[data-testid="send-btn"]')).toBeEnabled()
  })

  test('user bubble appears after sending', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'What is aging in single-cell biology?')
    await page.click('[data-testid="send-btn"]')
    await expect(page.locator('[data-testid="user-message"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('[data-testid="user-message"]')).toContainText('What is aging')
  })

  test('input clears after sending', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'Test message')
    await page.click('[data-testid="send-btn"]')
    await expect(page.locator('[data-testid="chat-input"]')).toHaveValue('')
  })

  test('assistant responds after user sends a message', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'What is Scanpy?')
    await page.click('[data-testid="send-btn"]')
    await expect(page.locator('[data-testid="assistant-message"]')).toBeVisible({ timeout: 20000 })
  })

  test('welcome chip triggers a message send', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.click('.chip >> nth=0')
    await expect(page.locator('[data-testid="user-message"]')).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Chat - conversations', () => {
  test('a conversation can be deleted', async ({ page }) => {
    await page.click('[data-testid="new-chat-btn"]')
    await page.fill('[data-testid="chat-input"]', 'Test')
    await page.click('[data-testid="send-btn"]')
    await expect(page.locator('[data-testid="conv-item"]').first()).toBeVisible({ timeout: 8000 })

    await page.hover('[data-testid="conv-item"] >> nth=0')
    await page.click('[data-testid="conv-delete"] >> nth=0')
    await expect(page.locator('.empty-list')).toBeVisible({ timeout: 3000 })
  })
})

test.describe('Chat - settings modal', () => {
  test('opens and closes the settings modal', async ({ page }) => {
    await page.click('[data-testid="settings-btn"]')
    await expect(page.locator('.modal')).toBeVisible()
    await page.click('.modal-close')
    await expect(page.locator('.modal')).not.toBeVisible()
  })

  test('settings modal has a provider selector', async ({ page }) => {
    await page.click('[data-testid="settings-btn"]')
    await expect(page.locator('.fsel')).toBeVisible()
    const options = await page.locator('.fsel option').count()
    expect(options).toBeGreaterThanOrEqual(4)
  })
})
