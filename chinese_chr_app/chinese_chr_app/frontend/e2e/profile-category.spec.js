import { test, expect } from '@playwright/test';

async function mockAuthProfile(page, displayName = '分类测试用户') {
  await page.route('**/api/profile', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== '/api/profile' || route.request().method() !== 'GET') {
      return route.continue();
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ profile: { display_name: displayName } }),
    });
  });
}

test.describe('Profile Category page', () => {
  test('covers guest, invalid category, and valid category with click-through', async ({ page }) => {
    await page.goto('/profile/category/learning_hard?e2e_guest=1');
    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible();
    await expect(page.getByText('请先登录后查看。')).toBeVisible();
    await expect(page.getByRole('link', { name: '返回搜索' })).toBeVisible();

    await mockAuthProfile(page);

    await page.route('**/api/profile/progress/category/**', async (route) => {
      const url = new URL(route.request().url());
      if (route.request().method() !== 'GET') return route.continue();
      if (url.pathname.endsWith('/learning_hard')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({
            characters: [{ character: '难' }, { character: '题' }],
          }),
        });
        return;
      }
      return route.continue();
    });

    await page.route('**/api/characters/search?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ found: false, error: '未找到该简体字' }),
      });
    });

    await page.goto('/profile/category/not_real');
    await expect(page.getByRole('heading', { name: '汉字掌握度' })).toBeVisible();
    await expect(page.locator('.profile-error')).toContainText('无效分类');
    await expect(page.getByRole('link', { name: '返回 我的' })).toBeVisible();

    await page.goto('/profile/category/learning_hard');
    await expect(page.getByRole('heading', { name: '汉字掌握度' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '难字' })).toBeVisible();
    const charLink = page.getByRole('link', { name: '难' });
    await expect(charLink).toBeVisible();
    await charLink.click();

    await expect(page).toHaveURL(/\/\?q=/);
    await expect(page.getByPlaceholder(/输入汉字或拼音/)).toHaveValue('难');
  });
});

