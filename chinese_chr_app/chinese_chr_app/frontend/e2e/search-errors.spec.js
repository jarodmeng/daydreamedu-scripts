import { test, expect } from '@playwright/test';

async function mockAuthProfile(page) {
  await page.route('**/api/profile', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== '/api/profile' || route.request().method() !== 'GET') {
      return route.continue();
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ profile: { display_name: 'Search Mock User' } }),
    });
  });
}

test.describe('Search error states', () => {
  test('shows backend search error and stroke loading fallback error', async ({ page }) => {
    await mockAuthProfile(page);

    await page.route('**/api/characters/search?*', async (route) => {
      const url = new URL(route.request().url());
      const q = url.searchParams.get('q');

      if (q === '错') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({ error: '模拟搜索失败' }),
        });
        return;
      }

      if (q === '专') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({
            found: true,
            dictionary: {
              character: '专',
              拼音: ['zhuan1'],
              部首: '一',
              总笔画: 4,
            },
          }),
        });
        return;
      }

      return route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ found: false, error: '未找到该简体字' }),
      });
    });

    await page.route('**/api/strokes?*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ error: '模拟笔顺失败' }),
      });
    });

    await page.route('**/hanzi-writer-data@2.0.1/**', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ error: '模拟 CDN 笔顺失败' }),
      });
    });

    await page.goto('/?q=%E9%94%99'); // 错
    await expect(page.getByText('模拟搜索失败')).toBeVisible();
    await expect(page.getByPlaceholder(/输入汉字或拼音/)).toHaveValue('错');

    await page.goto('/?q=%E4%B8%93'); // 专
    await expect(page.getByRole('heading', { name: '笔顺动画' })).toBeVisible();
    await expect(page.getByRole('heading', { name: /字典信息/ })).toBeVisible();
    await expect(page.getByText('无法加载“专”的笔顺动画')).toBeVisible();
  });
});

