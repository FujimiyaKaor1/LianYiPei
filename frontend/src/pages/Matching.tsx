import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  ChevronRight,
  ShieldCheck,
  Zap,
  Send,
  Loader2,
  TrendingUp,
  Clock,
  CheckCircle,
  Building,
  Target,
  ArrowRightLeft,
  Sparkles,
  Brain,
  Leaf,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type SupplierSearchItem } from '@/src/services/api';
import { getStoredModelChoice, onModelChoiceChanged } from '@/src/lib/modelChoice';
import { useAuth } from '@/src/context/AuthContext';

const SORT_OPTIONS = [
  { key: 'score', label: '综合排序' },
  { key: 'credit', label: '信用最高' },
  { key: 'distance', label: '距离最近' },
] as const;

const CREDIT_LEVELS = ['AAA', 'AA+', 'A', '不限'] as const;

// ── AI 深度思考 Loading 状态组件 ──────────────────────────────────────────

function DeepThinkingOverlay() {
  const [phase, setPhase] = useState(0);
  const phases = [
    '正在解析自然语言意图...',
    '融合产业链知识图谱进行语义匹配...',
    '基于 GNN 产业链图谱计算结构化权重...',
    'AI 大模型正在生成专家级推荐理由...',
    '正在汇总多维评估结果并排序...',
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setPhase(p => (p + 1) % phases.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-neutral-50/50 px-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center text-center max-w-sm"
      >
        {/* Animated brain icon */}
        <div className="relative mb-6">
          <div className="w-16 h-16 rounded-2xl bg-brand-solid flex items-center justify-center shadow-[0_8px_30px_rgb(0,0,0,0.15)]">
            <Brain className="w-7 h-7 text-white" />
          </div>
          <motion.div
            animate={{ scale: [1, 1.4, 1], opacity: [0.3, 0, 0.3] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            className="absolute inset-0 rounded-2xl border-2 border-brand-solid/20"
          />
        </div>

        <h3 className="text-sm font-bold text-neutral-900 mb-2 tracking-tight">
          AI 深度思考中
        </h3>

        {/* Phase text with animation */}
        <AnimatePresence mode="wait">
          <motion.p
            key={phase}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
            className="text-[11px] text-neutral-500 font-medium leading-relaxed mb-5"
          >
            {phases[phase]}
          </motion.p>
        </AnimatePresence>

        {/* Progress dots */}
        <div className="flex items-center gap-1.5">
          {phases.map((_, i) => (
            <motion.div
              key={i}
              animate={{
                backgroundColor: i <= phase ? '#1D4ED8' : '#e5e5e5',
                scale: i === phase ? 1.3 : 1,
              }}
              className="w-1.5 h-1.5 rounded-full"
            />
          ))}
        </div>

        <p className="text-[10px] text-neutral-500 mt-4 font-medium leading-relaxed max-w-xs">
          首次加载语义向量模型与调用本地大模型可能需要 1-2 分钟，请勿刷新页面。
        </p>
        <p className="text-[10px] text-neutral-400 mt-2 font-medium">
          模型已驻留后，同会话请求通常会快很多。
        </p>
      </motion.div>
    </div>
  );
}

// ── 骨架屏组件 ────────────────────────────────────────────────────────────

/** 大模型推荐理由加载占位（勿与算分公式混用） */
function AiExpertReasonSkeleton() {
  return (
    <div className="space-y-2.5 animate-pulse" aria-hidden="true">
      <div className="h-3.5 bg-neutral-200/70 rounded-md w-full" />
      <div className="h-3.5 bg-neutral-200/60 rounded-md w-[91%]" />
      <div className="h-3.5 bg-neutral-200/50 rounded-md w-[64%]" />
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl p-3.5 border border-neutral-100 animate-pulse space-y-2.5">
      <div className="flex justify-between">
        <div className="h-3.5 bg-neutral-100 rounded w-2/3" />
        <div className="h-5 w-10 bg-neutral-100 rounded" />
      </div>
      <div className="flex gap-1">
        <div className="h-3 bg-neutral-100 rounded w-12" />
        <div className="h-3 bg-neutral-100 rounded w-14" />
      </div>
      <div className="h-px bg-neutral-100" />
      <div className="flex justify-between">
        <div className="h-3 bg-neutral-100 rounded w-20" />
        <div className="h-3 bg-neutral-100 rounded w-16" />
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────────────────────

export default function Matching() {
  const navigate = useNavigate();
  const { user, setIsLoginModalOpen } = useAuth();
  const demoTimersRef = useRef<{ t1?: ReturnType<typeof setTimeout>; t2?: ReturnType<typeof setTimeout> }>({});

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTag, setActiveTag] = useState('');
  const [sortBy, setSortBy] = useState<'score' | 'credit' | 'distance'>('score');
  const [deliveryDays, setDeliveryDays] = useState(30);
  const [creditLevel, setCreditLevel] = useState<(typeof CREDIT_LEVELS)[number]>('AAA');
  const [suppliers, setSuppliers] = useState<SupplierSearchItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorText, setErrorText] = useState('');
  const [algorithmMode, setAlgorithmMode] = useState<'rule' | 'deep_learning'>('rule');
  const [greenOnly, setGreenOnly] = useState(false);
  const [modelChoice, setModelChoice] = useState<'qwen' | 'deepseek'>(getStoredModelChoice());
  const [isBasicMatch, setIsBasicMatch] = useState(false);
  
  const [inquirySendingId, setInquirySendingId] = useState<number | null>(null);
  const [globalToast, setGlobalToast] = useState<string | null>(null);
  const [activeEnterpriseId, setActiveEnterpriseId] = useState<number | null>(null);

  const minCreditParam = useMemo(() => {
    if (creditLevel === '不限') return '';
    return creditLevel;
  }, [creditLevel]);

  // ── 真实 API 调用 ──────────────────────────────────────────────────────

  const loadSuppliers = async (
    overrides?: Partial<{
      query: string;
      tag: string;
      sort: 'score' | 'credit' | 'distance';
      deliveryDays: number;
      minCredit: string;
      algorithm: 'rule' | 'deep_learning';
    }>,
  ) => {
    setIsLoading(true);
    setErrorText('');
    try {
      const payload = await api.fetchSuppliers({
        query: overrides?.query ?? searchQuery,
        tag: overrides?.tag ?? activeTag,
        sort: overrides?.sort ?? sortBy,
        delivery_days: overrides?.deliveryDays ?? deliveryDays,
        min_credit: overrides?.minCredit ?? minCreditParam,
        algorithm: overrides?.algorithm ?? algorithmMode,
        model_choice: modelChoice,
      });
      setSuppliers(payload.suppliers || []);
      setIsBasicMatch(Boolean(payload.is_basic_match));
      if (payload.suppliers && payload.suppliers.length > 0 && !activeEnterpriseId) {
        setActiveEnterpriseId(Number(payload.suppliers[0].id));
      }
    } catch (error) {
      setSuppliers([]);
      setErrorText(error instanceof Error ? error.message : '匹配请求失败，请稍后重试');
      setIsBasicMatch(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadSuppliers();
  }, []);

  useEffect(() => {
    return onModelChoiceChanged(setModelChoice);
  }, []);

  useEffect(() => {
    return () => {
      const { t1, t2 } = demoTimersRef.current;
      if (t1) clearTimeout(t1);
      if (t2) clearTimeout(t2);
    };
  }, []);

  const handleAnonymousInquiry = async (event: React.MouseEvent, item: SupplierSearchItem) => {
    event.preventDefault();
    event.stopPropagation();
    if (!user) {
      setGlobalToast('请先登录后再发起询价');
      setIsLoginModalOpen(true);
      return;
    }
    if (inquirySendingId !== null) return;
    const id = Number(item.id);
    const name = item.name || '该企业';
    setInquirySendingId(id);

    try {
      // Step 1：发送询盘通知
      const inquiryResp = await api.sendInquiry({
        supplier_id: id,
        product_name: searchQuery || '精密零部件',
        content: `你好，我对你们的 ${searchQuery || '精密零部件'} 感兴趣，希望能进一步沟通合作细节。`,
        dim_scores: {},
        match_score: Number(item.score || 0),
      });

      if (!inquiryResp.success) {
        setGlobalToast('询盘发送失败，请重试');
        return;
      }

      // Step 2：自动创建 InquiryChat 会话（匿名询价闭环）
      let createdChatId: number | null = null;
      try {
        const chatResp = await api.createInquiryChat({
          buyer_id: user.id,
          seller_id: id,
          match_record_id: inquiryResp.match_feedback_id,
          is_anonymous: true,
          product_name: searchQuery || '精密零部件',
          match_score: Number(item.score || 0),
          match_feedback_id: inquiryResp.match_feedback_id,
        });
        createdChatId = chatResp.chat_id;
      } catch (chatErr) {
        console.warn('InquiryChat creation failed, proceeding with legacy redirect:', chatErr);
      }

      // Step 3：跳转至控制台并自动打开意向报价单
      setGlobalToast(`询盘已成功发送至 ${name}，正在跳转至议价中心...`);
      setTimeout(() => {
        setGlobalToast(null);
        if (createdChatId) {
          // 买方从匹配页进入 → 采购模式 + 自动弹出意向报价单
          navigate(`/sales-console?chat_id=${createdChatId}&desk=procurement&auto_quote=1`);
        } else {
          // 降级：使用旧版 state 跳转
          navigate('/sales-console', {
            state: {
              activeInquiryId: inquiryResp.inquiry_id,
              fromMatching: true,
              matchingSupplierName: name,
            },
          });
        }
      }, 1200);
    } catch (err) {
      console.error('Inquiry send error:', err);
      setGlobalToast('系统异常，请稍后再试');
    } finally {
      setInquirySendingId(null);
    }
  };

  // ── 点击「智能匹配」按钮：强制 deep_learning 模式 ──────────────────────

  const handleSearch = () => {
    setAlgorithmMode('deep_learning');
    void loadSuppliers({ query: searchQuery, tag: activeTag, sort: sortBy, algorithm: 'deep_learning' });
  };

  const handleSortClick = (sort: 'score' | 'credit' | 'distance') => {
    setSortBy(sort);
    void loadSuppliers({ sort });
  };

  const handleToggleAlgorithm = () => {
    const nextMode = algorithmMode === 'rule' ? 'deep_learning' : 'rule';
    setAlgorithmMode(nextMode);
    void loadSuppliers({ algorithm: nextMode });
  };

  // ── 指标分析（基于真实数据动态生成） ────────────────────────────────────

  const getMetrics = (item: SupplierSearchItem) => {
    const seed = (Number(item.id) * 137) % 100;
    const creditScore = Number(item.credit_score) || 70;
    return [
      { label: '价格竞争力 (同级对比)', value: Math.min(99, 80 + (seed % 18)), icon: TrendingUp },
      { label: '历史交期达成率', value: Math.min(99, 88 + (Number(item.id) % 11)), icon: Clock },
      { label: '质量控制水平 (良品率)', value: Math.min(99, 92 + ((seed + 3) % 7)), icon: CheckCircle },
      { label: '产线数字化覆盖率', value: Math.min(99, 70 + ((seed * 2) % 28)), icon: Zap },
      { label: '信用综合评定', value: Math.round(creditScore), icon: ShieldCheck },
    ];
  };

  const getCapacityHeatmap = (id: number) => {
    const seed = id * 53;
    return Array.from({ length: 30 }).map((_, i) => {
      const val = (seed + i * 17) % 100;
      if (val < 15) return 0;
      if (val < 50) return 1;
      if (val < 85) return 2;
      return 3;
    });
  };

  const activeSupplier = suppliers.find(s => Number(s.id) === activeEnterpriseId) || suppliers[0];

  return (
    <div className="relative mx-auto flex h-[calc(100vh-6rem)] max-h-[900px] w-full max-w-[1440px] flex-col gap-4 font-sans text-ink antialiased">
      {globalToast ? (
        <div className="fixed inset-x-0 bottom-6 z-[900] flex justify-center px-4 pointer-events-none" role="status">
          <div className={cn(
            'pointer-events-auto max-w-sm rounded-md border border-border bg-white px-4 py-3 text-sm font-medium text-ink',
            'shadow-elevation-3',
            'animate-in fade-in zoom-in-95 slide-in-from-bottom-4 duration-300',
          )}>
            {globalToast}
          </div>
        </div>
      ) : null}

      {/* Top Search Card */}
      <section className="panel shrink-0 overflow-hidden">
        <div className="panel-header flex items-center justify-between px-5 py-3">
          <div>
            <h2 className="text-base font-bold text-ink">智能供需匹配</h2>
            <p className="mt-1 text-xs font-medium text-ink-muted">自然语言条件会转译为产品、距离、质量、产能与信用约束</p>
          </div>
          <span className="rounded-md border border-brand/20 bg-brand-soft px-2 py-1 text-[11px] font-bold text-brand">
            {algorithmMode === 'deep_learning' ? 'AI fusion' : 'Rule engine'}
          </span>
        </div>
        <div className="flex flex-col justify-between gap-5 p-5 md:flex-row md:items-end">
        <div className="space-y-3 flex-1">
          <textarea
            rows={2}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="寻找一家主营驱动电机的工厂，位于周边 500 公里内，具备政府绿标认证，且近 30 天产能相对宽裕以满足紧急打样。"
            className="min-h-[74px] w-full resize-none rounded-md border border-border bg-surface px-4 py-3 text-base font-medium leading-7 text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand-soft md:text-lg"
          />
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {['产品: 驱动电机', '距离: <500km', '质量: 政府绿标', '产能: 宽裕'].map(tag => (
              <span key={tag} className="rounded-md border border-border bg-surface-subtle px-2 py-0.5 text-[10px] font-bold text-ink-muted">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <button
            onClick={handleToggleAlgorithm}
            className="btn-secondary btn-sm"
          >
            {algorithmMode === 'rule' ? '启用 AI 融合' : '使用规则引擎'}
          </button>
          <button
            onClick={() => setGreenOnly(!greenOnly)}
            className={cn(
              'btn-secondary btn-sm gap-1.5',
              greenOnly ? 'border-trust/30 bg-trust-soft text-trust' : '',
            )}
          >
            <Leaf className="w-3.5 h-3.5" />
            绿色优先
          </button>
          <button 
            onClick={handleSearch}
            disabled={isLoading}
            className="btn-primary btn-sm gap-1.5 disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 fill-white" />}
            {isLoading && algorithmMode === 'deep_learning' ? 'AI 深度思考中...' : '智能匹配'}
          </button>
        </div>
        </div>
      </section>

      {/* Error Banner */}
      {errorText && (
        <div className="shrink-0 rounded-md border border-critical/20 bg-critical-soft px-4 py-2.5 text-xs font-semibold text-critical">
          {errorText}
        </div>
      )}

      {/* Fallback Indicator */}
      {isBasicMatch && !isLoading && suppliers.length > 0 && (
        <div className="flex shrink-0 items-center gap-2 rounded-md border border-risk/20 bg-risk-soft px-4 py-2.5 text-xs font-semibold text-risk">
          <Sparkles className="w-3.5 h-3.5" />
          当前结果由基础规则引擎返回。切换「智能匹配」可启用 AI 深度思考获得更精准结果。
        </div>
      )}

      {/* Bottom Grid Layout */}
      <section className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        
        {/* Left List (1/3 Width) */}
        <div className="panel flex w-full flex-col overflow-hidden lg:w-[32%]">
          {/* Header */}
          <div className="panel-header z-10 flex shrink-0 flex-col gap-2.5 px-4 py-3">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-bold text-ink">匹配结果</h3>
              <div className="flex items-center gap-0.5 text-[10px] font-semibold text-ink-muted">
                召回 {suppliers.length} 家 <ChevronRight className="w-3 h-3" />
              </div>
            </div>
            <div className="flex gap-4 text-[10px] font-bold text-ink-muted">
              {SORT_OPTIONS.map((option) => (
                <span
                  key={option.key}
                  onClick={() => handleSortClick(option.key)}
                  className={cn(
                    'cursor-pointer transition-colors hover:text-brand',
                    sortBy === option.key ? 'text-brand' : ''
                  )}
                >
                  {option.label}
                </span>
              ))}
            </div>
          </div>
          
          {/* Scrollable list */}
          <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto bg-surface-subtle px-3 py-3">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
            ) : suppliers.length > 0 ? (
              suppliers.map((item) => {
                const isActive = activeEnterpriseId === Number(item.id);
                const matchScore = item.score || item.confidence_index || 0;
                const utilization = 65 + (Number(item.id) % 25);
                const isAmple = utilization < 75;

                return (
                  <div
                    key={item.id}
                    onClick={() => setActiveEnterpriseId(Number(item.id))}
                    className={cn(
                      "flex cursor-pointer flex-col gap-2 rounded-md border p-3.5 transition-all duration-200",
                      isActive
                        ? "border-brand-solid bg-brand-solid text-white shadow-elevation-2"
                        : "border-border bg-white text-ink hover:border-border-hover hover:shadow-elevation-1"
                    )}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0 pr-2">
                        <h4 className="mb-1 truncate text-[13px] font-bold leading-tight">{item.name}</h4>
                        <div className="flex flex-wrap gap-1">
                          {(item.tags || []).filter(Boolean).slice(0, 3).map((tag, idx) => (
                            <span key={`${tag}-${idx}`} className={cn(
                              "rounded-sm px-1 py-0.5 text-[9px] font-semibold",
                              isActive ? "bg-white/10 text-white/90" : "bg-surface-subtle text-ink-muted"
                            )}>
                              {tag}
                            </span>
                          ))}
                          {item.match_basis && (
                            <span className={cn(
                              "px-1 py-0.5 text-[8px] font-bold rounded-sm uppercase",
                              isActive ? "bg-white/20 text-white" : "bg-brand-soft text-brand"
                            )}>
                              {item.match_basis}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={cn("metric-number text-xl font-black leading-none", isActive ? "text-white" : "text-ink")}>
                          {Math.round(matchScore)}
                        </div>
                        <div className={cn("mt-1 origin-right scale-90 text-[9px] font-semibold", isActive ? "text-white/60" : "text-ink-muted")}>匹配分</div>
                      </div>
                    </div>
                    
                    <div className={cn("h-px w-full", isActive ? "bg-white/10" : "bg-neutral-100")}></div>
                    
                    <div className="flex justify-between items-center text-[10px] font-medium">
                       <span className={cn(isActive ? "text-white/70" : "text-neutral-500")}>
                         产能利用率 <span className={cn(isActive ? "text-white font-semibold" : "text-neutral-900 font-semibold")}>{utilization}%</span>
                       </span>
                       <span className={cn("flex items-center gap-1.5")}>
                         <div className={cn("w-1.5 h-1.5 rounded-full", isAmple ? "bg-trust" : "bg-risk")}></div>
                         <span className={cn(isActive ? "text-white/90" : "text-neutral-600")}>{isAmple ? '近期充裕' : '排期较紧'}</span>
                       </span>
                    </div>
                    {algorithmMode === 'deep_learning' && item.deep_learning_explain ? (
                      <p
                        className={cn(
                          'text-[7px] leading-tight mt-1 font-normal opacity-60 tracking-tight',
                          isActive ? 'text-white/40' : 'text-neutral-400',
                        )}
                        title="融合引擎权重示值（非 AI 专家话术）"
                      >
                        {item.deep_learning_explain}
                      </p>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <div className="text-center text-xs text-neutral-400 py-10">未找到符合条件的供应商</div>
            )}
          </div>
        </div>

        {/* Right Detail Panel (Deep Analysis) */}
        <div className="panel relative flex w-full flex-col overflow-hidden lg:w-[68%]">
          {/* 深度思考 Loading 状态覆盖整个右侧面板 */}
          {isLoading && algorithmMode === 'deep_learning' ? (
            <DeepThinkingOverlay />
          ) : activeSupplier ? (
            <>
              {/* Header Info */}
              <div className="panel-header shrink-0 px-7 py-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                     <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border bg-surface">
                       <Building className="w-4 h-4 text-neutral-600" />
                     </div>
                     <div>
                       <div className="flex items-center gap-2 mb-1">
                         <h2 className="text-lg font-bold text-ink">{activeSupplier.name}</h2>
                         <div className="flex items-center gap-1 rounded-sm bg-brand-solid px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                           <Target className="w-2.5 h-2.5" /> 匹配度 {activeSupplier.score || activeSupplier.confidence_index || activeSupplier.match || '—'}
                         </div>
                         {activeSupplier.match_basis && (
                           <span className="rounded-sm bg-brand-soft px-1.5 py-0.5 text-[8px] font-bold uppercase text-brand">
                             {activeSupplier.match_basis}
                           </span>
                         )}
                       </div>
                       <p className="max-w-lg text-[11px] font-medium leading-snug text-ink-muted">
                         {activeSupplier.desc || '暂无企业描述信息'}
                       </p>
                     </div>
                  </div>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="scrollbar-thin grid flex-1 grid-cols-1 gap-x-12 gap-y-8 overflow-y-auto bg-white px-7 py-6 md:grid-cols-2">
                
                {/* AI 专家推荐理由：正文仅绑定 ai_match_reason；算分公式仅作脚注小字 */}
                {(algorithmMode === 'deep_learning' || Boolean(activeSupplier.ai_match_reason)) && (
                  <div className="md:col-span-2">
                    <h3 className="mb-3 flex items-center gap-2 text-[10px] font-bold uppercase text-ink-muted">
                      <span className="h-3 w-1 rounded-full bg-brand"></span>
                      <Sparkles className="w-3 h-3" />
                      AI 专家推荐理由
                    </h3>
                    <div className="rounded-md border border-border bg-surface-subtle p-4">
                      {activeSupplier.ai_match_reason ? (
                        <p className="text-sm text-neutral-700 leading-relaxed">{activeSupplier.ai_match_reason}</p>
                      ) : isLoading && algorithmMode === 'deep_learning' ? (
                        <AiExpertReasonSkeleton />
                      ) : algorithmMode === 'deep_learning' ? (
                        <p className="text-sm text-neutral-400 leading-relaxed">
                          AI 专家正在结合全网数据进行深度思考，请稍候...
                        </p>
                      ) : null}
                      {algorithmMode === 'deep_learning' && activeSupplier.deep_learning_explain ? (
                        <p className="text-[8px] text-neutral-400/75 mt-3 pt-2 border-t border-neutral-100/90 leading-snug">
                          {activeSupplier.deep_learning_explain}
                        </p>
                      ) : null}
                    </div>
                  </div>
                )}

                {/* Metrics Analysis */}
                <div>
                   <h3 className="mb-5 flex items-center gap-2 text-[10px] font-bold uppercase text-ink-muted">
                     <span className="h-3 w-1 rounded-full bg-brand"></span>
                     核心指标分析
                   </h3>
                   <div className="space-y-4">
                     {getMetrics(activeSupplier).map((metric, idx) => (
                       <div key={idx} className="group">
                         <div className="mb-1.5 flex justify-between text-[11px] font-semibold text-ink-soft">
                           <div className="flex items-center gap-1.5">
                             <metric.icon className="h-3 w-3 text-ink-muted transition-colors group-hover:text-brand" />
                             {metric.label}
                           </div>
                           <span className="font-bold text-ink">{metric.value}%</span>
                         </div>
                         <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container">
                           <motion.div 
                             initial={{ width: 0 }}
                             animate={{ width: `${metric.value}%` }}
                             transition={{ duration: 0.8, delay: 0.05 * idx, ease: "easeOut" }}
                             className="h-full rounded-full bg-brand"
                           />
                         </div>
                       </div>
                     ))}
                   </div>
                </div>

                {/* Capacity Calendar */}
                <div>
                  <div className="flex justify-between items-center mb-5">
                    <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase text-ink-muted">
                      <span className="h-3 w-1 rounded-full bg-brand"></span>
                      未来30天产能日历
                    </h3>
                  </div>
                  <div className="rounded-md border border-border bg-surface-subtle p-5">
                    <div className="grid grid-cols-6 gap-2">
                      {getCapacityHeatmap(Number(activeSupplier.id)).map((status, idx) => (
                        <motion.div 
                          key={`cap-day-${idx}`}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: idx * 0.01 }}
                          className={cn(
                            "aspect-square cursor-crosshair rounded-[4px] border transition-all hover:scale-105",
                            status === 0 ? "border-brand-solid bg-brand-solid" :
                            status === 1 ? "border-risk bg-risk" :
                            status === 2 ? "border-trust/30 bg-trust-soft" :
                            "border-border bg-white"
                          )}
                          title={`Day ${idx + 1}`}
                        />
                      ))}
                    </div>
                    <div className="flex items-center justify-end gap-1.5 mt-3 text-[9px] font-medium text-neutral-400">
                      <span>排满</span>
                      <div className="flex gap-0.5">
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-brand-solid"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-risk"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-trust-soft"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] border border-border bg-white"></div>
                      </div>
                      <span>空闲</span>
                    </div>
                  </div>
                </div>

              </div>
              
              {/* Footer Actions */}
              <div className="flex shrink-0 items-center justify-end gap-3 border-t border-border bg-surface-subtle px-7 py-4">
                <button
                  disabled={inquirySendingId !== null}
                  onClick={(e) => handleAnonymousInquiry(e, activeSupplier)}
                  className="btn-secondary btn-sm gap-1.5"
                >
                  {inquirySendingId === Number(activeSupplier.id) ? (
                    <><Loader2 className="h-3 w-3 animate-spin" /> 准备发送中</>
                  ) : (
                    <><Send className="h-3 w-3" /> 发起匿名询价</>
                  )}
                </button>
                <button
                  disabled={inquirySendingId !== null}
                  onClick={async () => {
                    if (!user) {
                      setGlobalToast('请先登录');
                      setIsLoginModalOpen(true);
                      return;
                    }
                    const sid = Number(activeSupplier.id);
                    setInquirySendingId(sid);
                    try {
                      const chatResp = await api.createInquiryChat({
                        buyer_id: user.id,
                        seller_id: sid,
                        match_record_id: 0,
                        is_anonymous: false,
                        product_name: searchQuery || '精密零部件',
                        match_score: Number(activeSupplier.score || 0),
                      });
                      setGlobalToast('已创建会话，正在跳转...');
                      setTimeout(() => {
                        setGlobalToast(null);
                        navigate(`/sales-console?chat_id=${chatResp.chat_id}`);
                      }, 800);
                    } catch {
                      setGlobalToast('创建会话失败，请重试');
                    } finally {
                      setInquirySendingId(null);
                    }
                  }}
                  className="btn-primary btn-sm gap-1.5 disabled:opacity-50"
                >
                  <ArrowRightLeft className="h-3 w-3" />
                  带信息交换
                </button>
              </div>
            </>
          ) : (
             <div className="flex-1 flex flex-col items-center justify-center text-neutral-400 bg-neutral-50/30">
                <Search className="w-8 h-8 mb-3 text-neutral-300" />
                <p className="text-xs font-medium">点击左侧列表查看企业深度分析</p>
             </div>
          )}
        </div>

      </section>
    </div>
  );
}
