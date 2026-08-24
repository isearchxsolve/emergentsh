import { test, expect } from '@playwright/test';

const token = 'e2e-test-token';

test('authenticated workspace completes a build and exposes preview/export', async ({ page }) => {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({ json: { id: 'user-1', username: 'e2e', email: 'e2e@example.com', credits: 10 } });
  });
  await page.route('**/api/pipeline/run', async route => {
    await route.fulfill({ json: { job_id: 'e2e-job-1', status: 'queued', phase: 'queued', target: 'react-native', artifacts: [], errors: [] } });
  });
  await page.route('**/api/pipeline/stream/e2e-job-1', async route => {
    const events = [
      { event: 'agent_start', role: 'planner', data: {} },
      { event: 'agent_done', role: 'planner', data: { artifacts: ['PLAN.md'], status: 'planning' } },
      { event: 'pipeline_complete', role: 'orchestrator', data: { status: 'complete', target: 'react-native', artifacts: ['PLAN.md'], errors: [] } },
    ];
    const body = events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body });
  });
  await page.route('**/api/pipeline/export/e2e-job-1', async route => {
    await route.fulfill({ status: 200, contentType: 'application/zip', body: Buffer.from('fake-zip') });
  });
  await page.route('**/api/pipeline/credits', async route => {
    await route.fulfill({ json: { credits: 9 } });
  });

  await page.addInitScript(value => localStorage.setItem('neonbuild_token', value), token);
  await page.goto('/workspace');

  await expect(page.getByText('Welcome to NeonBuild')).toBeVisible();
  const input = page.locator('textarea').last();
  await input.fill('Build a hello app');
  await input.press('Enter');

  await expect(page.getByText(/Build accepted · react-native target/i)).toBeVisible();
  await expect(page.getByText(/Analyzing the product and planning the architecture/i)).toBeVisible();
  await expect(page.getByText(/completed building your app/i)).toBeVisible();
  await expect(page.getByText(/planner is complete/i)).toBeVisible();
  await expect(page.getByTitle('Refresh preview')).toBeVisible();
  await expect(page.getByTitle('Mobile preview')).toBeVisible();
  await page.getByTitle('Mobile preview').click();
  await expect(page.getByTitle('Mobile preview')).toHaveAttribute('aria-pressed', 'true');
  await page.getByTitle('Expand preview').click();
  await expect(page.getByRole('dialog', { name: 'Expanded app preview' })).toBeVisible();
  await expect(page.getByText(/react-native interactive simulation/i)).toBeVisible();
  await expect(page.locator('iframe').last()).not.toHaveAttribute('sandbox', /allow-same-origin/);
  await page.getByTitle('Close preview').click();
  await expect(page.getByTitle('Open in new tab')).toBeVisible();
  await expect(page.getByTitle('Download code (.zip)')).toBeVisible();
});

test('stream interruption reconciles with completed backend status', async ({ page }) => {
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({ json: { id: 'user-1', username: 'e2e', email: 'e2e@example.com', credits: 10 } });
  });
  await page.route('**/api/pipeline/run', async route => {
    await route.fulfill({ json: { job_id: 'e2e-job-2', status: 'queued', phase: 'queued', artifacts: [], errors: [] } });
  });
  await page.route('**/api/pipeline/stream/e2e-job-2', async route => route.abort());
  await page.route('**/api/pipeline/status/e2e-job-2', async route => {
    await route.fulfill({ json: { job_id: 'e2e-job-2', status: 'complete', phase: 'complete', preview_url: '/preview/e2e-job-2/', artifacts: ['PLAN.md'], errors: [] } });
  });
  await page.route('**/api/pipeline/credits', async route => {
    await route.fulfill({ json: { credits: 9 } });
  });

  await page.addInitScript(value => localStorage.setItem('neonbuild_token', value), token);
  await page.goto('/workspace');
  await page.locator('textarea').last().fill('Build a resilient app');
  await page.locator('textarea').last().press('Enter');

  await expect(page.getByText(/completed while the live progress stream was reconnecting/i)).toBeVisible({ timeout: 10_000 });
});

test('validation errors are rendered as readable text', async ({ page }) => {
  await page.route('**/api/auth/login', async route => route.fulfill({
    status: 422,
    json: { detail: [{ type: 'string_too_short', loc: ['body', 'password'], msg: 'Password must contain at least 8 characters' }] },
  }));
  await page.goto('/workspace');
  await page.locator('input').nth(0).fill('demo@example.com');
  await page.locator('input').nth(1).fill('x');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page.getByText('Password must contain at least 8 characters')).toBeVisible();
  await expect(page.getByText(/\[object Object\]/)).toHaveCount(0);
});

test('registration preserves an email and signs in with the same identifier', async ({ page }) => {
  const email = 'isearch.xsolve@gmail.com';
  let registrationPayload: Record<string, string> | undefined;
  let loginIdentifier: string | null = null;

  await page.route('**/api/auth/register', async route => {
    registrationPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      json: { id: 'user-email', username: 'isearch_xsolve_gmail_com', email, credits: 10 },
    });
  });
  await page.route('**/api/auth/login', async route => {
    loginIdentifier = new URLSearchParams(route.request().postData() || '').get('username');
    await route.fulfill({ json: { access_token: token, token_type: 'bearer' } });
  });
  await page.route('**/api/pipeline/credits', async route => {
    await route.fulfill({ json: { credits: 10 } });
  });

  await page.goto('/workspace');
  await page.getByPlaceholder('Username or email').fill(email);
  await page.getByPlaceholder('Password').fill('valid-password');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByText('Welcome to NeonBuild')).toBeVisible();
  expect(registrationPayload).toEqual({
    email,
    username: 'isearch_xsolve_gmail_com',
    password: 'valid-password',
  });
  expect(loginIdentifier).toBe(email);
});
