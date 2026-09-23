import { expect, test } from '@playwright/test';

const homePayload = {
  stats: { enterprise_count: 1, product_count: 1, active_supply_count: 0, active_demand_count: 0, completed_transaction_count: 0, graph_node_count: 1, verified_count: 1 },
  featured_enterprises: [], featured_products: [], latest_inquiries: [],
  industries: [{ key: 'machinery', label: '机械制造' }],
  regions: [{ key: '广东省', label: '广东省', count: 1 }], industrial_belts: [], public_services: [],
  data_freshness: { mode: 'test', is_demo: true, label: '演示数据', updated_at: '2026-09-17T00:00:00Z' },
  data_status: { mode: 'test', message: '测试数据' },
};

function searchPayload(query = '', total = 2) {
  return {
    query, type: 'all', province: '', city: '', industry: '', sort: 'relevance', filters: {}, page: 1, per_page: 10, total, pages: 1, has_more: false,
    results: total ? [
      { kind: 'enterprise', id: 1, title: '华南精密制造', subtitle: '精密加工 · 广东省 佛山市', tags: ['已审核', '产能可用'], public_signals: { verification_status: 'approved', source: '测试数据', data_updated_at: '2026-09-17', is_demo: true, is_export: true, has_decision_maker: true, is_little_giant: true, is_green_factory: true, status: '存续' }, requires_login_for_action: true,
      },
      { kind: 'product', id: 2, title: '工业电机', subtitle: '华南精密制造 · 机械制造 · 广东省 佛山市', tags: ['机械制造'], public_signals: { enterprise_id: 1, source: '测试数据', data_updated_at: '2026-09-17', is_demo: true }, requires_login_for_action: true },
    ] : [],
  };
}

async function mockPublicSearch(page: import('@playwright/test').Page) {
  await page.route('**/api/public/home', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(homePayload) }));
  await page.route('**/api/public/search**', route => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get('q') || '';
    const isEmpty = query === '不存在';
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(searchPayload(query, isEmpty ? 0 : 2)) });
  });
}

test.describe('搜索中心', () => {
  test('筛选条件可以携带到 AI 找工厂', async ({ page }) => {
    await mockPublicSearch(page);
    await page.goto('/search');
    await expect(page.getByTestId('public-search-result')).toHaveCount(2);
    await page.getByTestId('public-search-input').fill('工业电机');
    await page.getByRole('button', { name: 'AI 找工厂' }).click();
    await expect(page).toHaveURL(/\/aia\?q=%E5%B7%A5%E4%B8%9A%E7%94%B5%E6%9C%BA/);
  });

  test('快捷筛选立即生效并支持移动端抽屉', async ({ page }) => {
    await mockPublicSearch(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/search');
    await page.getByRole('button', { name: '可出口' }).click();
    await expect(page).toHaveURL(/is_export=1/);
    await page.getByRole('button', { name: /筛选/ }).click();
    await expect(page.getByTestId('province-filter')).toBeVisible();
    await page.getByRole('button', { name: '清空' }).click();
    await expect(page).not.toHaveURL(/is_export=1/);
  });

  test('空结果态可见', async ({ page }) => {
    await mockPublicSearch(page);
    await page.goto('/search?q=%E4%B8%8D%E5%AD%98%E5%9C%A8');
    await expect(page.getByTestId('public-search-empty')).toBeVisible();
  });

  test('已登录时联系询价进入对应匹配结果，不再打开登录流程', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile-chrome', '移动端筛选结果卡片暂不展示联系/询价按钮');
    await mockPublicSearch(page);
    await page.route('**/api/session**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ authenticated: true, user: { id: 8, name: '测试企业', enterprise_name: '测试企业', role: 'enterprise' } }),
    }));
    await page.route('**/api/matching/search**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ suppliers: [{ id: 1, name: '华南精密制造', score: 92, tags: [], desc: '测试供应商' }] }),
    }));
    await page.goto('/search');
    await expect(page.getByTestId('public-search-result')).toHaveCount(2);
    await page.getByRole('button', { name: '联系 / 询价' }).first().click();
    await expect(page).toHaveURL(/\/matching\?query=%E5%8D%8E%E5%8D%97%E7%B2%BE%E5%AF%86%E5%88%B6%E9%80%A0&supplier_id=1/);
    await expect(page.getByRole('button', { name: /发起匿名询价|发送匿名报价/ })).toBeVisible();
  });

  test('从搜索进入匹配页时不应默认用 AAA 信用条件过滤掉真实结果', async ({ page }) => {
    await page.route('**/api/session**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ authenticated: false, user: null }),
    }));
    await page.route('**/api/matching/search**', route => {
      const url = new URL(route.request().url());
      const hasImplicitCreditFilter = Boolean(url.searchParams.get('min_credit'));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          suppliers: hasImplicitCreditFilter
            ? []
            : [{ id: 1, name: '电机真实供应商', score: 88, tags: [], desc: '匹配结果' }],
        }),
      });
    });
    await page.goto('/matching?query=%E7%94%B5%E6%9C%BA');
    await expect(page.getByText('召回 1 家')).toBeVisible();
    await expect(page.getByText('电机真实供应商').first()).toBeVisible();
  });

  test('工作台顶部搜索框回车后进入统一企业搜索', async ({ page }) => {
    await page.route('**/api/session**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ authenticated: false, user: null }),
    }));
    await page.route('**/api/enterprises/directory**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ enterprises: [], total: 0, count: 0, page: 1, pages: 0, per_page: 24 }),
    }));
    await page.goto('/workspace/enterprise-directory');
    const search = page.locator('input[placeholder="搜索企业、产品或工厂..."]:visible');
    await search.fill('电机');
    await search.press('Enter');
    await expect(page).toHaveURL(/\/search\?q=%E7%94%B5%E6%9C%BA/);
  });
});
