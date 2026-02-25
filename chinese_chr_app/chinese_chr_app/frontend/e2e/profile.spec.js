import { test, expect } from '@playwright/test';

// Use e2e_guest=1 to simulate unauthenticated state (bypasses E2E auth when set)
const guestQuery = '?e2e_guest=1';

const MOCK_PROGRESS = {
  viewed_characters_count: 5,
  viewed_characters_recent: ['你', '好', '学', '中', '文'],
  proficiency: {
    learned_count: 120,
    learning_count: 45,
    not_tested_count: 3499,
    total_characters: 3664,
    description: '120 / 3664',
    learning_hard: 10,
    learning_normal: 35,
    learned_mastered: 80,
    learned_normal: 40,
  },
  daily_stats: [
    {
      date: '2026-02-25',
      answered: 30,
      correct: 24,
      by_category: {
        '新字': { answered: 10, correct: 7 },
        '巩固': { answered: 15, correct: 14 },
        '重测': { answered: 5, correct: 3 },
      },
    },
    {
      date: '2026-02-24',
      answered: 20,
      correct: 18,
      by_category: {
        '新字': { answered: 8, correct: 6 },
        '巩固': { answered: 12, correct: 12 },
        '重测': { answered: 0, correct: 0 },
      },
    },
  ],
  category_trend: [],
};

async function routeMockProgress(page) {
  await page.route('**/api/profile/progress', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_PROGRESS),
    })
  );
}

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

  test('authenticated: shows progress snapshot report', async ({ page }) => {
    await routeMockProgress(page);
    await page.goto('/profile');

    // Page heading
    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible();

    // Display name section (shows "未设置" or name; editing button visible)
    await expect(page.getByText('编辑')).toBeVisible();

    // Proficiency section
    await expect(page.getByRole('heading', { name: '汉字掌握度' })).toBeVisible();

    // Stacked bar segments exist
    const bar = page.locator('.profile-proficiency-stacked');
    await expect(bar).toBeVisible();
    await expect(bar.locator('.profile-proficiency-segment-not-tested')).toBeVisible();
    await expect(bar.locator('.profile-proficiency-segment-learning')).toBeVisible();
    await expect(bar.locator('.profile-proficiency-segment-learned')).toBeVisible();

    // Counts text
    await expect(page.getByText('未学字', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('3499')).toBeVisible();
    await expect(page.getByText('在学字', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('45', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('已学字', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('120', { exact: false }).first()).toBeVisible();

    // Sub-category breakdown
    await expect(page.getByText('难字').first()).toBeVisible();
    await expect(page.getByText('掌握字').first()).toBeVisible();

    // Proficiency hint text
    await expect(page.getByText('掌握度根据拼音记忆游戏计算')).toBeVisible();

    // Recently viewed characters section
    await expect(page.getByRole('heading', { name: '最近查看的字' })).toBeVisible();
    for (const ch of MOCK_PROGRESS.viewed_characters_recent) {
      await expect(page.locator('.profile-char-link', { hasText: ch })).toBeVisible();
    }
    await expect(page.getByText('共查看过 5 个不同汉字')).toBeVisible();

    // Daily stats section
    await expect(page.getByRole('heading', { name: '每日练习统计' })).toBeVisible();
    const table = page.locator('.profile-daily-table');
    await expect(table).toBeVisible();

    // Table headers
    for (const header of ['日期', '答题数', '正确数', '正确率', '新字', '巩固', '重测']) {
      await expect(table.getByRole('columnheader', { name: header })).toBeVisible();
    }

    // First row data
    const rows = table.locator('tbody tr');
    await expect(rows).toHaveCount(2);
    const firstRow = rows.first();
    await expect(firstRow.locator('td').first()).toHaveText('2026-02-25');
    await expect(firstRow.locator('td').nth(1)).toHaveText('30');
    await expect(firstRow.locator('td').nth(2)).toHaveText('24');
    await expect(firstRow.locator('td').nth(3)).toHaveText('80%');
  });

});
