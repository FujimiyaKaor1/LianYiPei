export type HomepageLink = {
  label: string;
  href: string;
  kind: 'home' | 'external';
};

// 其他页面尚未接入链易配。后续只需在这里替换目标，不改首页组件和视觉结构。
export const homepageLinks: HomepageLink[] = [
  { label: '首页', href: '/indisea/', kind: 'home' },
  { label: '公开找厂', href: '/search', kind: 'home' },
  { label: 'AI 找工厂', href: '/aia', kind: 'home' },
  { label: 'AI 能力市场', href: '/agent-market', kind: 'home' },
];

export const companyLinks: HomepageLink[] = [
  { label: '企业入驻', href: '/', kind: 'home' },
  { label: '查找企业', href: '/search', kind: 'home' },
  { label: '供需协同', href: '/matching', kind: 'home' },
];
