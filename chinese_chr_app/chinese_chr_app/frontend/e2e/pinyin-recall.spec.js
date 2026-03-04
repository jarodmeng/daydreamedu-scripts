import { test, expect } from '@playwright/test';

// Use e2e_guest=1 to simulate unauthenticated state (bypasses E2E auth when set)
const guestQuery = '?e2e_guest=1';

async function mockAuthProfile(page, displayName = 'E2E User') {
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

test.describe('Pinyin Recall', () => {
  test('unauthenticated: shows login prompt', async ({ page }) => {
    await page.goto(`/games/pinyin-recall${guestQuery}`);
    await expect(page.getByRole('heading', { name: '拼音记忆' })).toBeVisible();
    await expect(page.getByText('请先登录后再玩。')).toBeVisible();
  });

  test('authenticated: "我不知道" enters learn phase and completes review', async ({ page }) => {
    await mockAuthProfile(page);

    await page.route('**/api/games/pinyin-recall/session', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          session_id: 'mock-session-1',
          batch_id: 1,
          items: [
            {
              character: '学',
              choices: ['xue', 'xué', 'xiao'],
              correct_pinyin: 'xué',
              all_pinyin: ['xué'],
              meanings: ['study'],
              stem_words: ['学生'],
              category: '新字',
            },
          ],
        }),
      });
    });

    await page.route('**/api/games/pinyin-recall/answer', async (route) => {
      const body = JSON.parse(route.request().postData() || '{}');
      await expect(body.i_dont_know).toBe(true);
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          correct: false,
          missed_item: {
            character: '学',
            correct_pinyin: 'xué',
            all_pinyin: ['xué'],
            is_polyphonic: false,
            meanings: ['study'],
            meaning_zh: '学习；模仿。',
            stem_words: ['学生'],
          },
        }),
      });
    });

    await page.route('**/api/games/pinyin-recall/next-batch', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          session_id: 'mock-session-1',
          batch_id: 2,
          items: [],
        }),
      });
    });

    await page.goto('/games/pinyin-recall');
    await page.getByRole('button', { name: '开始练习' }).click();

    await expect(page.locator('.pinyin-recall-character')).toContainText('学');
    await page.getByRole('button', { name: '我不知道' }).click();

    await expect(page.locator('.pinyin-recall-feedback-wrong-label')).toBeVisible();
    await expect(page.getByText('你选了：我不知道')).toBeVisible();
    await expect(page.getByText('正确答案：')).toBeVisible();
    await expect(page.getByText('基本解释：')).toBeVisible();
    await expect(page.getByText('学习；模仿。')).toBeVisible();
    await expect(page.getByRole('button', { name: '下一批' })).toBeVisible();
    await page.getByRole('button', { name: '下一批' }).click();

    await expect(page.getByRole('heading', { name: '复习这些字' })).toBeVisible();
    await expect(page.locator('.pinyin-recall-character')).toContainText('学');
    await expect(page.getByText('基本解释：')).toBeVisible();
    await expect(page.getByRole('button', { name: '完成' })).toBeVisible();
    await page.getByRole('button', { name: '完成' }).click();

    await expect(page.getByRole('heading', { name: '练习完成' })).toBeVisible();
    await expect(page.getByText('本次共 1 题。')).toBeVisible();
    await expect(page.getByText('有 1 个已加入复习。')).toBeVisible();
  });

  test('authenticated: session fetch error and answer submit error are surfaced', async ({ page }) => {
    await mockAuthProfile(page);

    let sessionCalls = 0;

    await page.route('**/api/games/pinyin-recall/session', async (route) => {
      sessionCalls += 1;
      if (sessionCalls === 1) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json; charset=utf-8',
          body: JSON.stringify({ error: '模拟加载失败' }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          session_id: 'mock-session-2',
          batch_id: 1,
          items: [
            {
              character: '中',
              choices: ['zhong', 'zhòng', 'zhōng'],
              correct_pinyin: 'zhōng',
              all_pinyin: ['zhōng', 'zhòng'],
              is_polyphonic: true,
              meanings: ['middle'],
            },
          ],
        }),
      });
    });

    await page.route('**/api/games/pinyin-recall/answer', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ error: '模拟提交失败' }),
      });
    });

    await page.goto('/games/pinyin-recall');

    const startBtn = page.getByRole('button', { name: '开始练习' });
    await startBtn.click();
    await expect(page.getByText('模拟加载失败')).toBeVisible();
    await expect(startBtn).toBeVisible();

    await startBtn.click();
    await expect(page.locator('.pinyin-recall-character')).toContainText('中');

    await page.locator('.pinyin-recall-choice').first().click();
    await expect(page.getByText('模拟提交失败')).toBeVisible();
    await expect(page.getByText('选择正确的拼音：')).toBeVisible();
    await expect(page.locator('.pinyin-recall-choices')).toBeVisible();
  });

  test('authenticated: polyphonic character shows all pinyin on wrong-answer and learn screens', async ({ page }) => {
    await mockAuthProfile(page);

    await page.route('**/api/games/pinyin-recall/session', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          session_id: 'mock-session-3',
          batch_id: 1,
          items: [
            {
              character: '中',
              choices: ['zhōng', 'zhòng', 'zhong'],
              correct_pinyin: 'zhōng',
              all_pinyin: ['zhōng', 'zhòng'],
              is_polyphonic: true,
              meanings: ['middle'],
            },
          ],
        }),
      });
    });

    await page.route('**/api/games/pinyin-recall/answer', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          correct: false,
          missed_item: {
            character: '中',
            correct_pinyin: 'zhōng',
            all_pinyin: ['zhōng', 'zhòng'],
            is_polyphonic: true,
            meanings: ['middle'],
            meaning_zh: '中间；当中。',
            stem_words: ['中国'],
          },
        }),
      });
    });

    await page.route('**/api/games/pinyin-recall/next-batch', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({
          session_id: 'mock-session-3',
          batch_id: 2,
          items: [],
        }),
      });
    });

    await page.goto('/games/pinyin-recall');
    await page.getByRole('button', { name: '开始练习' }).click();

    // Question screen: character 中 is shown; answer incorrectly to trigger wrong-answer learning screen
    await expect(page.locator('.pinyin-recall-character')).toContainText('中');
    await page.getByRole('button', { name: '我不知道' }).click();

    const wrongPinyin = page.locator('.pinyin-recall-learning-moment .pinyin-recall-correct-pinyin.pinyin-recall-all-pinyin');
    await expect(wrongPinyin).toContainText('zhōng');
    await expect(wrongPinyin).toContainText('zhòng');

    await page.getByRole('button', { name: '下一批' }).click();

    // Learn/review phase also shows all readings
    const learnPinyin = page.locator('.pinyin-recall-learn .pinyin-recall-correct-pinyin.pinyin-recall-all-pinyin');
    await expect(learnPinyin).toContainText('zhōng');
    await expect(learnPinyin).toContainText('zhòng');
  });
});
