import { expect, test } from '@playwright/test';

const homePayload = {
  stats: { enterprise_count: 1, product_count: 1, active_supply_count: 0, active_demand_count: 0, completed_transaction_count: 0, graph_node_count: 1, verified_count: 1 },
  featured_enterprises: [], featured_products: [], latest_inquiries: [], industries: [], regions: [], industrial_belts: [], public_services: [],
  data_freshness: { mode: 'test', is_demo: true, label: '演示数据', updated_at: '2026-09-17T00:00:00Z' },
  data_status: { mode: 'test', message: '测试数据' },
};

test('首页筛选入口携带关键词进入 Agent 会话页', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false, user: null }) }));
  await page.route('**/api/public/home', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(homePayload) }));
  await page.route('**/api/chain-xiaoyi/sessions', route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: '测试停止自动提交' }) }));
  // The public AI search home is /aisearch/; / now intentionally redirects
  // to the separate Indisea brand page.
  await page.goto('/aisearch/');
  await expect(page.getByTestId('public-home-search').getByRole('button', { name: 'AI 找工厂' })).toHaveClass(/bg-public-brand-soft/);
  await expect(page.locator('#factory-search')).toHaveAttribute('placeholder', '例如：找华东可做精密注塑、支持出口的工厂');
  await page.locator('#factory-search').fill('电机');
  await page.getByTestId('public-home-search-submit').click();
  await expect(page).toHaveURL(/\/aia\?q=%E7%94%B5%E6%9C%BA/);
});

test('只有在首页点亮 Agent 自动化并输入指定需求才进入演示流程', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false, user: null }) }));
  await page.route('**/api/public/home', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(homePayload) }));
  await page.route('**/api/chain-xiaoyi/sessions', route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: '测试停止自动提交' }) }));

  await page.goto('/aisearch/');
  const form = page.getByTestId('public-home-search');
  const automation = form.getByRole('button', { name: 'Agent 自动化' });
  await expect(automation).toHaveAttribute('aria-pressed', 'false');
  await page.locator('#factory-search').fill('找华东能做精密注塑、30天交付的工厂');
  await form.getByRole('button', { name: '开始分析' }).click();
  await expect(page).toHaveURL(/\/aia\?q=.*%E7%B2%BE%E5%AF%86%E6%B3%A8%E5%A1%91.*$/);
  await expect(page).not.toHaveURL(/agent=demo/);

  await page.goto('/aisearch/');
  await page.locator('#factory-search').fill('找华东能做精密注塑、30天交付的工厂');
  await automation.click();
  await expect(automation).toHaveAttribute('aria-pressed', 'true');
  await form.getByRole('button', { name: '开始分析' }).click();
  await expect(page).toHaveURL(/\/aia\?q=.*%E7%B2%BE%E5%AF%86%E6%B3%A8%E5%A1%91.*&agent=demo/);
});
