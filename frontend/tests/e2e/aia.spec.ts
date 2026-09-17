import { expect, test } from '@playwright/test';

const session = { id: 42, title: '找工业电机', surface: 'public', status: 'active', intent: {}, updated_at: '2026-09-17T00:00:00' };
const modelStatus = { local_enabled: false, cloud_enabled: false, local_model: '', cloud_provider: 'deepseek', cloud_model: 'deepseek-chat', active_provider: 'rules', is_configured: false, message: '本轮使用确定性规则与数据库匹配' };

async function mockAgent(page: import('@playwright/test').Page) {
  await page.route('**/api/session', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: false, user: null }) }));
  await page.route('**/api/chain-xiaoyi/sessions', route => route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ success: true, session, model_status: modelStatus }) }));
  await page.route('**/api/chain-xiaoyi/sessions/42/messages', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
    success: true, reply: '已按数据库九维算法找到 1 家候选工厂。',
    intent: { product: '工业电机', region: '四川' }, needs_clarification: false, suggestions: ['补充交期'], model_status: modelStatus,
    task: { id: 9, type: 'demand_intake', status: 'succeeded', requires_approval: false },
    match_result: { total: 1, degraded: true, explanation_provider: 'rules', results: [{ id: 7, name: '数据库工厂', province: '四川省', city: '成都市', business_scope: '电机制造', score: 88, confidence_index: 88, dimensions: { product: { score: 85, desc: '产品名称匹配' }, credit: { score: 90, desc: '信用分90' } }, trusted_labels: [], reason: '产品匹配，综合九维数据库评分推荐。', data_updated_at: '2026-09-17', degraded: true }] },
  }) }));
}

test('首页自然语言参数自动进入会话并展示数据库候选', async ({ page }) => {
  await mockAgent(page);
  await page.goto('/aia?q=%E6%89%BE%E5%9B%9B%E5%B7%9D%E5%B7%A5%E4%B8%9A%E7%94%B5%E6%9C%BA');
  await expect(page.locator('h3:visible', { hasText: '数据库工厂' })).toBeVisible();
  await expect(page.locator('span:visible', { hasText: '88分' })).toBeVisible();
  await expect(page.getByText(/数据库九维算法决定/)).toBeVisible();
});

test('移动端可打开历史和结果抽屉', async ({ page }) => {
  await mockAgent(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/aia?q=%E6%89%BE%E5%B7%A5%E4%B8%9A%E7%94%B5%E6%9C%BA');
  await expect(page.getByRole('heading', { name: '数据库工厂' }).last()).toBeVisible();
  await page.getByRole('button', { name: '关闭' }).click();
  await page.getByRole('button', { name: '打开历史' }).click();
  await expect(page.getByText('登录后查看历史会话并继续追问').last()).toBeVisible();
});
