import { expect, test } from '@playwright/test';

const market = {
  layers: [
    { key: 'data', title: '产业数据底座', description: '企业、产品、产能、信用和产业关系' },
    { key: 'business', title: '企业业务数据', description: '订单、库存、BOM、客户和报价' },
    { key: 'agent', title: '岗位型 AI Agent', description: '名单、询价单、排产建议和风险告警' },
  ],
  groups: [
    {
      title: 'AI 销售员',
      summary: '寻找高匹配客户，辅助销售推进。',
      demo: true,
      agents: ['客户线索筛选', '商机跟进建议'],
      skills: [],
    },
    {
      title: 'AI 采购员',
      summary: '从真实需求出发，快速找到合适供应商。',
      demo: false,
      agents: ['供应商寻源', '询价准备'],
      skills: [],
    },
  ],
};

test('Agent 能力市场保持清晰布局并适配移动端', async ({ page }) => {
  await page.route('**/api/session', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ authenticated: false, user: null }),
  }));
  await page.route('**/api/public/agent-market', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(market),
  }));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/agent-market');

  await expect(page.getByRole('heading', { name: /把 AI 放进真实的.*制造业务里/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'AI 销售员' })).toBeVisible();
  await expect(page.getByText('从数据到行动结果')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
