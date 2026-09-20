import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { homepageLinks } from '../src/indisea/homepageLinks';
import { customerLogos } from '../src/indisea/homepageContent';

assert.equal(homepageLinks.length, 4, 'Homepage menu should expose four configured destinations');
assert.equal(homepageLinks[0].href, '/indisea/', '首页导航应回到独立首页');
assert.ok(homepageLinks.every((link) => link.href.length > 0), 'Every homepage link must have a destination');

const appSource = readFileSync(resolve(process.cwd(), 'src/indisea/App.tsx'), 'utf8');
const publicHeaderSource = readFileSync(resolve(process.cwd(), 'src/components/PublicSiteHeader.tsx'), 'utf8');
const mainRouterSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
const standaloneEntrySource = readFileSync(resolve(process.cwd(), 'src/indisea/main.tsx'), 'utf8');
assert.ok(appSource.includes('<HomePage />'), 'Standalone entry should render the homepage');
assert.ok(publicHeaderSource.includes('to="/indisea/"'), '公共导航首页应进入 Indisea 首页');
assert.ok(publicHeaderSource.includes('to="/search"'), '公共导航应保留筛选工厂入口');
assert.ok(publicHeaderSource.includes('href="/aisearch/"'), '公共导航 AI 找工厂应进入 AI 搜索主页');
assert.ok(publicHeaderSource.includes('筛选工厂'), '公共导航应显示筛选工厂');
assert.ok(appSource.includes('<PublicSiteHeader'), 'Indisea homepage should reuse the main public navigation');
assert.ok(mainRouterSource.includes('path="/indisea/*"'), 'Main router should own the Indisea homepage route');
assert.ok(mainRouterSource.includes('Navigate to="/indisea/" replace'), 'Unauthenticated root visits should redirect to Indisea home');
assert.ok(mainRouterSource.includes('path="/aisearch/*"'), 'AI search home should be available at /aisearch/');
assert.ok(mainRouterSource.includes('path="/indesea/*"'), 'Misspelled Indisea alias should resolve to the canonical route');
assert.ok(standaloneEntrySource.includes('<AuthProvider>'), 'Standalone Indisea entry should provide auth context for the shared navigation');
assert.ok(standaloneEntrySource.includes("'../index.css'"), 'Standalone Indisea entry should load the main site styles for shared navigation');
assert.ok(!appSource.includes('AboutPage'), 'Standalone entry should not require a separate About page');
assert.ok(!appSource.includes("from './pages'"), 'Standalone entry must not load the legacy multi-page draft');

for (const file of ['indisea/index.html', 'src/indisea/main.tsx', 'src/indisea/HomePage.tsx', 'src/indisea/SiteChrome.tsx', 'src/indisea/ScrollSpine.tsx', 'src/indisea/CustomCursor.tsx', 'src/indisea/HomepageMotion.tsx', 'src/indisea/homepage.css']) {
  assert.ok(existsSync(resolve(process.cwd(), file)), `Missing standalone Indisea entry file: ${file}`);
}

const spineSource = existsSync(resolve(process.cwd(), 'src/indisea/ScrollSpine.tsx'))
  ? readFileSync(resolve(process.cwd(), 'src/indisea/ScrollSpine.tsx'), 'utf8')
  : '';
assert.ok(spineSource.includes('strokeDasharray'), 'Scroll spine must measure its path length');
assert.ok(spineSource.includes('strokeDashoffset'), 'Scroll spine must draw progressively with scrolling');
assert.ok(spineSource.includes('data-spine-end'), 'Scroll spine must expose the final hollow terminal');
assert.ok(spineSource.includes('ResizeObserver'), 'Scroll spine must rebuild when the page layout changes');
assert.ok(spineSource.includes('fraction(0.84)'), '首屏蓝环必须定位在桌面标题右侧安全区');

const cursorSource = existsSync(resolve(process.cwd(), 'src/indisea/CustomCursor.tsx'))
  ? readFileSync(resolve(process.cwd(), 'src/indisea/CustomCursor.tsx'), 'utf8')
  : '';
assert.ok(cursorSource.includes('pointermove'), 'Custom cursor must track pointer movement');
assert.ok(cursorSource.includes('(pointer: fine)'), 'Custom cursor must only run for precise pointing devices');
assert.ok(cursorSource.includes('elementsFromPoint'), 'Custom cursor must detect the surface beneath it');

assert.ok(appSource.includes('<CustomCursor />'), 'Standalone entry should mount the custom cursor once');
assert.ok(appSource.includes('<HomepageMotion'), 'Standalone entry should mount the homepage motion controller once');
assert.ok(appSource.includes('data-loader-count'), 'Loader should expose its animated count');

const homeSource = readFileSync(resolve(process.cwd(), 'src/indisea/HomePage.tsx'), 'utf8').toLowerCase();
const styleSource = readFileSync(resolve(process.cwd(), 'src/indisea/homepage.css'), 'utf8');
assert.ok(homeSource.includes('<scrollspine />'), 'Homepage should mount one continuous scroll spine');
assert.ok(!homeSource.includes('<heroline />'), 'Homepage should not keep the old static hero line');
assert.ok(!homeSource.includes('<bridgeline />'), 'Homepage should not keep the old static bridge line');
assert.ok(!homeSource.includes('indisea-who__rail'), 'Who section should not keep the obsolete static-line rail');
assert.ok(homeSource.includes('indisea-benefit__number'), 'Benefits should render circular number badges');
assert.ok(homeSource.includes('data-count-target'), 'Homepage statistics should expose count-up targets');
assert.ok(homeSource.includes('data-draw-path'), 'Connection diagram should expose animated paths');
assert.ok(homeSource.includes('data-cta-line'), 'Final CTA should expose staggered reveal lines');
assert.ok(homeSource.includes('indisea-hero__verbs'), '首屏三个动词必须使用独立排版容器');
assert.ok(homeSource.includes('indisea-hero__cta'), '首屏进入平台按钮必须使用独立放大样式');
assert.ok(styleSource.includes('.indisea-hero h1 mark.is-active { color:var(--ind-charcoal); background:var(--ind-yellow); }'), '首屏激活动词必须使用整块黄色底色');
assert.ok(!homeSource.includes('className="is-light"'), 'Blue CTA should use the dark reference button');
assert.ok(styleSource.includes('.indisea-page > .indisea-problem-story > .indisea-problem-story__sticky { position:sticky; }'), 'Problem story must remain sticky while its staged text and detail line reveal');
assert.ok(styleSource.includes('.indisea-page > .indisea-reasons > .indisea-reason { position:sticky; }'), 'Reasons cards must remain sticky so their offsets overlap');

const chromeSource = readFileSync(resolve(process.cwd(), 'src/indisea/SiteChrome.tsx'), 'utf8');
assert.ok(chromeSource.includes('indisea-footer__brand'), 'Footer should restore its logo and statement block');
assert.ok(chromeSource.includes('公开页面展示脱敏摘要'), '页脚应说明公开数据边界');
assert.ok(chromeSource.indexOf('indisea-footer__top') < chromeSource.indexOf('wordmark />'), 'Footer grid should appear before the large wordmark');
assert.ok(chromeSource.includes('lianyipei-logo.png'), 'Indisea brand should use the cropped 链易配 PNG logo');
for (const section of ['01 / 英雄', '02 / 十二项协同能力', '03 / 我们是谁', '04 / 当前难题', '05 / 链易配如何连接', '07 / 为什么需要链易配', '08 / 你能得到什么', '09 / 为谁而建', '10 / 协同依据', '11 / 开始协同']) {
  assert.ok(homeSource.includes(section), `Missing homepage section: ${section}`);
}

assert.equal(customerLogos.length, 21, '第 02 段必须展示用户提供的全部二十一个企业图标');
assert.ok(customerLogos.every((item) => item.asset.startsWith('/indisea/customer-logos/')), '企业图标必须从本地静态目录加载');
assert.ok(homeSource.includes('customerlogos'), '第 02 段必须实际渲染企业图标数据');
assert.ok(homeSource.includes('indisea-logo-card__image'), '企业图标卡必须渲染图片元素');
assert.ok(styleSource.includes('.indisea-logo-card__image'), '企业图标卡必须为图片保留统一样式');
assert.ok(styleSource.includes('min-height:clamp(480px,36vw,620px)'), '第 05 段桌面流程图必须限制在可完整显示的高度');
assert.ok(styleSource.includes('.indisea-diagram__targets { position:absolute; top:6%; right:5%; bottom:6%;'), '第 05 段流程图节点必须给底部标签留出空间');
for (const logo of customerLogos) {
  assert.ok(existsSync(resolve(process.cwd(), `public${logo.asset}`)), `Missing local customer logo: ${logo.asset}`);
}

for (const asset of ['logo/Indisea-Logo-Primary.svg', 'logo/Indisea-Logo-Primary-Alt.svg', 'logo/Indisea-Wordmark-Black.svg', 'fonts/IBMPlexSans-SemiBold.woff']) {
  assert.ok(existsSync(resolve(process.cwd(), 'public/indisea', asset)), `Missing local homepage asset: ${asset}`);
}
assert.ok(existsSync(resolve(process.cwd(), 'public/lianyipei-logo.png')), 'Missing cropped 链易配 PNG logo');

console.log('Indisea homepage contract passed (single entry, ten sections, twenty-one local customer logos)');
