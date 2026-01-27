import { test, expect } from '@playwright/test';

test('anonymous game start and basic flow, then leaderboard', async ({ page }) => {
  // Home page: prompt for name and disabled Start button until name is entered
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Enter Your First Name' })).toBeVisible();

  const nameInput = page.getByPlaceholder('Your name');
  await expect(nameInput).toBeVisible();

  const startButton = page.getByRole('button', { name: 'Start Game' });
  await expect(startButton).toBeDisabled();

  // Enter name and start the game
  await nameInput.fill('Alice');
  await expect(startButton).toBeEnabled();
  await startButton.click();

  // Game view: question, timer, and answer input should appear
  await expect(page.getByText(/Question \d+\/\d+ • Round \d+/)).toBeVisible();
  await expect(page.locator('.timer')).toBeVisible();

  const questionDisplay = page.locator('.question-display');
  await expect(questionDisplay).toBeVisible();
  await expect(questionDisplay).toContainText('×');

  const answerInput = page.locator('.answer-input');
  await expect(answerInput).toBeVisible();

  // Submit an obviously wrong answer (0 can never be correct)
  await answerInput.fill('0');
  await answerInput.press('Enter');

  // We should see incorrect feedback overlay
  const feedbackOverlay = page.locator('.feedback-overlay');
  await expect(feedbackOverlay).toBeVisible();
  await expect(feedbackOverlay).toContainText('✗');

  // Navigate to leaderboard and ensure it renders
  await page.goto('/leaderboard');
  await expect(page.getByRole('heading', { name: 'Leaderboard' })).toBeVisible();

  // Either a "no games" message or a table of results is acceptable
  const emptyMessage = page.getByText('No games recorded yet. Be the first to play!');
  const table = page.locator('table');

  if (await emptyMessage.isVisible()) {
    await expect(emptyMessage).toBeVisible();
  } else {
    await expect(table).toBeVisible();
  }
});

