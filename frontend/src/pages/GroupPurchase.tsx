import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, 
  Plus,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Users,
  Package,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, type GroupPurchaseItem, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

// ── 工具函数 ──────────────────────────────────────────────────────────────

function getDeadlineText(deadline: string | null): { text: string; urgent: boolean } {
  if (!deadline) return { text: '无截止时间', urgent: false };
  try {
    const target = new Date(deadline);
    const now = new Date();
    const diffMs = target.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.ceil(diffMs / (1000 * 60 * 60));
    if (diffMs <= 0) return { text: '已截止', urgent: true };
    if (diffHours < 24) return { text: '即刻截止', urgent: true };
    if (diffDays === 1) return { text: '1 天', urgent: true };
    return { text: `${diffDays} 天`, urgent: diffDays <= 3 };
  } catch {
    return { text: '—', urgent: false };
  }
}

function calcProgress(current: number | null, target: number | null): number {
  if (!target || target <= 0) return 0;
  const cur = current || 0;
  return Math.min(100, Math.round((cur / target) * 100));
}

function estimateDiscount(progress: number, participants: number): string {
  // 简单估算节省百分比：参与人越多、进度越高 → 节省越大
  const base = 8 + Math.round(progress * 0.15) + Math.min(participants, 20);
  return `预计节省 ${Math.min(base, 30)}%`;
}

function formatQuantity(n: number | null): string {
  if (n === null || n === undefined) return '—';
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

// ── 骨架屏组件 ────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-white rounded-[16px] p-6 border border-neutral-100 animate-pulse flex flex-col gap-4">
      <div className="flex justify-between">
        <div className="h-5 bg-neutral-100 rounded w-2/3" />
        <div className="h-5 w-20 bg-neutral-100 rounded" />
      </div>
      <div className="space-y-2">
        <div className="flex justify-between">
          <div className="h-3 bg-neutral-100 rounded w-24" />
          <div className="h-3 bg-neutral-100 rounded w-20" />
        </div>
        <div className="h-1.5 bg-neutral-100 rounded-full" />
      </div>
      <div className="flex justify-between items-end">
        <div className="flex -space-x-1.5">
          <div className="w-7 h-7 bg-neutral-100 rounded-full" />
          <div className="w-7 h-7 bg-neutral-100 rounded-full" />
        </div>
        <div className="h-8 w-20 bg-neutral-100 rounded-lg" />
      </div>
    </div>
  );
}

// ── 高级占位头像组件 ──────────────────────────────────────────────────────

const FallbackAvatar: React.FC<{ name: string; bgClass: string; textClass: string; zIndex: number }> = ({ name, bgClass, textClass, zIndex }) => {
  return (
    <div 
      className={cn("w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold border-2 border-white relative overflow-hidden", bgClass, textClass)}
      style={{ zIndex }}
    >
      {name.slice(0, 1)}
    </div>
  );
};

// 根据 id 生成稳定的头像配色
function getAvatarsForGp(gp: GroupPurchaseItem) {
  const combos = [
    { bg: 'bg-slate-800', text: 'text-white' },
    { bg: 'bg-gray-200', text: 'text-gray-700' },
    { bg: 'bg-neutral-100', text: 'text-neutral-500' },
    { bg: 'bg-neutral-800', text: 'text-white' },
    { bg: 'bg-zinc-600', text: 'text-white' },
  ];
  const name = gp.product_name || '拼';
  const count = Math.min(gp.participant_count || 1, 3);
  return Array.from({ length: count }).map((_, i) => ({
    name: name.slice(i, i + 1) || '?',
    ...combos[(gp.id + i) % combos.length],
  }));
}

// ── 主组件 ────────────────────────────────────────────────────────────────

export default function GroupPurchase() {
  const { user, loading: authLoading, setIsLoginModalOpen } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [items, setItems] = useState<GroupPurchaseItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');
  const [joiningId, setJoiningId] = useState<number | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      const res = await api.getGroupPurchases();
      setItems(res.group_purchases || []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setIsLoginModalOpen(true);
      setIsLoading(false);
      setItems([]);
      return;
    }
    void loadData();
  }, [authLoading, user]);

  const handleJoin = async (gpId: number) => {
    if (joiningId !== null) return;
    setJoiningId(gpId);
    try {
      await api.joinGroupPurchase(gpId, 1000); // 默认加入 1000 的数量
      // 重新加载数据以获取最新进度
      await loadData();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : '加入拼单失败');
    } finally {
      setJoiningId(null);
    }
  };

  // 前端搜索过滤
  const filtered = searchQuery.trim()
    ? items.filter(gp => gp.product_name.toLowerCase().includes(searchQuery.toLowerCase()))
    : items;

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-300" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center py-24 px-6 max-w-md mx-auto text-center">
        <Package className="w-12 h-12 text-neutral-300 mb-4" strokeWidth={1.1} />
        <p className="text-sm font-semibold text-neutral-600 mb-2">登录后查看集采拼单</p>
        <p className="text-xs text-neutral-400 mb-6">数据来自数据库中的开放拼单，登录企业账号后即可加载。</p>
        <button
          type="button"
          onClick={() => setIsLoginModalOpen(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-black text-white text-xs font-bold hover:bg-neutral-800"
        >
          去登录
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto w-full font-sans antialiased text-neutral-900 pb-10">
      
      {/* 顶部 Header 区 */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pt-2">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-neutral-900 leading-snug">集采拼单大厅</h1>
          <p className="text-xs text-neutral-500 font-medium tracking-wide mt-1">整合区域零散需求，提升议价能力</p>
        </div>
        
        <div className="flex items-center gap-4 w-full md:w-auto">
          {/* 搜索框 */}
          <div className="relative flex-1 md:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input 
              type="text" 
              placeholder="搜索组件或材料..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-neutral-100 border-transparent focus:border-neutral-300 focus:bg-white focus:ring-0 rounded-lg py-2.5 pl-9 pr-4 text-xs font-semibold text-neutral-800 placeholder:text-neutral-400 transition-all"
            />
          </div>
          
          <button 
            onClick={() => void loadData()}
            disabled={isLoading}
            className="p-2 text-neutral-600 hover:text-black hover:bg-neutral-100 rounded-full transition-colors"
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </button>
          
          <button
            onClick={() => showToast('拼单创建功能即将上线', 'info')}
            className="bg-black text-white px-5 py-2.5 rounded-lg text-xs font-bold hover:bg-neutral-800 transition-all flex items-center gap-2 shadow-[0_4px_14px_0_rgb(0,0,0,0.1)] shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            发起新拼单
          </button>
        </div>
      </header>

      {/* 仅网络/服务端错误时显示，空列表不视为错误 */}
      {errorText && (
        <div className="bg-amber-50/90 border border-amber-100/80 rounded-xl px-4 py-2.5 text-xs text-amber-900 font-medium flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
          <span className="flex-1">{errorText}</span>
          <button type="button" onClick={() => void loadData()} className="text-amber-800 hover:underline text-[10px] font-bold shrink-0">
            重试
          </button>
        </div>
      )}

      {/* 成功拉取但无数据：优雅空状态 */}
      {!isLoading && !errorText && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 px-6 rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/80 max-w-lg mx-auto">
          <Package className="w-12 h-12 text-neutral-300 mb-4" strokeWidth={1.1} />
          <p className="text-sm font-semibold text-neutral-600 mb-1">暂无进行中的集采拼单</p>
          <p className="text-xs text-neutral-400 text-center mb-6">当前没有开放中的拼单。发起新拼单并写入数据库后将在此展示。</p>
          <button
            type="button"
            onClick={() => showToast('拼单创建功能即将上线', 'info')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-black text-white text-xs font-bold hover:bg-neutral-800 shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            发起新拼单
          </button>
        </div>
      )}

      {/* 核心网格内容区 */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <AnimatePresence>
            {filtered.map((gp, i) => {
              const progress = calcProgress(gp.current_quantity, gp.target_quantity);
              const deadline = getDeadlineText(gp.deadline);
              const discount = estimateDiscount(progress, gp.participant_count || 0);
              const avatars = getAvatarsForGp(gp);
              const isJoining = joiningId === gp.id;

              return (
                <motion.div 
                  key={gp.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-white rounded-[16px] p-6 border border-neutral-100 shadow-sm hover:shadow-md hover:border-neutral-200 transition-all group flex flex-col"
                >
                  {/* Header */}
                  <div className="flex justify-between items-start mb-6 gap-3">
                    <h3 className="text-[17px] font-bold tracking-tight leading-snug text-neutral-900 group-hover:text-black transition-colors line-clamp-2">
                      {gp.product_name}
                    </h3>
                    <div className="bg-black text-white px-2 py-1 rounded-[4px] text-[9px] font-bold uppercase tracking-widest shrink-0">
                      {discount}
                    </div>
                  </div>

                  {/* Progress */}
                  <div className="space-y-2 mb-6 mt-auto">
                    <div className="flex justify-between text-[11px] font-bold text-neutral-500">
                      <span>已集结 {formatQuantity(gp.current_quantity)}</span>
                      <span>目标 {formatQuantity(gp.target_quantity)}</span>
                    </div>
                    <div className="w-full h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut' }}
                        className="h-full bg-black rounded-full"
                      />
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex justify-between items-end mt-2">
                    {/* Avatars */}
                    <div className="flex items-center">
                      <div className="flex -space-x-1.5 mr-2">
                        {avatars.map((ava, idx) => (
                          <FallbackAvatar 
                            key={idx} 
                            name={ava.name} 
                            bgClass={ava.bg as string} 
                            textClass={ava.text as string} 
                            zIndex={10 - idx} 
                          />
                        ))}
                      </div>
                      <div className="bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded-[4px] text-[9px] font-bold flex items-center gap-0.5">
                        <Users className="w-2.5 h-2.5" />
                        {gp.participant_count || 0}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col items-end gap-2">
                      <div className={cn(
                        "text-[10px] font-bold pr-1",
                        deadline.urgent ? "text-red-500" : "text-neutral-400"
                      )}>
                        {deadline.text === '已截止' ? '已截止' : `距截止 ${deadline.text}`}
                      </div>
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => navigate(`/group-purchase/${gp.id}`)}
                          className="text-[13px] font-bold text-neutral-500 hover:text-black transition-colors"
                        >
                          查看详情
                        </button>
                        <button 
                          disabled={isJoining || deadline.text === '已截止'}
                          onClick={() => void handleJoin(gp.id)}
                          className="bg-black text-white px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-neutral-800 transition-all shadow-sm disabled:opacity-40 flex items-center gap-1.5"
                        >
                          {isJoining ? (
                            <><Loader2 className="w-3 h-3 animate-spin" /> 加入中</>
                          ) : (
                            '立即加入'
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </section>

      {/* 底部深色报告 Banner */}
      <section className="mt-6 bg-[#0f1115] text-white rounded-3xl p-8 md:p-12 flex flex-col lg:flex-row gap-8 items-center relative overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-white/5 pointer-events-none"></div>
        <div className="flex-1 space-y-4 relative z-10 w-full">
          <div className="text-[9px] font-black tracking-[0.2em] uppercase text-neutral-500">
            Industrial Intelligence
          </div>
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white/90">
            季度集采趋势报告：<br/><span className="text-white">电子元器件波动分析</span>
          </h2>
          <p className="text-neutral-400 text-xs md:text-sm leading-relaxed max-w-lg font-medium pt-2">
            基于 Lianyi 平台全球供应链数据，为您提供最具参考价值的采购决策建议。本季度原材料成本预计下降 4.3% ...
          </p>
          <div className="pt-2">
            <button
              onClick={() => showToast('洞察报告即将上线', 'info')}
              className="bg-white/10 hover:bg-white/20 text-white border border-white/10 px-6 py-2.5 rounded-lg font-bold text-xs transition-all"
            >
              提取完整洞察
            </button>
          </div>
        </div>
        
        {/* 背景装饰文字 */}
        <div className="hidden md:flex absolute right-10 top-1/2 -translate-y-1/2 flex-col items-end opacity-20 pointer-events-none select-none">
           <div className="text-right text-[4rem] font-black leading-none tracking-tighter text-transparent" style={{ WebkitTextStroke: '2px white' }}>
             SMART
           </div>
           <div className="text-right text-[3.5rem] font-black leading-none tracking-tighter text-transparent" style={{ WebkitTextStroke: '1px white' }}>
             MANUFACTURING
           </div>
        </div>
      </section>
      
    </div>
  );
}
