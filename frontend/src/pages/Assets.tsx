import React, { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  Award, 
  Plus, 
  FileText, 
  Lock, 
  Database,
  MapPin,
  Building2,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Sparkles
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api, type EnterpriseAssetData, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

export default function Assets() {
  const [data, setData] = useState<EnterpriseAssetData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      const res = await api.getAssets();
      setData(res.assets || null);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-neutral-300">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-neutral-400" />
      </div>
    );
  }

  if (errorText || !data) {
    return (
      <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-8 text-xs text-red-600 font-medium flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-8 h-8 opacity-80" />
        {errorText || "无法加载企业画像数据"}
        <button onClick={() => void loadData()} className="mt-2 text-white bg-red-500 hover:bg-red-600 px-4 py-2 rounded-lg font-bold">重新加载</button>
      </div>
    );
  }

  const tags = Array.isArray(data.tags) ? data.tags : [];
  const qualifications = Array.isArray(data.qualifications) ? data.qualifications : [];
  const dataAuth = Array.isArray(data.data_auth) ? data.data_auth : [];
  const creditBreakdown = Array.isArray(data.credit_breakdown) ? data.credit_breakdown : [];
  const activeAuthCount = dataAuth.filter((item) => item.status === '已连接').length;

  return (
    <div className="mx-auto w-full max-w-[1440px] space-y-8 pb-8">
      {/* Identity Banner */}
      <section className="relative overflow-hidden rounded-[28px] bg-gradient-to-br from-[#155EEF] via-[#2563EB] to-[#123A73] p-6 text-white shadow-[0_20px_55px_-28px_rgba(21,94,239,.7)] sm:p-8 lg:p-10">
        <div className="pointer-events-none absolute -right-28 -top-36 h-[460px] w-[460px] rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 left-1/3 h-[300px] w-[560px] rounded-full bg-cyan-300/10 blur-3xl" />
        
        <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-5 sm:gap-7">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[22px] bg-white text-3xl font-black text-brand shadow-xl sm:h-24 sm:w-24 sm:text-4xl">
              {data.name.slice(0, 1)}
            </div>
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-3">
                <h1 className="truncate text-2xl font-extrabold tracking-tight text-white sm:text-3xl lg:text-4xl">{data.name}</h1>
                {data.is_certified && (
                  <span className="rounded-full border border-emerald-200/30 bg-emerald-300/15 px-3 py-1 text-[10px] font-bold tracking-widest text-emerald-100">已认证</span>
                )}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium text-blue-100/80">
                <span className="flex items-center gap-2"><MapPin className="h-4 w-4 text-blue-200" /> {data.location}</span>
                <span className="flex items-center gap-2"><Building2 className="h-4 w-4 text-blue-200" /> 制造业 · {data.industry_tag}</span>
                {tags.slice(0, 1).map((tag, i) => (
                  <span key={i} className="flex items-center gap-2"><Award className="h-4 w-4 text-blue-200" /> {tag}</span>
                ))}
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-3 sm:flex sm:gap-8 lg:pr-2">
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-4 text-left backdrop-blur-sm sm:min-w-[128px] sm:text-center">
              <div className="text-3xl font-black tracking-tight sm:text-4xl">{data.credit_score == null ? '—' : data.credit_score}</div>
              <div className="mt-1 text-[10px] font-bold tracking-widest text-blue-100/70">履约信用分</div>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-4 text-left backdrop-blur-sm sm:min-w-[128px] sm:text-center">
              <div className="text-3xl font-black tracking-tight sm:text-4xl">{data.patent_count}</div>
              <div className="mt-1 text-[10px] font-bold tracking-widest text-blue-100/70">核心专利</div>
            </div>
          </div>
        </div>
      </section>

      {/* Grid Content */}
      <section className="grid grid-cols-12 gap-6 lg:gap-8">
        {/* Left: Certifications & Data */}
        <div className="col-span-12 space-y-8 lg:col-span-8">
          {/* Certifications */}
          <div className="space-y-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Business credentials</p>
                <h3 className="mt-1 text-xl font-bold text-ink">企业资质与证书</h3>
              </div>
              <button className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-bold text-ink-muted transition-colors hover:bg-brand-soft hover:text-brand">
                上传新证书 <Plus className="w-4 h-4" />
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {qualifications.map((cert, i) => (
                <div key={i} className="group flex items-center justify-between rounded-2xl border border-border bg-surface-raised p-4 shadow-elevation-1 transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-elevation-2">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand transition-colors group-hover:bg-brand group-hover:text-white">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="truncate text-sm font-bold text-ink">{cert.title}</h4>
                      <p className="mt-1 text-[10px] text-ink-muted">{cert.date}</p>
                    </div>
                  </div>
                  {cert.status === '有效' ? <ShieldCheck className="h-5 w-5 shrink-0 text-success" /> : <CircleDashed className="h-5 w-5 shrink-0 text-ink-faint" />}
                </div>
              ))}
              {qualifications.length === 0 && (
                <div className="col-span-2 flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface-raised px-6 py-10 text-center">
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-brand-soft text-brand"><FileText className="h-5 w-5" /></div>
                  <p className="text-sm font-semibold text-ink-soft">暂无资质信息</p>
                  <p className="mt-1 text-xs text-ink-muted">上传证书后，企业可信度信息会在这里集中展示</p>
                </div>
              )}
            </div>
          </div>

          {/* Data Auth */}
          <div className="space-y-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Connected sources</p>
                <h3 className="mt-1 text-xl font-bold text-ink">数据授权接口</h3>
              </div>
              <span className="rounded-full bg-success-soft px-2.5 py-1 text-[11px] font-bold text-success">{activeAuthCount} 个已连接</span>
            </div>
            <div className="overflow-hidden rounded-2xl border border-border bg-surface-raised shadow-elevation-1">
              <div className="flex items-center justify-between border-b border-border/60 px-5 py-4 sm:px-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-soft text-brand"><Database className="h-4 w-4" /></span>
                  <div><span className="block text-sm font-bold text-ink">外部系统同步状态</span><span className="mt-0.5 block text-[10px] text-ink-muted">数据授权后自动同步业务信息</span></div>
                </div>
                <span className="hidden text-[10px] font-bold text-ink-muted sm:block">最后同步：10分钟前</span>
              </div>
              <div className="divide-y divide-border/50">
                {dataAuth.map((sys, i) => (
                  <div key={i} className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-surface-subtle/60 sm:px-6">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface-subtle">
                        <Building2 className="h-5 w-5 text-ink-muted" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="truncate text-sm font-bold text-ink">{sys.name}</h4>
                        <p className="mt-1 truncate text-[10px] text-ink-muted">同步内容：{sys.data}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className={cn(
                        "rounded-full px-2.5 py-1 text-[10px] font-bold",
                        sys.status === '已连接' ? "bg-success-soft text-success" : "bg-surface-subtle text-ink-muted"
                      )}>{sys.status}</span>
                      <button aria-label={sys.status === '已连接' ? '查看授权状态' : '连接外部系统'} className="rounded-lg p-2 transition-all hover:bg-surface-subtle">
                        {sys.status === '已连接' ? <Lock className="h-4 w-4 text-ink-muted" /> : <Plus className="h-4 w-4 text-ink-muted" />}
                      </button>
                    </div>
                  </div>
                ))}
                {dataAuth.length === 0 && <div className="flex flex-col items-center justify-center px-6 py-10 text-center"><CircleDashed className="mb-3 h-7 w-7 text-ink-faint" /><p className="text-sm font-semibold text-ink-soft">暂无授权接口</p><p className="mt-1 text-xs text-ink-muted">连接外部系统后，可在这里查看同步状态</p></div>}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Credit */}
        <div className="col-span-12 lg:col-span-4">
          {/* Credit Score Detail */}
          <div className="rounded-2xl border border-border bg-surface-container-highest/70 p-6 shadow-elevation-1 sm:p-7">
            <div className="mb-7 flex items-start justify-between gap-4">
              <div><p className="eyebrow text-brand">Trust profile</p><h4 className="mt-1 text-lg font-bold text-ink">信用分构成</h4></div>
              <Sparkles className="h-5 w-5 text-brand" />
            </div>
            <div className="space-y-5">
              {creditBreakdown.map((item, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between text-xs font-bold">
                    <span className="text-ink-soft">{item.label}</span>
                    <span className="text-brand">{item.score}<span className="ml-0.5 text-[10px] text-ink-muted">分</span></span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/70">
                    <div 
                      className={cn("h-full rounded-full transition-all duration-1000", item.score > 80 ? 'bg-brand-solid' : 'bg-ink-faint')}
                      style={{ width: `${Math.max(0, Math.min(100, item.score))}%` }}>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {creditBreakdown.length === 0 && <div className="rounded-xl border border-dashed border-border bg-white/30 px-4 py-6 text-center text-xs text-ink-muted">暂无可用信用事件</div>}
            <p className="mt-7 flex items-start gap-2 border-t border-white/60 pt-5 text-[11px] leading-relaxed text-ink-muted">
              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
              * 这里只展示已持久化的信用事件和授权数据；缺少证据时不会补出信用分。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
