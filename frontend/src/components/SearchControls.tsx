import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  QUICK_FILTERS,
  RESOURCE_TYPE_LABELS,
  type PublicResourceType,
  type SearchQuickFilters,
} from '@/src/lib/searchFilters';
import { cn } from '@/src/lib/utils';

export function QuickFilterChips({
  filters,
  onToggle,
  compact = false,
}: {
  filters: SearchQuickFilters;
  onToggle: (key: keyof SearchQuickFilters) => void;
  compact?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="quick-filters">
      <span className="mr-1 py-1 text-xs font-bold text-public-muted">快速筛选</span>
      {QUICK_FILTERS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          aria-pressed={filters[key]}
          onClick={() => onToggle(key)}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-md border font-semibold transition',
            compact ? 'px-2 py-1.5 text-[11px]' : 'px-3 py-2 text-xs',
            filters[key]
              ? 'border-public-brand bg-public-brand-soft text-public-brand'
              : 'border-public-border text-public-muted hover:border-public-brand hover:text-public-brand',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}

export function ResourceTypeTabs({
  value,
  onChange,
}: {
  value: PublicResourceType;
  onChange: (value: PublicResourceType) => void;
}) {
  return (
    <div className="flex max-w-full overflow-x-auto rounded-md border border-public-border bg-white p-1" role="tablist" aria-label="资源类型">
      {(Object.keys(RESOURCE_TYPE_LABELS) as PublicResourceType[]).map((type) => (
        <button
          key={type}
          type="button"
          role="tab"
          aria-selected={value === type}
          onClick={() => onChange(type)}
          className={cn(
            'shrink-0 rounded px-3 py-1.5 text-xs font-bold transition',
            value === type ? 'bg-public-brand-soft text-public-brand' : 'text-public-muted hover:text-public-brand',
          )}
        >
          {RESOURCE_TYPE_LABELS[type]}
        </button>
      ))}
    </div>
  );
}

export function SearchPagination({
  page,
  pages,
  onChange,
}: {
  page: number;
  pages: number;
  onChange: (page: number) => void;
}) {
  if (pages <= 1) return null;
  const count = Math.min(5, pages);
  const start = Math.max(1, Math.min(page - 2, pages - count + 1));
  const pageButtons = Array.from({ length: count }, (_, index) => start + index);

  return (
    <nav className="mt-5 flex flex-wrap items-center justify-center gap-2" aria-label="搜索结果分页">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        aria-label="上一页"
        className="inline-flex h-9 items-center gap-1 rounded-md border border-public-border bg-white px-3 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand disabled:cursor-not-allowed disabled:opacity-40"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">上一页</span>
      </button>
      {pageButtons.map((pageNumber) => (
        <button
          key={pageNumber}
          type="button"
          aria-current={pageNumber === page ? 'page' : undefined}
          onClick={() => onChange(pageNumber)}
          className={cn(
            'h-9 w-9 rounded-md text-xs font-bold transition',
            pageNumber === page
              ? 'bg-public-brand text-white'
              : 'border border-public-border bg-white text-public-muted hover:border-public-brand hover:text-public-brand',
          )}
        >
          {pageNumber}
        </button>
      ))}
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
        aria-label="下一页"
        className="inline-flex h-9 items-center gap-1 rounded-md border border-public-border bg-white px-3 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand disabled:cursor-not-allowed disabled:opacity-40"
      >
        <span className="hidden sm:inline">下一页</span>
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </nav>
  );
}
