import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const fixturesDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  'fixtures',
  'hanzi-writer'
);

async function routeStrokeFixtures(page) {
  await page.route('**/api/strokes?*', async (route) => {
    const requestUrl = new URL(route.request().url());
    const ch = requestUrl.searchParams.get('char');
    if (!ch) return route.continue();

    const decoded = decodeURIComponent(ch);
    const fixturePath = path.join(fixturesDir, `${decoded}.json`);
    if (!fs.existsSync(fixturePath)) return route.continue();

    const body = fs.readFileSync(fixturePath, 'utf-8');
    return route.fulfill({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body,
    });
  });
}

test.beforeEach(async ({ page }) => {
  await routeStrokeFixtures(page);
});

test('core flows: search + dictionary-only + radicals', async ({ page }) => {
  // 1) Search: full character (专)
  await page.goto('/?q=%E4%B8%93');
  await expect(page.getByRole('heading', { name: '笔顺动画' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /字典信息/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: '字卡', exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: '字符信息（来源：冯氏早教识字卡）' })
  ).toBeVisible();
  await expect(page.getByRole('button', { name: '重播' })).toBeEnabled();

  // 2) Search: dictionary-only (刁) -> only top row (no 字卡 / 字符信息)
  await page.goto('/?q=%E5%88%81');
  await expect(page.getByRole('heading', { name: '笔顺动画' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /字典信息/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: '字卡', exact: true })).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: '字符信息（来源：冯氏早教识字卡）' })
  ).toHaveCount(0);
  await expect(page.getByRole('button', { name: '重播' })).toBeEnabled();

  // 3) Radicals list + detail -> click through to search
  await page.goto('/radicals');
  await expect(page.getByRole('heading', { name: '部首' })).toBeVisible();
  await expect(page.getByText('共224个部首')).toBeVisible();

  // Click radical "口"
  await page.locator('.radical-box').filter({ hasText: '口' }).first().click();
  await expect(page.getByText('部首: 口')).toBeVisible();
  await expect(page.getByText('共194个汉字')).toBeVisible();

  // Click character "囊" under radical "口" -> should navigate back to search
  await page.locator('.character-box').filter({ hasText: '囊' }).first().click();
  await expect(page.getByRole('textbox', { name: '输入一个汉字' })).toHaveValue('囊');
  await expect(page.getByRole('button', { name: '重播' })).toBeEnabled();
});

