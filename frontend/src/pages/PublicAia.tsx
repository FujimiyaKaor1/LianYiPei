import { FormEvent, useEffect, useRef, useState } from 'react';
import { Archive, ChevronRight, Download, History, Loader2, Menu, MessageSquare, PanelRight, Plus, Send, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type ChainXiaoYiMatchResult, type ChainXiaoYiSession } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

type ChatMessage = { role: 'user' | 'assistant'; content: string };
const QUICK_PROMPTS = ['找华东能做精密注塑、30天交付的工厂', '找支持出口的汽车零部件工厂', '找有产能的工业电机供应商'];
const DIMENSION_NAMES: Record<string, string> = { product: '产品', distance: '距离', capacity: '产能', green: '绿色', semantic: '语义', credit: '信用', tech: '技术', history: '合作', gnn: '图谱' };

function IntentChips({ intent }: { intent: Record<string, unknown> }) {
  const values = [
    typeof intent.product === 'string' && `产品：${intent.product}`,
    typeof intent.region === 'string' && `地区：${intent.region}`,
    typeof intent.quantity === 'number' && `数量：${intent.quantity}${typeof intent.unit === 'string' ? intent.unit : ''}`,
    typeof intent.delivery_days === 'number' && `交期：${intent.delivery_days}天`,
    Array.isArray(intent.processes) && intent.processes.length > 0 && `工艺：${intent.processes.join('、')}`,
    Array.isArray(intent.certifications) && intent.certifications.length > 0 && `资质：${intent.certifications.join('、')}`,
    intent.is_export === true && '支持出口', intent.is_green_factory === true && '绿色工厂',
  ].filter((value): value is string => Boolean(value));
  return <div className="flex flex-wrap gap-1.5">{values.map(value => <span key={value} className="rounded-full bg-public-brand-soft px-2.5 py-1 text-[11px] font-semibold text-public-brand">{value}</span>)}</div>;
}

export default function PublicAia() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { user, requestLogin } = useAuth();
  const initialQuery = params.get('q') || params.get('query') || '';
  const [query, setQuery] = useState(initialQuery);
  const [session, setSession] = useState<ChainXiaoYiSession | null>(null);
  const [history, setHistory] = useState<ChainXiaoYiSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [intent, setIntent] = useState<Record<string, unknown>>({});
  const [matches, setMatches] = useState<ChainXiaoYiMatchResult | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [error, setError] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [resultsOpen, setResultsOpen] = useState(false);
  const autoSent = useRef(false);

  const refreshHistory = async () => {
    if (!user) return;
    try { setHistory((await api.listChainXiaoYiSessions()).sessions); } catch { setHistory([]); }
  };

  const ensureSession = async () => {
    if (session) return session;
    setStage('正在创建安全会话');
    const created = await api.createChainXiaoYiSession('public');
    setSession(created.session);
    return created.session;
  };

  const send = async (content: string) => {
    const clean = content.trim();
    if (!clean || loading) return;
    setLoading(true); setError(''); setStage('正在理解需求');
    setMessages(previous => [...previous, { role: 'user', content: clean }]);
    setQuery('');
    try {
      const active = await ensureSession();
      setStage('数据库正在召回并计算九维分数');
      const response = await api.sendChainXiaoYiMessage(active.id, clean);
      setIntent(response.intent); setMatches(response.match_result); setSuggestions(response.suggestions || []);
      setMessages(previous => [...previous, { role: 'assistant', content: response.reply }]);
      setResultsOpen(true);
      if (user) await refreshHistory();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Agent 暂时不可用，请稍后重试';
      setError(message);
      if (message.includes('登录')) requestLogin(`/aia?q=${encodeURIComponent(clean)}`);
    } finally { setLoading(false); setStage(''); }
  };

  useEffect(() => {
    if (!autoSent.current && initialQuery.trim()) { autoSent.current = true; void send(initialQuery); }
  // Initial URL input is intentionally submitted once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void refreshHistory(); }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!user || !session || session.status !== 'active') return;
    void api.claimChainXiaoYiSession(session.id).then(({ session: claimed }) => { setSession(claimed); void refreshHistory(); }).catch(() => undefined);
  // Claim is attempted when auth/session identity changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, session?.id]);

  const openHistory = async (item: ChainXiaoYiSession) => {
    try {
      const detail = await api.getChainXiaoYiSession(item.id);
      setSession(detail.session); setIntent(detail.intent || {}); setMatches(detail.match_result || null);
      setMessages(detail.messages.map(message => ({ role: message.role === 'user' ? 'user' : 'assistant', content: message.content })));
      setHistoryOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : '会话加载失败'); }
  };

  const archive = async (item: ChainXiaoYiSession) => {
    await api.archiveChainXiaoYiSession(item.id);
    if (session?.id === item.id) { setSession(null); setMessages([]); setMatches(null); setIntent({}); }
    await refreshHistory();
  };

  const submit = (event: FormEvent) => { event.preventDefault(); void send(query); };

  const HistoryPanel = <aside className="flex h-full flex-col border-r border-public-border bg-white p-4">
    <button type="button" onClick={() => { setSession(null); setMessages([]); setMatches(null); setIntent({}); setSuggestions([]); setHistoryOpen(false); }} className="btn-public-primary w-full"><Plus className="h-4 w-4" />新建会话</button>
    <h2 className="mt-6 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-public-muted"><History className="h-4 w-4" />历史会话</h2>
    {!user ? <button type="button" onClick={() => requestLogin('/aia')} className="mt-4 rounded-lg bg-public-bg p-4 text-left text-xs leading-5 text-public-muted">登录后查看历史会话并继续追问</button> : <div className="mt-3 space-y-2 overflow-y-auto">{history.map(item => <div key={item.id} className="group rounded-lg border border-public-border p-3"><button type="button" onClick={() => void openHistory(item)} className="w-full text-left"><p className="truncate text-sm font-bold">{item.title || '找厂会话'}</p><p className="mt-1 text-[11px] text-public-muted">{item.match_count ?? 0} 家候选 · {item.updated_at?.slice(0, 10)}</p></button><button type="button" aria-label="归档会话" onClick={() => void archive(item)} className="mt-2 text-public-muted opacity-0 transition group-hover:opacity-100"><Archive className="h-3.5 w-3.5" /></button></div>)}</div>}
  </aside>;

  const ResultsPanel = <aside className="h-full overflow-y-auto border-l border-public-border bg-public-bg p-4">
    <div className="flex items-center justify-between"><div><p className="text-xs font-bold text-public-brand">实时匹配</p><h2 className="mt-1 font-black">{matches ? `${matches.total} 家候选工厂` : '等待需求'}</h2></div>{session && user && matches && <a href={`/api/chain-xiaoyi/sessions/${session.id}/export.xlsx`} className="btn-public-secondary btn-sm"><Download className="h-3.5 w-3.5" />导出</a>}</div>
    {matches?.degraded && <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-[11px] text-amber-700">解释模型不可用，本轮使用确定性数据库理由；匹配与排序不受影响。</p>}
    <div className="mt-4 space-y-3">{matches?.results.map((item, index) => <article key={item.id} className="rounded-xl border border-public-border bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-[10px] font-bold text-public-muted">#{index + 1} · {item.province}{item.city}</p><h3 className="mt-1 truncate font-black">{item.name}</h3></div><span className="shrink-0 text-xl font-black text-emerald-600">{Math.round(item.score)}<small className="text-[10px]">分</small></span></div><p className="mt-3 text-xs leading-5 text-public-muted">{item.reason}</p><div className="mt-3 grid grid-cols-3 gap-1">{(Object.entries(item.dimensions) as Array<[string, { score?: number; desc?: string }]>).map(([key, value]) => <div key={key} title={value.desc || ''} className="rounded bg-public-bg px-1.5 py-1 text-center"><p className="text-[9px] text-public-muted">{DIMENSION_NAMES[key] || key}</p><p className="text-[11px] font-bold">{typeof value.score === 'number' ? Math.round(value.score <= 1 ? value.score * 100 : value.score) : '—'}</p></div>)}</div><div className="mt-4 flex gap-2"><button type="button" onClick={() => navigate(`/factory/${item.id}`)} className="btn-public-secondary btn-sm flex-1">详情</button><button type="button" onClick={() => user ? navigate(`/matching?query=${encodeURIComponent(String(intent.product || ''))}&supplier_id=${item.id}`) : requestLogin('/aia')} className="btn-public-primary btn-sm flex-1"><ShieldCheck className="h-3.5 w-3.5" />询价</button></div></article>)}</div>
    {matches && matches.total === 0 && <div className="mt-8 rounded-xl border border-dashed border-public-border bg-white p-6 text-center text-sm text-public-muted">没有符合全部硬条件的企业。可在对话中说“取消地区限制”或放宽资质要求。</div>}
  </aside>;

  return <div className="public-site flex h-screen flex-col overflow-hidden bg-public-bg text-public-text"><PublicSiteHeader onLogin={() => requestLogin('/aia')} />
    <div className="flex min-h-0 flex-1 lg:grid lg:grid-cols-[240px_minmax(420px,1fr)_380px]">
      <div className="hidden min-h-0 lg:block">{HistoryPanel}</div>
      <main className="flex min-w-0 flex-1 flex-col bg-white">
        <header className="flex items-center justify-between border-b border-public-border px-4 py-3"><button type="button" aria-label="打开历史" onClick={() => setHistoryOpen(true)} className="lg:hidden"><Menu className="h-5 w-5" /></button><div className="text-center"><h1 className="font-black">链小易 · AI 找工厂</h1><p className="text-[10px] text-public-muted">数据库九维算法决定召回、排序与分数</p></div><button type="button" aria-label="打开结果" onClick={() => setResultsOpen(true)} className="lg:hidden"><PanelRight className="h-5 w-5" /></button></header>
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8"><div className="mx-auto max-w-3xl space-y-5">{messages.length === 0 && <section className="py-12 text-center"><span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-public-brand text-white"><Sparkles className="h-7 w-7" /></span><h2 className="mt-5 text-2xl font-black">用一句话描述你要找的工厂</h2><p className="mt-2 text-sm text-public-muted">产品、工艺、地区、数量、交期和资质都可以直接说</p><div className="mt-6 flex flex-wrap justify-center gap-2">{QUICK_PROMPTS.map(prompt => <button key={prompt} type="button" onClick={() => void send(prompt)} className="rounded-full border border-public-border px-3 py-2 text-xs hover:border-public-brand hover:text-public-brand">{prompt}</button>)}</div></section>}{messages.map((message, index) => <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'bg-public-brand text-white' : 'bg-public-bg text-public-text'}`}>{message.role === 'assistant' && <MessageSquare className="mr-2 inline h-4 w-4 text-public-brand" />}{message.content}</div></div>)}{Object.keys(intent).length > 0 && <IntentChips intent={intent} />}{suggestions.length > 0 && <div className="flex flex-wrap gap-2">{suggestions.map(item => <button key={item} type="button" onClick={() => setQuery(item)} className="rounded-full bg-public-bg px-3 py-1.5 text-[11px] text-public-muted">{item}<ChevronRight className="ml-1 inline h-3 w-3" /></button>)}</div>}{loading && <div className="flex items-center gap-2 text-sm text-public-muted"><Loader2 className="h-4 w-4 animate-spin text-public-brand" />{stage}</div>}{error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}</div></div>
        <form onSubmit={submit} className="border-t border-public-border bg-white p-4"><div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-public-border bg-public-bg p-2 focus-within:border-public-brand"><textarea value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(query); } }} rows={2} maxLength={2000} placeholder="继续补充或修改条件，例如：只看四川，信用分至少 80" className="min-h-12 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none" /><button type="submit" disabled={loading || !query.trim()} className="flex h-10 w-10 items-center justify-center rounded-lg bg-public-brand text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></div><p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-public-muted">AI 仅解释数据库事实；请在询价前核验企业最新能力与资质。</p></form>
      </main>
      <div className="hidden min-h-0 lg:block">{ResultsPanel}</div>
    </div>
    {historyOpen && <div className="fixed inset-0 z-50 flex bg-black/30 lg:hidden"><div className="h-full w-[82%] max-w-xs">{HistoryPanel}</div><button type="button" aria-label="关闭" onClick={() => setHistoryOpen(false)} className="m-4 h-9 w-9 rounded-full bg-white"><X className="mx-auto h-4 w-4" /></button></div>}
    {resultsOpen && <div className="fixed inset-0 z-50 flex justify-end bg-black/30 lg:hidden"><button type="button" aria-label="关闭" onClick={() => setResultsOpen(false)} className="m-4 h-9 w-9 rounded-full bg-white"><X className="mx-auto h-4 w-4" /></button><div className="h-full w-[88%] max-w-md">{ResultsPanel}</div></div>}
  </div>;
}
