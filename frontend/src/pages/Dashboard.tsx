import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, ArrowRight, ClipboardList, Factory, FileCheck2, RefreshCw, Send, ShieldCheck, TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api, type EnterpriseDashboardSummary, type EnterpriseDashboardTrends } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';

function DataState({ error, loading, onRetry }: { error: string; loading: boolean; onRetry: () => void }) {
  if (loading) return <div className="panel px-5 py-4 text-sm text-ink-muted">正在同步企业经营数据…</div>;
  if (!error) return null;
  return <div className="panel flex items-center justify-between border-critical/20 bg-critical-soft px-5 py-4 text-sm text-critical"><span>{error}</span><button type="button" onClick={onRetry} className="btn-secondary btn-sm gap-1.5"><RefreshCw className="h-3.5 w-3.5" />重试</button></div>;
}

function Metric({ label, value, unit, icon: Icon }: { label: string; value: string | number; unit?: string; icon: typeof Activity }) {
  return <div className="card-hover p-5"><div className="flex items-center gap-2 text-[11px] font-bold text-ink-muted"><span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-soft text-brand"><Icon className="h-4 w-4" /></span>{label}</div><p className="mt-4 text-3xl font-black tracking-tight text-ink">{value}<span className="ml-1 text-sm font-semibold text-ink-muted">{unit}</span></p></div>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<EnterpriseDashboardSummary | null>(null);
  const [trends, setTrends] = useState<EnterpriseDashboardTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = async () => {
    setLoading(true); setError('');
    const [summaryResult, trendsResult] = await Promise.allSettled([api.getEnterpriseDashboardSummary(), api.getEnterpriseDashboardTrends()]);
    if (summaryResult.status === 'fulfilled') setSummary(summaryResult.value);
    if (trendsResult.status === 'fulfilled') setTrends(trendsResult.value);
    if (summaryResult.status === 'rejected' || trendsResult.status === 'rejected') setError('经营数据暂不可用，请确认后端服务后重试');
    setLoading(false);
  };
  useEffect(() => { if (user?.role === 'enterprise') void load(); }, [user?.id]);
  const metrics = summary?.metrics;
  const maxTrend = Math.max(...(trends?.inquiries || []), ...(trends?.quotes || []), 1);
  const quickActions = [{ label: '找工厂', path: '/search', icon: Factory }, { label: '匹配结果', path: '/matching', icon: TrendingUp }, { label: '查看报价', path: '/matching?panel=quotes', icon: ClipboardList }, { label: '订单工作流', path: '/orders', icon: Activity }, { label: '产能日历', path: '/capacity-calendar', icon: Factory }];
  return <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5">
    <section className="panel flex flex-wrap items-start justify-between gap-4 p-6"><div><p className="eyebrow text-brand">Enterprise cockpit</p><h1 className="mt-1 text-2xl font-black text-ink">{user?.enterpriseName || '企业'}经营看板</h1><p className="mt-2 text-xs text-ink-muted">近 30 天经营摘要 · 数据来源：业务记录 · {summary?.is_demo ? '演示数据' : '真实数据'}</p></div><button type="button" onClick={() => void load()} disabled={loading} className="btn-secondary btn-sm gap-1.5"><RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />刷新数据</button></section>
    <DataState error={error} loading={loading && !summary} onRetry={() => void load()} />
    {summary && <>
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric label="新增询盘" value={metrics?.inquiries ?? 0} unit="条" icon={Send} /><Metric label="收到 / 提交报价" value={metrics?.quotes ?? 0} unit="条" icon={ClipboardList} /><Metric label="进行中订单" value={metrics?.orders ?? 0} unit="单" icon={Activity} /><Metric label="履约完成率" value={metrics?.fulfillment_rate ?? 0} unit="%" icon={ShieldCheck} /></section>
      <section className="grid gap-5 lg:grid-cols-[1fr_1.45fr]"><div className="panel p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="text-sm font-bold text-ink">待办中心</h2><p className="mt-1 text-xs text-ink-muted">需要你确认或继续处理的业务</p></div><AlertTriangle className="h-4 w-4 text-risk" /></div>{summary.todos.length ? <div className="space-y-2">{summary.todos.map(todo => <button key={todo.key} type="button" onClick={() => navigate(todo.path)} className="flex w-full items-center gap-3 rounded-md border border-border p-3 text-left transition hover:border-brand/40 hover:bg-surface-subtle"><span className="flex h-8 w-8 items-center justify-center rounded-md bg-risk-soft text-risk"><ClipboardList className="h-4 w-4" /></span><span className="flex-1"><span className="block text-xs font-bold text-ink">{todo.label}</span><span className="mt-0.5 block text-[11px] text-ink-muted">{todo.count} 项待处理</span></span><ArrowRight className="h-4 w-4 text-ink-faint" /></button>)}</div> : <div className="rounded-md border border-dashed border-border px-4 py-10 text-center text-xs text-ink-muted">暂无待办事项</div>}</div>
      <div className="panel p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="text-sm font-bold text-ink">近 6 个月业务趋势</h2><p className="mt-1 text-xs text-ink-muted">只展示当前企业真实业务记录</p></div><span className="text-[10px] text-ink-muted">更新于 {summary.updated_at.slice(0, 10)}</span></div>{trends ? <div className="grid grid-cols-6 gap-3">{trends.labels.map((label, index) => <div key={label} className="min-w-0"><div className="flex h-32 items-end gap-1 border-b border-border pb-1">{[{ value: trends.inquiries[index] || 0, color: 'bg-brand' }, { value: trends.quotes[index] || 0, color: 'bg-trust' }].map((bar, barIndex) => <div key={barIndex} title={`${bar.value} 条`} className={`w-1/2 rounded-t ${bar.color}`} style={{ height: `${Math.max(3, (bar.value / maxTrend) * 100)}%` }} />)}</div><p className="mt-2 truncate text-center text-[10px] text-ink-muted">{label.slice(5)}</p></div>)}</div> : <div className="py-12 text-center text-xs text-ink-muted">趋势数据暂不可用</div>}<div className="mt-3 flex gap-4 text-[10px] text-ink-muted"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-brand" />询盘</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-trust" />报价</span></div></div></section>
      <section className="panel p-5"><div className="mb-4 flex items-center justify-between"><h2 className="text-sm font-bold text-ink">快捷动作</h2><span className="text-[11px] text-ink-muted">企业业务入口</span></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{quickActions.map(({ label, path, icon: Icon }) => <button key={path} type="button" onClick={() => navigate(path)} className="flex items-center gap-3 rounded-md border border-border p-3 text-left transition hover:border-brand/40 hover:bg-surface-subtle"><Icon className="h-4 w-4 text-brand" /><span className="text-xs font-bold text-ink">{label}</span><ArrowRight className="ml-auto h-3.5 w-3.5 text-ink-faint" /></button>)}<button type="button" onClick={() => navigate('/assets')} className="flex items-center gap-3 rounded-md border border-border p-3 text-left transition hover:border-brand/40 hover:bg-surface-subtle"><FileCheck2 className="h-4 w-4 text-brand" /><span className="text-xs font-bold text-ink">上传企业资质</span></button></div></section>
    </>}
  </div>;
}
