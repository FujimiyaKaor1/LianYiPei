import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BadgeCheck, Building2, Factory, Filter, Globe2, Leaf, Loader2, MapPin, Search, ShieldCheck, SlidersHorizontal, X } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';
import { QuickFilterChips, ResourceTypeTabs, SearchPagination } from '@/src/components/SearchControls';
import { useAuth } from '@/src/context/AuthContext';
import { EMPTY_SEARCH_QUICK_FILTERS, hasActiveQuickFilters, readQuickFilters, RESOURCE_TYPE_LABELS, type PublicResourceType, type SearchQuickFilters, writeQuickFilters } from '@/src/lib/searchFilters';
import { cn } from '@/src/lib/utils';
import { api, type PublicResourceItem } from '@/src/services/api';

function formatDate(value?: string | null) {
  if (!value) return '待更新';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat('zh-CN').format(date);
}

type SearchState = {
  query: string;
  province: string;
  city: string;
  industry: string;
  type: PublicResourceType;
  sort: 'relevance' | 'name';
  companyStatus: string;
  minCapital: string;
  quickFilters: SearchQuickFilters;
};

const VALID_TYPES: PublicResourceType[] = ['all', 'enterprise', 'product', 'supply', 'demand'];

function stateFromParams(params: URLSearchParams): SearchState {
  const type = params.get('type') as PublicResourceType;
  return {
    query: params.get('q') || '', province: params.get('province') || '', city: params.get('city') || '', industry: params.get('industry') || '',
    type: VALID_TYPES.includes(type) ? type : 'all', sort: params.get('sort') === 'name' ? 'name' : 'relevance', companyStatus: params.get('company_status') || '',
    minCapital: params.get('min_registered_capital') || '', quickFilters: readQuickFilters(params),
  };
}

function paramsFromState(state: SearchState, page = 1) {
  const params = new URLSearchParams();
  if (state.query.trim()) params.set('q', state.query.trim());
  if (state.province) params.set('province', state.province);
  if (state.city.trim()) params.set('city', state.city.trim());
  if (state.industry) params.set('industry', state.industry);
  if (state.type !== 'all') params.set('type', state.type);
  if (state.sort !== 'relevance') params.set('sort', state.sort);
  if (state.companyStatus) params.set('company_status', state.companyStatus);
  if (state.minCapital) params.set('min_registered_capital', state.minCapital);
  writeQuickFilters(params, state.quickFilters);
  if (page > 1) params.set('page', String(page));
  return params;
}

function ResultRow({ item, onOpen, onLogin }: { key?: string; item: PublicResourceItem; onOpen: () => void; onLogin: () => void }) {
  const signals = item.public_signals;
  return <article data-testid="public-search-result" className="group border-b border-public-border/70 bg-white px-4 py-5 transition last:border-b-0 hover:bg-public-bg/50 md:px-6"><div className="flex gap-4"><div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand sm:flex">{item.kind === 'enterprise' ? <Factory className="h-6 w-6" /> : <Building2 className="h-6 w-6" />}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><button type="button" onClick={onOpen} className="max-w-full truncate text-left text-base font-black text-public-text hover:text-public-brand">{item.title}</button><span className="rounded bg-public-brand-soft px-1.5 py-0.5 text-[10px] font-bold text-public-brand">{RESOURCE_TYPE_LABELS[item.kind]}</span>{signals.verification_status === 'approved' && <span className="badge badge-success">已审核</span>}</div><p className="mt-2 text-sm leading-6 text-public-muted">{item.subtitle}</p><div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-public-muted"><span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{item.subtitle.split(' · ').at(-1) || '区域待补充'}</span>{signals.status && <span>{signals.status}</span>}{signals.is_export && <span className="inline-flex items-center gap-1 text-emerald-700"><Globe2 className="h-3.5 w-3.5" />支持出口</span>}{signals.has_decision_maker && <span className="inline-flex items-center gap-1 text-blue-700"><ShieldCheck className="h-3.5 w-3.5" />有决策人联系方式</span>}{signals.is_little_giant && <span className="inline-flex items-center gap-1 text-violet-700"><BadgeCheck className="h-3.5 w-3.5" />专精特新</span>}{signals.is_green_factory && <span className="inline-flex items-center gap-1 text-emerald-700"><Leaf className="h-3.5 w-3.5" />绿色工厂</span>}</div><div className="mt-3 flex flex-wrap gap-1.5">{item.tags.map(tag => <span key={tag} className="badge badge-default">{tag}</span>)}</div><p className="mt-3 text-[11px] text-public-muted">来源：{signals.source || '平台公开档案'} · 更新于 {formatDate(signals.data_updated_at || signals.created_at)}{signals.is_demo ? ' · 演示数据' : ''}</p></div><div className="hidden shrink-0 flex-col items-end gap-3 sm:flex"><button type="button" onClick={onOpen} className="inline-flex items-center gap-1 text-xs font-bold text-public-brand">查看详情 <ArrowRight className="h-3.5 w-3.5" /></button><button type="button" onClick={onLogin} className="rounded-md border border-public-border px-3 py-2 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand">联系 / 询价</button></div></div></article>;
}

function SearchFilterPanel({ state, home, onChange, onApply, onClear, mobileOpen, onClose }: { state: SearchState; home: Awaited<ReturnType<typeof api.fetchPublicHome>> | null; onChange: (patch: Partial<SearchState>) => void; onApply: () => void; onClear: () => void; mobileOpen: boolean; onClose: () => void }) {
  return <><>{mobileOpen && <button type="button" aria-label="关闭筛选" onClick={onClose} className="fixed inset-0 z-40 bg-slate-900/25 lg:hidden" />}</><aside className={cn('border-public-border bg-white p-4 shadow-public lg:sticky lg:top-24 lg:block lg:h-fit lg:rounded-xl lg:border', mobileOpen ? 'fixed inset-y-0 left-0 z-50 block w-[min(88vw,320px)] overflow-y-auto border-r' : 'hidden')}><div className="flex items-center justify-between"><h2 className="text-sm font-black">筛选条件</h2><div className="flex items-center gap-3"><button type="button" onClick={onClear} className="text-xs font-bold text-public-brand">清空</button><button type="button" onClick={onClose} aria-label="关闭筛选" className="text-public-muted lg:hidden"><X className="h-4 w-4" /></button></div></div><div className="mt-5 space-y-5"><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">省份地区</span><select data-testid="province-filter" value={state.province} onChange={event => onChange({ province: event.target.value })} className="input w-full text-sm"><option value="">全部地区</option>{(home?.regions || []).map(region => <option key={region.key} value={region.key}>{region.label}</option>)}</select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">城市</span><input value={state.city} onChange={event => onChange({ city: event.target.value })} placeholder="如：佛山市" className="input w-full text-sm" /></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">行业分类</span><select value={state.industry} onChange={event => onChange({ industry: event.target.value })} className="input w-full text-sm"><option value="">全部行业</option>{(home?.industries || []).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">经营状态</span><select value={state.companyStatus} onChange={event => onChange({ companyStatus: event.target.value })} className="input w-full text-sm"><option value="">全部状态</option><option value="存续">存续</option><option value="在业">在业</option><option value="注销">注销</option></select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">注册资本（万元）</span><input type="number" min="0" value={state.minCapital} onChange={event => onChange({ minCapital: event.target.value })} placeholder="如：1000" className="input w-full text-sm" /></label><button type="button" onClick={onApply} className="btn-public-secondary w-full">应用筛选</button></div></aside></>;
}

export default function PublicSearch() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { requestLogin } = useAuth();
  const [home, setHome] = useState<Awaited<ReturnType<typeof api.fetchPublicHome>> | null>(null);
  const [results, setResults] = useState<Awaited<ReturnType<typeof api.searchPublicResources>> | null>(null);
  const [draft, setDraft] = useState<SearchState>(() => stateFromParams(params));
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const searchKey = params.toString();
  const applied = useMemo(() => stateFromParams(new URLSearchParams(searchKey)), [searchKey]);

  useEffect(() => { setDraft(applied); }, [applied]);
  useEffect(() => { let cancelled = false; void api.fetchPublicHome().then(value => { if (!cancelled) setHome(value); }).catch(() => undefined); return () => { cancelled = true; }; }, []);
  useEffect(() => { let cancelled = false; const page = Math.max(1, Number(new URLSearchParams(searchKey).get('page') || 1)); setLoading(true); setError(null); void api.searchPublicResources({ q: applied.query, type: applied.type, province: applied.province, city: applied.city, industry: applied.industry, sort: applied.sort, company_status: applied.companyStatus, min_registered_capital: applied.minCapital ? Number(applied.minCapital) : undefined, ...applied.quickFilters, page, per_page: 10 }).then(value => { if (!cancelled) setResults(value); }).catch(() => { if (!cancelled) setError('搜索失败，请稍后重试'); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, [applied, retryTick, searchKey]);

  const updateUrl = (next: SearchState, page = 1) => setParams(paramsFromState(next, page));
  const updateDraft = (patch: Partial<SearchState>) => setDraft(current => ({ ...current, ...patch }));
  const toggleQuickFilter = (key: keyof SearchQuickFilters) => { const next = { ...draft, quickFilters: { ...draft.quickFilters, [key]: !draft.quickFilters[key] } }; setDraft(next); updateUrl(next); };
  const clearFilters = () => { const next = { ...draft, province: '', city: '', industry: '', companyStatus: '', minCapital: '', type: 'all' as const, quickFilters: { ...EMPTY_SEARCH_QUICK_FILTERS } }; setDraft(next); updateUrl(next); };
  const openItem = (item: PublicResourceItem) => item.kind === 'enterprise' ? navigate(`/factory/${item.id}`) : navigate(`/matching?query=${encodeURIComponent(item.title)}`);
  const actionPath = (item: PublicResourceItem) => item.kind === 'enterprise' ? `/factory/${item.id}` : item.public_signals.enterprise_id ? `/factory/${item.public_signals.enterprise_id}` : '/search';
  const activeFilterCount = [applied.province, applied.city, applied.industry, applied.companyStatus, applied.minCapital].filter(Boolean).length + (hasActiveQuickFilters(applied.quickFilters) ? 1 : 0);

  return <div className="public-site min-h-screen bg-public-bg text-public-text"><PublicSiteHeader onLogin={() => requestLogin('/dashboard')} /><main className="mx-auto max-w-[1320px] px-4 py-6 md:px-8 md:py-10"><section className="mb-6 rounded-xl border border-public-border bg-white p-4 shadow-public md:p-5"><form data-testid="public-search-form" onSubmit={event => { event.preventDefault(); updateUrl(draft); }} className="flex flex-col gap-3 md:flex-row"><div className="relative flex-1"><Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-public-brand" /><input data-testid="public-search-input" value={draft.query} onChange={event => updateDraft({ query: event.target.value })} placeholder="输入产品、工艺、公司名或统一社会信用代码" className="h-12 w-full rounded-lg border border-public-border bg-public-bg pl-12 pr-4 text-sm outline-none transition focus:border-public-brand focus:bg-white focus:ring-2 focus:ring-public-brand-soft" /></div><button data-testid="public-search-submit" type="submit" className="btn-public-primary h-12 px-7"><Search className="h-4 w-4" />查找工厂 <ArrowRight className="h-4 w-4" /></button></form><div className="mt-4"><QuickFilterChips filters={draft.quickFilters} onToggle={toggleQuickFilter} /></div></section><div className="grid gap-6 lg:grid-cols-[250px_1fr]"><SearchFilterPanel state={draft} home={home} onChange={updateDraft} onApply={() => { updateUrl(draft); setMobileFiltersOpen(false); }} onClear={clearFilters} mobileOpen={mobileFiltersOpen} onClose={() => setMobileFiltersOpen(false)} /><section className="min-w-0"><div className="mb-3 flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow text-public-brand">Factory directory</p><h1 data-testid="public-search-count" className="mt-1 text-2xl font-black">{results ? `找到 ${results.total.toLocaleString('zh-CN')} 条资源` : '搜索制造资源'}</h1><p className="mt-1 text-xs text-public-muted">{activeFilterCount ? `已启用 ${activeFilterCount} 项筛选` : '按产品、工艺、企业和供需信息检索'}</p></div><div className="flex items-center gap-2"><button type="button" onClick={() => setMobileFiltersOpen(true)} className="btn-public-secondary lg:hidden"><SlidersHorizontal className="h-4 w-4" />筛选{activeFilterCount ? ` (${activeFilterCount})` : ''}</button><select aria-label="排序" value={applied.sort} onChange={event => updateUrl({ ...applied, sort: event.target.value as SearchState['sort'] })} className="input h-9 text-xs"><option value="relevance">综合排序</option><option value="name">名称排序</option></select></div></div><div className="mb-3"><ResourceTypeTabs value={applied.type} onChange={type => updateUrl({ ...applied, type })} /></div>{error && <div className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><span>{error}</span><button type="button" onClick={() => setRetryTick(value => value + 1)} className="font-bold">重试</button></div>}<div className="overflow-hidden rounded-xl border border-public-border shadow-public">{loading ? <div data-testid="public-search-loading" className="flex min-h-64 items-center justify-center gap-2 bg-white text-sm text-public-muted"><Loader2 className="h-5 w-5 animate-spin" />正在检索制造资源…</div> : results?.results.length ? results.results.map(item => <ResultRow key={`${item.kind}-${item.id}`} item={item} onOpen={() => openItem(item)} onLogin={() => requestLogin(actionPath(item))} />) : <div data-testid="public-search-empty" className="flex min-h-64 flex-col items-center justify-center bg-white px-6 text-center"><Filter className="h-8 w-8 text-public-muted/50" /><h2 className="mt-3 font-bold">没有找到匹配资源</h2><p className="mt-1 text-sm text-public-muted">尝试减少筛选条件，或用产品、工艺和公司名称重新搜索。</p><button type="button" onClick={clearFilters} className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-public-brand">清除筛选 <X className="h-3.5 w-3.5" /></button></div>}</div><SearchPagination page={results?.page || 1} pages={results?.pages || 0} onChange={page => updateUrl(applied, page)} /></section></div></main></div>;
}
