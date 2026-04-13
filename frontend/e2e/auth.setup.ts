import { test as setup, expect } from '@playwright/test'
import { config } from './config'

const authFile = 'e2e/.auth/user.json'

/**
 * Authentication Setup
 * Runs before all tests to create authenticated session
 * 
 * UCM Login Flow:
 * 1. Enter username → Continue
 * 2. Auto-detects auth methods (mTLS, WebAuthn, Password)
 * 3. If WebAuthn available, shows fingerprint prompt and waits
 * 4. After WebAuthn timeout, "Use password instead" link appears
 * 5. Click link → Enter password → Sign in
 */
setup('authenticate', async ({ page }) => {
  // Force English locale for consistent E2E selectors
  await page.goto('/login')
  await page.evaluate(() => localStorage.setItem('i18nextLng', 'en'))
  await page.goto('/login')
  
  // Wait for login form
  await page.waitForSelector('input[type="text"], input[name="username"]', { timeout: 10000 })
  
  // Step 1: Enter username
  const usernameInput = page.locator('input[type="text"], input[name="username"]').first()
  await usernameInput.fill(config.credentials.username)
  
  // Click Continue button
  const continueButton = page.locator('button[type="submit"]').first()
  await continueButton.click()
  
  // Wait for password field or "Use password instead" link
  // Login flow may show password directly or require clicking through WebAuthn
  await page.waitForTimeout(2000)
  
  const passwordField = page.locator('input[type="password"]')
  const usePasswordLink = page.locator('text=Use password instead')
  
  // Check if password field is already visible
  if (await passwordField.isVisible().catch(() => false)) {
    // Password field already shown — proceed
  } else {
    // Wait for "Use password instead" link (WebAuthn timeout)
    try {
      await usePasswordLink.waitFor({ state: 'visible', timeout: 40000 })
      await usePasswordLink.click()
    } catch {
      console.log('Password link not found, checking for password field directly')
    }
    await passwordField.waitFor({ state: 'visible', timeout: 10000 })
  }
  const passwordInput = page.locator('input[type="password"]')
  await passwordInput.fill(config.credentials.password)
  
  // Click Sign In button
  const signInButton = page.locator('button[type="submit"]').first()
  await signInButton.click()
  
  // Wait for navigation after login
  await page.waitForURL('**/*', { timeout: 15000 })
  
  // Handle "Password Change Required" modal if it appears
  const skipBtn = page.locator('button:has-text("Skip for now")')
  try {
    await skipBtn.waitFor({ state: 'visible', timeout: 3000 })
    await skipBtn.click()
    await page.waitForTimeout(1000)
  } catch {
    // No password change modal - continue
  }
  
  // Verify we're logged in (wait for sidebar logo link to dashboard)
  await expect(page.locator('a[href="/"]').first()).toBeVisible({ timeout: 10000 })
  
  // Save authentication state
  await page.context().storageState({ path: authFile })
})
