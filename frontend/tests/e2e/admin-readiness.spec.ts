import { expect, test } from '@playwright/test';

test('管理员首页展示生产就绪门禁且不暴露敏感配置', async ({ page }) => {
  await page.route('**/api/session**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ authenticated: true, user: { id: 1, name: '平台管理员', enterprise_name: '平台管理员', role: 'admin' } }),
  }));
  await page.route('**/api/admin/production-readiness', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      data: {
        ready: false,
        environment: 'development',
        required_failures: ['secret_key', 'database', 'explicit_approval'],
        checks: {
          secret_key: { configured: false, required: true, status: 'required_missing', provider: 'application_secret' },
          database: { configured: false, required: true, status: 'required_missing', provider: 'configured_database' },
          deepseek: { configured: true, required: false, status: 'ok', provider: 'deepseek' },
          explicit_approval: { configured: false, required: true, status: 'required_missing', provider: 'approval_policy' },
          work_wechat: { configured: false, required: false, status: 'optional_missing', provider: 'wecom' },
        },
      },
    }),
  }));
  await page.route('**/api/alerts**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ total: 0, alerts: [] }),
  }));

  await page.goto('/admin/dashboard');
  await page.waitForTimeout(1000);
  await expect(page.getByRole('heading', { name: '生产就绪门禁' })).toBeVisible();
  await expect(page.getByText('不可上线 · 3 项必需配置缺失')).toBeVisible();
  await expect(page.getByText('DeepSeek 模型')).toBeVisible();
  await expect(page.getByText('应用密钥', { exact: true })).toBeVisible();
  await expect(page.getByText('询价显式审批', { exact: true })).toBeVisible();
  await expect(page.getByText(/sk-|API_KEY|password/i)).toHaveCount(0);
});
