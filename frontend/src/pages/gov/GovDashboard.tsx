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
    if (level === 'red') return 'bg-critical-soft text-critical border-critical/20';
    if (level === 'yellow') return 'bg-risk-soft text-risk border-risk/20';
    return 'bg-brand-soft text-brand border-brand/20';
  };

  const getLevelLabel = (level: string) => {
    if (level === 'red') return '高危';
    if (level === 'yellow') return '中级';
    return '低级';
  };

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">

      {/* Welcome Banner */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="panel overflow-hidden"
      >
        <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="relative overflow-hidden bg-sidebar-bg p-7 text-white">
            <div className="absolute inset-0 bg-grid-fade opacity-10" />
            <div className="relative">
              <p className="mb-2 text-xs font-bold uppercase text-sidebar-text">产业监管平台</p>
              <h1 className="mb-3 text-2xl font-black">产业链健康监管大屏</h1>
              <p className="max-w-xl text-sm leading-6 text-sidebar-text">
                以质量标签与验厂认证守住企业端产品合规底线，结合预警与产业链图谱实现精准监管与补链强链。
              </p>
              {error && (
                <button onClick={() => void load()} className="btn-secondary btn-sm mt-5 gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" /> 重新加载
                </button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 bg-surface p-5">
            {[
              ['质量标签', '合规基线'],
              ['预警中心', '风险处置'],
              ['产业图谱', '链路洞察'],
              ['招商决策', '补链强链'],
            ].map(([label, sub]) => (
              <div key={label} className="rounded-md border border-border bg-surface-subtle p-4">
                <div className="text-sm font-bold text-ink">{label}</div>
                <div className="mt-1 text-[11px] font-semibold text-ink-muted">{sub}</div>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
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
              'card-hover p-5',
              item.accent ? 'border-risk/30' : '',
            )}
          >
            <div className="flex items-center gap-2 mb-3">
              <div className={cn('flex h-8 w-8 items-center justify-center rounded-md', item.accent ? 'bg-risk-soft' : 'bg-brand-soft')}>
                <item.icon className={cn('h-4 w-4', item.accent ? 'text-risk' : 'text-brand')} />
              </div>
              <span className="text-[10px] font-bold uppercase text-ink-muted">{item.label}</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              {statsLoading ? (
                <span className="inline-block h-9 w-14 animate-pulse rounded-lg bg-neutral-100" />
              ) : (
                <span className={cn('metric-number text-3xl font-black text-ink', item.accent && (stats?.alert_count ?? 0) > 0 ? 'text-risk' : '')}>
                  {item.value ?? '—'}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-[10px] font-semibold text-ink-muted">{item.sub}</p>
          </motion.div>
        ))}
      </div>

      {/* Neo4j 产业链预览 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="panel p-6"
      >
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-brand" />
            <div>
              <h3 className="text-sm font-bold text-ink">全平台产业链图谱（Neo4j）</h3>
              <p className="text-[10px] font-medium text-ink-muted">预览为采样子图，可拖拽缩放；完整画布见独立页。</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/gov/supply-chain')}
            className="btn-secondary btn-sm gap-1"
          >
            全屏查看 <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
        <GovSupplyChainGraph height={280} compact />
      </motion.div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* Recent Alerts */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="panel p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-ink">最近活跃预警</h3>
            <button
              onClick={() => navigate('/gov/alerts')}
              className="flex items-center gap-1 text-[10px] font-bold text-ink-muted transition-colors hover:text-brand"
            >
              查看全部 <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          {alertsLoading ? (
            <div className="space-y-2 py-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex animate-pulse gap-3 rounded-md p-3">
                  <div className="h-6 w-12 shrink-0 rounded bg-surface-container" />
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="h-3 w-3/4 rounded bg-surface-container" />
                    <div className="h-3 w-full rounded bg-surface-subtle" />
                  </div>
                </div>
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8">
              <ShieldAlert className="mb-2 h-8 w-8 text-ink-faint" />
              <p className="text-xs text-ink-muted">暂无活跃预警</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.slice(0, 5).map((alert) => (
                <div
                  key={alert.id}
                  onClick={() => navigate('/gov/alerts')}
                  className="group flex cursor-pointer items-center gap-3 rounded-md p-3 transition-colors hover:bg-surface-subtle"
                >
                  <span className={cn('text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0', getLevelColor(alert.level))}>
                    {getLevelLabel(alert.level)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="truncate text-xs font-semibold text-ink">{alert.product_name}</p>
                    <p className="truncate text-[10px] text-ink-muted">{alert.message}</p>
                  </div>
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-faint transition-colors group-hover:text-brand" />
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
          className="panel p-6"
        >
          <h3 className="mb-4 text-sm font-bold text-ink">快捷操作</h3>
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
                className="group flex w-full items-center gap-4 rounded-md border border-border p-4 text-left transition-all hover:border-brand/40 hover:shadow-elevation-1"
              >
                <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-md border transition-all', action.urgent ? 'border-risk/20 bg-risk-soft text-risk' : 'border-border bg-surface-subtle text-ink-muted group-hover:bg-brand-soft group-hover:text-brand')}>
                  <action.icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-ink">{action.label}</p>
                  <p className="text-[10px] text-ink-muted">{action.sub}</p>
                </div>
                <ArrowRight className="h-4 w-4 shrink-0 text-ink-faint transition-colors group-hover:text-brand" />
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
        className="panel flex items-center justify-between p-6"
      >
        <div>
          <p className="mb-1 text-sm font-bold text-ink">手动触发预警检查</p>
          <p className="text-xs text-ink-muted">对全部链内企业立即执行一次风险扫描，生成最新预警</p>
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
      {result && <span className="text-xs text-ink-muted">{result}</span>}
      <button
        onClick={() => void run()}
        disabled={running}
        className="btn-primary whitespace-nowrap disabled:opacity-50"
      >
        {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4 fill-white" />}
        立即扫描
      </button>
    </div>
  );
}
