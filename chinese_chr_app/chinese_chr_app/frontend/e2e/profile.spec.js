import { test, expect } from '@playwright/test';

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

  test('authenticated: play pinyin recall then view progress snapshot', async ({ page }) => {
    // ── Step 1: Play pinyin recall — answer at least 3 questions ──
    await page.goto('/games/pinyin-recall');
    await expect(page.getByRole('heading', { name: '拼音记忆' })).toBeVisible();

    const startBtn = page.getByRole('button', { name: '开始练习' });
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    const MIN_ANSWERS = 3;
    for (let i = 0; i < MIN_ANSWERS; i++) {
      // Wait for question phase: the character display and choice buttons
      const characterEl = page.locator('.pinyin-recall-character');
      const waitStartMs = Date.now();
      await expect(characterEl).toBeVisible({ timeout: 120_000 });
      if (i === 0) {
        const elapsedMs = Date.now() - waitStartMs;
        console.log(`[e2e] Initial pinyin-recall characters visible after ${elapsedMs}ms`);
      }

      // Pick the first pinyin choice (not "我不知道")
      const firstChoice = page.locator('.pinyin-recall-choice').first();
      await expect(firstChoice).toBeVisible();
      await firstChoice.click();

      // Wait for feedback phase
      const feedbackCorrect = page.locator('.pinyin-recall-feedback-correct');
      const feedbackWrong = page.locator('.pinyin-recall-feedback-wrong-label');
      await expect(feedbackCorrect.or(feedbackWrong)).toBeVisible({ timeout: 15_000 });

      // Advance to next question (or next batch)
      if (i < MIN_ANSWERS - 1) {
        const nextBtn = page.getByRole('button', { name: /下一题|下一批/ });
        await expect(nextBtn).toBeVisible();
        await nextBtn.click();
      }
    }

    // End the session
    const endBtn = page.getByRole('button', { name: '结束本局' });
    await expect(endBtn).toBeVisible();
    await endBtn.click();

    // Should transition to learn phase or complete phase
    const completeHeading = page.getByRole('heading', { name: '练习完成' });
    const learnHeading = page.getByRole('heading', { name: '复习这些字' });
    await expect(completeHeading.or(learnHeading)).toBeVisible({ timeout: 10_000 });

    // If in learn phase, click through all review cards to reach complete
    if (await learnHeading.isVisible()) {
      for (let j = 0; j < 20; j++) {
        const doneOrNext = page.getByRole('button', { name: /完成|下一个/ });
        await expect(doneOrNext).toBeVisible();
        const text = await doneOrNext.textContent();
        await doneOrNext.click();
        if (text === '完成') break;
      }
      await expect(completeHeading).toBeVisible({ timeout: 5_000 });
    }

    // Verify the completion summary mentions the answered count
    await expect(page.getByText(`本次共 ${MIN_ANSWERS} 题`)).toBeVisible();

    // ── Step 2: Navigate to profile and verify progress snapshot ──
    await page.goto('/profile');
    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible();

    // Wait for progress to load (no loading spinner, no error)
    // 45s timeout: profile progress replays pinyin_recall_item_answered; e2e-dev can accumulate many rows across CI runs
    await expect(page.locator('.profile-loading')).toHaveCount(0, { timeout: 45_000 });
    await expect(page.locator('.profile-error')).toHaveCount(0);

    // Proficiency section
    await expect(page.getByRole('heading', { name: '汉字掌握度' })).toBeVisible();
    const bar = page.locator('.profile-proficiency-stacked');
    await expect(bar).toBeVisible();
    await expect(bar.locator('.profile-proficiency-segment-not-tested')).toBeVisible();

    // Counts: total_characters line should mention /3664
    await expect(page.getByText(/\/ 3664 字/).first()).toBeVisible();

    // Sub-category links
    await expect(page.getByRole('link', { name: '难字' })).toBeVisible();
    await expect(page.getByRole('link', { name: '掌握字' })).toBeVisible();

    // Proficiency hint text
    await expect(page.getByText('掌握度根据拼音记忆游戏计算')).toBeVisible();

    // Daily stats section should have at least one row from the game we just played
    await expect(page.getByRole('heading', { name: '每日练习统计' })).toBeVisible();
    const table = page.locator('.profile-daily-table');
    await expect(table).toBeVisible();
    for (const header of ['日期', '答题数', '正确数', '正确率', '新字', '巩固', '重测']) {
      await expect(table.getByRole('columnheader', { name: header })).toBeVisible();
    }
    const rows = table.locator('tbody tr');
    await expect(rows.first()).toBeVisible();
  });
});
