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
      { kind: 'product', id: 2, title: '工业电机', subtitle: '华南精密制造 · 机械制造 · 广东省 佛山市', tags: ['机械制造'], public_signals: { source: '测试数据', data_updated_at: '2026-09-17', is_demo: true }, requires_login_for_action: true },
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
  test('可以搜索并将条件写入 URL', async ({ page }) => {
    await mockPublicSearch(page);
    await page.goto('/search');
    await expect(page.getByTestId('public-search-result')).toHaveCount(2);
    await page.getByTestId('public-search-input').fill('工业电机');
    await page.getByTestId('public-search-submit').click();
    await expect(page).toHaveURL(/q=%E5%B7%A5%E4%B8%9A%E7%94%B5%E6%9C%BA/);
    await expect(page.getByTestId('public-search-count')).toContainText('2');
    await page.screenshot({ path: 'test-results/search-desktop.png', fullPage: true });
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
});
