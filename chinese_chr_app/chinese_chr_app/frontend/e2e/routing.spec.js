import { test, expect } from '@playwright/test';

test.describe('Routing', () => {
  test('unknown path redirects to home', async ({ page }) => {
    await page.goto('/nonexistent-path');
    await expect(page).toHaveURL('/');
    await expect(page.getByPlaceholder(/输入汉字或拼音/)).toBeVisible({ timeout: 5000 });
  });

  test('direct URL to radical detail loads correctly', async ({ page }) => {
    await page.goto('/radicals/口');
    await expect(page.getByText('部首: 口')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/共\d+个简体字/)).toBeVisible();
  });

  test('direct URL to stroke count detail loads correctly', async ({ page }) => {
    await page.goto('/stroke-counts/5');
    await expect(page.getByRole('heading', { name: '笔画: 5画' })).toBeVisible({ timeout: 10000 });
  });
});
