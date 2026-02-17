import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('navbar: logo and search link on homepage', async ({ page }) => {
    await page.goto('/');
    const logo = page.getByRole('link', { name: '学简体字 - 返回首页' });
    await expect(logo).toBeVisible();
    await expect(page.getByRole('link', { name: '搜索' })).toBeVisible();
    await expect(page.getByRole('link', { name: '搜索' })).toHaveAttribute('class', /nav-link-active/);
  });

  test('navbar: 分类 dropdown has radicals and stroke-counts links', async ({ page }) => {
    await page.goto('/');
    const classificationBtn = page.getByRole('button', { name: '分类' });
    await classificationBtn.hover();
    const radicalsLink = page.getByRole('link', { name: '部首' });
    const strokeCountsLink = page.getByRole('link', { name: '笔画' });
    await expect(radicalsLink).toBeVisible();
    await expect(strokeCountsLink).toBeVisible();
    await radicalsLink.click();
    await expect(page).toHaveURL(/\/radicals/);
  });

  test('navbar: 游戏 dropdown has pinyin-recall link', async ({ page }) => {
    await page.goto('/');
    const gamesBtn = page.getByRole('button', { name: '游戏' });
    await gamesBtn.hover();
    const pinyinRecallLink = page.getByRole('link', { name: '拼音记忆' });
    await expect(pinyinRecallLink).toBeVisible();
    await pinyinRecallLink.click();
    await expect(page).toHaveURL(/\/games\/pinyin-recall/);
  });

});
