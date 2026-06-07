import React, { useState, useEffect } from 'react';
import {
  Building2, TrendingUp, Users,
  ShieldAlert, Landmark, ChevronRight, Loader2,
  RefreshCw, ArrowRight, Zap, Network,
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type GovStatsData, type GovAlertItem } from '@/src/services/api';
import { useNavigate } from 'react-router-dom';
import { GovSupplyChainGraph } from '@/src/components/GovSupplyChainGraph';

export default function GovDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<GovStatsData | null>(null);
  const [alerts, setAlerts] = useState<GovAlertItem[]>([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    setError(false);
    setStatsLoading(true);
    api
      .getGovStats()
      .then(setStats)
      .catch(() => setError(true))
      .finally(() => setStatsLoading(false));

    setAlertsLoading(true);
    api
      .getGovAlertsList()
      .then((v) => setAlerts(Array.isArray(v) ? v : []))
      .catch(() => {})
      .finally(() => setAlertsLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const getLevelColor = (level: string) => {
    if (level === 'red') return 'bg-neutral-900 text-white border-neutral-900 shadow-sm';
    if (level === 'yellow') return 'bg-neutral-200 text-neutral-800 border-neutral-300';
    return 'bg-neutral-50 text-neutral-500 border-neutral-200';
  };

  const getLevelLabel = (level: string) => {
    if (level === 'red') return '高危';
    if (level === 'yellow') return '中级';
    return '低级';
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">

      {/* Welcome Banner */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-[#1C1C1E] to-black text-white p-8 rounded-[2rem] relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <Building2 className="w-48 h-48" />
        </div>
        <p className="text-xs font-bold uppercase tracking-widest text-white/50 mb-2">产业监管平台</p>
        <h1 className="text-2xl font-black tracking-tight mb-2">产业链健康监管大屏</h1>
        <p className="text-sm text-white/50 max-w-lg">
          以<strong className="text-white/80">质量标签与验厂认证</strong>守住企业端产品合规底线，结合预警与产业链图谱实现精准监管与补链强链。
        </p>
        {error && (
          <button onClick={() => void load()} className="mt-4 flex items-center gap-1.5 px-4 py-2 bg-white/10 text-white rounded-lg text-xs font-bold hover:bg-white/20 transition-all">
            <RefreshCw className="w-3.5 h-3.5" /> 重新加载
          </button>
        )}
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: Building2, label: '链内企业总数', value: stats?.enterprise_count, sub: '已注册企业' },
          { icon: TrendingUp, label: '活跃供应', value: stats?.supply_count, sub: '在售询盘' },
          { icon: Users, label: '活跃采购', value: stats?.demand_count, sub: '在途需求' },
          { icon: ShieldAlert, label: '当前活跃预警', value: stats?.alert_count, sub: '待处置', accent: (stats?.alert_count ?? 0) > 0 },
        ].map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className={cn(
              'bg-white rounded-2xl border shadow-sm p-5',
              item.accent ? 'border-neutral-300' : 'border-neutral-100',
            )}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', item.accent ? 'bg-neutral-900 shadow-sm' : 'bg-neutral-100')}>
                <item.icon className={cn('w-4 h-4', item.accent ? 'text-white' : 'text-neutral-600')} />
              </div>
              <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{item.label}</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              {statsLoading ? (
                <span className="inline-block h-9 w-14 animate-pulse rounded-lg bg-neutral-100" />
              ) : (
                <span className={cn('text-3xl font-black tracking-tight', item.accent && (stats?.alert_count ?? 0) > 0 ? 'text-black' : '')}>
                  {item.value ?? '—'}
                </span>
              )}
            </div>
            <p className="text-[10px] text-neutral-400 mt-0.5 font-medium">{item.sub}</p>
          </motion.div>
        ))}
      </div>

      {/* Neo4j 产业链预览 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="rounded-[2rem] border border-neutral-100 bg-white p-6 shadow-sm"
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-neutral-700" />
            <div>
              <h3 className="text-sm font-bold tracking-tight">全平台产业链图谱（Neo4j）</h3>
              <p className="text-[10px] text-neutral-400">预览为采样子图，可拖拽缩放；完整画布见独立页。</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/gov/supply-chain')}
            className="flex items-center gap-1 rounded-xl border border-neutral-200 px-4 py-2 text-xs font-bold text-neutral-700 hover:border-black"
          >
            全屏查看 <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <GovSupplyChainGraph height={280} compact />
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent Alerts */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold tracking-tight">最近活跃预警</h3>
            <button
              onClick={() => navigate('/gov/alerts')}
              className="text-[10px] font-bold text-neutral-500 hover:text-black flex items-center gap-1 transition-colors"
            >
              查看全部 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          {alertsLoading ? (
            <div className="space-y-2 py-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex animate-pulse gap-3 rounded-xl p-3">
                  <div className="h-6 w-12 shrink-0 rounded bg-neutral-100" />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="h-3 w-3/4 rounded bg-neutral-100" />
                    <div className="h-3 w-full rounded bg-neutral-50" />
                  </div>
                </div>
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8">
              <ShieldAlert className="w-8 h-8 text-neutral-200 mb-2" />
              <p className="text-xs text-neutral-400">暂无活跃预警</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.slice(0, 5).map((alert) => (
                <div
                  key={alert.id}
                  onClick={() => navigate('/gov/alerts')}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-neutral-50 cursor-pointer transition-colors group"
                >
                  <span className={cn('text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0', getLevelColor(alert.level))}>
                    {getLevelLabel(alert.level)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{alert.product_name}</p>
                    <p className="text-[10px] text-neutral-400 truncate">{alert.message}</p>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-neutral-300 group-hover:text-black shrink-0 transition-colors" />
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
        >
          <h3 className="text-sm font-bold tracking-tight mb-4">快捷操作</h3>
          <div className="space-y-3">
            {[
              { icon: Users, label: '质量标签', sub: '绿标与验厂：为企业端产品合规把关', path: '/gov/labels', urgent: false },
              { icon: ShieldAlert, label: '预警中心', sub: '查看并处置产业链风险预警', path: '/gov/alerts', urgent: (stats?.alert_count ?? 0) > 0 },
              { icon: Network, label: '产业链图谱', sub: 'Neo4j 全平台供应关系网络', path: '/gov/supply-chain', urgent: false },
              { icon: Landmark, label: '招商决策', sub: '分析产业链缺口，发布招商任务', path: '/gov/recruitment', urgent: false },
            ].map((action) => (
              <button
                key={action.path}
                onClick={() => navigate(action.path)}
                className="w-full flex items-center gap-4 p-4 rounded-xl border border-neutral-100 hover:border-black hover:shadow-sm transition-all group text-left"
              >
                <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border transition-all', action.urgent ? 'bg-black border-black text-white shadow-sm' : 'bg-neutral-50 border-neutral-200 text-neutral-600 group-hover:bg-neutral-100')}>
                  <action.icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold">{action.label}</p>
                  <p className="text-[10px] text-neutral-400">{action.sub}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-neutral-300 group-hover:text-black shrink-0 transition-colors" />
              </button>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Run Alert Checks */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-neutral-50 border border-neutral-100 rounded-2xl p-6 flex items-center justify-between"
      >
        <div>
          <p className="text-sm font-bold text-neutral-800 mb-1">手动触发预警检查</p>
          <p className="text-xs text-neutral-500">对全部链内企业立即执行一次风险扫描，生成最新预警</p>
        </div>
        <RunChecksButton onSuccess={() => void load()} />
      </motion.div>
    </div>
  );
}

function RunChecksButton({ onSuccess }: { onSuccess: () => void }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await api.runAlertChecks();
      setResult(`检查完成，共生成 ${res.alert_count} 条新预警`);
      onSuccess();
    } catch {
      setResult('检查失败，请稍后重试');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {result && <span className="text-xs text-neutral-500">{result}</span>}
      <button
        onClick={() => void run()}
        disabled={running}
        className="flex items-center gap-2 px-5 py-3 bg-black text-white rounded-xl text-xs font-bold hover:bg-neutral-800 transition-all shadow-lg shadow-black/10 disabled:opacity-50 whitespace-nowrap"
      >
        {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4 fill-white" />}
        立即扫描
      </button>
    </div>
  );
}
