import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

const repoRoot = path.resolve(__dirname, '..');
const isWindows = process.platform === 'win32';
const pythonBin = process.env.PYTHON_BIN
  ? process.env.PYTHON_BIN
  : isWindows
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : 'python3';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 45_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: `${pythonBin} -m uvicorn jane_avenue.api.app:app --port 8000`,
      cwd: path.join(repoRoot, 'backend'),
      url: 'http://localhost:8000/api/health',
      // Never reuse a running backend: it may be a live-mode dev server (real Gemini calls, other code). The tests
      // must run against their own mock-mode server; stop anything on :8000 first.
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        ...process.env,
        JANE_MODE: 'mock',
        JANE_DB_PATH: ':memory:',
        PYTHONPATH: path.join(repoRoot, 'backend'),
      },
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      cwd: path.join(repoRoot, 'frontend'),
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
