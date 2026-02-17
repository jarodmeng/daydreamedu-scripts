import { test, expect } from '@playwright/test';

// Use e2e_guest=1 to simulate unauthenticated state (bypasses E2E auth when set)
const guestQuery = '?e2e_guest=1';

test.describe('Profile page', () => {
  test('unauthenticated: shows login prompt and return link', async ({ page }) => {
    await page.goto(`/profile${guestQuery}`);
    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible();
    await expect(page.getByText('请先登录后查看您的学习进度。')).toBeVisible();
    const backLink = page.getByRole('link', { name: '返回搜索' });
    await expect(backLink).toBeVisible();
    await backLink.click();
    await expect(page).toHaveURL('/');
  });

});
