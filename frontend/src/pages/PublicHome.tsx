import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight, BadgeCheck, Boxes, Building2, CheckCircle2, CircleAlert, Factory,
  FileCheck2, Globe2, Leaf, Loader2, MapPin, Network, PackageSearch, Search,
  ShieldCheck, Sparkles, Truck, Users, Wrench,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';
import { api, type PublicResourceItem, type PublicResourceKind, type PublicSearchResponse } from '@/src/services/api';
import { cn } from '@/src/lib/utils';

type SearchMode = 'keyword' | 'agent';

const RESOURCE_LABELS: Record<PublicResourceKind, string> = {
  enterprise: '企业', product: '产品', supply: '供应', demand: '采购需求',
};
const INDUSTRIES = [
  { key: 'machinery', label: '通用设备及零部件', icon: Wrench },
  { key: 'metal', label: '金属制品 · 铸造 · 表面处理', icon: Factory },
  { key: 'automotive', label: '汽车及汽车部件', icon: Truck },
  { key: 'electronics', label: '计算机 · 通信 · 电子器件', icon: Boxes },
  { key: 'electric', label: '电机 · 电缆 · 电池 · 灯具', icon: Network },
  { key: 'medicine', label: '医药制造 · 医疗器械', icon: ShieldCheck },
];
const QUICK_FILTERS = [
  { label: '可出口', key: 'is_export', icon: Globe2 },
  { label: '有决策人联系方式', key: 'has_decision_maker', icon: Users },
  { label: '专精特新', key: 'is_little_giant', icon: BadgeCheck },
  { label: '绿色工厂', key: 'is_green_factory', icon: Leaf },
] as const;

function formatNumber(value?: number) { return new Intl.NumberFormat('zh-CN').format(value || 0); }
function formatDate(value?: string | null) {
  if (!value) return '待更新';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.slice(0, 10) : new Intl.DateTimeFormat('zh-CN').format(date);
}

function ResourceCard({ item, onOpen }: { key?: string; item: PublicResourceItem; onOpen: (item: PublicResourceItem) => void }) {
  const Icon = item.kind === 'enterprise' ? Building2 : item.kind === 'product' ? Boxes : item.kind === 'supply' ? Truck : PackageSearch;
  return <article className="group rounded-xl border border-public-border bg-public-surface p-4 shadow-public transition hover:-translate-y-0.5 hover:border-public-brand/50">
    <div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand"><Icon className="h-5 w-5" /></span><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="text-[10px] font-bold uppercase tracking-[0.14em] text-public-muted">{RESOURCE_LABELS[item.kind]}</span>{item.public_signals.verification_status === 'approved' && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-label="已审核" />}</div><h3 className="mt-1 truncate text-sm font-black text-public-text" title={item.title}>{item.title}</h3></div><button type="button" aria-label={`查看${item.title}`} onClick={() => onOpen(item)} className="text-public-muted transition hover:text-public-brand"><ArrowRight className="h-4 w-4" /></button></div>
    <p className="mt-3 line-clamp-2 min-h-10 text-xs leading-5 text-public-muted">{item.subtitle}</p><div className="mt-3 flex flex-wrap gap-1.5">{item.tags.slice(0, 3).map(tag => <span key={tag} className="badge badge-default">{tag}</span>)}</div><p className="mt-3 text-[10px] text-public-muted">{item.public_signals.is_demo ? '演示数据 · ' : ''}更新于 {formatDate(item.public_signals.data_updated_at || item.public_signals.created_at)}</p>
  </article>;
}

export default function PublicHome() {
  const navigate = useNavigate();
  const { requestLogin } = useAuth();
  const [home, setHome] = useState<Awaited<ReturnType<typeof api.fetchPublicHome>> | null>(null);
  const [keyword, setKeyword] = useState('');
  const [searchMode, setSearchMode] = useState<SearchMode>('keyword');
  const [province, setProvince] = useState('');
  const [industry, setIndustry] = useState('');
  const [filters, setFilters] = useState({ is_export: false, has_decision_maker: false, is_little_giant: false, is_green_factory: false });
  const [search, setSearch] = useState<PublicSearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false);
  const [error, setError] = useState('');

  const loadHome = async () => { setLoading(true); try { setHome(await api.fetchPublicHome()); } catch { setError('平台数据暂时无法加载，请稍后重试'); } finally { setLoading(false); } };
  useEffect(() => { void loadHome(); }, []);
  const openLogin = (intent = '进入链易配工作台') => requestLogin(`/dashboard?${new URLSearchParams({ intent, source: 'public-home' }).toString()}`);
  const submitSearch = async (event?: FormEvent, override?: { keyword?: string; industry?: string }) => {
    event?.preventDefault();
    const nextKeyword = (override?.keyword ?? keyword).trim();
    const nextIndustry = override?.industry ?? industry;
    // All factory searches now enter the conversational Agent; keep filters in the natural-language request.
    const filterText = [
      province && `地区限定为${province}`,
      nextIndustry && `行业限定为${nextIndustry}`,
      filters.is_export && '要求支持出口',
      filters.has_decision_maker && '要求有决策人联系方式',
      filters.is_little_giant && '要求专精特新',
      filters.is_green_factory && '要求绿色工厂',
    ].filter(Boolean).join('，');
    if (nextKeyword || filterText || searchMode === 'agent') {
      const agentQuery = [nextKeyword || '帮我找合适的工厂', filterText].filter(Boolean).join('，');
      navigate(`/aia?q=${encodeURIComponent(agentQuery)}`);
      return;
    }
    if (!nextKeyword && !nextIndustry && !province && !Object.values(filters).some(Boolean)) { navigate('/search'); return; }
    setSearchLoading(true);
    try { const result = await api.searchPublicResources({ q: nextKeyword, province, industry: nextIndustry, ...filters, page: 1, per_page: 6 }); setSearch(result); window.setTimeout(() => document.getElementById('home-search-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0); }
    catch { setError('搜索失败，请稍后重试'); } finally { setSearchLoading(false); }
  };
  const displayedStats = useMemo(() => [['已收录企业', home?.stats.enterprise_count], ['已验证企业', home?.stats.verified_count], ['覆盖行业', home?.industries.length], ['活跃供需', (home?.stats.active_supply_count || 0) + (home?.stats.active_demand_count || 0)]], [home]);
  const openResource = (item: PublicResourceItem) => { if (item.kind === 'enterprise') navigate(`/factory/${item.id}`); else if (item.kind === 'product') navigate(`/search?q=${encodeURIComponent(item.title)}&type=product`); else openLogin(`${RESOURCE_LABELS[item.kind]}：${item.title}`); };

  return <div className="public-site min-h-screen bg-public-bg text-public-text">
    <PublicSiteHeader onLogin={() => openLogin()} /><main>
      <section className="relative overflow-hidden border-b border-public-border bg-public-bg"><div className="pointer-events-none absolute inset-0 opacity-60 [background-image:linear-gradient(rgba(36,107,219,.06)_1px,transparent_1px),linear-gradient(90deg,rgba(36,107,219,.06)_1px,transparent_1px)] [background-size:48px_48px]" /><div className="relative mx-auto max-w-[1120px] px-4 pb-14 pt-16 text-center md:px-8 md:pb-20 md:pt-24"><p className="eyebrow text-public-brand">链易配 · 制造业公开找厂平台</p><h1 className="mx-auto mt-4 max-w-3xl text-4xl font-black leading-tight tracking-tight text-public-text md:text-6xl">查工厂、找老板、找渠道</h1><p className="mx-auto mt-5 max-w-2xl text-base leading-8 text-public-muted md:text-lg">让每一次采购直达可核验的制造能力</p>
        <form data-testid="public-home-search" onSubmit={event => void submitSearch(event)} className="mx-auto mt-9 max-w-4xl rounded-xl border border-public-border bg-public-surface p-3 text-left shadow-public md:p-4"><div className="flex flex-wrap gap-2 border-b border-public-border pb-3"><button type="button" onClick={() => setSearchMode('keyword')} className={cn('rounded-md px-3 py-2 text-xs font-bold', searchMode === 'keyword' ? 'bg-public-brand-soft text-public-brand' : 'text-public-muted')}>关键词搜索</button><button type="button" onClick={() => setSearchMode('agent')} className={cn('inline-flex items-center gap-1 rounded-md px-3 py-2 text-xs font-bold', searchMode === 'agent' ? 'bg-public-brand-soft text-public-brand' : 'text-public-muted')}><Sparkles className="h-3.5 w-3.5" /> AI 找工厂</button><span className="ml-auto hidden items-center gap-1 text-[11px] text-public-muted sm:flex"><ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />信息来源和更新时间随结果展示</span></div><div className="mt-3 flex flex-col gap-2 md:flex-row"><div className="relative min-w-0 flex-1"><Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-public-brand" /><input id="factory-search" value={keyword} onChange={event => setKeyword(event.target.value)} placeholder={searchMode === 'agent' ? '例如：找华东可做精密注塑、支持出口的工厂' : '输入产品、工艺、公司名或地区'} className="h-12 w-full rounded-lg border border-public-border bg-public-bg pl-12 pr-4 text-sm outline-none transition focus:border-public-brand focus:bg-white focus:ring-2 focus:ring-public-brand-soft" /></div><button data-testid="public-home-search-submit" type="submit" disabled={searchLoading} className="btn-public-primary h-12 min-w-32">{searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : searchMode === 'agent' ? <Sparkles className="h-4 w-4" /> : <Search className="h-4 w-4" />}{searchMode === 'agent' ? '开始分析' : '搜索工厂'}<ArrowRight className="h-4 w-4" /></button></div>
          {searchMode === 'keyword' && <div className="mt-3 flex flex-col gap-2 sm:flex-row"><select aria-label="省份" value={province} onChange={event => setProvince(event.target.value)} className="input h-9 text-xs"><option value="">全部地区</option>{(home?.regions || []).map(region => <option key={region.key} value={region.key}>{region.label}</option>)}</select><select aria-label="行业" value={industry} onChange={event => setIndustry(event.target.value)} className="input h-9 text-xs"><option value="">全部行业</option>{(home?.industries || []).map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select><div className="flex flex-1 flex-wrap items-center gap-1.5"><span className="mr-1 text-[11px] font-bold text-public-muted">硬筛选</span>{QUICK_FILTERS.map(({ key, label, icon: Icon }) => <button key={key} type="button" onClick={() => setFilters(current => ({ ...current, [key]: !current[key] }))} className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-1.5 text-[11px] font-semibold', filters[key] ? 'border-public-brand bg-public-brand-soft text-public-brand' : 'border-public-border text-public-muted')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div></div>}</form>
        <div className="mt-5 flex flex-wrap justify-center gap-x-4 gap-y-2 text-xs text-public-muted"><span className="font-bold text-public-text">热门搜索</span>{['精密加工', '工业电机', '电子元器件', '汽车零部件'].map(item => <button key={item} type="button" onClick={() => { setKeyword(item); setSearchMode('keyword'); void submitSearch(undefined, { keyword: item }); }} className="transition hover:text-public-brand">{item}</button>)}</div><div className="mt-7 flex flex-wrap justify-center gap-3"><button type="button" onClick={() => openLogin('发布采购需求')} className="btn-public-primary"><PackageSearch className="h-4 w-4" />发布采购需求</button><button type="button" onClick={() => navigate('/aia')} className="btn-public-secondary"><Sparkles className="h-4 w-4 text-public-brand" />让 AI 帮我找</button></div></div></section>
      <section className="border-b border-public-border bg-public-surface"><div className="mx-auto grid max-w-[1120px] grid-cols-2 divide-x divide-public-border md:grid-cols-4">{displayedStats.map(([label, value], index) => <div key={label} className={cn('px-4 py-6 text-center md:py-7', index > 1 && 'hidden md:block')}><p className="metric-number text-2xl font-black text-public-text">{loading ? '—' : formatNumber(value as number)}</p><p className="mt-1 text-xs text-public-muted">{label}</p></div>)}</div></section>
      <div className="mx-auto max-w-[1120px] px-4 md:px-8">{error && <div className="mt-6 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><span>{error}</span><button type="button" onClick={() => { setError(''); void loadHome(); }} className="font-bold">重试</button></div>}{home?.data_freshness && <p className="mt-5 flex flex-wrap items-center justify-center gap-2 text-center text-[11px] text-public-muted"><CircleAlert className="h-3.5 w-3.5 text-amber-600" />数据口径：{home.data_freshness.is_demo ? '演示数据' : '生产数据'} · 最近更新时间 {formatDate(home.data_freshness.updated_at)}</p>}
        {search && <section id="home-search-results" className="scroll-mt-24 py-10"><div className="mb-4 flex items-end justify-between gap-3"><div><p className="eyebrow text-public-brand">Search results</p><h2 className="mt-1 text-xl font-black">找到 {formatNumber(search.total)} 条公开资源</h2></div><button type="button" onClick={() => navigate(`/search?q=${encodeURIComponent(search.query)}`)} className="text-xs font-bold text-public-brand">查看完整搜索 <ArrowRight className="ml-1 inline h-3.5 w-3.5" /></button></div>{search.results.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{search.results.map(item => <ResourceCard key={`${item.kind}-${item.id}`} item={item} onOpen={openResource} />)}</div> : <div className="rounded-xl border border-dashed border-public-border bg-public-surface p-10 text-center text-sm text-public-muted">暂无匹配结果，请减少筛选条件或换一种描述。</div>}</section>}
        <section id="discover" className="scroll-mt-24 py-14 md:py-16"><div className="mb-6 flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow text-public-brand">Industry & region</p><h2 className="mt-2 text-2xl font-black">从产业带开始找工厂</h2><p className="mt-2 text-sm text-public-muted">只展示当前平台已收录地区，不虚构全国规模。</p></div><button type="button" onClick={() => navigate('/search')} className="btn-public-secondary btn-sm">进入搜索 <ArrowRight className="h-3.5 w-3.5" /></button></div><div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]"><div className="rounded-xl border border-public-border bg-public-surface p-5 shadow-public"><div className="grid gap-2 sm:grid-cols-2">{INDUSTRIES.map(({ key, label, icon: Icon }) => <button key={key} type="button" onClick={() => navigate(`/search?industry=${key}`)} className="group flex items-center gap-3 rounded-lg border border-public-border bg-public-surface p-3 text-left transition hover:border-public-brand hover:bg-public-brand-soft"><span className="flex h-8 w-8 items-center justify-center rounded-md bg-public-brand-soft text-public-brand"><Icon className="h-4 w-4" /></span><span className="min-w-0 flex-1 truncate text-xs font-bold">{label}</span><ArrowRight className="h-3.5 w-3.5 text-public-muted group-hover:text-public-brand" /></button>)}</div></div><div className="rounded-xl border border-public-border bg-public-surface p-5 shadow-public"><div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-public-brand" /><h3 className="text-sm font-black">当前产业带</h3></div><div className="mt-4 grid grid-cols-2 gap-2">{(home?.industrial_belts || home?.regions || []).map(belt => <button key={belt.key} type="button" onClick={() => navigate(`/search?province=${encodeURIComponent(belt.key)}`)} className="rounded-lg bg-public-bg p-3 text-left text-xs font-bold transition hover:bg-public-brand-soft hover:text-public-brand"><span className="block truncate">{belt.label}</span><span className="mt-1 block text-[10px] font-normal text-public-muted">{formatNumber(belt.count)} 家企业</span></button>)}{!home?.industrial_belts?.length && <p className="col-span-2 py-8 text-center text-xs text-public-muted">地区数据同步后展示</p>}</div></div></div></section>
        <section id="services" className="scroll-mt-24 border-t border-public-border py-14 md:py-16"><div className="mb-6"><p className="eyebrow text-public-brand">Services</p><h2 className="mt-2 text-2xl font-black">从找厂到协同，接上真实业务</h2></div><div className="grid gap-3 md:grid-cols-3">{(home?.public_services || []).map(service => <button key={service.key} type="button" onClick={() => openLogin(service.title)} className="group rounded-xl border border-public-border bg-public-surface p-5 text-left shadow-public transition hover:-translate-y-0.5 hover:border-public-brand/50"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand"><FileCheck2 className="h-4 w-4" /></span><ArrowRight className="h-4 w-4 text-public-muted group-hover:text-public-brand" /></div><h3 className="mt-4 text-base font-black">{service.title}</h3><p className="mt-2 text-xs leading-5 text-public-muted">{service.summary}</p></button>)}{!home?.public_services?.length && <p className="text-sm text-public-muted">服务信息加载中…</p>}</div></section>
        <section id="agent-preview" className="border-t border-public-border py-14 md:py-16"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="eyebrow text-public-brand">Role-based AI</p><h2 className="mt-2 text-2xl font-black">AI 智能体，让岗位型 AI 进入制造流程</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-public-muted">产业数据底座连接订单、库存、BOM、客户和报价，再输出名单、询价单、排产建议和风险告警。</p></div><button type="button" onClick={() => navigate('/agent-market')} className="btn-public-secondary btn-sm">查看 Agent 市场 <ArrowRight className="h-3.5 w-3.5" /></button></div><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{['AI 销售员', 'AI 采购员', 'AI 计划员', 'AI 情报官'].map((title, index) => <div key={title} className="rounded-xl border border-public-border bg-public-surface p-4 shadow-public"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand">{index === 0 ? <Users className="h-4 w-4" /> : index === 1 ? <PackageSearch className="h-4 w-4" /> : index === 2 ? <Network className="h-4 w-4" /> : <CircleAlert className="h-4 w-4" />}</span><h3 className="mt-4 text-sm font-black">{title}</h3><p className="mt-1 text-xs leading-5 text-public-muted">规划中的岗位能力，演示状态以 Agent 市场为准。</p></div>)}</div></section>
      </div></main><footer className="border-t border-public-border bg-public-surface"><div className="mx-auto flex max-w-[1120px] flex-col gap-3 px-4 py-8 text-xs text-public-muted md:flex-row md:items-center md:justify-between md:px-8"><span className="font-bold text-public-text">链易配 · 产业链供需协同平台</span><span>公开数据脱敏展示 · 企业授权后协同 · 数据口径以实际同步状态为准</span><button type="button" onClick={() => openLogin('企业入驻')} className="font-bold text-public-brand">企业入驻 <ArrowRight className="ml-1 inline h-3.5 w-3.5" /></button></div></footer>
  </div>;
}
