import { test, expect } from '@playwright/test';

// Use e2e_guest=1 to simulate unauthenticated state (bypasses E2E auth when set)
const guestQuery = '?e2e_guest=1';

test.describe('Pinyin Recall', () => {
  test('unauthenticated: shows login prompt', async ({ page }) => {
    await page.goto(`/games/pinyin-recall${guestQuery}`);
    await expect(page.getByRole('heading', { name: '拼音记忆' })).toBeVisible();
    await expect(page.getByText('请先登录后再玩。')).toBeVisible();
  });
});
