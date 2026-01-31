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
    const fallbackPath = path.join(fixturesDir, `专.json`);
    const selectedPath = fs.existsSync(fixturePath) ? fixturePath : fallbackPath;
    if (!fs.existsSync(selectedPath)) return route.continue();
    const body = fs.readFileSync(selectedPath, 'utf-8');
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

test('search box: pinyin redirects to pinyin results, single CJK stays on search', async ({ page }) => {
  await page.goto('/');
  const input = page.getByPlaceholder(/输入汉字或拼音/);
  await expect(input).toBeVisible();

  // Submit pinyin -> redirect to /pinyin/:query
  await input.fill('wo3');
  await page.getByRole('button', { name: '搜索' }).click();
  await expect(page).toHaveURL(/\/pinyin\/wo3/);
  await expect(page.getByTestId('pinyin-result-card').first()).toBeVisible({ timeout: 10000 });

  // Submit single CJK character -> stay on / and show character result
  await page.goto('/');
  await input.fill('我');
  await page.getByRole('button', { name: '搜索' }).click();
  await expect(page).toHaveURL(/\/\?q=/);
  await expect(page.getByRole('heading', { name: '笔顺动画' })).toBeVisible({ timeout: 10000 });
});

test('pinyin results page: success and click through to character', async ({ page }) => {
  await page.goto('/pinyin/wo3');
  await expect(page.getByRole('heading', { name: /拼音: wo3/ })).toBeVisible({ timeout: 10000 });
  const cards = page.getByTestId('pinyin-result-card');
  await expect(cards.first()).toBeVisible();
  await expect(cards.first().locator('.pinyin-character-main')).toContainText('我', { timeout: 5000 });
  await cards.first().click();
  await expect(page).toHaveURL(/\/\?q=/);
  await expect(page.getByRole('heading', { name: '笔顺动画' })).toBeVisible({ timeout: 10000 });
});

test('pinyin results page: no match shows error', async ({ page }) => {
  await page.goto('/pinyin/xyz');
  await expect(page.getByTestId('pinyin-error')).toContainText('未找到该拼音的汉字', { timeout: 10000 });
});

test('pinyin results page: invalid format shows error', async ({ page }) => {
  await page.goto('/pinyin/n%C4%AB3'); // nǐ3 - mixed tone mark and digit
  await expect(page.getByTestId('pinyin-error')).toContainText('拼音输入格式错误', { timeout: 10000 });
});

test('search placeholder indicates pinyin', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByPlaceholder('输入汉字或拼音（如 ke 或 ke3）')).toBeVisible();
});
