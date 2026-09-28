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

test('管理员从公开页面登录后进入管理后台', async ({ page }) => {
  let authenticated = false;

  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(authenticated
      ? { authenticated: true, user: { id: 1, name: 'admin', enterprise_name: 'admin', role: 'admin' } }
      : { authenticated: false, user: null }),
  }));
  await page.route('**/auth/login', async route => {
    authenticated = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, redirect: '/admin/dashboard', role: 'admin' }),
    });
  });

  await page.goto('/indisea/');
  await page.getByRole('button', { name: '登录 / 入驻' }).click();
  await page.locator('input[autocomplete="username"]').fill('admin');
  await page.locator('input[autocomplete="current-password"]').fill('admin');
  await page.getByRole('button', { name: '登录', exact: true }).click();

  await expect(page).toHaveURL(/\/admin\/dashboard$/);
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

test('登录后公共导航与企业账号区域不重叠', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      authenticated: true,
      user: { id: 8, name: '测试企业', enterprise_name: '测试企业', role: 'enterprise' },
    }),
  }));

  await page.goto('/indisea/');
  await expect(page.getByTestId('authenticated-user')).toBeVisible();

  const navigation = page.getByRole('navigation', { name: '公共平台导航' });
  const account = page.getByTestId('authenticated-user');
  const navigationBox = await navigation.boundingBox();
  const accountBox = await account.boundingBox();

  expect(navigationBox).not.toBeNull();
  expect(accountBox).not.toBeNull();
  expect(navigationBox!.x + navigationBox!.width).toBeLessThanOrEqual(accountBox!.x);
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

test('默认公开导航不展示企业协同和服务入口', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ authenticated: false, user: null }),
  }));

  await page.goto('/industry-news');
  const navigation = page.getByRole('navigation', { name: '公共平台导航' });
  await expect(navigation.getByRole('link', { name: '进入企业协同' })).toHaveCount(0);
  await expect(navigation.getByRole('link', { name: '服务' })).toHaveCount(0);
});
