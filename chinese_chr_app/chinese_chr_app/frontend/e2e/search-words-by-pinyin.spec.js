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
    const fallbackPath = path.join(fixturesDir, '专.json');
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

test('search groups 词组 by pinyin for polyphonic Feng characters', async ({ page }) => {
  await page.goto('/?q=%E5%8F%82');

  await expect(
    page.getByRole('heading', { name: '字符信息（来源：冯氏早教识字卡）' })
  ).toBeVisible();

  const groupedWords = page.getByTestId('words-by-pinyin-groups');
  await expect(groupedWords).toBeVisible();
  await expect(page.getByTestId('words-by-pinyin-group')).toHaveCount(3);

  await expect(groupedWords).toContainText('cān');
  await expect(groupedWords).toContainText('参照、参加、参与、参观');
  await expect(groupedWords).toContainText('cēn');
  await expect(groupedWords).toContainText('参差不齐');
  await expect(groupedWords).toContainText('shēn');
  await expect(groupedWords).toContainText('人参、党参');
});

test('search groups 英语 by pinyin for polyphonic dictionary characters', async ({ page }) => {
  await page.goto('/?q=%E7%B4%AF');

  await expect(
    page.getByRole('heading', { name: '字典信息（来源：hwxnet）' })
  ).toBeVisible();

  const groupedEnglish = page.getByTestId('english-by-pinyin-groups');
  await expect(groupedEnglish).toBeVisible();
  await expect(page.getByTestId('english-by-pinyin-group')).toHaveCount(3);

  await expect(groupedEnglish).toContainText('lèi');
  await expect(groupedEnglish).toContainText('tired, weary, to strain, to wear out');
  await expect(groupedEnglish).toContainText('léi');
  await expect(groupedEnglish).toContainText('burden, numerous, cumbersome');
  await expect(groupedEnglish).toContainText('lěi');
  await expect(groupedEnglish).toContainText('accumulate, successive, involve');
});
