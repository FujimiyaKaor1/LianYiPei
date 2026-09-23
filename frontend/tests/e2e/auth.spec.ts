import { expect, test } from '@playwright/test';

test('登录弹窗拒绝空白凭据并在成功后同步会话', async ({ page }) => {
  let loginRequests = 0;
  let authenticated = false;

  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(authenticated
      ? { authenticated: true, user: { id: 8, name: '测试企业', enterprise_name: '测试企业', role: 'enterprise' } }
      : { authenticated: false, user: null }),
  }));
  await page.route('**/auth/login', async route => {
    loginRequests += 1;
    authenticated = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, redirect: '/dashboard', role: 'enterprise' }),
    });
  });

  await page.goto('/indisea/');
  await page.getByRole('button', { name: '登录 / 入驻' }).click();
  await expect(page.getByRole('heading', { name: '用户登录' })).toBeVisible();

  await page.locator('input[autocomplete="username"]').fill('   ');
  await page.locator('input[autocomplete="current-password"]').fill('x');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByText('请填写企业名称与密码')).toBeVisible();
  expect(loginRequests).toBe(0);

  await page.locator('input[autocomplete="username"]').fill('测试企业');
  await page.locator('input[autocomplete="current-password"]').fill('test123456');
  await page.getByRole('button', { name: '登录', exact: true }).click();

  await expect(page).toHaveURL(/\/indisea\//);
  await expect(page.getByRole('heading', { name: '用户登录' })).toBeHidden();
  await expect(page.getByText('测试企业')).toBeVisible();
  expect(loginRequests).toBe(1);
});

test('登录和退出都在当前公共页面同步全局状态', async ({ page }) => {
  let authenticated = false;

  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(authenticated
      ? { authenticated: true, user: { id: 8, name: '测试企业', enterprise_name: '测试企业', role: 'enterprise' } }
      : { authenticated: false, user: null }),
  }));
  await page.route('**/auth/login', async route => {
    authenticated = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, redirect: '/dashboard', role: 'enterprise' }),
    });
  });
  await page.route('**/api/logout', async route => {
    authenticated = false;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
  });

  await page.goto('/industry-news');
  await page.getByRole('button', { name: '登录 / 入驻' }).click();
  await page.locator('input[autocomplete="username"]').fill('测试企业');
  await page.locator('input[autocomplete="current-password"]').fill('test123456');
  await page.getByRole('button', { name: '登录', exact: true }).click();

  await expect(page).toHaveURL(/\/industry-news$/);
  await expect(page.getByText('测试企业')).toBeVisible();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('button', { name: '登录 / 入驻' })).toBeVisible();
  await expect(page.getByText('测试企业')).toBeHidden();
});

test('公共页面未传登录回调时仍能打开登录弹窗', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ authenticated: false, user: null }),
  }));

  await page.goto('/industry-news');
  await page.getByRole('button', { name: '登录 / 入驻' }).click();
  await expect(page.getByRole('heading', { name: '用户登录' })).toBeVisible();
});
