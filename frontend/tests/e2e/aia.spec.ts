import { expect, test } from '@playwright/test';

const session = { id: 42, title: '找工业电机', surface: 'public', status: 'active', intent: {}, updated_at: '2026-09-17T00:00:00' };
const modelStatus = { local_enabled: false, cloud_enabled: false, local_model: '', cloud_provider: 'deepseek', cloud_model: 'deepseek-v4-flash-vision-exp', active_provider: 'rules', is_configured: false, message: '本轮使用确定性规则与数据库匹配' };

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

test('自然语言暂停询价后显示可恢复状态', async ({ page }) => {
  const authenticatedUser = { id: 8, name: '测试采购企业', enterprise_name: '测试采购企业', role: 'enterprise' };
  await page.route('**/api/session', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, user: authenticatedUser }) }));
  await page.route('**/api/chain-xiaoyi/sessions', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ success: true, session, model_status: modelStatus }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, sessions: [] }) });
  });
  await page.route('**/api/chain-xiaoyi/tasks?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, tasks: [], total: 0 }) }));
  await page.route('**/api/chain-xiaoyi/sessions/42/claim', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, session }) }));
  await page.route('**/api/chain-xiaoyi/sessions/42/messages', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      reply: '已暂停当前询价任务；不会继续对外发送。',
      intent: { product: '连接器' },
      needs_clarification: false,
      suggestions: [],
      model_status: modelStatus,
      task: { id: 90, type: 'workflow_command', status: 'succeeded', requires_approval: false },
      workflow: { action: 'task_cancelled', source_task_id: 9, status: 'cancelled' },
      match_result: { total: 1, degraded: true, explanation_provider: 'rules', results: [{ id: 7, name: '授权连接器工厂', province: '广东', city: '东莞', business_scope: '连接器制造', score: 88, confidence_index: 88, dimensions: {}, trusted_labels: [], reason: '已授权触达', data_updated_at: '2026-09-17', degraded: true, contact_eligible: true }] },
    }),
  }));
  await page.route('**/api/chain-xiaoyi/procurement-tasks/9', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, task: { id: 9, type: 'rfq', status: 'cancelled', requires_approval: true, input: { intent: { product: '连接器' } }, output: {} } }),
  }));

  await page.goto('/aia');
  await page.locator('textarea').fill('暂停当前询价');
  await page.locator('textarea').press('Enter');
  await expect(page.getByText('已暂停当前询价任务；不会继续对外发送。')).toBeVisible();
  await expect(page.getByRole('button', { name: '恢复询价任务' })).toBeVisible();
});

test('上传多行采购单后为每个采购项自动找厂并可切换结果', async ({ page }) => {
  const authenticatedUser = { id: 8, name: '测试采购企业', enterprise_name: '测试采购企业', role: 'enterprise' };
  await page.route('**/api/session', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, user: authenticatedUser }) }));
  await page.route('**/api/chain-xiaoyi/sessions?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, sessions: [] }) }));
  await page.route('**/api/chain-xiaoyi/tasks?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, tasks: [], total: 0 }) }));
  await page.route('**/api/chain-xiaoyi/sessions', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ success: true, session, model_status: modelStatus }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, sessions: [] }) });
  });
  await page.route('**/api/chain-xiaoyi/sessions/42/claim', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, session }) }));
  await page.route('**/api/chain-xiaoyi/sessions/42/files', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      file: { id: 5, filename: '多物料.csv', status: 'parsed', detected_kind: 'table', preview: {}, errors: [] },
      task: { id: 77, type: 'procurement_intake', status: 'draft', requires_approval: false },
      draft: {
        fields: { product: { value: '连接器', confidence: 0.98, evidence: { row: 2 } }, quantity: { value: 2000, confidence: 0.98, evidence: { row: 2 } } },
        items: [
          { index: 1, fields: { product: { value: '连接器', confidence: 0.98, evidence: { row: 2 } }, quantity: { value: 2000, confidence: 0.98, evidence: { row: 2 } } }, missing_required: [] },
          { index: 2, fields: { product: { value: '五金冲压件', confidence: 0.98, evidence: { row: 3 } }, quantity: { value: 5000, confidence: 0.98, evidence: { row: 3 } } }, missing_required: [] },
        ],
        missing_required: [], clarifying_questions: [], schema_version: 'procurement.v2',
      },
    }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/recompute', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      task: { id: 77, type: 'procurement_intake', status: 'ready', requires_approval: false },
      item_matches: [
        { item_index: 1, intent: { product: '连接器', quantity: 2000 }, evidence: {}, match_result: { total: 1, degraded: false, explanation_provider: 'rules', results: [{ id: 31, name: '连接器工厂', province: '广东', city: '东莞', business_scope: '连接器制造', score: 91, confidence_index: 91, dimensions: {}, trusted_labels: [], reason: '产品能力匹配', degraded: false, contact_eligible: true }] } },
        { item_index: 2, intent: { product: '五金冲压件', quantity: 5000 }, evidence: {}, match_result: { total: 1, degraded: false, explanation_provider: 'rules', results: [{ id: 32, name: '五金冲压工厂', province: '广东', city: '佛山', business_scope: '五金加工', score: 89, confidence_index: 89, dimensions: {}, trusted_labels: [], reason: '工艺能力匹配', degraded: false, contact_eligible: true }] } },
      ],
    }),
  }));
  await page.route('**/api/chain-xiaoyi/procurement-tasks/77/auto-plan', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      idempotent: false,
      task: { id: 77, type: 'procurement_intake', status: 'awaiting_approval', requires_approval: true },
      item_matches: [
        { item_index: 1, intent: { product: '连接器', quantity: 2000 }, evidence: {}, match_result: { total: 1, degraded: false, explanation_provider: 'rules', results: [{ id: 31, name: '连接器工厂', province: '广东', city: '东莞', business_scope: '连接器制造', score: 91, confidence_index: 91, dimensions: {}, trusted_labels: [], reason: '产品能力匹配', degraded: false, contact_eligible: true }] } },
        { item_index: 2, intent: { product: '五金冲压件', quantity: 5000 }, evidence: {}, match_result: { total: 1, degraded: false, explanation_provider: 'rules', results: [{ id: 32, name: '五金冲压工厂', province: '广东', city: '佛山', business_scope: '五金加工', score: 89, confidence_index: 89, dimensions: {}, trusted_labels: [], reason: '工艺能力匹配', degraded: false, contact_eligible: true }] } },
      ],
      preview: { status: 'awaiting_approval', item_count: 2, supplier_count: 2, channels: ['site'], task_ids: [81, 82], disclosures: [] },
    }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/rfq-batch-preview', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      success: true,
      idempotent: false,
      task: { id: 77, type: 'procurement_intake', status: 'awaiting_approval', requires_approval: true },
      rfq_tasks: [
        { id: 81, type: 'rfq', status: 'awaiting_approval', requires_approval: true },
        { id: 82, type: 'rfq', status: 'awaiting_approval', requires_approval: true },
      ],
      preview: { status: 'awaiting_approval', item_count: 2, supplier_count: 2, channels: ['site'], task_ids: [81, 82], disclosures: [] },
    }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/rfq-batch-approve', route => route.fulfill({
    status: 202,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, queued: 2, idempotent: false, task: { id: 77, type: 'procurement_intake', status: 'running', requires_approval: true } }),
  }));
  const batchItems = [
    { item_index: 1, rfq_task_id: 81, task_id: 81, product: '连接器', quotes: [{ quote_id: 101, supplier_id: 31, supplier_name: '连接器工厂', price: 9.8, unit: '件', quantity: 2000, delivery_days: 20, notes: '含税', status: 'accepted', tax_included: true }], recommendation: null },
    { item_index: 2, rfq_task_id: 82, task_id: 82, product: '五金冲压件', quotes: [{ quote_id: 102, supplier_id: 32, supplier_name: '五金冲压工厂', price: 4.6, unit: '件', quantity: 5000, delivery_days: 25, notes: '含税', status: 'accepted', tax_included: true }], recommendation: null },
  ];
  await page.route('**/api/chain-xiaoyi/tasks/77/batch-quote-summary', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, task_id: 77, item_count: 2, quoted_item_count: 2, quote_count: 2, complete: true, items: batchItems }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/batch-quote-query', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, task_id: 77, query: '每个采购项只看含税价最低且30天内能交付的一家', item_count: 2, complete: true, missing_items: [], items: batchItems, selections: [{ item_index: 1, rfq_task_id: 81, supplier_id: 31 }, { item_index: 2, rfq_task_id: 82, supplier_id: 32 }], explanation: '全部来自供应商回复', evidence_only: true }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/batch-order-drafts', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, idempotent: false, orders: [{ draft_id: 'rfq-81-31', status: 'draft' }, { draft_id: 'rfq-82-32', status: 'draft' }], selection: {}, requires_formal_order_confirmation: true }),
  }));
  await page.route('**/api/chain-xiaoyi/tasks/77/batch-order-drafts/confirm', route => route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({ success: true, idempotent: false, orders: [
      { id: 1, order_no: 'ORD-DEMO-1', status: 'pending', metadata: { requires_contract_confirmation: true, requires_payment_confirmation: true } },
      { id: 2, order_no: 'ORD-DEMO-2', status: 'pending', metadata: { requires_contract_confirmation: true, requires_payment_confirmation: true } },
    ], requires_contract_confirmation: true, requires_payment_confirmation: true }),
  }));

  await page.goto('/aia');
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: '多物料.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('产品,数量\n连接器,2000\n五金冲压件,5000\n'),
  });

  await expect(page.locator('p:visible', { hasText: '材料采购项 · 已自动分别找厂' })).toBeVisible();
  await expect(page.locator('h3:visible', { hasText: '连接器工厂' })).toBeVisible();
  const workWeChatChannel = page.getByRole('button', { name: '企业微信（仅授权时）' });
  await expect(workWeChatChannel).toHaveAttribute('aria-pressed', 'false');
  await workWeChatChannel.click();
  await expect(workWeChatChannel).toHaveAttribute('aria-pressed', 'true');
  await page.locator('button:visible', { hasText: '#2 五金冲压件' }).click();
  await expect(page.locator('h3:visible', { hasText: '五金冲压工厂' })).toBeVisible();
  await expect(page.locator('p:visible', { hasText: '将发送 2 个采购项，共 2 个供应商触达记录' })).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('button:visible', { hasText: '一次确认并全部加入发送队列' }).click();
  await expect(page.locator('p:visible', { hasText: '已确认，后台发送中' })).toBeVisible();
  await page.locator('button:visible', { hasText: '刷新全部报价' }).click();
  await expect(page.locator('p:visible', { hasText: '2/2 个采购项已有符合条件的报价' }).first()).toBeVisible();
  await page.locator('button:visible', { hasText: '逐项筛选' }).click();
  await expect(page.locator('div:visible', { hasText: '已按你的条件为 2 个采购项分别选出供应商' }).first()).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('button:visible', { hasText: '按这句话生成全部订单草稿' }).click();
  await expect(page.locator('div:visible', { hasText: '已生成 2 份订单草稿；正式订单、合同和付款尚未执行' }).first()).toBeVisible();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('button:visible', { hasText: '人工确认并创建全部正式订单' }).click();
  await expect(page.locator('p:visible', { hasText: '正式订单 ORD-DEMO-1' }).first()).toBeVisible();
  await expect(page.locator('p:visible', { hasText: '合同：待确认 · 付款：待确认' }).first()).toBeVisible();
});
