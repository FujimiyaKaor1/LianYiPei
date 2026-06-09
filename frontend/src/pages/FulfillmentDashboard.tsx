import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, TrendingUp, Clock, Eye, EyeOff, Loader2, RefreshCw, ChevronUp, ChevronDown, Briefcase, Truck, ShieldCheck, Wallet, Package, Plus } from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, type ActiveFulfillmentItem, type FulfillmentDashboardData, type CaseItem } from '@/src/services/api';

const FulfillmentPipelineCard: React.FC<{ row: ActiveFulfillmentItem }> = ({ row }) => {
  const nodes = Array.isArray(row.logistics_nodes) ? row.logistics_nodes : [];
  const steps =
    nodes.length > 0
      ? nodes.map((n: unknown, i: number) => ({
          label: typeof n === 'object' && n !== null && 'label' in n ? String((n as { label?: string }).label) : `节点 ${i + 1}`,
          done: typeof n === 'object' && n !== null && 'done' in n ? Boolean((n as { done?: boolean }).done) : i === 0,
        }))
      : [
          { label: '物流', done: ['delivered', 'invoiced', 'verified'].includes(row.fulfillment_status) },
          { label: '质检', done: row.qc_status === 'passed' || row.qc_status === 'approved' },
          { label: '付款', done: row.payment_progress >= 100 },
        ];
  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-ink">{row.product_name}</p>
          <p className="mt-0.5 text-[10px] font-semibold uppercase text-ink-muted">
            {row.fulfillment_status} · 质检 {row.qc_status} · 付款 {Math.round(row.payment_progress)}%
          </p>
        </div>
        <span className="rounded-md border border-border bg-surface-subtle px-2 py-0.5 text-[10px] font-bold text-ink-muted">#{row.id}</span>
      </div>
      <div className="flex items-center gap-1">
        {steps.map((s, idx) => (
          <div key={idx} className="flex items-center flex-1 min-w-0">
            <div
              className={cn(
                'flex-1 h-1 rounded-full transition-colors',
                s.done ? 'bg-brand' : 'bg-surface-container',
              )}
            />
            {idx < steps.length - 1 && <div className="w-1 shrink-0" />}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap justify-between gap-1 text-[9px] font-bold uppercase text-ink-muted">
        {steps.map((s, idx) => (
          <span key={idx} className="flex items-center gap-1 min-w-0 truncate">
            {idx === 0 ? <Truck className="w-3 h-3 shrink-0" /> : idx === 1 ? <ShieldCheck className="w-3 h-3 shrink-0" /> : <Wallet className="w-3 h-3 shrink-0" />}
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function MiniLineChart({ data }: { data: { month: string; score: number }[] }) {
  if (!data.length) return <div className="flex h-24 items-center justify-center text-xs text-ink-faint">暂无趋势数据</div>;
  const scores = data.map(d => d.score);
  const min = Math.min(...scores) - 5;
  const max = Math.max(...scores) + 5;
  const range = max - min || 1;
  const w = 100 / Math.max(data.length - 1, 1);

  const points = data.map((d, i) => {
    const x = i * w;
    const y = 100 - ((d.score - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="relative h-28">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
        <polyline fill="none" stroke="#155EEF" strokeWidth="1.5" points={points} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="absolute bottom-0 left-0 right-0 flex justify-between px-1 text-[8px] text-ink-muted">
        <span>{data[0]?.month}</span>
        <span>{data[data.length - 1]?.month}</span>
      </div>
    </div>
  );
}

export default function FulfillmentDashboard() {
  const navigate = useNavigate();
  const { user, loading: authLoading, setIsLoginModalOpen } = useAuth();
  const { showToast } = useToast();
  const [dashData, setDashData] = useState<FulfillmentDashboardData | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(false);
  const [casesLoadFailed, setCasesLoadFailed] = useState(false);

  const load = async () => {
    setFetching(true);
    setError(false);
    setCasesLoadFailed(false);
    try {
      const [dashboard, caseRes] = await Promise.allSettled([
        api.getFulfillmentDashboard(),
        api.getCaseLibrary(),
      ]);
      if (dashboard.status === 'fulfilled') {
        setDashData(dashboard.value);
      } else {
        setDashData(null);
        setError(true);
      }
      if (caseRes.status === 'fulfilled') {
        setCases(caseRes.value.cases || []);
      } else {
        setCases([]);
        setCasesLoadFailed(true);
      }
    } catch {
      setDashData(null);
      setError(true);
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setIsLoginModalOpen(true); return; }
    void load();
  }, [authLoading, user]);

  const toggleCase = async (c: CaseItem) => {
    try {
      await api.toggleCaseVisibility(c.id, !c.is_public);
      setCases(prev => prev.map(item => item.id === c.id ? { ...item, is_public: !item.is_public } : item));
    } catch {
      showToast('操作失败，请重试', 'error');
    }
  };

  if (authLoading || fetching) {
    return <div className="flex items-center justify-center py-32"><Loader2 className="h-6 w-6 animate-spin text-brand" /></div>;
  }
  if (error || !dashData) {
    return (
      <div className="panel mx-auto flex max-w-md flex-col items-center p-12">
        <p className="mb-4 text-center text-sm text-ink-muted">网络异常，无法加载履约看板</p>
        <button type="button" onClick={() => void load()} className="btn-primary btn-sm gap-1.5">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  const activeList = dashData.active_fulfillments ?? [];

  const dimEntries = Object.entries(dashData.dimensions).filter(([, v]) => v !== 0);
  const maxDim = Math.max(...dimEntries.map(([, v]) => Math.abs(v as number)), 1);

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <section className="panel overflow-hidden">
        <div className="panel-header flex items-center justify-between px-6 py-5">
          <div>
            <h2 className="text-xl font-black text-ink">履约可信度看板</h2>
            <p className="mt-1 text-xs font-semibold text-ink-muted">从订单交付、质检、付款与案例公开度综合评估履约表现</p>
          </div>
          <button type="button" onClick={() => navigate('/orders')} className="btn-secondary btn-sm gap-1.5">
            <Plus className="h-3.5 w-3.5" /> 新建订单
          </button>
        </div>
      </section>
      {/* Top Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[
          { icon: Activity, label: '当前信用分', value: String(Math.round(dashData.current_score)), sub: '/ 100' },
          { icon: TrendingUp, label: '按时交付率', value: `${dashData.delivery_stats.own_rate}%`, sub: `行业 ${dashData.delivery_stats.industry_rate}%` },
          { icon: Clock, label: '已完成订单', value: String(dashData.delivery_stats.total_count), sub: `准时 ${dashData.delivery_stats.on_time_count}` },
          { icon: Briefcase, label: '合作案例', value: String(cases.length), sub: `公开 ${cases.filter(c => c.is_public).length}` },
        ].map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
            className="card-hover p-5"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-soft"><stat.icon className="h-4 w-4 text-brand" /></div>
              <span className="text-[10px] font-bold uppercase text-ink-muted">{stat.label}</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="metric-number text-2xl font-black text-ink">{stat.value}</span>
              <span className="text-xs text-ink-muted">{stat.sub}</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* 进行中履约 */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="panel overflow-hidden"
      >
        <div className="panel-header mb-0 flex items-center justify-between px-5 py-4">
          <h3 className="text-sm font-bold text-ink">进行中履约</h3>
          <span className="text-[10px] font-semibold text-ink-muted">{activeList.length} 条</span>
        </div>
        <div className="p-5">
          {activeList.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-border bg-surface-subtle px-4 py-14 text-center">
            <Package className="mb-3 h-10 w-10 text-ink-faint" strokeWidth={1.25} />
            <p className="mb-1 text-sm font-semibold text-ink-muted">暂无进行中的履约数据</p>
            <p className="mb-5 max-w-sm text-[11px] text-ink-muted">数据来自真实成交与履约链路，新建订单并推进履约后将在此展示。</p>
            <button
              type="button"
              className="btn-primary btn-sm gap-1.5"
              onClick={() => navigate('/orders')}
            >
              <Plus className="w-3.5 h-3.5" /> 新建
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {activeList.map((rawRow) => {
              const row = rawRow as ActiveFulfillmentItem;
              return <FulfillmentPipelineCard key={row.id} row={row} />;
            })}
          </div>
        )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* Credit Trend */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
          className="panel p-6"
        >
          <h3 className="mb-4 text-sm font-bold text-ink">信用分 12 个月趋势</h3>
          <MiniLineChart data={dashData.trend} />
        </motion.div>

        {/* Score Dimensions */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="panel p-6"
        >
          <h3 className="mb-4 text-sm font-bold text-ink">信用分维度构成</h3>
          <div className="space-y-3">
            {dimEntries.map(([label, val]) => {
              const v = val as number;
              return (
              <div key={label} className="flex items-center gap-3">
                <span className="w-16 shrink-0 text-xs text-ink-muted">{label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-container">
                  <div className={cn('h-full rounded-full', v >= 0 ? 'bg-brand' : 'bg-critical')} style={{ width: `${Math.min(100, Math.abs(v) / maxDim * 100)}%` }} />
                </div>
                <span className={cn('w-10 text-right text-xs font-bold', v >= 0 ? 'text-brand' : 'text-critical')}>
                  {v >= 0 ? '+' : ''}{v.toFixed(1)}
                </span>
              </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Recent History */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}
        className="panel p-6"
      >
        <h3 className="mb-4 text-sm font-bold text-ink">最近信用分变动</h3>
        {dashData.history.length === 0 ? (
          <p className="py-8 text-center text-xs text-ink-muted">暂无变动记录</p>
        ) : (
          <div className="divide-y divide-border">
            {dashData.history.map(h => (
              <div key={String(h.id)} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className={cn('flex h-7 w-7 items-center justify-center rounded-md', h.change_value >= 0 ? 'bg-brand-soft' : 'bg-critical-soft')}>
                    {h.change_value >= 0 ? <ChevronUp className="h-4 w-4 text-brand" /> : <ChevronDown className="h-4 w-4 text-critical" />}
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-ink">{h.reason || h.change_type}</p>
                    <p className="text-[10px] text-ink-muted">{h.created_at}</p>
                  </div>
                </div>
                <span className={cn('text-sm font-bold', h.change_value >= 0 ? 'text-brand' : 'text-critical')}>
                  {h.change_value >= 0 ? '+' : ''}{h.change_value}
                </span>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Case Library */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
        className="panel p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-ink">合作案例库</h3>
          <span className="text-[10px] font-semibold text-ink-muted">{cases.length} 条案例</span>
        </div>
        {casesLoadFailed && (
          <p className="mb-4 text-[11px] text-ink-muted">案例列表暂不可用（权限或网络），履约数据仍为实时结果。</p>
        )}
        {cases.length === 0 ? (
          <p className="py-8 text-center text-xs text-ink-muted">暂无合作案例</p>
        ) : (
          <div className="divide-y divide-border">
            {cases.map(c => (
              <div key={c.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-xs font-semibold text-ink">{c.product_category} — {c.buyer_name_masked}</p>
                  <p className="text-[10px] text-ink-muted">{c.cooperation_time} · {c.amount_range}</p>
                </div>
                <button
                  onClick={() => void toggleCase(c)}
                  className={cn(
                    'flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-bold transition-all',
                    c.is_public ? 'bg-brand text-white' : 'bg-surface-subtle text-ink-muted hover:bg-surface-container',
                  )}
                >
                  {c.is_public ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                  {c.is_public ? '公开' : '私密'}
                </button>
              </div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
