#!/usr/bin/env node
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(path.resolve(process.cwd(), 'frontend/package.json'));
const { chromium } = require('@playwright/test');

const BASE_URL = process.env.QA_BASE_URL || 'http://127.0.0.1:3000';
const OUTPUT_DIR = path.resolve(process.env.DEMO_OUTPUT_DIR || 'demo-recordings');
const WIDTH = 1280;
const HEIGHT = 720;
const REHEARSAL = process.argv.includes('--rehearse');
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function injectCursor(page) {
  await page.evaluate(() => {
    document.getElementById('demo-cursor')?.remove();
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    cursor.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    cursor.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;width:24px;height:24px;transition:left .1s,top .1s;filter:drop-shadow(1px 1px 2px rgba(0,0,0,.35));left:0;top:0;';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', (event) => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
    }, { passive: true });
  });
}

async function injectSubtitleBar(page) {
  await page.evaluate(() => {
    document.getElementById('demo-subtitle')?.remove();
    const bar = document.createElement('div');
    bar.id = 'demo-subtitle';
    bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:999998;text-align:center;padding:11px 24px;background:rgba(0,0,0,.76);color:white;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:16px;font-weight:500;letter-spacing:.3px;pointer-events:none;min-height:22px;';
    document.body.appendChild(bar);
  });
}

async function subtitle(page, text) {
  await page.evaluate((value) => {
    const bar = document.getElementById('demo-subtitle');
    if (bar) bar.textContent = value;
  }, text);
  await delay(text ? 850 : 350);
}

async function prepare(page, label) {
  await page.waitForLoadState('domcontentloaded').catch(() => {});
  await delay(700);
  await injectCursor(page);
  await injectSubtitleBar(page);
  await subtitle(page, label);
}

async function visit(page, label, route, options = {}) {
  await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' });
  await prepare(page, label);
  const headings = await page.locator('h1,h2,h3').evaluateAll((els) => els.filter((el) => el.offsetParent !== null).slice(0, 5).map((el) => el.textContent?.trim()).filter(Boolean));
  console.log(`VISIT ${route} :: ${headings.join(' | ')}`);
  if (options.scroll) {
    for (const position of options.scroll) {
      await page.evaluate((top) => window.scrollTo({ top, behavior: 'smooth' }), position);
      await delay(750);
    }
  }
  if (options.pan) {
    const elements = await page.locator(options.pan).all();
    for (const element of elements.slice(0, 6)) {
      const box = await element.boundingBox().catch(() => null);
      if (box && box.y < HEIGHT - 40) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 8 });
        await delay(300);
      }
    }
  }
  await delay(options.pause || 900);
}

async function login(page, name, password, label) {
  await page.goto(`${BASE_URL}/`);
  await prepare(page, label);
  const trigger = page.getByRole('button', { name: '登录 / 入驻' });
  await trigger.click();
  await page.locator('input[autocomplete="username"]:visible').last().fill(name);
  await page.locator('input[autocomplete="current-password"]:visible').last().fill(password);
  await page.getByRole('button', { name: '登录', exact: true }).last().click();
  await page.waitForTimeout(1200);
  const session = await page.evaluate(() => fetch('/api/session').then((response) => response.json()));
  if (!session.authenticated) throw new Error(`Login failed for ${name}`);
  await injectCursor(page);
  await injectSubtitleBar(page);
  console.log(`LOGIN ${name} -> ${page.url()}`);
}

async function recordSegment(name, build) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    ...(REHEARSAL ? {} : { recordVideo: { dir: OUTPUT_DIR, size: { width: WIDTH, height: HEIGHT } } }),
  });
  const page = await context.newPage();
  try {
    await build(page);
    await subtitle(page, '演示结束');
    await delay(2200);
  } finally {
    const video = page.video();
    await context.close();
    if (video && !REHEARSAL) {
      const source = await video.path();
      const target = path.join(OUTPUT_DIR, `${name}.webm`);
      fs.copyFileSync(source, target);
      console.log(`VIDEO ${target}`);
    }
    await browser.close();
  }
}

async function publicSegment(page) {
  await visit(page, '公开平台 · 首页总览', '/', { pan: 'h1,h2,button', scroll: [350, 850] });
  await visit(page, '公开平台 · Indisea 首页与主导航', '/indisea/', { scroll: [500, 1200, 2100, 3200] });
  await visit(page, '公开平台 · 工厂搜索', '/search', { pan: 'input,button', pause: 700 });
  const searchInput = page.getByTestId('public-search-input');
  if (await searchInput.isVisible().catch(() => false)) {
    await searchInput.fill('工业电机');
    await page.getByTestId('public-search-submit').click();
    await delay(1200);
  }
  await visit(page, '公开平台 · AI 找工厂', '/aia', { pan: 'textarea,button', pause: 700 });
  const prompt = page.locator('textarea:visible').first();
  if (await prompt.isVisible().catch(() => false)) {
    await prompt.pressSequentially('找华东能做精密注塑、支持出口的工厂', { delay: 22 });
    await delay(900);
  }
  await visit(page, '公开平台 · 行业资讯', '/industry-news', { pan: 'button,a', pause: 700 });
  const newsSearch = page.locator('input[placeholder*="搜索政策"]');
  if (await newsSearch.isVisible().catch(() => false)) {
    await newsSearch.fill('供应链');
    await delay(700);
  }
  await visit(page, '公开平台 · AI 能力市场', '/agent-market', { pan: 'button,a', pause: 700 });
  await visit(page, '公开平台 · 企业名录', '/enterprise-directory', { pan: 'input,select,button', pause: 700 });
  const detailButton = page.getByRole('button', { name: '查看详情' }).first();
  if (await detailButton.isVisible().catch(() => false)) {
    await detailButton.click();
    await prepare(page, '公开平台 · 企业详情');
    await delay(900);
  }
  await visit(page, '公开平台 · 资讯详情', '/industry-news', { pause: 500 });
  const article = page.locator('main a[href*="/industry-news/"]').first();
  if (await article.isVisible().catch(() => false)) await article.click();
  await delay(1100);
}

async function enterpriseSegment(page) {
  await login(page, '长沙德远智造科技有限公司', 'demo123456', '买方演示企业 · 登录');
  const pages = [
    ['/dashboard', '企业端 · 经营看板'],
    ['/matching', '企业端 · 供需匹配'],
    ['/workspace/enterprise-directory', '企业端 · 名录筛选'],
    ['/group-purchase', '企业端 · 集采拼单'],
    ['/fulfillment', '企业端 · 履约看板'],
    ['/capacity-calendar', '企业端 · 产能日历'],
    ['/orders', '企业端 · 订单工作流'],
    ['/assets', '企业端 · 资产管理'],
    ['/settings', '企业端 · 设置'],
    ['/sales-console', '企业端 · 销售控制台'],
    ['/risk', '企业端 · 风险预警'],
    ['/alert-workflow', '企业端 · 预警工作流'],
    ['/quote-pool', '企业端 · 报价池'],
  ];
  for (const [route, label] of pages) await visit(page, label, route, { pan: 'h1,h2,button,a', pause: 650 });
}

async function sellerSegment(page) {
  await login(page, '湖南星瀚精密制造有限公司', 'seller123456', '卖方演示企业 · 登录');
  const pages = [
    ['/sales-console', '卖方演示企业 · 销售协同'],
    ['/orders', '卖方演示企业 · 订单工作流'],
    ['/fulfillment', '卖方演示企业 · 履约看板'],
    ['/quote-pool', '卖方演示企业 · 报价池'],
  ];
  for (const [route, label] of pages) await visit(page, label, route, { pan: 'h1,h2,button,a', pause: 650 });
}

async function governmentSegment(page) {
  await login(page, '成都市产业链协同专班', '123456', '政府端 · 登录');
  const pages = [
    ['/gov', '政府端 · 监管首页'],
    ['/gov/screen', '政府端 · 数字大屏'],
    ['/gov/labels', '政府端 · 质量标签'],
    ['/gov/alerts', '政府端 · 预警中心'],
    ['/gov/supply-chain', '政府端 · 产业链图谱'],
    ['/gov/recruitment', '政府端 · 招商决策'],
  ];
  for (const [route, label] of pages) await visit(page, label, route, { pan: 'h1,h2,button,a', pause: 750 });
}

async function adminSegment(page) {
  await login(page, 'admin', 'admin', '管理员端 · 登录');
  const pages = [
    ['/admin/dashboard', '管理员端 · 管理首页'],
    ['/admin/dashboard/overview', '管理员端 · 控制台大屏'],
    ['/admin/dashboard/onboarding', '管理员端 · 入驻审核'],
    ['/admin/dashboard/rules', '管理员端 · 规则配置'],
    ['/admin/dashboard/risk', '管理员端 · 风控中心'],
    ['/admin/dashboard/api-management', '管理员端 · API 管理'],
    ['/admin/dashboard/audit', '管理员端 · 审计日志'],
    ['/admin/dashboard/news', '管理员端 · 行业资讯管理'],
  ];
  for (const [route, label] of pages) await visit(page, label, route, { pan: 'h1,h2,button,a', pause: 750 });
}

const segments = process.argv.slice(2).filter((argument) => !argument.startsWith('--'));
const requested = segments.length ? segments : ['public', 'enterprise', 'seller', 'government', 'admin'];
const jobs = {
  public: ['01-public-platform', publicSegment],
  enterprise: ['02-enterprise-platform', enterpriseSegment],
  seller: ['03-seller-demo-platform', sellerSegment],
  government: ['04-government-platform', governmentSegment],
  admin: ['05-admin-platform', adminSegment],
};

const manifest = [];
for (const key of requested) {
  if (!jobs[key]) throw new Error(`Unknown segment: ${key}`);
  const [name, builder] = jobs[key];
  await recordSegment(name, builder);
  manifest.push({ segment: key, file: `${name}.webm` });
}
fs.writeFileSync(path.join(OUTPUT_DIR, 'manifest.json'), JSON.stringify({ baseUrl: BASE_URL, recordedAt: new Date().toISOString(), segments: manifest }, null, 2));
console.log(`MANIFEST ${path.join(OUTPUT_DIR, 'manifest.json')}`);
