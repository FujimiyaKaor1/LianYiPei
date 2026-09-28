import { expect, test } from '@playwright/test';

test('企业看板不显示产能日历且顶部导航居中', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      authenticated: true,
      user: { id: 8, name: '测试企业', enterprise_name: '测试企业', role: 'enterprise' },
    }),
  }));
  await page.route('**/api/enterprise/dashboard/summary**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      metrics: { inquiries: 1, quotes: 2, orders: 0, fulfillment_rate: 0 },
      todos: [],
      updated_at: '2026-09-23T00:00:00Z',
      source: 'test',
      is_demo: false,
    }),
  }));
  await page.route('**/api/enterprise/dashboard/trends**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      labels: ['2026-04'],
      inquiries: [1],
      quotes: [2],
      orders: [0],
      fulfillment: [0],
      updated_at: '2026-09-23T00:00:00Z',
      source: 'test',
      is_demo: false,
    }),
  }));
  await page.route('**/api/alerts**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ alerts: [], total: 0 }),
  }));

  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: '测试企业经营看板' })).toBeVisible();
  await expect(page.getByText('产能日历')).toHaveCount(0);

  const navigation = page.getByRole('navigation', { name: '企业工作台导航' });
  await expect(navigation).toBeVisible();
  await expect(navigation.getByText('企业协同')).toBeVisible();
  await expect(navigation).toHaveCSS('justify-content', 'center');
});
