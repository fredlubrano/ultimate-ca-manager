/**
 * Lab integration: ACME DNS-01 via Gandi + preferred_chain on LE Staging.
 *
 * Run against the UCM lab (not CI):
 *   UCM_LAB=1 \
 *   UCM_BASE_URL=https://admin.ucm.example.com:8443 \
 *   UCM_PASSWORD='…' \
 *   npx playwright test e2e/lab/acme-dns-preferred-chain.spec.ts
 */
import { test, expect } from '@playwright/test'
import { selectByLabel } from '../helpers/select'

const isLab = process.env.UCM_LAB === '1'
const PREFERRED_CHAIN = 'ISRG Root X1'
const CA_LABEL = /Let's Encrypt Staging/i
const DNS_PROVIDER = /register-gandi/i

test.describe('Lab — ACME DNS + preferred_chain', () => {
  test.skip(!isLab, 'Set UCM_LAB=1 to run against the UCM lab')

  test.setTimeout(6 * 60 * 1000)

  test.beforeEach(async ({ page }) => {
    await page.goto('/acme')
    await page.evaluate(() => localStorage.setItem('i18nextLng', 'en'))
    await page.reload()
    await page.waitForLoadState('networkidle')
  })

  test('issues staging cert with Gandi DNS auto-create', async ({ page }) => {
    const domain = `test-pw-${Date.now()}.lab.ucm.example.com`

    // Ensure LE Staging has preferred_chain configured (idempotent).
    const stagingCard = page.locator('div').filter({ hasText: CA_LABEL }).first()
    await expect(stagingCard).toBeVisible({ timeout: 15000 })

    if (!(await stagingCard.getByText(PREFERRED_CHAIN).isVisible().catch(() => false))) {
      await stagingCard.getByRole('button', { name: /edit|modifier/i }).click()
      await page.getByLabel(/preferred chain|chaîne préférée/i).fill(PREFERRED_CHAIN)
      await page.getByRole('button', { name: /^save$|^enregistrer$/i }).click()
      await expect(stagingCard.getByText(PREFERRED_CHAIN)).toBeVisible({ timeout: 10000 })
    }

    // Open request modal — UI sends dns_provider_id (unlike bare API without it).
    await page.getByRole('button', { name: /request certificate|demander un certificat/i }).click()
    const modal = page.getByRole('dialog')
    await expect(modal).toBeVisible()

    await modal.locator('textarea').fill(domain)
    await selectByLabel(page, /DNS Provider|Fournisseur DNS/i, DNS_PROVIDER, modal)
    await selectByLabel(page, /Certificate Authority|Autorité de certification/i, CA_LABEL, modal)

    await modal.getByRole('button', { name: /^request certificate$|^demander un certificat$/i }).click()
    await expect(modal).toBeHidden({ timeout: 30000 })

    // Order card — wait until backend marks it issued/valid (auto-poll runs in background).
    const orderCard = page.locator('main div.cursor-pointer').filter({ hasText: domain }).first()
    await expect(orderCard).toBeVisible({ timeout: 20000 })

    await expect.poll(async () => {
      await page.reload({ waitUntil: 'networkidle' })
      const card = page.locator('main div.cursor-pointer').filter({ hasText: domain }).first()
      if (!(await card.isVisible().catch(() => false))) return false
      const text = await card.textContent()
      return /issued|valid/i.test(text ?? '')
    }, { timeout: 5 * 60 * 1000, intervals: [3000, 5000, 10000] }).toBe(true)

    const issuedCard = page.locator('main div.cursor-pointer').filter({ hasText: domain }).first()
    await expect(issuedCard.getByText(DNS_PROVIDER)).toBeVisible()
  })
})
