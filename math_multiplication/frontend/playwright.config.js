// @ts-check
import { defineConfig, devices } from '@playwright/test';

// Use GitHub Actions as the authoritative CI signal.
const isCI = process.env.GITHUB_ACTIONS === 'true';

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: isCI ? 2 : 0,
  reporter: isCI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html']],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      name: 'Backend',
      command: 'node ./scripts/run-backend-for-e2e.mjs',
      url: 'http://127.0.0.1:5001/api/health',
      reuseExistingServer: !isCI,
      timeout: 120_000,
      env: {
        ...process.env,
        PORT: '5001',
      },
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      name: 'Frontend',
      command: 'npm run dev -- --host 127.0.0.1 --port 3000',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: !isCI,
      timeout: 120_000,
      env: {
        ...process.env,
        NODE_ENV: 'development',
      },
      stdout: 'ignore',
      stderr: 'pipe',
    },
  ],
});

