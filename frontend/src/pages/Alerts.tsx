import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  ShieldAlert,
  Info,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Sparkles,
  ArrowRight,
  Loader2,
  RefreshCw,
  LogIn,
  Search,
  AlertCircle,
  Cpu,
  Zap,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, type AlertData } from '@/src/services/api';

// ── 工具函数 ──────────────────────────────────────────────────────────────

function getLevelLabel(level: string): string {
  if (level === 'red') return '高级';
  if (level === 'yellow') return '中级';
  return '低级';
}

function getLevelBadgeClass(level: string): string {
  if (level === 'red') return 'bg-red-600 text-white';
  if (level === 'yellow') return 'bg-amber-500 text-white';
  return 'bg-blue-500 text-white';
}

function formatTime(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffH = diffMs / (1000 * 60 * 60);
  if (diffH < 1) return '刚刚';
  if (diffH < 24) return `${Math.round(diffH)} 小时前`;
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
}

function getAlertTitle(alert: AlertData): string {
  const typeMap: Record<string, string> = {
    capacity_risk: '预警：产能利用率连续偏低',
    supply_chain_break: '预警：供应链断链风险',
    business_risk: '预警：企业经营信用异常',
    credit_anomaly: '预警：信用分快速下滑',
  };
  return typeMap[alert.alert_type] || `预警：${alert.product_name}`;
}

// ── 极简迷你柱状图 ────────────────────────────────────────────────────────

function MiniBarChart({ data }: { data: number[] }) {
  const maxVal = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-1 h-12">
      {data.map((val, idx) => {
        const heightPct = Math.round((val / maxVal) * 100);
        const isLast2 = idx >= data.length - 2;
        return (
          <motion.div
            key={idx}
            initial={{ height: 0 }}
            animate={{ height: `${heightPct}%` }}
            transition={{ delay: idx * 0.05, duration: 0.4, ease: 'easeOut' }}
            className={cn(
              'flex-1 rounded-[2px]',
              isLast2 ? 'bg-brand-solid' : 'bg-neutral-300',
            )}
            style={{ minHeight: 3 }}
          />
        );
      })}
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────────────────

export default function Alerts() {
  const { user, loading: authLoading, setIsLoginModalOpen } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [fetching, setFetching] = useState(false);
  const [loadIssue, setLoadIssue] = useState(false);
  const [activeAlertId, setActiveAlertId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTab, setFilterTab] = useState<'all' | 'unread' | 'risk'>('all');

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setIsLoginModalOpen(true);
      setAlerts([]);
      setLoadIssue(false);
      setFetching(false);
      return;
    }
    let cancelled = false;
    const run = async () => {
      setFetching(true);
      setLoadIssue(false);
      try {
        const data = await api.getAlerts({ page: 1, per_page: 50 });
        if (cancelled) return;
        const list = Array.isArray(data.alerts) ? data.alerts : [];
        setAlerts(list);
        if (list.length > 0) setActiveAlertId(list[0].id);
      } catch (error) {
        if (cancelled) return;
        setAlerts([]);
        setLoadIssue(true);
      } finally {
        if (!cancelled) setFetching(false);
      }
    };
    void run();
    return () => { cancelled = true; };
  }, [authLoading, user, setIsLoginModalOpen]);

  const refetch = () => {
    if (!user || authLoading) { setIsLoginModalOpen(true); return; }
    void (async () => {
      setFetching(true);
      setLoadIssue(false);
      try {
        const data = await api.getAlerts({ page: 1, per_page: 50 });
        const list = Array.isArray(data.alerts) ? data.alerts : [];
        setAlerts(list);
        if (list.length > 0) setActiveAlertId(list[0].id);
      } catch {
        setAlerts([]);
        setLoadIssue(true);
      } finally {
        setFetching(false);
      }
    })();
  };

  const filteredAlerts = alerts.filter(a => {
    if (searchQuery && !a.product_name.includes(searchQuery) && !a.message.includes(searchQuery)) return false;
    if (filterTab === 'risk' && a.level !== 'red') return false;
    return true;
  });

  const activeAlert = alerts.find(a => a.id === activeAlertId) || alerts[0] || null;

  const showLoginHint = !authLoading && !user;
  const showLoader = authLoading || (Boolean(user) && fetching);

  return (
    <div className="h-[calc(100vh-5rem)] max-h-[860px] flex gap-5 max-w-7xl mx-auto w-full font-sans antialiased">

      {/* ── LEFT: 消息列表 (Master) ─────────── */}
      <div className="w-[340px] shrink-0 flex flex-col bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden">

        {/* 搜索框 */}
        <div className="px-4 pt-4 pb-3 shrink-0 border-b border-neutral-100">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400" />
            <input
              type="text"
              placeholder="搜索消息或预警..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-neutral-50 border border-neutral-100 rounded-lg text-xs font-medium text-neutral-700 placeholder:text-neutral-400 focus:outline-none focus:ring-0 focus:border-neutral-300 transition-all"
            />
          </div>

          {/* 筛选 Tabs */}
          <div className="flex items-center gap-1 mt-3">
            {[
              { key: 'all', label: '所有消息' },
              { key: 'unread', label: '未读' },
              { key: 'risk', label: '风险预警' },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setFilterTab(tab.key as typeof filterTab)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-[10px] font-bold transition-all',
                  filterTab === tab.key
                    ? 'bg-brand-solid text-white'
                    : 'text-neutral-500 hover:text-black hover:bg-neutral-100'
                )}
              >
                {tab.label}
              </button>
            ))}
            {alerts.length > 0 && (
              <span className="ml-auto text-[9px] font-bold text-neutral-400 bg-neutral-100 px-1.5 py-0.5 rounded-sm">
                {alerts.length} NEW
              </span>
            )}
          </div>
        </div>

        {/* 列表滚动区 */}
        <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
          {showLoader ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-5 h-5 animate-spin text-neutral-300" />
            </div>
          ) : showLoginHint ? (
            <div className="flex flex-col items-center justify-center h-40 text-center px-4">
              <LogIn className="w-8 h-8 text-neutral-300 mb-2" />
              <p className="text-xs text-neutral-500 font-medium">请登录后查看预警</p>
              <button onClick={() => setIsLoginModalOpen(true)} className="mt-3 text-xs font-bold text-black underline">
                去登录
              </button>
            </div>
          ) : loadIssue ? (
            <div className="flex flex-col items-center justify-center h-40 text-center px-4">
              <Bell className="w-8 h-8 text-neutral-300 mb-2" />
              <p className="text-xs text-neutral-500 font-medium">暂时无法获取预警</p>
              <button onClick={refetch} className="mt-3 flex items-center gap-1 text-xs font-bold text-black">
                <RefreshCw className="w-3 h-3" /> 重试
              </button>
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-center">
              <CheckCircle2 className="w-8 h-8 text-blue-400 mb-2" />
              <p className="text-xs text-neutral-400 font-medium">暂无预警消息</p>
            </div>
          ) : (
            filteredAlerts.map((alert, i) => {
              const isActive = activeAlertId === alert.id;
              const isRed = alert.level === 'red';
              const timeStr = formatTime(alert.created_at);
              return (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  onClick={() => setActiveAlertId(alert.id)}
                  className={cn(
                    'cursor-pointer p-3.5 rounded-xl border transition-all duration-200',
                    isActive
                      ? 'bg-brand-solid border-brand-solid text-white shadow-[0_4px_20px_rgb(0,0,0,0.15)]'
                      : 'bg-white border-neutral-100 text-neutral-900 hover:border-neutral-200 hover:shadow-sm'
                  )}
                >
                  <div className="flex justify-between items-start mb-1.5 gap-2">
                    <div className={cn('text-[9px] font-bold uppercase tracking-wider', isActive ? 'text-white/50' : 'text-neutral-400')}>
                      {timeStr}
                    </div>
                    {isActive && <AlertCircle className="w-3.5 h-3.5 text-white/80 shrink-0" />}
                    {!isActive && isRed && <div className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0 mt-0.5" />}
                  </div>
                  <h4 className={cn('text-[13px] font-bold leading-snug tracking-tight mb-1', isActive ? 'text-white' : 'text-neutral-900')}>
                    {isRed && !isActive && '高危预警 - '}
                    {alert.product_name}
                  </h4>
                  <p className={cn('text-[11px] leading-snug line-clamp-2', isActive ? 'text-white/60' : 'text-neutral-500')}>
                    {alert.message.slice(0, 60)}...
                  </p>
                </motion.div>
              );
            })
          )}
        </div>
      </div>

      {/* ── RIGHT: 深度分析面板 (Detail) ─────── */}
      <div className="flex-1 min-w-0 bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden flex flex-col">
        {activeAlert ? (
          <>
            {/* 头部 */}
            <div className="px-8 py-6 border-b border-neutral-100 shrink-0">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={cn('text-[9px] font-bold px-2 py-1 rounded-[4px] uppercase tracking-widest', getLevelBadgeClass(activeAlert.level))}>
                    预警等级：{getLevelLabel(activeAlert.level)}
                  </span>
                  <span className="text-[11px] text-neutral-400 font-medium">
                    ID: WRN-{String(activeAlert.id).padStart(8, '0')}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-neutral-400">
                  <span className="text-[10px] font-medium">{formatTime(activeAlert.created_at)}</span>
                </div>
              </div>
              <h1 className="text-2xl font-black tracking-tight text-neutral-900 leading-snug">
                {getAlertTitle(activeAlert)}
              </h1>
            </div>

            {/* 可滚动内容区 */}
            <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">

              {/* 链小易 AI 风险解读大卡片 */}
              <div className="bg-slate-50/50 rounded-2xl p-6 border border-neutral-100">
                <div className="flex items-center gap-2 mb-5">
                  <Sparkles className="w-4 h-4 text-neutral-600" />
                  <h2 className="text-sm font-bold text-neutral-800 tracking-tight">链小易 AI 风险解读</h2>
                </div>

                {/* 左右两栏结构 */}
                <div className="space-y-4 mb-5">
                  {[
                    { label: '[风险原因]', content: activeAlert.risk_reason || activeAlert.message },
                    { label: '[影响范围]', content: activeAlert.impact_scope || activeAlert.suggestion || '暂无影响范围分析' },
                  ].map(({ label, content }) => (
                    <div key={label} className="flex gap-4">
                      <div className="w-[88px] shrink-0 text-[10px] font-bold text-neutral-400 pt-0.5 tracking-wide">
                        {label}
                      </div>
                      <p className="flex-1 text-sm text-neutral-700 leading-relaxed">{content}</p>
                    </div>
                  ))}
                </div>

                {/* AI 建议措施 */}
                {(activeAlert.ai_suggestions?.length ?? 0) > 0 && (
                  <div>
                    <div className="flex gap-4 mb-3">
                      <div className="w-[88px] shrink-0 text-[10px] font-bold text-neutral-400 pt-0.5 tracking-wide">
                        [AI 建议措施]
                      </div>
                      <p className="flex-1 text-[11px] text-neutral-500">系统已为您实时检索到以下处置建议：</p>
                    </div>
                    <div className="space-y-2 ml-[104px]">
                      {(activeAlert.ai_suggestions || []).map((sug, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-3 bg-white rounded-xl px-4 py-3 border border-neutral-100 hover:border-neutral-200 hover:shadow-sm transition-all cursor-pointer group"
                        >
                          <span className="text-xs text-neutral-700 font-medium leading-snug flex-1">{sug}</span>
                          <ArrowRight className="w-3.5 h-3.5 text-neutral-300 group-hover:text-black shrink-0 transition-colors" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 底部微型看板：两列 */}
              <div className="grid grid-cols-2 gap-4">

                {/* 数据源明细 */}
                <div className="bg-white rounded-xl border border-neutral-100 p-4">
                  <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-3">数据源明细</h3>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-brand-solid flex items-center justify-center shrink-0">
                      <Cpu className="w-4 h-4 text-white/80" />
                    </div>
                    <div>
                      <div className="text-[13px] font-bold text-neutral-900 leading-tight">
                        {activeAlert.data_source_info?.name || 'IoT 终端'}
                      </div>
                      <div className="text-[10px] text-neutral-400 mt-0.5 font-medium">
                        {activeAlert.data_source_info?.last_sync || '最近同步: 未知'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 历史趋势 (近7日) */}
                <div className="bg-white rounded-xl border border-neutral-100 p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">历史趋势 (近7日)</h3>
                  </div>
                  {(activeAlert.historical_trend?.length ?? 0) > 0 ? (
                    <MiniBarChart data={activeAlert.historical_trend!} />
                  ) : (
                    <div className="h-12 flex items-center justify-center text-[10px] text-neutral-300">暂无趋势数据</div>
                  )}
                  <div className="flex justify-between mt-1 text-[9px] text-neutral-300 font-medium">
                    <span>7天前</span>
                    <span>今日</span>
                  </div>
                </div>
              </div>

            </div>

            {/* 底部操作栏 */}
            <div className="px-8 py-4 border-t border-neutral-100 bg-[#fafafa] shrink-0 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    if (activeAlert) showToast(`预警 WRN-${String(activeAlert.id).padStart(8, '0')} 已标记为已知晓`, 'success');
                  }}
                  className="px-4 py-2 bg-white border border-neutral-200 rounded-lg text-xs font-semibold text-neutral-600 hover:border-neutral-400 hover:text-black transition-all"
                >
                  已知晓预警
                </button>
              </div>
              <button
                onClick={() => navigate('/quote-pool')}
                className="flex items-center gap-2 px-5 py-2 bg-brand-solid text-white text-xs font-bold rounded-lg hover:bg-brand-solid-hover transition-all shadow-[0_4px_14px_0_rgb(0,0,0,0.1)]"
              >
                <Zap className="w-3.5 h-3.5 fill-white" />
                一键生成意向报价去接单
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-neutral-400 bg-neutral-50/30">
            <Bell className="w-10 h-10 mb-3 text-neutral-200" />
            <p className="text-xs font-medium">点击左侧预警消息查看深度解读</p>
          </div>
        )}
      </div>

    </div>
  );
}
