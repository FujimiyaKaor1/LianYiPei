import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(process.cwd(), 'src/pages/PublicHome.tsx'), 'utf8');

const requiredMarkers = [
  '关键词搜索',
  'AI 找工厂',
  'AI 智能体',
  '硬筛选',
  'api.fetchPublicHome',
  'api.searchPublicResources',
  'data-testid="public-home-search"',
];

const missingMarkers = requiredMarkers.filter((marker) => !source.includes(marker));
if (missingMarkers.length > 0) {
  throw new Error(`PublicHome contract missing: ${missingMarkers.join(', ')}`);
}

console.log(`PublicHome contract passed (${requiredMarkers.length} markers)`);
