import { type Locator, type Page } from '@playwright/test'

/** Select an option in a Radix/shadcn combobox located by label text. */
export async function selectByLabel(
  page: Page,
  label: RegExp,
  option: RegExp,
  scope: Page | Locator = page,
): Promise<void> {
  const field = scope.getByLabel(label)
  await field.click()
  await page.getByRole('option', { name: option }).click()
}
