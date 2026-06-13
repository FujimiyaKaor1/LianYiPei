import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Award,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  Factory,
  Gauge,
  LineChart,
  Loader2,
  MapPin,
  RefreshCw,
  TrendingUp,
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import {
  api,
  type AlertData,
  type CreditScoreData,
  type OrderStatistics,
  NETWORK_ERROR_MESSAGE,
} from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { CollaborationModal } from '@/src/components/CollaborationModal';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [creditScore, setCreditScore] = useState<CreditScoreData | null>(null);
  const [creditLoading, setCreditLoading] = useState(true);
  const [creditError, setCreditError] = useState<string | null>(null);

  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const [matches, setMatches] = useState<any[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(true);

  const [orderStats, setOrderStats] = useState<OrderStatistics | null>(null);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [quotesTotal, setQuotesTotal] = useState(0);
  const [quotesLoading, setQuotesLoading] = useState(true);
  const [isCollaborationOpen, setIsCollaborationOpen] = useState(false);

  const creditCacheKey = user?.id ? `credit_score_${user.id}` : '';

  const fetchCreditScore = async (showLoading = true) => {
    if (showLoading) setCreditLoading(true);
    setCreditError(null);
    if (!user?.id) {
      setCreditLoading(false);
      return;
    }
    try {
      const data = await api.fetchCreditScore(user.id);
      setCreditScore(data);
      if (creditCacheKey) {
        try {
          localStorage.setItem(creditCacheKey, JSON.stringify(data));
        } catch {
          /* quota exceeded or private browsing */
        }
      }
    } catch {
      setCreditError(NETWORK_ERROR_MESSAGE);
      if (creditCacheKey) {
        try {
          const raw = localStorage.getItem(creditCacheKey);
          if (raw) {
            setCreditScore(JSON.parse(raw) as CreditScoreData);
          } else {
            setCreditScore((prev) => prev ?? { credit_score: 70, level: '一般' });
          }
        } catch {
          setCreditScore((prev) => prev ?? { credit_score: 70, level: '一般' });
        }
      }
    } finally {
      setCreditLoading(false);
    }
  };

  const fetchAlerts = async (showLoading = true) => {
    if (showLoading) setAlertsLoading(true);
    setAlertsError(null);
    try {
      const data = await api.getAlerts({ page: 1, per_page: 20 });
      setAlerts(data.alerts || []);
    } catch {
      setAlertsError(NETWORK_ERROR_MESSAGE);
    } finally {
      setAlertsLoading(false);
    }
  };

  const fetchMatches = async () => {
    setMatchesLoading(true);
    try {
      const data = await api.fetchSuppliers({ query: '' });
      setMatches(data.suppliers?.slice(0, 4) || []);
    } catch (e) {
      console.error('fetch matches failed', e);
    } finally {
      setMatchesLoading(false);
    }
  };

  const fetchOperations = async (showLoading = true) => {
    if (showLoading) {
      setOrdersLoading(true);
      setQuotesLoading(true);
    }
    const [statsResult, quotesResult] = await Promise.allSettled([
      api.getOrderStatistics(),
      api.getQuotesList({ page: 1, per_page: 5 }),
    ]);

    if (statsResult.status === 'fulfilled') {
      setOrderStats(statsResult.value.statistics);
    }
    if (quotesResult.status === 'fulfilled') {
      setQuotesTotal(quotesResult.value.total || quotesResult.value.quotes?.length || 0);
    }

    setOrdersLoading(false);
    setQuotesLoading(false);
  };

  const refreshAll = async () => {
    setCreditLoading(true);
    setAlertsLoading(true);
    setOrdersLoading(true);
    setQuotesLoading(true);
    await Promise.allSettled([
      fetchCreditScore(false),
      fetchAlerts(false),
      fetchMatches(),
      fetchOperations(false),
    ]);
  };

  useEffect(() => {
    if (!user?.id) {
      return;
    }
    refreshAll();
  }, [user?.id]);

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'capacity_risk':
        return Factory;
      case 'supply_chain_break':
        return AlertTriangle;
      case 'business_risk':
        return LineChart;
      default:
        return AlertTriangle;
    }
  };

  const getAlertColor = (level: string) => {
    switch (level) {
      case 'red':
        return 'red';
      case 'yellow':
        return 'orange';
      case 'blue':
        return 'blue';
      default:
        return 'orange';
    }
  };

  const isInitialLoading = creditLoading || alertsLoading;
  const hasNetworkError = Boolean(creditError || alertsError);
  const scorePercent = Math.min(100, Math.max(0, Number(creditScore?.credit_score || 0)));
  const privilegeText = creditScore
    ? creditScore.credit_score >= 70
      ? '无限报价权益已解锁'
      : '基础报价权益：每日 3 次'
    : '权益状态加载中';
  const visibleAlerts = alerts.slice(0, 4);
  const visibleMatches = matches.slice(0, 4);
  const scoreLabel = creditScore?.level || '待评估';
  const supplyHealth = Math.max(42, Math.min(96, Math.round(scorePercent * 0.72 + 18)));
  const pendingOrders = (orderStats?.pending || 0) + (orderStats?.in_progress || 0);
  const completedOrders = orderStats?.completed || 0;
  const operationsLoading = ordersLoading || quotesLoading;
  const actionCards = [
    {
      label: '处理风险',
      value: alertsLoading ? '...' : `${alerts.length} 条`,
      note: '进入风险监测',
      path: '/risk',
      icon: AlertTriangle,
      tone: alerts.length ? 'risk' : 'trust',
    },
    {
      label: '推进订单',
      value: ordersLoading ? '...' : `${pendingOrders} 单`,
      note: '查看订单工作流',
      path: '/orders',
      icon: Factory,
      tone: pendingOrders ? 'brand' : 'trust',
    },
    {
      label: '寻找客商',
      value: matchesLoading ? '...' : `${visibleMatches.length} 家`,
      note: '打开智能匹配',
      path: '/matching',
      icon: Award,
      tone: 'trust',
    },
    {
      label: '维护报价',
      value: quotesLoading ? '...' : `${quotesTotal} 条`,
      note: '进入报价池',
      path: '/quote-pool',
      icon: LineChart,
      tone: quotesTotal ? 'brand' : 'trust',
    },
    {
      label: '真实性验证',
      value: '凭证',
      note: '上传交易凭证',
      onClick: () => setIsCollaborationOpen(true),
      icon: FileCheck2,
      tone: 'brand',
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4">
        <CollaborationModal
          open={isCollaborationOpen}
          onClose={() => setIsCollaborationOpen(false)}
          enterpriseId={user?.id ?? null}
          currentCreditScore={Number(creditScore?.credit_score || 70)}
        />
        {(isInitialLoading || hasNetworkError) && (
          <div className="panel flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2 text-xs font-medium text-ink-muted">
              {isInitialLoading ? (
                <Loader2 className="h-4 w-4 animate-spin text-brand" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-critical" />
              )}
              <span>
                {isInitialLoading ? '正在同步经营数据...' : '网络请求失败，请检查后端服务'}
              </span>
            </div>
            {hasNetworkError && (
              <button onClick={refreshAll} className="btn-secondary btn-sm gap-1.5">
                <RefreshCw className="h-3.5 w-3.5" /> 重试
              </button>
            )}
          </div>
        )}

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel overflow-hidden"
          >
            <div className="grid min-h-[300px] grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="relative overflow-hidden bg-brand-hero p-6 text-white">
                <div className="absolute inset-0 bg-grid-fade opacity-10" />
                <div className="relative flex h-full flex-col">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold text-sidebar-text">履约信用等级</p>
                      <div className="mt-3 flex items-end gap-3">
                        {creditLoading ? (
                          <Loader2 className="mb-2 h-8 w-8 animate-spin text-white/50" />
                        ) : (
                          <span className="metric-number text-[52px] font-black leading-none">
                            {creditScore?.credit_score ?? '--'}
                          </span>
                        )}
                        <span className="pb-2 text-sm font-semibold text-white/45">/ 100</span>
                      </div>
                    </div>
                    <div className="flex h-11 w-11 items-center justify-center rounded-md border border-white/10 bg-white/8">
                      <Gauge className="h-5 w-5 text-brand-muted" />
                    </div>
                  </div>

                  <div className="mt-6">
                    <div className="h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-brand-muted"
                        style={{ width: `${scorePercent}%` }}
                      />
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-white px-2 py-1 text-[11px] font-bold text-sidebar-bg">
                        {scoreLabel}
                      </span>
                      <span className="rounded-md border border-trust/30 bg-trust/12 px-2 py-1 text-[11px] font-bold text-trust">
                        {privilegeText}
                      </span>
                    </div>
                  </div>

                  <div className="mt-auto grid grid-cols-3 gap-3 pt-8">
                    {[
                      ['履约健康', `${supplyHealth}%`],
                      ['待处理预警', String(alerts.length)],
                      ['待推进订单', operationsLoading ? '...' : String(pendingOrders)],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border border-white/10 bg-white/6 p-3">
                        <div className="metric-number text-lg font-bold">{value}</div>
                        <div className="mt-1 text-[10px] font-medium text-white/45">{label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-col bg-surface p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold text-ink-muted">经营动作建议</p>
                    <h3 className="mt-2 text-xl font-bold text-ink">先处理风险，再推进履约</h3>
                    <p className="mt-3 max-w-md text-sm leading-6 text-ink-muted">
                      根据当前信用、预警、订单和报价数据，把企业每天最该处理的经营动作集中到这里。
                    </p>
                  </div>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-trust-soft text-trust">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-2">
                  {actionCards.map((action) => {
                    const ActionIcon = action.icon;
                    return (
                      <button
                        key={action.label}
                        type="button"
                        onClick={() => {
                          if ('onClick' in action && action.onClick) {
                            action.onClick();
                            return;
                          }
                          if ('path' in action && action.path) {
                            navigate(action.path);
                          }
                        }}
                        className="rounded-md border border-border bg-surface-subtle p-3 text-left transition-colors hover:border-border-strong hover:bg-surface"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="metric-number text-sm font-bold text-ink">
                              {action.value}
                            </div>
                            <div className="mt-1 text-[10px] font-medium text-ink-muted">
                              {action.label}
                            </div>
                          </div>
                          <div
                            className={cn(
                              'flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
                              action.tone === 'risk'
                                ? 'bg-risk-soft text-risk'
                                : action.tone === 'brand'
                                  ? 'bg-brand-soft text-brand'
                                  : 'bg-trust-soft text-trust',
                            )}
                          >
                            <ActionIcon className="h-3.5 w-3.5" />
                          </div>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2 text-[10px] font-semibold text-ink-muted">
                          <span>{action.note}</span>
                          <ArrowRight className="h-3 w-3" />
                        </div>
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  onClick={() => navigate('/fulfillment')}
                  className="btn-primary mt-auto w-full gap-2"
                >
                  查看履约看板
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 }}
            className="grid grid-cols-1 gap-4 sm:grid-cols-3 xl:grid-cols-1"
          >
            {[
              {
                label: '供应链健康',
                value: `${supplyHealth}%`,
                note: '综合信用与履约趋势',
                icon: TrendingUp,
                tone: 'brand',
              },
              {
                label: '待推进订单',
                value: ordersLoading ? '...' : String(pendingOrders),
                note: `已完成 ${completedOrders} 单`,
                icon: Factory,
                tone: pendingOrders ? 'brand' : 'trust',
              },
              {
                label: '匹配机会',
                value: matchesLoading ? '...' : String(matches.length),
                note: '可推进客商',
                icon: Award,
                tone: 'trust',
              },
            ].map((item) => (
              <div key={item.label} className="panel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-ink-muted">{item.label}</p>
                    <div className="metric-number mt-2 text-3xl font-black text-ink">
                      {item.value}
                    </div>
                  </div>
                  <div
                    className={cn(
                      'flex h-9 w-9 items-center justify-center rounded-md',
                      item.tone === 'risk'
                        ? 'bg-risk-soft text-risk'
                        : item.tone === 'trust'
                          ? 'bg-trust-soft text-trust'
                          : 'bg-brand-soft text-brand',
                    )}
                  >
                    <item.icon className="h-4.5 w-4.5" />
                  </div>
                </div>
                <p className="mt-3 text-xs font-medium text-ink-muted">{item.note}</p>
              </div>
            ))}
          </motion.div>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="panel min-h-[320px] overflow-hidden"
          >
            <div className="panel-header flex items-center justify-between px-5 py-4">
              <div>
                <h3 className="text-base font-bold text-ink">风险自检与预警</h3>
                <p className="mt-1 text-xs font-medium text-ink-muted">按影响面和处理紧急度排序</p>
              </div>
              {!alertsLoading && !alertsError && alerts.length > 0 && (
                <span className="rounded-md bg-critical-soft px-2 py-1 text-[11px] font-bold text-critical">
                  {alerts.length} 条待处理
                </span>
              )}
            </div>

            <div className="p-3">
              {alertsLoading ? (
                <div className="flex h-48 flex-col items-center justify-center text-ink-muted">
                  <Loader2 className="h-6 w-6 animate-spin text-brand" />
                  <p className="mt-2 text-xs font-medium">正在加载预警信息...</p>
                </div>
              ) : alertsError ? (
                <div className="flex h-48 flex-col items-center justify-center text-center">
                  <p className="text-xs font-semibold text-critical">网络请求失败，请检查后端服务</p>
                  <button onClick={() => fetchAlerts()} className="btn-secondary btn-sm mt-3 gap-1.5">
                    <RefreshCw className="h-3.5 w-3.5" /> 重试
                  </button>
                </div>
              ) : visibleAlerts.length === 0 ? (
                <div className="flex h-48 flex-col items-center justify-center text-ink-muted">
                  <CheckCircle2 className="mb-2 h-7 w-7 text-trust" />
                  <p className="text-xs font-semibold">当前无风险预警</p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {visibleAlerts.map((item, i) => {
                    const Icon = getAlertIcon(item.alert_type);
                    const color = getAlertColor(item.level);
                    return (
                      <button
                        key={item.id || i}
                        type="button"
                        className="group flex w-full items-center gap-3 px-2 py-3 text-left transition-colors hover:bg-surface-subtle"
                      >
                        <div
                          className={cn(
                            'flex h-9 w-9 shrink-0 items-center justify-center rounded-md',
                            color === 'orange'
                              ? 'bg-risk-soft text-risk'
                              : color === 'red'
                                ? 'bg-critical-soft text-critical'
                                : 'bg-brand-soft text-brand',
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-bold text-ink">
                            {item.message || item.product_name}
                          </p>
                          <p className="mt-1 truncate text-xs font-medium text-ink-muted">
                            {item.suggestion || '请及时关注并处理该风险。'}
                          </p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-ink-faint transition-transform group-hover:translate-x-0.5" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14 }}
            className="panel min-h-[320px] overflow-hidden"
          >
            <div className="panel-header flex items-center justify-between px-5 py-4">
              <div>
                <h3 className="text-base font-bold text-ink">智能匹配推荐</h3>
                <p className="mt-1 text-xs font-medium text-ink-muted">优先展示高信用、近距离、可履约客商</p>
              </div>
              <button onClick={() => navigate('/matching')} className="btn-secondary btn-sm gap-1.5">
                查看全部 <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="p-3">
              {matchesLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-brand" />
                </div>
              ) : visibleMatches.length === 0 ? (
                <div className="flex h-48 items-center justify-center text-xs font-medium text-ink-muted">
                  暂无推荐
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                  {visibleMatches.map((item, i) => (
                    <button
                      key={item.id || i}
                      type="button"
                      onClick={() => navigate('/matching')}
                      className="card-hover min-w-0 p-4 text-left"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <h4 className="min-w-0 truncate text-sm font-bold text-ink">
                          {item.name}
                        </h4>
                        <span className="shrink-0 rounded-md border border-border bg-surface-subtle px-1.5 py-0.5 text-[10px] font-bold text-ink-muted">
                          {(item.tags && item.tags[0]) || '高信用企业'}
                        </span>
                      </div>
                      <div className="mt-4 flex min-w-0 flex-wrap items-center gap-3 text-xs font-medium text-ink-muted">
                        <span className="flex min-w-0 items-center gap-1">
                          <MapPin className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{item.address || '未知地区'}</span>
                        </span>
                        <span className="flex items-center gap-1 text-trust">
                          <Award className="h-3.5 w-3.5" />
                          {item.match || item.score || '90%'} 匹配度
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </section>
    </div>
  );
}
