import { useState, useEffect } from 'react';
import { 
  Gauge, 
  TrendingUp, 
  CheckCircle2, 
  ArrowRight, 
  Factory, 
  AlertTriangle, 
  LineChart,
  MapPin,
  Award,
  ChevronRight,
  RefreshCw,
  Loader2
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type AlertData, type CreditScoreData, NETWORK_ERROR_MESSAGE } from '@/src/services/api';
import { CollaborationModal } from '@/src/components/CollaborationModal';
import { useAuth } from '@/src/context/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();
  const [isCollaborationModalOpen, setIsCollaborationModalOpen] = useState(false);
  const [creditScore, setCreditScore] = useState<CreditScoreData | null>(null);
  const [creditLoading, setCreditLoading] = useState(true);
  const [creditError, setCreditError] = useState<string | null>(null);

  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const [matches, setMatches] = useState<any[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(true);

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
        localStorage.setItem(creditCacheKey, JSON.stringify(data));
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
      // Empty query returns top suppliers ranked by credit
      const data = await api.fetchSuppliers({ query: '' });
      setMatches(data.suppliers?.slice(0, 3) || []);
    } catch (e) {
      console.error("fetch matches failed", e);
    } finally {
      setMatchesLoading(false);
    }
  };

  const refreshAll = async () => {
    setCreditLoading(true);
    setAlertsLoading(true);
    await Promise.allSettled([fetchCreditScore(false), fetchAlerts(false), fetchMatches()]);
  };

  useEffect(() => {
    if (!user?.id) {
      return;
    }
    refreshAll();
  }, [user?.id]);

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'capacity_risk': return Factory;
      case 'supply_chain_break': return AlertTriangle;
      case 'business_risk': return LineChart;
      default: return AlertTriangle;
    }
  };

  const getAlertColor = (level: string) => {
    switch (level) {
      case 'red': return 'red';
      case 'yellow': return 'orange';
      case 'blue': return 'blue';
      default: return 'orange';
    }
  };

  const isInitialLoading = creditLoading || alertsLoading;
  const hasNetworkError = Boolean(creditError || alertsError);
  const scorePercent = Math.min(100, Math.max(0, Number(creditScore?.credit_score || 0)));
  const privilegeText = creditScore
    ? creditScore.credit_score >= 70
      ? '已解锁：无限报价特权'
      : '当前为基础报价权益（每日 3 次）'
    : '权益状态加载中';

  return (
    <>
    <CollaborationModal
      open={isCollaborationModalOpen}
      onClose={() => setIsCollaborationModalOpen(false)}
      enterpriseId={user?.id ?? null}
      currentCreditScore={Number(creditScore?.credit_score || 70)}
    />
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full auto-rows-auto">
      {(isInitialLoading || hasNetworkError) && (
        <div className="col-span-2 bg-white p-3 rounded-2xl border border-white shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            {isInitialLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <AlertTriangle className="w-4 h-4 text-red-400" />}
            <span>{isInitialLoading ? '正在同步后端数据...' : '网络请求失败，请检查后端服务'}</span>
          </div>
          {hasNetworkError && (
            <button onClick={refreshAll} className="px-3 py-1 bg-neutral-100 rounded-full text-xs hover:bg-neutral-200 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> 重试
            </button>
          )}
        </div>
      )}

      {/* Performance Score Card */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-[#1C1C1E] to-[#000000] text-white p-6 rounded-[2rem] shadow-2xl relative overflow-hidden group flex flex-col min-h-[260px]"
      >
        <div className="absolute top-0 right-0 p-6 opacity-10">
          <Gauge className="w-24 h-24" />
        </div>
        <p className="text-xs font-medium uppercase tracking-widest text-white/60 mb-2">履约信用等级</p>
        
        {creditLoading ? (
          <div className="flex flex-col items-center justify-center flex-1 min-h-0">
            <Loader2 className="w-8 h-8 animate-spin text-white/60" />
            <p className="text-xs text-white/40 mt-2">正在加载信用分...</p>
          </div>
        ) : creditError ? (
          <div className="flex flex-col items-center justify-center flex-1 min-h-0">
            <p className="text-xs text-red-400 mb-2">网络请求失败，请检查后端服务</p>
            <button onClick={() => fetchCreditScore()} className="px-3 py-1 bg-white/10 rounded-full text-xs hover:bg-white/20 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> 重试
            </button>
          </div>
        ) : (
          <div className="flex flex-col flex-1 min-h-0">
            <div className="flex items-baseline gap-2 mb-4">
              <h3 className="text-5xl font-black tracking-tighter">{creditScore?.credit_score ?? '--'}</h3>
              <span className="text-xl text-white/40">/ 100</span>
            </div>
            <div>
              <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-full text-[10px] font-semibold border border-white/10">
                <span className={cn("w-1.5 h-1.5 rounded-full", creditScore?.credit_score && creditScore.credit_score >= 70 ? 'bg-green-400 animate-pulse' : 'bg-amber-400')}></span>
                {privilegeText}
              </div>
            </div>
            <div className="mt-auto pt-4 border-t border-white/10 flex justify-between items-end">
              <div className="space-y-1">
                <p className="text-[10px] text-white/40">当前信用等级：{creditScore?.level || '--'}</p>
                <div className="w-24 h-1 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-white" style={{ width: `${scorePercent}%` }}></div>
                </div>
              </div>
              <TrendingUp className="w-4 h-4 text-white/40" />
            </div>
          </div>
        )}
      </motion.div>

      {/* Collaborative Tasks */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white p-6 rounded-[2rem] border border-white shadow-sm flex flex-col min-h-[260px]"
      >
        <div className="flex justify-between items-start mb-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-widest text-neutral-400 mb-1">合作闭环任务</p>
            <h4 className="text-xl font-bold">验证交易真实性</h4>
          </div>
          <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>
        <div className="mb-4">
          <p className="text-neutral-500 text-xs leading-relaxed">
            完成本季度 3 笔大宗采购的链上存证，验证交易真实性后，您的履约信用分最高可获 <span className="text-primary font-bold">+10 分</span> 奖励，并获得“诚信供应商”勋章。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsCollaborationModalOpen(true)}
          className="mt-auto w-full py-3 bg-primary text-white rounded-xl text-sm font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-all active:scale-[0.98] shrink-0"
        >
          立即发起验证
          <ArrowRight className="w-4 h-4" />
        </button>
      </motion.div>

      {/* Risk Monitoring */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white p-6 rounded-[2rem] border border-white shadow-sm flex flex-col min-h-[260px]"
      >
        <div className="flex items-center justify-between mb-4 shrink-0">
          <h4 className="text-base font-bold">风险自检与预警</h4>
          {!alertsLoading && !alertsError && alerts.length > 0 && (
            <span className="text-[10px] font-semibold text-error px-2 py-0.5 bg-error/10 rounded-full">{alerts.length} 条待处理</span>
          )}
        </div>
        
        {alertsLoading ? (
          <div className="flex flex-col items-center justify-center flex-1 min-h-0">
            <Loader2 className="w-6 h-6 animate-spin text-neutral-300" />
            <p className="text-[10px] text-neutral-400 mt-2">正在加载预警信息...</p>
          </div>
        ) : alertsError ? (
          <div className="flex flex-col items-center justify-center flex-1 min-h-0">
            <p className="text-[10px] text-red-400 mb-2">网络请求失败，请检查后端服务</p>
            <button onClick={() => fetchAlerts()} className="px-3 py-1 bg-neutral-100 rounded-full text-[10px] hover:bg-neutral-200 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> 重试
            </button>
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 min-h-0 text-neutral-400">
            <CheckCircle2 className="w-6 h-6 mb-2 text-green-400" />
            <p className="text-xs">当前无风险预警</p>
          </div>
        ) : (
          <div className="space-y-3 flex-1 min-h-0">
            {alerts.slice(0, 3).map((item, i) => {
              const Icon = getAlertIcon(item.alert_type);
              const color = getAlertColor(item.level);
              return (
                <div key={item.id || i} className="flex gap-3 p-3 rounded-xl hover:bg-surface-container transition-colors group cursor-pointer border border-transparent hover:border-black/5">
                  <div className={cn(
                    "w-8 h-8 shrink-0 rounded-full flex items-center justify-center",
                    color === 'orange' ? 'bg-orange-100 text-orange-600' : 
                    color === 'red' ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'
                  )}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className={cn("text-xs font-bold truncate", color === 'red' && "text-error")}>
                      {item.message || item.product_name}
                    </p>
                    <p className="text-[10px] text-neutral-500 mt-0.5 truncate">{item.suggestion || '请及时关注并处理该风险。'}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* Smart Matching */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-white p-6 rounded-[2rem] border border-white shadow-sm flex flex-col min-h-[260px]"
      >
        <div className="flex items-center justify-between mb-4 shrink-0">
          <h4 className="text-base font-bold">智能匹配推荐</h4>
          <button className="text-[10px] font-bold text-primary flex items-center gap-1 hover:underline">
            查看全部 <ChevronRight className="w-3 h-3" />
          </button>
        </div>
        <div className="space-y-3 flex-1 min-h-0">
          {matchesLoading ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Loader2 className="w-5 h-5 animate-spin text-neutral-300" />
            </div>
          ) : matches.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-xs text-neutral-400">
              暂无推荐
            </div>
          ) : (
            matches.map((item, i) => (
              <div key={item.id || i} className="p-4 rounded-xl border border-surface-container-highest hover:shadow-md transition-all bg-surface-container-lowest cursor-pointer group">
                <div className="flex justify-between items-start mb-2">
                  <h5 className="font-bold text-xs group-hover:text-primary transition-colors truncate pr-2">{item.name}</h5>
                  <span className="px-1.5 py-0.5 bg-neutral-100 text-neutral-600 text-[9px] font-bold rounded border border-neutral-200 whitespace-nowrap shrink-0">{(item.tags && item.tags[0]) || '优质客商'}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-neutral-500">
                  <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {item.address || '未知地区'}</span>
                  <span className="flex items-center gap-1"><Award className="w-3 h-3" /> {item.match || '90%'} 匹配度</span>
                </div>
              </div>
            ))
          )}
        </div>
      </motion.div>
    </div>
    </>
  );
}
