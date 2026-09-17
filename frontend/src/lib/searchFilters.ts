import { BadgeCheck, Globe2, Leaf, Users, type LucideIcon } from 'lucide-react';

export type PublicResourceType = 'all' | 'enterprise' | 'product' | 'supply' | 'demand';

export type SearchQuickFilters = {
  is_export: boolean;
  has_decision_maker: boolean;
  is_little_giant: boolean;
  is_green_factory: boolean;
};

export const EMPTY_SEARCH_QUICK_FILTERS: SearchQuickFilters = {
  is_export: false,
  has_decision_maker: false,
  is_little_giant: false,
  is_green_factory: false,
};

export const QUICK_FILTERS: Array<{
  key: keyof SearchQuickFilters;
  label: string;
  icon: LucideIcon;
}> = [
  { key: 'is_export', label: '可出口', icon: Globe2 },
  { key: 'has_decision_maker', label: '有决策人联系方式', icon: Users },
  { key: 'is_little_giant', label: '专精特新', icon: BadgeCheck },
  { key: 'is_green_factory', label: '绿色工厂', icon: Leaf },
];

export const RESOURCE_TYPE_LABELS: Record<PublicResourceType, string> = {
  all: '全部资源',
  enterprise: '工厂',
  product: '产品',
  supply: '供应信息',
  demand: '采购需求',
};

export function readQuickFilters(params: URLSearchParams): SearchQuickFilters {
  return QUICK_FILTERS.reduce((filters, { key }) => {
    filters[key] = params.get(key) === '1';
    return filters;
  }, { ...EMPTY_SEARCH_QUICK_FILTERS });
}

export function writeQuickFilters(params: URLSearchParams, filters: SearchQuickFilters) {
  QUICK_FILTERS.forEach(({ key }) => {
    if (filters[key]) params.set(key, '1');
    else params.delete(key);
  });
}

export function hasActiveQuickFilters(filters: SearchQuickFilters) {
  return Object.values(filters).some(Boolean);
}
