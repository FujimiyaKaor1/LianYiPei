import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, TrendingUp, Clock, Eye, EyeOff, Loader2, RefreshCw, ChevronUp, ChevronDown, Briefcase, Truck, ShieldCheck, Wallet, Package, Plus } from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { api, type ActiveFulfillmentItem, type FulfillmentDashboardData, type CaseItem } from '@/src/services/api';

function FulfillmentPipelineCard({ row }: { row: ActiveFulfillmentItem }) {
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
    <div className="rounded-xl border border-neutral-100 bg-neutral-50/50 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-neutral-900 tracking-tight">{row.product_name}</p>
          <p className="text-[10px] text-neutral-400 mt-0.5 font-medium uppercase tracking-wide">
            {row.fulfillment_status} · 质检 {row.qc_status} · 付款 {Math.round(row.payment_progress)}%
          </p>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-white border border-neutral-200 text-neutral-600">#{row.id}</span>
      </div>
      <div className="flex items-center gap-1">
        {steps.map((s, idx) => (
          <div key={idx} className="flex items-center flex-1 min-w-0">
            <div
              className={cn(
                'flex-1 h-1 rounded-full transition-colors',
                s.done ? 'bg-black' : 'bg-neutral-200',
              )}
            />
            {idx < steps.length - 1 && <div className="w-1 shrink-0" />}
          </div>
        ))}
      </div>
      <div className="flex justify-between gap-1 flex-wrap text-[9px] font-bold text-neutral-400 uppercase tracking-widest">
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
  if (!data.length) return <div className="h-24 flex items-center justify-center text-xs text-neutral-300">暂无趋势数据</div>;
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
        <polyline fill="none" stroke="black" strokeWidth="1.5" points={points} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-[8px] text-neutral-400 px-1">
        <span>{data[0]?.month}</span>
        <span>{data[data.length - 1]?.month}</span>
      </div>
    </div>
  );
}

export default function FulfillmentDashboard() {
  const navigate = useNavigate();
  const { user, loading: authLoading, setIsLoginModalOpen } = useAuth();
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
    } catch { /* ignore */ }
  };

  if (authLoading || fetching) {
    return <div className="flex items-center justify-center py-32"><Loader2 className="w-6 h-6 animate-spin text-neutral-300" /></div>;
  }
  if (error || !dashData) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-100 p-12 flex flex-col items-center max-w-md mx-auto">
        <p className="text-sm text-neutral-500 mb-4 text-center">网络异常，无法加载履约看板</p>
        <button type="button" onClick={() => void load()} className="flex items-center gap-1.5 px-4 py-2 bg-neutral-900 text-white rounded-lg text-xs font-bold hover:bg-neutral-800">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  const activeList = dashData.active_fulfillments ?? [];

  const dimEntries = Object.entries(dashData.dimensions).filter(([, v]) => v !== 0);
  const maxDim = Math.max(...dimEntries.map(([, v]) => Math.abs(v)), 1);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { icon: Activity, label: '当前信用分', value: String(Math.round(dashData.current_score)), sub: '/ 100' },
          { icon: TrendingUp, label: '按时交付率', value: `${dashData.delivery_stats.own_rate}%`, sub: `行业 ${dashData.delivery_stats.industry_rate}%` },
          { icon: Clock, label: '已完成订单', value: String(dashData.delivery_stats.total_count), sub: `准时 ${dashData.delivery_stats.on_time_count}` },
          { icon: Briefcase, label: '合作案例', value: String(cases.length), sub: `公开 ${cases.filter(c => c.is_public).length}` },
        ].map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
            className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-5"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-neutral-100 flex items-center justify-center"><stat.icon className="w-4 h-4 text-neutral-600" /></div>
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{stat.label}</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-black tracking-tight">{stat.value}</span>
              <span className="text-xs text-neutral-400">{stat.sub}</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* 进行中履约 */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold tracking-tight">进行中履约</h3>
          <span className="text-[10px] text-neutral-400 font-medium">{activeList.length} 条</span>
        </div>
        {activeList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 px-4 text-center rounded-xl border border-dashed border-neutral-200 bg-neutral-50/80">
            <Package className="w-10 h-10 text-neutral-300 mb-3" strokeWidth={1.25} />
            <p className="text-sm font-medium text-neutral-500 mb-1">暂无进行中的履约数据</p>
            <p className="text-[11px] text-neutral-400 mb-5 max-w-sm">数据来自真实成交与履约链路，新建订单并推进履约后将在此展示。</p>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-neutral-900 text-white text-xs font-bold hover:bg-neutral-800"
              onClick={() => navigate('/orders')}
            >
              <Plus className="w-3.5 h-3.5" /> 新建
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {activeList.map(row => (
              <FulfillmentPipelineCard key={row.id} row={row} />
            ))}
          </div>
        )}
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Credit Trend */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
          className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
        >
          <h3 className="text-sm font-bold mb-4 tracking-tight">信用分 12 个月趋势</h3>
          <MiniLineChart data={dashData.trend} />
        </motion.div>

        {/* Score Dimensions */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
        >
          <h3 className="text-sm font-bold mb-4 tracking-tight">信用分维度构成</h3>
          <div className="space-y-3">
            {dimEntries.map(([label, val]) => (
              <div key={label} className="flex items-center gap-3">
                <span className="w-16 text-xs text-neutral-500 shrink-0">{label}</span>
                <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
                  <div className={cn('h-full rounded-full', val >= 0 ? 'bg-black' : 'bg-red-400')} style={{ width: `${Math.min(100, Math.abs(val) / maxDim * 100)}%` }} />
                </div>
                <span className={cn('text-xs font-bold w-10 text-right', val >= 0 ? 'text-black' : 'text-red-500')}>
                  {val >= 0 ? '+' : ''}{val.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Recent History */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}
        className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
      >
        <h3 className="text-sm font-bold mb-4 tracking-tight">最近信用分变动</h3>
        {dashData.history.length === 0 ? (
          <p className="text-xs text-neutral-400 text-center py-8">暂无变动记录</p>
        ) : (
          <div className="divide-y divide-neutral-50">
            {dashData.history.map(h => (
              <div key={String(h.id)} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className={cn('w-7 h-7 rounded-full flex items-center justify-center', h.change_value >= 0 ? 'bg-green-50' : 'bg-red-50')}>
                    {h.change_value >= 0 ? <ChevronUp className="w-4 h-4 text-green-600" /> : <ChevronDown className="w-4 h-4 text-red-500" />}
                  </div>
                  <div>
                    <p className="text-xs font-medium">{h.reason || h.change_type}</p>
                    <p className="text-[10px] text-neutral-400">{h.created_at}</p>
                  </div>
                </div>
                <span className={cn('text-sm font-bold', h.change_value >= 0 ? 'text-green-600' : 'text-red-500')}>
                  {h.change_value >= 0 ? '+' : ''}{h.change_value}
                </span>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Case Library */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
        className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold tracking-tight">合作案例库</h3>
          <span className="text-[10px] text-neutral-400 font-medium">{cases.length} 条案例</span>
        </div>
        {casesLoadFailed && (
          <p className="text-[11px] text-neutral-400 mb-4">案例列表暂不可用（权限或网络），履约数据仍为实时结果。</p>
        )}
        {cases.length === 0 ? (
          <p className="text-xs text-neutral-400 text-center py-8">暂无合作案例</p>
        ) : (
          <div className="divide-y divide-neutral-50">
            {cases.map(c => (
              <div key={c.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-xs font-medium">{c.product_category} — {c.buyer_name_masked}</p>
                  <p className="text-[10px] text-neutral-400">{c.cooperation_time} · {c.amount_range}</p>
                </div>
                <button
                  onClick={() => void toggleCase(c)}
                  className={cn(
                    'flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-bold transition-all',
                    c.is_public ? 'bg-black text-white' : 'bg-neutral-100 text-neutral-500 hover:bg-neutral-200',
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
