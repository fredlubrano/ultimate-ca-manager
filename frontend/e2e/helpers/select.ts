import { type Locator, type Page } from '@playwright/test'

/** Select an option in a Radix/shadcn combobox located by visible label text. */
export async function selectByLabel(
  page: Page,
  label: RegExp,
  option: RegExp,
  scope: Page | Locator = page,
): Promise<void> {
  const block = scope.locator('div').filter({ hasText: label }).last()
  await block.getByRole('combobox').click()
  await page.getByRole('option', { name: option }).click()
}
