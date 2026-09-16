import { FormEvent, useState } from 'react';
import { ArrowRight, CheckCircle2, Factory, Loader2, MapPin, MessageSquare, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type PublicAiFindResponse } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

const QUICK_PROMPTS = ['找华东可做精密注塑的工厂', '找能出口的汽车零部件工厂', '找有产能的工业电机供应商', '找广东专精特新制造企业'];

function IntentSummary({ intent }: { intent: Record<string, unknown> }) {
  const values = [
    typeof intent.region === 'string' ? `地区：${intent.region}` : '',
    typeof intent.quantity === 'number' ? `数量：${intent.quantity}${typeof intent.unit === 'string' ? intent.unit : ''}` : '',
    typeof intent.delivery_days === 'number' ? `交期：${intent.delivery_days} 天` : '',
    Array.isArray(intent.processes) && intent.processes.length ? `工艺：${intent.processes.join('、')}` : '',
    Array.isArray(intent.certifications) && intent.certifications.length ? `资质：${intent.certifications.join('、')}` : '',
    intent.is_export === true ? '支持出口' : '',
  ].filter(Boolean);
  return <div className="mt-3 flex flex-wrap gap-2">{values.length ? values.map(value => <span key={value} className="rounded-md bg-public-brand-soft px-2.5 py-1.5 text-xs font-semibold text-public-brand">{value}</span>) : <span className="rounded-md bg-public-bg px-2.5 py-1.5 text-xs text-public-muted">已提取基础产品条件，更多约束可在工作台补充</span>}</div>;
}

export default function PublicAia() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { requestLogin } = useAuth();
  const [query, setQuery] = useState(params.get('query') || '');
  const [result, setResult] = useState<PublicAiFindResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [creatingDraft, setCreatingDraft] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!query.trim()) { setError('请先描述你要找的产品、工艺或地区'); return; }
    setLoading(true); setError('');
    try { setResult(await api.publicAiFind(query)); }
    catch (err) { setError(err instanceof Error ? err.message : 'AI 找厂暂时不可用，请稍后重试'); }
    finally { setLoading(false); }
  };

  const matchingPath = result ? `/matching?query=${encodeURIComponent(query)}&mode=agent&intent=${encodeURIComponent(JSON.stringify(result.parsed_intent))}` : '/matching?mode=agent';

  const createDraft = async () => {
    if (!result) return;
    setCreatingDraft(true); setError('');
    try {
      const session = await api.createChainXiaoYiSession('enterprise');
      const draft = await api.createChainXiaoYiDemandDraft(session.session.id, result.parsed_intent, session.session.token || undefined);
      navigate(`/matching?query=${encodeURIComponent(result.product)}&mode=agent&inquiry_id=${draft.inquiry.id}&intent=${encodeURIComponent(JSON.stringify(result.parsed_intent))}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '请登录后创建需求草稿');
      requestLogin(`/aia?query=${encodeURIComponent(query)}`);
    } finally { setCreatingDraft(false); }
  };

  return <div className="public-site min-h-screen bg-public-bg text-public-text"><PublicSiteHeader onLogin={() => requestLogin('/aia')} /><main className="mx-auto max-w-[1180px] px-4 py-10 md:px-8 md:py-16">
    <section className="mx-auto max-w-4xl text-center"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-public-brand text-white shadow-public"><Sparkles className="h-6 w-6" /></div><p className="eyebrow mt-5 text-public-brand">AI factory finder</p><h1 className="mt-3 text-3xl font-black tracking-tight md:text-5xl">今天，你想找什么工厂？</h1><p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-public-muted md:text-base">像跟业务员说话一样描述需求，链易配会帮你拆解产品、工艺、地区和能力条件，给出可以继续联系的候选工厂。</p>
      <form onSubmit={event => void submit(event)} className="mt-8 rounded-xl border border-public-border bg-public-surface p-3 text-left shadow-public"><textarea value={query} onChange={event => setQuery(event.target.value)} rows={4} placeholder="例如：找华东地区能做精密注塑、支持出口、交期 30 天以内的工厂" className="w-full resize-none rounded-lg bg-public-bg p-4 text-sm leading-7 outline-none focus:bg-white focus:ring-2 focus:ring-public-brand-soft" /><div className="mt-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div className="flex flex-wrap gap-2">{QUICK_PROMPTS.slice(0, 2).map(prompt => <button key={prompt} type="button" onClick={() => setQuery(prompt)} className="rounded-md bg-public-bg px-2.5 py-1.5 text-[11px] font-semibold text-public-muted hover:text-public-brand">{prompt}</button>)}</div><button type="submit" disabled={loading} className="btn-public-primary min-w-32">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{loading ? '正在分析' : '问 AI 找工厂'}</button></div></form>
      {error && <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-left text-sm text-red-700"><span>{error}</span><button type="button" onClick={() => setError('')} className="font-bold">知道了</button></div>}
    </section>
    {result && <section className="mt-12"><div className="rounded-xl border border-public-border bg-public-surface p-5 shadow-public"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow text-public-brand">需求解析</p><h2 className="mt-1 text-lg font-black">我理解你要找：{result.product}</h2><div className="mt-3 flex flex-wrap gap-2 text-xs text-public-muted"><span className="rounded-md bg-public-bg px-2.5 py-1.5">自然语言：{result.query}</span><span className="rounded-md bg-public-bg px-2.5 py-1.5"><CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-emerald-600" />已生成候选条件</span></div><IntentSummary intent={result.parsed_intent} /></div><button type="button" onClick={() => { setResult(null); setQuery(''); }} className="btn-public-secondary"><RotateCcw className="h-4 w-4" />重新描述</button></div></div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow text-public-brand">Recommended factories</p><h2 className="mt-1 text-xl font-black">为你找到 {result.results.length} 家候选工厂</h2></div><div className="flex items-center gap-3"><button type="button" disabled={creatingDraft} onClick={() => void createDraft()} className="text-xs font-bold text-public-brand disabled:opacity-50">{creatingDraft ? '正在创建…' : '创建需求草稿'} <ArrowRight className="ml-1 inline h-3.5 w-3.5" /></button><button type="button" onClick={() => navigate(matchingPath)} className="text-xs font-bold text-public-brand">直接进入匹配 <ArrowRight className="ml-1 inline h-3.5 w-3.5" /></button></div></div>
      {result.results.length ? <div className="mt-4 grid gap-3 md:grid-cols-2">{result.results.map(item => <article key={item.id} className="rounded-xl border border-public-border bg-public-surface p-5 shadow-public transition hover:-translate-y-0.5 hover:border-public-brand/50"><div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-public-brand-soft text-public-brand"><Factory className="h-5 w-5" /></span><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><h3 className="truncate font-black">{item.title}</h3><span className="text-lg font-black text-emerald-600">{Math.round(item.score)}<small className="ml-0.5 text-[10px]">分</small></span></div><p className="mt-1 text-xs text-public-muted">{item.subtitle}</p><div className="mt-3 flex flex-wrap gap-1.5">{item.tags.map(tag => <span key={tag} className="badge badge-default">{tag}</span>)}</div><p className="mt-3 text-xs leading-5 text-public-muted"><MessageSquare className="mr-1 inline h-3.5 w-3.5 text-public-brand" />{item.reason}</p><p className="mt-2 text-[11px] text-public-muted"><MapPin className="mr-1 inline h-3.5 w-3.5" />{item.public_signals.data_updated_at ? `数据更新于 ${item.public_signals.data_updated_at.slice(0, 10)}` : '数据更新时间待补充'} · {item.public_signals.is_demo ? '演示数据' : '公开档案'}</p><div className="mt-4 flex gap-2"><button type="button" onClick={() => navigate(`/factory/${item.id}`)} className="btn-public-secondary btn-sm flex-1">查看工厂</button><button type="button" onClick={() => requestLogin(`/factory/${item.id}`)} className="btn-public-primary btn-sm flex-1"><ShieldCheck className="h-3.5 w-3.5" />联系 / 询价</button></div></div></div></article>)}</div> : <div className="mt-4 rounded-xl border border-dashed border-public-border bg-public-surface px-6 py-12 text-center"><h3 className="font-bold">暂时没有找到合适工厂</h3><p className="mt-2 text-sm text-public-muted">试试减少地区或资质限制，或换一种产品/工艺描述。</p><div className="mt-4 flex flex-wrap justify-center gap-2">{QUICK_PROMPTS.slice(2).map(prompt => <button key={prompt} type="button" onClick={() => setQuery(prompt)} className="rounded-md bg-public-bg px-3 py-2 text-xs font-semibold text-public-muted">{prompt}</button>)}</div></div>}
    </section>}
  </main></div>;
}
