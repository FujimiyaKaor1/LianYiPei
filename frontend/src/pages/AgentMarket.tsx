import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight, Bot, Check, CheckCircle2, Download, ExternalLink, FileCheck2, Globe2,
  Info, Loader2, Network, PackageSearch, PhoneCall, Search, Target, Wrench, X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api, type PublicAgentMarketResponse, type PublicAgentSkill } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

const ICONS = [Target, PackageSearch, Network, Wrench, FileCheck2, Globe2, Search];
const FALLBACK_LAYERS = [
  { key: 'data', title: '产业数据底座', description: '企业、产品、产能、信用和产业关系' },
  { key: 'business', title: '企业业务数据', description: '订单、库存、BOM、客户和报价' },
  { key: 'agent', title: '岗位型 AI Agent', description: '名单、询价单、排产建议和风险告警' },
];

function SkillDownload({ skill, onDownload }: { key?: string; skill: PublicAgentSkill; onDownload: (skill: PublicAgentSkill) => void }) {
  return <div className="flex min-w-0 items-center gap-3 rounded-xl border border-public-border/70 bg-public-bg/70 px-3 py-2.5">
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-public-brand shadow-sm"><Download className="h-3.5 w-3.5" /></span>
    <div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-public-text">{skill.label}</p><p className="mt-0.5 truncate text-[10px] text-public-muted">{skill.purpose}</p></div>
    <button type="button" onClick={() => onDownload(skill)} className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-public-brand px-2.5 py-1.5 text-[11px] font-bold text-white transition hover:bg-[#1C5CBD]" aria-label={`下载 ${skill.label}`}><Download className="h-3 w-3" />下载</button>
  </div>;
}

export default function AgentMarket() {
  const navigate = useNavigate();
  const { requestLogin } = useAuth();
  const [market, setMarket] = useState<PublicAgentMarketResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedSkill, setSelectedSkill] = useState<PublicAgentSkill | null>(null);

  const loadMarket = async () => {
    setLoading(true);
    try { setMarket(await api.fetchPublicAgentMarket()); }
    catch { setError('Agent 能力目录暂时无法加载，请稍后重试'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void loadMarket(); }, []);

  const layers = market?.layers?.length ? market.layers : FALLBACK_LAYERS;
  const groupCount = market?.groups.length || 0;
  const skillCount = useMemo(() => market?.groups.reduce((total, group) => total + group.skills.length, 0) || 0, [market]);
  const downloadSkill = (skill: PublicAgentSkill) => {
    const link = document.createElement('a');
    link.href = skill.download_url; link.download = `${skill.repo.split('/')[1]}-${skill.branch}.zip`; link.target = '_blank'; link.rel = 'noreferrer';
    document.body.appendChild(link); link.click(); link.remove(); setSelectedSkill(skill);
  };

  return <div className="public-site min-h-screen bg-public-bg text-public-text">
    <PublicSiteHeader onLogin={() => requestLogin('/agent-market')} />
    <main>
      <section className="relative overflow-hidden border-b border-public-border bg-white">
        <div className="pointer-events-none absolute -right-32 -top-36 h-[500px] w-[500px] rounded-full bg-public-brand-soft/70 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-40 w-72 bg-[radial-gradient(circle_at_bottom_left,rgba(36,107,219,.12),transparent_68%)]" />
        <div className="relative mx-auto grid max-w-[1240px] gap-10 px-4 pb-14 pt-12 md:px-8 md:pb-20 md:pt-20 lg:grid-cols-[minmax(0,1.08fr)_minmax(380px,.82fr)] lg:items-center lg:gap-16">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-public-brand/20 bg-public-brand-soft px-3 py-1.5 text-[11px] font-bold text-public-brand"><span className="h-1.5 w-1.5 rounded-full bg-public-brand" />AI capability market</div>
            <h1 className="mt-5 max-w-3xl text-4xl font-black leading-[1.12] tracking-tight text-public-text md:text-6xl">把 AI 放进真实的<span className="block text-public-brand">制造业务里</span></h1>
            <p className="mt-5 max-w-xl text-base leading-8 text-public-muted md:text-lg">围绕销售、采购、计划、生产、财法务、出海和产业情报，选择可以接入企业数据的岗位型 AI 能力。</p>
            <div className="mt-8 flex flex-wrap gap-3"><button type="button" onClick={() => navigate('/aia')} className="btn-public-primary">先试用 AI 找工厂 <ArrowRight className="h-4 w-4" /></button><button type="button" onClick={() => requestLogin('/agent-market')} className="btn-public-secondary">预约业务诊断</button></div>
            <div className="mt-9 flex flex-wrap gap-x-7 gap-y-3 border-t border-public-border/70 pt-5 text-xs text-public-muted"><span><strong className="mr-1 text-lg font-black text-public-text">{groupCount || '—'}</strong> 个岗位方向</span><span><strong className="mr-1 text-lg font-black text-public-text">{skillCount || '—'}</strong> 个可接入 Skill</span><span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />数据边界清晰</span></div>
          </div>
          <div className="relative rounded-3xl border border-public-brand/15 bg-public-bg p-2 shadow-[0_24px_70px_-36px_rgba(36,107,219,.5)]"><div className="rounded-[1.35rem] border border-white/80 bg-white p-5 md:p-6">
            <div className="flex items-center gap-3 border-b border-public-border/70 pb-5"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-public-brand text-white shadow-lg shadow-blue-200"><Bot className="h-6 w-6" /></span><div><p className="text-xs font-bold text-public-brand">链小易 Agent 编队</p><h2 className="mt-1 text-lg font-black">从数据到行动结果</h2></div><span className="ml-auto h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,.12)]" /></div>
            <div className="mt-5 space-y-2.5">{layers.map((layer, index) => <div key={layer.key || layer.title} className="group flex items-center gap-3 rounded-xl border border-transparent bg-public-bg p-3.5 transition hover:border-public-brand/20 hover:bg-public-brand-soft/50"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-public-brand-soft text-xs font-black text-public-brand">0{index + 1}</span><div className="min-w-0"><p className="text-sm font-bold">{layer.title}</p><p className="mt-1 truncate text-xs text-public-muted">{layer.description}</p></div>{index === layers.length - 1 && <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-public-brand" />}</div>)}</div>
          </div></div>
        </div>
      </section>

      <div className="mx-auto max-w-[1240px] px-4 py-12 md:px-8 md:py-16">
        {error && <div className="mb-10 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"><span>{error}</span><button type="button" onClick={() => { setError(''); void loadMarket(); }} className="font-bold">重试</button></div>}
        <section aria-labelledby="agent-groups-title">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-public-border/70 pb-5"><div><p className="eyebrow text-public-brand">Role-based agents</p><h2 id="agent-groups-title" className="mt-2 text-2xl font-black md:text-3xl">按岗位选择 AI 能力</h2><p className="mt-2 text-sm text-public-muted">先从一项具体工作开始，再逐步连接企业数据与协同流程。</p></div><span className="rounded-full bg-public-brand-soft px-3 py-1.5 text-xs font-bold text-public-brand">可下载 · 可配置 · 可演示</span></div>
          {loading ? <div className="mt-7 flex min-h-48 items-center justify-center gap-2 rounded-2xl border border-public-border bg-white text-sm text-public-muted shadow-public"><Loader2 className="h-5 w-5 animate-spin text-public-brand" />正在加载能力目录…</div> : market?.groups.length ? <div className="mt-7 grid items-stretch gap-5 md:grid-cols-2 xl:grid-cols-3">{market.groups.map((group, index) => { const Icon = ICONS[index % ICONS.length]; return <article key={group.title} className="group flex min-w-0 flex-col rounded-2xl border border-public-border bg-white p-5 shadow-public transition duration-200 hover:-translate-y-1 hover:border-public-brand/40 hover:shadow-[0_18px_36px_-24px_rgba(36,107,219,.6)] md:p-6"><div className="flex items-start justify-between gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-public-brand-soft text-public-brand"><Icon className="h-5 w-5" /></span><span className={group.demo ? 'badge badge-success' : 'badge badge-default'}>{group.demo ? '可演示' : '规划能力'}</span></div><h3 className="mt-5 text-xl font-black">{group.title}</h3><p className="mt-2 min-h-12 text-sm leading-6 text-public-muted">{group.summary}</p><div className="mt-5 space-y-2 border-t border-public-border/70 pt-4">{group.agents.map(agent => <div key={agent} className="flex items-center gap-2 text-xs font-medium text-public-muted"><Check className="h-3.5 w-3.5 text-emerald-600" />{agent}</div>)}</div><div className="mt-5 flex-1 border-t border-public-border/70 pt-4"><p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[.12em] text-public-muted"><Download className="h-3.5 w-3.5 text-public-brand" />推荐 GitHub skills</p>{group.skills.length ? <div className="space-y-2">{group.skills.map(skill => <SkillDownload key={skill.name} skill={skill} onDownload={downloadSkill} />)}</div> : <p className="rounded-xl bg-public-bg px-3 py-3 text-xs text-public-muted">该岗位的接入 Skill 正在整理中。</p>}</div><button type="button" onClick={() => group.demo ? navigate('/aia') : requestLogin(`/agent-market?agent=${encodeURIComponent(group.title)}`)} className="mt-5 inline-flex items-center gap-1 self-start text-xs font-bold text-public-brand">{group.demo ? '打开体验' : '预约配置'} <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" /></button></article>; })}</div> : <div className="mt-7 rounded-2xl border border-dashed border-public-border bg-white px-6 py-14 text-center text-sm text-public-muted">暂无可展示的 Agent 能力，请稍后重试。</div>}
        </section>
        <section className="relative mt-16 overflow-hidden rounded-3xl bg-public-brand px-6 py-8 text-white shadow-[0_18px_50px_-28px_rgba(36,107,219,.9)] md:mt-20 md:px-10 md:py-10"><div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full border-[36px] border-white/10" /><div className="relative flex flex-col justify-between gap-7 md:flex-row md:items-center"><div><p className="text-[11px] font-bold uppercase tracking-[.18em] text-white/65">Start with one workflow</p><h2 className="mt-2 text-2xl font-black md:text-3xl">先找到最值得交给 AI 的一件事</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">从一次真实询价或供应商寻源开始，明确数据、验收指标和实施边界，再逐步扩展到其他岗位。</p></div><button type="button" onClick={() => requestLogin('/agent-market')} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-bold text-public-brand transition hover:bg-public-brand-soft">预约业务诊断 <PhoneCall className="h-4 w-4" /></button></div></section>
      </div>
    </main>

    {selectedSkill && <div className="fixed inset-0 z-50 flex items-center justify-center bg-public-text/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="skill-dialog-title"><div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl md:p-7"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.14em] text-public-brand">Skill 已开始下载</p><h2 id="skill-dialog-title" className="mt-2 text-xl font-black">{selectedSkill.label}</h2></div><button type="button" onClick={() => setSelectedSkill(null)} className="rounded-xl p-2 text-public-muted transition hover:bg-public-bg hover:text-public-text" aria-label="关闭"><X className="h-5 w-5" /></button></div><div className="mt-6 rounded-2xl bg-public-bg p-4"><p className="flex items-center gap-2 text-sm font-bold"><Info className="h-4 w-4 text-public-brand" />如何使用</p><ol className="mt-3 space-y-2 text-sm leading-6 text-public-muted">{selectedSkill.usage.map((step, index) => <li key={step} className="flex gap-2"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-public-brand text-xs font-bold text-white">{index + 1}</span><span>{step}</span></li>)}</ol></div><div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-public-muted"><span>路径：{selectedSkill.path}</span><a href={selectedSkill.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-bold text-public-brand hover:underline">查看 GitHub 来源 <ExternalLink className="h-3.5 w-3.5" /></a></div><button type="button" onClick={() => downloadSkill(selectedSkill)} className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-public-brand px-4 py-3 text-sm font-bold text-white transition hover:bg-[#1C5CBD]"><Download className="h-4 w-4" />再次下载 ZIP</button></div></div>}
  </div>;
}
