import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

function read(path: string) {
  return readFileSync(resolve(root, path), 'utf8');
}

function assertIncludes(file: string, needle: string, label: string) {
  const source = read(file);
  if (!source.includes(needle)) {
    throw new Error(`${label}: missing ${needle} in ${file}`);
  }
}

function assertPattern(file: string, pattern: RegExp, label: string) {
  const source = read(file);
  if (!pattern.test(source)) {
    throw new Error(`${label}: pattern ${pattern} not found in ${file}`);
  }
}

const page = 'src/pages/gov/GovDigitalScreen.tsx';

[
  '政府产业监管数字化大屏',
  'ECHARTS-DEMO CONFIG',
  'mainbox',
  'className="no"',
  'className="map1"',
  'className="map2"',
  'className="map3"',
  '柱形图-供需趋势',
  '折线图-风险等级',
  '饼形图-处置闭环',
  '柱形图-活跃预警',
  '折线图-补链强链缺口',
  '饼形图-地区分布',
  'api.fetchEnterpriseDirectory({ limit: 200 })',
].forEach((needle) => assertIncludes(page, needle, 'GovDigitalScreen structure'));

assertPattern('src/App.tsx', /path="\/gov\/screen"[\s\S]*<GovDigitalScreen \/>/, 'route registration');
assertIncludes('src/components/GovSidebar.tsx', "label: '数字大屏', path: '/gov/screen'", 'sidebar navigation');
assertIncludes('src/pages/gov/GovDashboard.tsx', "label: '数字大屏'", 'dashboard shortcut');
assertIncludes('src/index.css', '.gov-digital-screen .mainbox', 'screen layout styles');
assertIncludes('src/index.css', '@keyframes gov-screen-rotate', 'screen map rotation styles');

console.log('Gov digital screen structure checks passed');
