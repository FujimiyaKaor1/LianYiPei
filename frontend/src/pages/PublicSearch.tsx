import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BadgeCheck, Building2, Factory, Filter, Globe2, Leaf, Loader2, MapPin, Search, ShieldCheck, SlidersHorizontal, X } from 'lucide-react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api, type PublicResourceItem } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';
import { cn } from '@/src/lib/utils';

const RESOURCE_LABELS = { enterprise: '工厂', product: '产品', supply: '供应信息', demand: '采购需求' } as const;

function formatDate(value?: string | null) {
  if (!value) return '待更新';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat('zh-CN').format(date);
}

function ResultRow({ item, onOpen, onLogin }: { key?: string; item: PublicResourceItem; onOpen: () => void; onLogin: () => void }) {
  const signals = item.public_signals;
  const isFactory = item.kind === 'enterprise';
  return (
    <article className="group border-b border-public-border/70 bg-white px-4 py-5 transition hover:bg-public-bg/50 md:px-6">
      <div className="flex gap-4">
        <div className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand sm:flex">
          {isFactory ? <Factory className="h-6 w-6" /> : <Building2 className="h-6 w-6" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={onOpen} className="truncate text-left text-base font-black text-public-text hover:text-public-brand">{item.title}</button>
            <span className="rounded bg-public-brand-soft px-1.5 py-0.5 text-[10px] font-bold text-public-brand">{RESOURCE_LABELS[item.kind]}</span>
            {signals.verification_status === 'approved' && <span className="badge badge-success">已审核</span>}
          </div>
          <p className="mt-2 text-sm leading-6 text-public-muted">{item.subtitle}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-public-muted">
            <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {item.subtitle.split(' · ').at(-1) || '区域待补充'}</span>
            {signals.is_export && <span className="inline-flex items-center gap-1 text-emerald-700"><Globe2 className="h-3.5 w-3.5" />支持出口</span>}
            {signals.has_decision_maker && <span className="inline-flex items-center gap-1 text-blue-700"><ShieldCheck className="h-3.5 w-3.5" />有决策人联系方式</span>}
            {signals.is_little_giant && <span className="inline-flex items-center gap-1 text-violet-700"><BadgeCheck className="h-3.5 w-3.5" />专精特新</span>}
            {signals.is_green_factory && <span className="inline-flex items-center gap-1 text-emerald-700"><Leaf className="h-3.5 w-3.5" />绿色工厂</span>}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">{item.tags.map(tag => <span key={tag} className="badge badge-default">{tag}</span>)}</div>
          <p className="mt-3 text-[11px] text-public-muted">来源：{signals.source || '平台公开档案'} · 更新于 {formatDate(signals.data_updated_at || signals.created_at)}{signals.is_demo ? ' · 演示数据' : ''}</p>
        </div>
        <div className="hidden shrink-0 flex-col items-end gap-3 sm:flex">
          <button type="button" onClick={onOpen} className="inline-flex items-center gap-1 text-xs font-bold text-public-brand">查看详情 <ArrowRight className="h-3.5 w-3.5" /></button>
          <button type="button" onClick={onLogin} className="rounded-md border border-public-border px-3 py-2 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand">联系 / 询价</button>
        </div>
      </div>
    </article>
  );
}

export default function PublicSearch() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { requestLogin } = useAuth();
  const [query, setQuery] = useState(params.get('q') || '');
  const [province, setProvince] = useState(params.get('province') || '');
  const [city, setCity] = useState(params.get('city') || '');
  const [industry, setIndustry] = useState(params.get('industry') || '');
  const [type, setType] = useState<'all' | 'enterprise' | 'product' | 'supply' | 'demand'>((params.get('type') as 'all' | 'enterprise' | 'product' | 'supply' | 'demand') || 'all');
  const [sort, setSort] = useState(params.get('sort') || 'relevance');
  const [companyStatus, setCompanyStatus] = useState(params.get('company_status') || '');
  const [minCapital, setMinCapital] = useState(params.get('min_registered_capital') || '');
  const [filters, setFilters] = useState({ is_export: params.get('is_export') === '1', has_decision_maker: params.get('has_decision_maker') === '1', is_little_giant: params.get('is_little_giant') === '1', is_green_factory: params.get('is_green_factory') === '1' });
  const [results, setResults] = useState<Awaited<ReturnType<typeof api.searchPublicResources>> | null>(null);
  const [home, setHome] = useState<Awaited<ReturnType<typeof api.fetchPublicHome>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runSearch = async (page = 1, overrides: { sort?: string } = {}) => {
    setLoading(true); setError(null);
    const nextSort = overrides.sort ?? sort;
    const next = new URLSearchParams();
    if (query.trim()) next.set('q', query.trim());
    if (province) next.set('province', province);
    if (city) next.set('city', city);
    if (industry) next.set('industry', industry);
    if (type !== 'all') next.set('type', type);
    if (nextSort !== 'relevance') next.set('sort', nextSort);
    if (companyStatus) next.set('company_status', companyStatus);
    if (minCapital) next.set('min_registered_capital', minCapital);
    Object.entries(filters).forEach(([key, value]) => { if (value) next.set(key, '1'); });
    if (page > 1) next.set('page', String(page));
    setParams(next);
    try { setResults(await api.searchPublicResources({ q: query, type, province, city, industry, sort: nextSort, company_status: companyStatus, min_registered_capital: minCapital ? Number(minCapital) : undefined, ...filters, page, per_page: 10 })); }
    catch { setError('搜索失败，请稍后重试'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void api.fetchPublicHome().then(setHome).catch(() => undefined); void runSearch(Number(params.get('page') || 1)); }, []);

  const setFilter = (key: keyof typeof filters) => setFilters(current => ({ ...current, [key]: !current[key] }));
  const clearFilters = () => { setProvince(''); setCity(''); setIndustry(''); setCompanyStatus(''); setMinCapital(''); setFilters({ is_export: false, has_decision_maker: false, is_little_giant: false, is_green_factory: false }); };
  const openItem = (item: PublicResourceItem) => item.kind === 'enterprise' ? navigate(`/factory/${item.id}`) : navigate(`/matching?query=${encodeURIComponent(item.title)}`);
  const actionPath = (item: PublicResourceItem) => item.kind === 'enterprise' ? `/factory/${item.id}` : item.public_signals.enterprise_id ? `/factory/${item.public_signals.enterprise_id}` : '/search';
  const totalPages = results?.pages || 0;
  const currentPage = results?.page || 1;
  const pageButtons = useMemo(() => {
    const count = Math.min(5, totalPages);
    const start = Math.max(1, Math.min(currentPage - 2, totalPages - count + 1));
    return Array.from({ length: count }, (_, index) => start + index);
  }, [currentPage, totalPages]);

  return <div className="public-site min-h-screen bg-public-bg text-public-text"><PublicSiteHeader onLogin={() => requestLogin('/dashboard')} /><main className="mx-auto max-w-[1320px] px-4 py-6 md:px-8 md:py-10">
    <section className="mb-6 rounded-xl border border-public-border bg-white p-4 shadow-public md:p-5">
      <form onSubmit={event => { event.preventDefault(); void runSearch(); }} className="flex flex-col gap-3 md:flex-row">
        <div className="relative flex-1"><Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-public-brand" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="输入产品、工艺、公司名或统一社会信用代码" className="h-12 w-full rounded-lg border border-public-border bg-public-bg pl-12 pr-4 text-sm outline-none transition focus:border-public-brand focus:bg-white focus:ring-2 focus:ring-public-brand-soft" /></div>
        <button type="submit" className="btn-public-primary h-12 px-7">查找工厂 <ArrowRight className="h-4 w-4" /></button>
      </form>
      <div className="mt-4 flex flex-wrap gap-2"><span className="mr-1 py-2 text-xs font-bold text-public-muted">快速筛选</span>{[['is_export', '可出口', Globe2], ['has_decision_maker', '有决策人联系方式', ShieldCheck], ['is_little_giant', '专精特新', BadgeCheck], ['is_green_factory', '绿色工厂', Leaf]].map(([key, label, Icon]) => <button key={key as string} type="button" onClick={() => setFilter(key as keyof typeof filters)} className={cn('inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-xs font-semibold transition', filters[key as keyof typeof filters] ? 'border-public-brand bg-public-brand-soft text-public-brand' : 'border-public-border text-public-muted hover:border-public-brand')}><Icon className="h-3.5 w-3.5" />{label as string}</button>)}</div>
    </section>
    <div className="grid gap-6 lg:grid-cols-[250px_1fr]">
      <aside className={cn('rounded-xl border border-public-border bg-white p-4 shadow-public lg:block', showFilters ? 'block' : 'hidden')}><div className="flex items-center justify-between"><h2 className="text-sm font-black">筛选条件</h2><button type="button" onClick={clearFilters} className="text-xs font-bold text-public-brand">清空</button></div><div className="mt-5 space-y-5"><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">省份地区</span><select value={province} onChange={event => setProvince(event.target.value)} className="input w-full text-sm"><option value="">全部地区</option>{(home?.regions || []).map(region => <option key={region.key} value={region.key}>{region.label}</option>)}</select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">城市</span><input value={city} onChange={event => setCity(event.target.value)} placeholder="如：佛山市" className="input w-full text-sm" /></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">行业分类</span><select value={industry} onChange={event => setIndustry(event.target.value)} className="input w-full text-sm"><option value="">全部行业</option>{(home?.industries || []).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">资源类型</span><select value={type} onChange={event => setType(event.target.value as typeof type)} className="input w-full text-sm"><option value="all">全部资源</option><option value="enterprise">工厂</option><option value="product">产品</option><option value="supply">供应信息</option><option value="demand">采购需求</option></select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">经营状态</span><select value={companyStatus} onChange={event => setCompanyStatus(event.target.value)} className="input w-full text-sm"><option value="">全部状态</option><option value="存续">存续</option><option value="在业">在业</option><option value="注销">注销</option></select></label><label className="block"><span className="mb-2 block text-xs font-bold text-public-muted">注册资本（万元）</span><input type="number" min="0" value={minCapital} onChange={event => setMinCapital(event.target.value)} placeholder="如：1000" className="input w-full text-sm" /></label><button type="button" onClick={() => void runSearch()} className="btn-public-secondary w-full">应用筛选</button></div></aside>
      <section className="min-w-0"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow text-public-brand">Factory directory</p><h1 className="mt-1 text-2xl font-black">{results ? `找到 ${results.total.toLocaleString('zh-CN')} 条资源` : '搜索制造资源'}</h1></div><div className="flex items-center gap-2"><button type="button" onClick={() => setShowFilters(value => !value)} className="btn-public-secondary lg:hidden"><SlidersHorizontal className="h-4 w-4" />筛选</button><select value={sort} onChange={event => { const value = event.target.value; setSort(value); void runSearch(1, { sort: value }); }} className="input h-9 text-xs"><option value="relevance">综合排序</option><option value="name">名称排序</option></select></div></div>{error && <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}<div className="overflow-hidden rounded-xl border border-public-border shadow-public">{loading ? <div className="flex min-h-64 items-center justify-center gap-2 bg-white text-sm text-public-muted"><Loader2 className="h-5 w-5 animate-spin" />正在检索制造资源…</div> : results?.results.length ? results.results.map(item => <ResultRow key={`${item.kind}-${item.id}`} item={item} onOpen={() => openItem(item)} onLogin={() => requestLogin(actionPath(item))} />) : <div className="flex min-h-64 flex-col items-center justify-center bg-white px-6 text-center"><Filter className="h-8 w-8 text-public-muted/50" /><h2 className="mt-3 font-bold">没有找到匹配资源</h2><p className="mt-1 text-sm text-public-muted">尝试减少筛选条件，或用产品、工艺和公司名称重新搜索。</p><button type="button" onClick={clearFilters} className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-public-brand">清除筛选 <X className="h-3.5 w-3.5" /></button></div>}</div><div className="mt-5 flex justify-center gap-2">{pageButtons.map(page => <button key={page} type="button" onClick={() => void runSearch(page)} className={cn('h-9 w-9 rounded-md text-xs font-bold', results?.page === page ? 'bg-public-brand text-white' : 'border border-public-border bg-white text-public-muted hover:border-public-brand')}>{page}</button>)}</div></section>
    </div>
  </main></div>;
}
