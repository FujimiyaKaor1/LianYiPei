import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { createHmac } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const BASE_URL = process.env.DEMO_BASE_URL || 'http://127.0.0.1:5150';
const VIDEO_DIR = process.env.DEMO_VIDEO_DIR || '/Users/fujimiyakaori/Documents/ChatGPT/lypdemo/tmp/chain-xiaoyi-demo-video';
const OUTPUT = process.env.DEMO_OUTPUT || '/Users/fujimiyakaori/Documents/ChatGPT/lypdemo/tmp/chain-xiaoyi-procurement-demo.webm';
const MATERIAL = '/Users/fujimiyakaori/Documents/ChatGPT/lypdemo/tmp/demo_purchase_request.csv';
const BUYER = '链易配演示·湾区采购中心';
const SUPPLIER = '链易配演示·深圳精密连接器厂';
const PASSWORD = 'DemoAgent2026!';
const FULFILLMENT_SECRET = 'chain-xiaoyi-video-secret';
const REHEARSE = process.argv.includes('--rehearse');

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

async function visibleTarget(locator, label, timeout = 10000) {
  const candidates = typeof locator === 'string' ? locator : locator;
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const count = await candidates.count().catch(() => 0);
    for (let index = 0; index < count; index += 1) {
      const item = candidates.nth(index);
      if (await item.isVisible().catch(() => false)) return item;
    }
    await sleep(250);
  }
  throw new Error(`录制步骤找不到可见元素：${label}`);
}

async function injectCursor(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-cursor')) return;
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    cursor.innerHTML = '<svg width="25" height="25" viewBox="0 0 24 24" fill="none"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="#102a43" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    cursor.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;width:25px;height:25px;transition:left .1s,top .1s;filter:drop-shadow(1px 1px 2px rgba(0,0,0,.35));left:0;top:0';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', event => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
    });
  });
}

async function injectSubtitleBar(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-subtitle')) return;
    const bar = document.createElement('div');
    bar.id = 'demo-subtitle';
    bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:999998;text-align:center;padding:12px 24px;background:rgba(8,24,42,.84);color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:16px;font-weight:600;letter-spacing:.3px;transition:opacity .25s;pointer-events:none;opacity:0';
    document.body.appendChild(bar);
  });
}

async function showSubtitle(page, text, pause = 900) {
  await page.evaluate(value => {
    const bar = document.getElementById('demo-subtitle');
    if (!bar) return;
    bar.textContent = value;
    bar.style.opacity = value ? '1' : '0';
  }, text);
  if (text && pause) await sleep(pause);
}

async function moveAndClick(page, locator, label, pause = 700) {
  const target = await visibleTarget(typeof locator === 'string' ? page.locator(locator) : locator, label);
  await target.scrollIntoViewIfNeeded();
  await sleep(250);
  const box = await target.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 });
  await sleep(300);
  await target.click();
  await sleep(pause);
}

async function typeSlowly(page, locator, value, label, delay = 32) {
  const target = await visibleTarget(typeof locator === 'string' ? page.locator(locator) : locator, label);
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 10 });
  await target.click();
  await target.fill('');
  await target.pressSequentially(value, { delay });
  await sleep(500);
}

async function ensureVisible(page, locator, label) {
  try {
    await visibleTarget(typeof locator === 'string' ? page.locator(locator) : locator, label);
    console.log(`REHEARSAL OK: ${label}`);
    return true;
  } catch {
    console.log(`REHEARSAL FAIL: ${label}`);
    return false;
  }
}

async function login(page, enterprise) {
  await page.goto(`${BASE_URL}/aia`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);
  const loginButton = page.getByRole('button', { name: '登录 / 入驻' });
  if (await loginButton.count()) await moveAndClick(page, loginButton, '打开登录弹窗', 350);
  const inputs = page.locator('input:visible');
  const count = await inputs.count();
  if (count < 2) throw new Error('登录表单未出现');
  await inputs.nth(count - 2).fill(enterprise);
  await inputs.nth(count - 1).fill(PASSWORD);
  await moveAndClick(page, page.getByRole('button', { name: '登录', exact: true }), '提交登录', 1300);
  await page.goto(`${BASE_URL}/aia`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  await injectCursor(page);
  await injectSubtitleBar(page);
}

async function acceptLatestSupplierQuote(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  try {
    await login(page, SUPPLIER);
    const listing = await page.evaluate(async () => (await fetch('/api/intent-quote/seller/list')).json());
    const pending = (listing.quotes || []).find(row => row.status === 'pending' && row.product_name === '广东精密连接器' && Number(row.quantity) === 1000);
    if (!pending) throw new Error('未找到等待供应商回复的演示报价');
    const result = await page.evaluate(async quoteId => {
      const response = await fetch(`/api/intent-quote/${quoteId}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reply_price: 12.8,
          reply_notes: '含税含运费，25天交付，报价有效期7天',
          reply_details: { tax_included: true, tax_rate: 13, delivery_days: 25, moq: 100, mold_fee: 0, freight: 0, payment_terms: '月结30天', valid_until: '7天' },
        }),
      });
      return { status: response.status, body: await response.json() };
    }, pending.id);
    if (result.status !== 200 || result.body.status !== 'accepted') throw new Error(`供应商报价回收失败：${JSON.stringify(result.body)}`);
    console.log(`供应商演示报价已回收：quote #${pending.id}`);
  } finally {
    await context.close();
  }
}

async function getLatestOrder(page) {
  const payload = await page.evaluate(async () => (await fetch('/api/orders?per_page=50&page=1')).json());
  const orders = payload.orders || [];
  return orders.sort((a, b) => Number(b.id || 0) - Number(a.id || 0))[0] || null;
}

async function postSignedFulfillment(orderId, eventType, extra = {}) {
  const payload = { event_id: `chain-xiaoyi-video-${eventType}-${orderId}-${Date.now()}`, enterprise_id: 33, order_id: orderId, event_type: eventType, ...extra };
  const raw = JSON.stringify(payload);
  const signature = createHmac('sha256', FULFILLMENT_SECRET).update(raw).digest('hex');
  const response = await fetch(`${BASE_URL}/api/chain-xiaoyi/fulfillment-event-callback/erp`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Lianyipei-Signature': signature }, body: raw,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(`履约回写失败：${JSON.stringify(body)}`);
  return body;
}

async function runFlow(page, browser) {
  await showSubtitle(page, '链易配 · 文件即任务采购 Agent', 1400);
  await moveAndClick(page, page.getByRole('button', { name: '新建会话' }), '新建采购会话', 500);

  await showSubtitle(page, 'Step 1 · 上传采购文件，自动生成采购任务', 900);
  const fileInput = page.locator('input[type=file]');
  // The native file input is intentionally hidden by the UI. Validate the
  // visible trigger, then use Playwright's setInputFiles to perform the upload
  // without relying on an OS file picker.
  await ensureVisible(page, page.getByRole('button', { name: '上传采购材料' }), '采购材料上传入口');
  await fileInput.setInputFiles(MATERIAL);
  await page.waitForTimeout(2600);
  await ensureVisible(page, page.getByText(/材料已解析为 1 个采购项/), '材料解析成功提示');
  await page.evaluate(() => document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' }));
  await sleep(1200);

  await showSubtitle(page, 'Step 2 · 一句话补充条件，匹配广东授权工厂', 900);
  await moveAndClick(page, page.getByRole('button', { name: '新建会话' }), '进入自然语言采购会话', 350);
  const prompt = '找广东精密连接器，采购1000件，30天交付，并准备询价';
  await typeSlowly(page, page.locator('textarea:visible'), prompt, '自然语言采购需求');
  await page.locator('textarea:visible').press('Enter');
  await page.waitForTimeout(2400);
  await ensureVisible(page, page.getByText(/1 家候选工厂/), '候选工厂结果');
  await page.evaluate(() => document.querySelector('aside:last-of-type')?.scrollTo({ top: 0, behavior: 'smooth' }));
  await sleep(1500);

  await showSubtitle(page, 'Step 3 · 审批前查看供应商范围与披露字段', 1000);
  await moveAndClick(page, page.getByRole('button', { name: '生成询价发送预览' }), '生成询价发送预览', 1000);
  await ensureVisible(page, page.getByText(/将触达 1 家供应商/), '询价审批预览卡');
  await sleep(1700);
  await moveAndClick(page, page.getByRole('button', { name: '确认并发送' }), '一次确认并发送询价', 1500);
  await ensureVisible(page, page.getByText(/询价已发送给 1 家供应商/), '询价发送结果');

  await showSubtitle(page, 'Step 4 · 回收供应商结构化报价', 1100);
  await acceptLatestSupplierQuote(browser);
  await page.bringToFront();
  await moveAndClick(page, page.getByRole('button', { name: '刷新状态' }), '刷新报价状态', 1100);
  await ensureVisible(page, page.getByText(/¥12\.8\/件/), '供应商报价汇总');
  await sleep(1300);

  await showSubtitle(page, 'Step 5 · 用一句话筛选报价并推荐选厂', 900);
  const filter = page.locator('input[placeholder*="只看含税价最低"]:visible');
  await typeSlowly(page, filter, '只看含税价最低且30天内能交付的一家', '一句话报价筛选', 28);
  await moveAndClick(page, page.getByRole('button', { name: '筛选' }), '执行报价筛选', 1200);
  await ensureVisible(page, page.getByText(/推荐：链易配演示·深圳精密连接器厂/), '选厂推荐结果');
  await sleep(1000);

  await showSubtitle(page, 'Step 6 · 生成订单草稿，保留人工确认边界', 900);
  await moveAndClick(page, page.getByRole('button', { name: '生成订单草稿' }), '生成订单草稿', 1000);
  await ensureVisible(page, page.getByText(/订单草稿已生成/), '订单草稿');
  page.on('dialog', dialog => { console.log(`自动确认浏览器提示：${dialog.message()}`); void dialog.accept(); });
  await moveAndClick(page, page.getByRole('button', { name: '人工确认并创建正式订单' }), '确认创建正式订单', 1400);
  await ensureVisible(page, page.getByText(/正式订单 .* 已创建/), '正式订单创建结果');

  await showSubtitle(page, 'Step 7 · 合同与付款分别确认', 900);
  await moveAndClick(page, page.getByRole('button', { name: '确认合同' }), '确认合同', 900);
  await moveAndClick(page, page.getByRole('button', { name: '确认付款' }), '确认付款', 1100);
  await ensureVisible(page, page.getByText(/合同已确认/), '合同确认结果');
  await ensureVisible(page, page.getByText(/付款已确认/), '付款确认结果');

  const order = await getLatestOrder(page);
  if (!order?.id) throw new Error('未找到刚创建的正式订单');
  await postSignedFulfillment(Number(order.id), 'shipment_dispatched', { tracking_no: 'SF-DEMO-001' });
  await postSignedFulfillment(Number(order.id), 'delivery_confirmed');

  await showSubtitle(page, 'Step 8 · ERP 履约回写完成', 1000);
  await page.goto(`${BASE_URL}/fulfillment`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2200);
  await injectCursor(page); await injectSubtitleBar(page);
  await ensureVisible(page, page.getByText(/履约可信度看板/), '履约看板');
  await page.evaluate(() => window.scrollTo({ top: 260, behavior: 'smooth' }));
  await sleep(1800);

  await showSubtitle(page, '其他能力 · 订单工作流与企业看板', 900);
  await page.goto(`${BASE_URL}/orders`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);
  await injectCursor(page); await injectSubtitleBar(page);
  await ensureVisible(page, page.getByText(/订单工作流/), '订单工作流');
  await sleep(1300);
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);
  await injectCursor(page); await injectSubtitleBar(page);
  await ensureVisible(page, page.getByText(/企业看板/), '企业看板');
  await sleep(1800);
  await showSubtitle(page, '', 300);
}

async function rehearsal() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  try {
    await login(page, BUYER);
    const selectors = [
      [page.getByRole('button', { name: '新建会话' }), '新建会话'],
      [page.getByRole('button', { name: '上传采购材料' }), '采购材料上传入口'],
      [page.locator('textarea:visible'), '自然语言输入框'],
    ];
    let ok = true;
    for (const [locator, label] of selectors) ok = await ensureVisible(page, locator, label) && ok;
    if (!ok) throw new Error('排练失败：基础选择器未通过');
    console.log('REHEARSAL PASSED - 基础录制入口均已确认');
  } finally {
    await context.close();
    await browser.close();
  }
}

async function record() {
  fs.mkdirSync(VIDEO_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 720 } }, viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  try {
    await login(page, BUYER);
    await runFlow(page, browser);
  } catch (error) {
    console.error('DEMO ERROR:', error);
    await page.screenshot({ path: '/Users/fujimiyakaori/Documents/ChatGPT/lypdemo/tmp/chain-xiaoyi-demo-error.png', fullPage: false }).catch(() => {});
    throw error;
  } finally {
    const video = page.video();
    await context.close();
    if (video) {
      const source = await video.path();
      fs.copyFileSync(source, OUTPUT);
      console.log(`VIDEO_SAVED=${OUTPUT}`);
      console.log(`VIDEO_SOURCE=${source}`);
    }
    await browser.close();
  }
}

if (REHEARSE) await rehearsal();
else await record();
