import { test, expect } from '@playwright/test';

test.describe('Profile interactions', () => {
  test('display name edit/cancel/save works and category links are present', async ({ page }) => {
    let displayName = '原名称';
    let putCalls = 0;

    await page.route('**/api/profile**', async (route) => {
      const url = new URL(route.request().url());
      const { pathname } = url;
      const method = route.request().method();

      if (pathname === '/api/profile' && method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({ profile: { display_name: displayName } }),
        });
        return;
      }

      if (pathname === '/api/profile' && method === 'PUT') {
        putCalls += 1;
        const body = JSON.parse(route.request().postData() || '{}');
        displayName = (body.display_name || '').trim() || displayName;
        await route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({ profile: { display_name: displayName } }),
        });
        return;
      }

      if (pathname === '/api/profile/progress' && method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({
            proficiency: {
              total_characters: 3664,
              learned_count: 12,
              learning_count: 8,
              not_tested_count: 3644,
              learning_hard: 3,
              learning_normal: 5,
              learned_mastered: 7,
              learned_normal: 5,
            },
            category_trend: [],
            viewed_characters_recent: [],
            viewed_characters_count: 0,
            daily_stats: [],
          }),
        });
        return;
      }

      return route.continue();
    });

    await page.goto('/profile');

    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible();
    await expect(page.getByText('原名称')).toBeVisible();

    await page.getByRole('button', { name: '编辑' }).click();
    const input = page.locator('.profile-name-input');
    await expect(input).toBeVisible();
    await expect(input).toHaveValue('原名称');

    await input.fill('临时名称');
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.getByText('原名称')).toBeVisible();

    await page.getByRole('button', { name: '编辑' }).click();
    await input.fill('新名称');
    await page.getByRole('button', { name: '保存' }).click();

    await expect(page.getByText('新名称')).toBeVisible();
    await expect(putCalls).toBe(1);

    await expect(page.getByRole('link', { name: '难字' })).toHaveAttribute(
      'href',
      '/profile/category/learning_hard'
    );
    await expect(page.getByRole('link', { name: '掌握字' })).toHaveAttribute(
      'href',
      '/profile/category/learned_mastered'
    );
    await expect(page.getByRole('link', { name: /^普通$/ }).first()).toBeVisible();
  });
});

