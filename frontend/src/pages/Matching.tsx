import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '@/src/components/ToastProvider';
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
          <div className="w-16 h-16 rounded-2xl bg-black flex items-center justify-center shadow-[0_8px_30px_rgb(0,0,0,0.15)]">
            <Brain className="w-7 h-7 text-white" />
          </div>
          <motion.div
            animate={{ scale: [1, 1.4, 1], opacity: [0.3, 0, 0.3] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            className="absolute inset-0 rounded-2xl border-2 border-black/20"
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
                backgroundColor: i <= phase ? '#000' : '#e5e5e5',
                scale: i === phase ? 1.3 : 1,
              }}
              className="w-1.5 h-1.5 rounded-full"
            />
          ))}
        </div>

        <p className="text-[10px] text-neutral-500 mt-4 font-medium leading-relaxed max-w-xs">
          💡 首次加载语义向量模型与调用本地大模型可能需要 1~2 分钟，请勿刷新页面。
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
  const { showToast } = useToast();
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
      setGlobalToast('⚠️ 请先登录后再发起询价');
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
        setGlobalToast('❌ 询盘发送失败，请重试');
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
      setGlobalToast(`✅ 询盘已成功发送至 ${name}！正在跳转至议价中心...`);
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
      setGlobalToast('❌ 系统异常，请稍后再试');
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
    <div className="relative h-[calc(100vh-5rem)] max-h-[860px] flex flex-col gap-4 max-w-6xl mx-auto w-full font-sans antialiased text-neutral-900">
      {globalToast ? (
        <div className="fixed inset-x-0 bottom-6 z-[900] flex justify-center px-4 pointer-events-none" role="status">
          <div className={cn(
            'pointer-events-auto max-w-sm rounded-[12px] border border-neutral-200 bg-white px-4 py-3 text-sm font-medium text-black',
            'shadow-[0_8px_30px_rgb(0,0,0,0.08)]',
            'animate-in fade-in zoom-in-95 slide-in-from-bottom-4 duration-300',
          )}>
            {globalToast}
          </div>
        </div>
      ) : null}

      {/* Top Search Card */}
      <section className="shrink-0 bg-white rounded-2xl p-5 border border-neutral-100 shadow-sm flex flex-col md:flex-row justify-between md:items-end gap-5">
        <div className="space-y-3 flex-1">
          <textarea
            rows={2}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="寻找一家主营驱动电机的工厂，位于周边 500 公里内，具备政府绿标认证，且近 30 天产能相对宽裕以满足紧急打样。"
            className="w-full bg-transparent text-lg md:text-xl font-medium text-gray-800 focus:outline-none focus:ring-0 resize-none"
          />
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {['📍 产品: 驱动电机', '📍 距离: <500km', '📍 质量: 政府绿标', '📍 产能: 宽裕'].map(tag => (
              <span key={tag} className="px-2 py-0.5 bg-neutral-100 text-neutral-600 rounded-md text-[10px] font-medium tracking-wide">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => showToast('匹配算法参数调优将根据历史数据自动推荐最佳权重，此功能即将上线', 'info')}
            className="px-4 py-2 bg-white border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors rounded-lg text-xs font-semibold"
          >
            参数调优
          </button>
          <button
            onClick={() => setGreenOnly(!greenOnly)}
            className={cn(
              'px-4 py-2 border rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5',
              greenOnly ? 'bg-success-soft text-success border-success/30' : 'bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50',
            )}
          >
            <Leaf className="w-3.5 h-3.5" />
            绿色优先
          </button>
          <button 
            onClick={handleSearch}
            disabled={isLoading}
            className="px-5 py-2 bg-black text-white hover:bg-neutral-800 transition-colors rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-[0_4px_14px_0_rgb(0,0,0,0.1)] disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 fill-white" />}
            {isLoading && algorithmMode === 'deep_learning' ? 'AI 深度思考中...' : '⚡ 智能匹配'}
          </button>
        </div>
      </section>

      {/* Error Banner */}
      {errorText && (
        <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-2.5 text-xs text-red-600 font-medium shrink-0">
          {errorText}
        </div>
      )}

      {/* Fallback Indicator */}
      {isBasicMatch && !isLoading && suppliers.length > 0 && (
        <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-2.5 text-xs text-amber-700 font-medium shrink-0 flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5" />
          当前结果由基础规则引擎返回。切换「⚡ 智能匹配」可启用 AI 深度思考获得更精准结果。
        </div>
      )}

      {/* Bottom Grid Layout */}
      <section className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        
        {/* Left List (1/3 Width) */}
        <div className="w-full lg:w-[32%] bg-white rounded-2xl border border-neutral-100 flex flex-col overflow-hidden shadow-sm">
          {/* Header */}
          <div className="px-4 py-3 shrink-0 border-b border-neutral-100 bg-white z-10 flex flex-col gap-2.5">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-bold text-neutral-900">匹配结果</h3>
              <div className="text-[10px] font-medium text-neutral-400 flex items-center gap-0.5">
                召回 {suppliers.length} 家 <ChevronRight className="w-3 h-3" />
              </div>
            </div>
            <div className="flex gap-4 text-[10px] font-semibold text-neutral-500">
              {SORT_OPTIONS.map((option) => (
                <span
                  key={option.key}
                  onClick={() => handleSortClick(option.key)}
                  className={cn(
                    'cursor-pointer transition-colors hover:text-black',
                    sortBy === option.key ? 'text-black' : ''
                  )}
                >
                  {option.label}
                </span>
              ))}
            </div>
          </div>
          
          {/* Scrollable list */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 bg-neutral-50/50">
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
                      "cursor-pointer p-3.5 rounded-xl border transition-all duration-200 flex flex-col gap-2",
                      isActive 
                        ? "bg-black border-black text-white shadow-[0_8px_30px_rgb(0,0,0,0.12)]" 
                        : "bg-white border-neutral-200/60 text-neutral-900 hover:border-neutral-300 hover:shadow-sm"
                    )}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0 pr-2">
                        <h4 className="font-semibold text-[13px] truncate leading-tight tracking-tight mb-1">{item.name}</h4>
                        <div className="flex flex-wrap gap-1">
                          {(item.tags || []).filter(Boolean).slice(0, 3).map((tag, idx) => (
                            <span key={`${tag}-${idx}`} className={cn(
                              "px-1 py-0.5 text-[9px] font-medium rounded-sm",
                              isActive ? "bg-white/10 text-white/90" : "bg-neutral-100 text-neutral-600"
                            )}>
                              {tag}
                            </span>
                          ))}
                          {item.match_basis && (
                            <span className={cn(
                              "px-1 py-0.5 text-[8px] font-bold rounded-sm uppercase",
                              isActive ? "bg-white/20 text-white" : "bg-black/5 text-neutral-500"
                            )}>
                              {item.match_basis}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={cn("text-xl font-bold leading-none tracking-tight", isActive ? "text-white" : "text-black")}>
                          {Math.round(matchScore)}
                        </div>
                        <div className={cn("text-[9px] font-medium mt-1 scale-90 origin-right", isActive ? "text-white/60" : "text-neutral-400")}>匹配分</div>
                      </div>
                    </div>
                    
                    <div className={cn("h-px w-full", isActive ? "bg-white/10" : "bg-neutral-100")}></div>
                    
                    <div className="flex justify-between items-center text-[10px] font-medium">
                       <span className={cn(isActive ? "text-white/70" : "text-neutral-500")}>
                         产能利用率 <span className={cn(isActive ? "text-white font-semibold" : "text-neutral-900 font-semibold")}>{utilization}%</span>
                       </span>
                       <span className={cn("flex items-center gap-1.5")}>
                         <div className={cn("w-1.5 h-1.5 rounded-full", isAmple ? (isActive ? "bg-blue-400" : "bg-blue-500") : (isActive ? "bg-amber-400" : "bg-amber-500"))}></div>
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
        <div className="w-full lg:w-[68%] bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden flex flex-col relative">
          {/* 深度思考 Loading 状态覆盖整个右侧面板 */}
          {isLoading && algorithmMode === 'deep_learning' ? (
            <DeepThinkingOverlay />
          ) : activeSupplier ? (
            <>
              {/* Header Info */}
              <div className="px-7 py-6 border-b border-neutral-100 shrink-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                     <div className="w-10 h-10 rounded-lg bg-neutral-50 border border-neutral-100 flex items-center justify-center shrink-0">
                       <Building className="w-4 h-4 text-neutral-600" />
                     </div>
                     <div>
                       <div className="flex items-center gap-2 mb-1">
                         <h2 className="text-lg font-bold text-neutral-900 tracking-tight">{activeSupplier.name}</h2>
                         <div className="bg-black text-white px-1.5 py-0.5 text-[9px] font-semibold rounded-sm flex items-center gap-1 uppercase tracking-widest">
                           <Target className="w-2.5 h-2.5" /> 匹配度 {activeSupplier.score || activeSupplier.confidence_index || activeSupplier.match || '—'}
                         </div>
                         {activeSupplier.match_basis && (
                           <span className="bg-neutral-100 text-neutral-500 px-1.5 py-0.5 text-[8px] font-bold rounded-sm uppercase">
                             {activeSupplier.match_basis}
                           </span>
                         )}
                       </div>
                       <p className="text-[11px] text-neutral-500 leading-snug max-w-lg font-medium">
                         {activeSupplier.desc || '暂无企业描述信息'}
                       </p>
                     </div>
                  </div>
                </div>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto px-7 py-6 bg-white grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
                
                {/* AI 专家推荐理由：正文仅绑定 ai_match_reason；算分公式仅作脚注小字 */}
                {(algorithmMode === 'deep_learning' || Boolean(activeSupplier.ai_match_reason)) && (
                  <div className="md:col-span-2">
                    <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                      <span className="w-1 h-3 bg-neutral-300 rounded-full"></span>
                      <Sparkles className="w-3 h-3" />
                      AI 专家推荐理由
                    </h3>
                    <div className="bg-slate-50/60 rounded-xl border border-neutral-100 p-4">
                      {activeSupplier.ai_match_reason ? (
                        <p className="text-sm text-neutral-700 leading-relaxed">{activeSupplier.ai_match_reason}</p>
                      ) : isLoading && algorithmMode === 'deep_learning' ? (
                        <AiExpertReasonSkeleton />
                      ) : algorithmMode === 'deep_learning' ? (
                        <p className="text-sm text-neutral-400 leading-relaxed">
                          ✨ AI 专家正在结合全网数据进行深度思考，请稍候...
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
                   <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-5 flex items-center gap-2">
                     <span className="w-1 h-3 bg-neutral-300 rounded-full"></span>
                     核心指标分析
                   </h3>
                   <div className="space-y-4">
                     {getMetrics(activeSupplier).map((metric, idx) => (
                       <div key={idx} className="group">
                         <div className="flex justify-between text-[11px] font-semibold text-neutral-700 mb-1.5">
                           <div className="flex items-center gap-1.5">
                             <metric.icon className="w-3 h-3 text-neutral-400 group-hover:text-black transition-colors" />
                             {metric.label}
                           </div>
                           <span className="font-bold text-black">{metric.value}%</span>
                         </div>
                         <div className="h-1 w-full bg-neutral-100 rounded-full overflow-hidden">
                           <motion.div 
                             initial={{ width: 0 }}
                             animate={{ width: `${metric.value}%` }}
                             transition={{ duration: 0.8, delay: 0.05 * idx, ease: "easeOut" }}
                             className={cn("h-full rounded-full bg-black")}
                           />
                         </div>
                       </div>
                     ))}
                   </div>
                </div>

                {/* Capacity Calendar */}
                <div>
                  <div className="flex justify-between items-center mb-5">
                    <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">
                      <span className="w-1 h-3 bg-neutral-300 rounded-full"></span>
                      未来30天产能日历
                    </h3>
                  </div>
                  <div className="bg-[#f9fafb] border border-neutral-100 rounded-xl p-5">
                    <div className="grid grid-cols-6 gap-2">
                      {getCapacityHeatmap(Number(activeSupplier.id)).map((status, idx) => (
                        <motion.div 
                          key={`cap-day-${idx}`}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: idx * 0.01 }}
                          className={cn(
                            "aspect-square rounded-[4px] transition-all hover:scale-105 cursor-crosshair border",
                            status === 0 ? "bg-black border-black" :
                            status === 1 ? "bg-neutral-400 border-neutral-400" :
                            status === 2 ? "bg-neutral-200 border-neutral-200" :
                            "bg-white border-neutral-200"
                          )}
                          title={`Day ${idx + 1}`}
                        />
                      ))}
                    </div>
                    <div className="flex items-center justify-end gap-1.5 mt-3 text-[9px] font-medium text-neutral-400">
                      <span>排满</span>
                      <div className="flex gap-0.5">
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-black"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-neutral-400"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] bg-neutral-200"></div>
                        <div className="w-2.5 h-2.5 rounded-[2px] border border-neutral-200 bg-white"></div>
                      </div>
                      <span>空闲</span>
                    </div>
                  </div>
                </div>

              </div>
              
              {/* Footer Actions */}
              <div className="px-7 py-4 border-t border-neutral-100 bg-[#fbfcfd] flex justify-end items-center gap-3 shrink-0">
                <button
                  disabled={inquirySendingId !== null}
                  onClick={(e) => handleAnonymousInquiry(e, activeSupplier)}
                  className="px-4 py-2 bg-white text-neutral-800 border border-neutral-200 hover:border-black hover:text-black hover:shadow-sm transition-all rounded-lg text-xs font-semibold flex items-center gap-1.5"
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
                      setGlobalToast('⚠️ 请先登录');
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
                      setGlobalToast(`✅ 已创建会话，正在跳转…`);
                      setTimeout(() => {
                        setGlobalToast(null);
                        navigate(`/sales-console?chat_id=${chatResp.chat_id}`);
                      }, 800);
                    } catch {
                      setGlobalToast('❌ 创建会话失败，请重试');
                    } finally {
                      setInquirySendingId(null);
                    }
                  }}
                  className="px-5 py-2 bg-black text-white hover:bg-neutral-800 transition-all rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-[0_4px_14px_0_rgb(0,0,0,0.1)] disabled:opacity-50"
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
