import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  CloudUpload,
  Receipt,
  Truck,
  Package,
  Building2,
  ChevronRight,
  Sparkles,
  ShieldCheck,
  Info,
  Plus,
  Loader2,
  CircleAlert,
  CheckCircle2,
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type CreditHistoryRecord } from '@/src/services/api';

/**
 * 意向合作 / 履约协作「纯业务区」：不含应用级 Sidebar / TopBar / 搜索栏。
 * 独立路由页由 Layout 提供外壳；弹窗内仅渲染本组件，避免重复全局导航。
 */
/** 与 Tab 过滤对齐的履约状态（仅闭环/验证两种展示） */
function _recordUiStatus(record: CreditHistoryRecord): 'verifying' | 'completed' {
  return Number(record.change_value || 0) >= 0 ? 'completed' : 'verifying';
}

function _historyStatus(record: CreditHistoryRecord): '已闭环' | '验证中' {
  return _recordUiStatus(record) === 'completed' ? '已闭环' : '验证中';
}


function _scoreLabel(record: CreditHistoryRecord): string {
  const delta = Number(record.change_value || 0);
  if (delta > 0) {
    return `+${delta} 信用分`;
  }
  if (delta < 0) {
    return `${delta} 信用分`;
  }
  return '分值未变';
}


const TAB_ITEMS: { key: 'all' | 'verifying' | 'completed'; label: string }[] = [
  { key: 'all', label: '全部记录' },
  { key: 'verifying', label: '验证中' },
  { key: 'completed', label: '已闭环' },
];

/** 无后端记录时的演示数据（change_value≥0 → completed，&lt;0 → verifying） */
const FALLBACK_FULFILLMENT_DEMO: CreditHistoryRecord[] = [
  {
    id: 'demo-closed-1',
    old_score: 72,
    new_score: 82,
    change_value: 10,
    change_type: 'fulfillment',
    reason: '演示：增值税发票核验通过，履约已闭环',
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
  },
  {
    id: 'demo-closed-2',
    old_score: 82,
    new_score: 88,
    change_value: 6,
    change_type: 'fulfillment',
    reason: '演示：物流回单已归档',
    created_at: new Date(Date.now() - 86400000 * 5).toISOString(),
  },
  {
    id: 'demo-verify-1',
    old_score: 78,
    new_score: 78,
    change_value: -1,
    change_type: 'fulfillment',
    reason: '演示：云端交叉核验中（模拟验证中）',
    created_at: new Date().toISOString(),
  },
];

export function CollaborationWorkspaceBody({
  creditScore,
  history,
  loading,
  onUploadFile,
  uploadLoading,
}: {
  creditScore: number;
  history: CreditHistoryRecord[];
  loading: boolean;
  onUploadFile: (file: File) => Promise<void>;
  uploadLoading: boolean;
}) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadZoneRef = useRef<HTMLDivElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [activeTab, setActiveTab] = useState<'all' | 'verifying' | 'completed'>('all');
  const [showGuide, setShowGuide] = useState(false);
  const [pulseUploadZone, setPulseUploadZone] = useState(false);

  const scorePercent = Math.max(0, Math.min(100, creditScore));
  const ringOffset = 653 - (653 * scorePercent) / 100;
  const gapTo90 = Math.max(0, Math.ceil(90 - creditScore));

  const sourceHistory = useMemo(() => {
    if (history.length > 0) return history;
    if (loading) return [];
    return FALLBACK_FULFILLMENT_DEMO;
  }, [history, loading]);

  const filteredHistory = useMemo(() => {
    const filtered =
      activeTab === 'all'
        ? sourceHistory
        : sourceHistory.filter((item) => _recordUiStatus(item) === activeTab);
    return filtered.slice(0, 8);
  }, [sourceHistory, activeTab]);

  const isUsingDemoList = !loading && history.length === 0 && sourceHistory.length > 0;

  const handleNewFlowClick = () => {
    uploadZoneRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setPulseUploadZone(true);
    window.setTimeout(() => setPulseUploadZone(false), 2400);
  };

  const handleUpload = async (candidate: File | null) => {
    if (!candidate || uploadLoading) return;
    await onUploadFile(candidate);
  };

  return (
    <div className="space-y-12 lg:space-y-16 w-full max-w-full">
      {/* Section A: Hero & Upload */}
      <section className="flex flex-col lg:flex-row gap-10 lg:gap-12 items-center">
        <div className="flex-1 min-w-0">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter text-neutral-900 mb-5">
            合作闭环<span className="text-transparent bg-clip-text bg-gradient-to-r from-black to-neutral-400">与验证</span>
          </h1>
          <p className="text-neutral-500 text-lg sm:text-xl font-light mb-10 lg:mb-12">
            上传真实交易凭证，解锁信用分奖励，构建数字化商业信任
          </p>
          <div className="flex flex-wrap gap-3 lg:gap-4">
            <button
              type="button"
              onClick={handleNewFlowClick}
              className="bg-gradient-to-r from-neutral-900 to-neutral-600 text-white px-6 sm:px-10 py-3 sm:py-4 rounded-2xl font-bold hover:shadow-xl hover:shadow-neutral-500/30 hover:-translate-y-0.5 transition-all flex items-center gap-2 shadow-lg shadow-neutral-500/20 text-sm sm:text-base border border-neutral-600/20"
            >
              <Plus className="w-5 h-5 shrink-0" />
              新建闭环流程
            </button>
            <button
              type="button"
              onClick={() => setShowGuide((v) => !v)}
              className={cn(
                'px-6 sm:px-10 py-3 sm:py-4 rounded-2xl font-bold transition-all shadow-sm text-sm sm:text-base border',
                showGuide
                  ? 'bg-neutral-100 text-black border-neutral-300'
                  : 'bg-white border-neutral-200 text-neutral-700 hover:bg-neutral-50 hover:shadow-md',
              )}
            >
              查看验证指南
            </button>
          </div>
        </div>

        <div ref={uploadZoneRef} className="w-full lg:w-[520px] shrink-0 scroll-mt-24">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={(e) => {
              void handleUpload(e.target.files?.[0] || null);
              e.currentTarget.value = '';
            }}
          />
          <div
            className={cn(
              'border border-dashed bg-[#F8FAFC] rounded-2xl p-8 sm:p-12 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300',
              dragging ? 'border-neutral-500 bg-neutral-100/80 shadow-inner' : 'border-neutral-200 hover:border-neutral-400 hover:bg-neutral-50 hover:shadow-md hover:shadow-neutral-500/5',
              uploadLoading ? 'cursor-wait' : '',
              pulseUploadZone &&
                'ring-2 ring-neutral-500/80 ring-offset-4 ring-offset-[#F8FAFC] shadow-[0_0_0_1px_rgba(0,0,0,0.1),0_0_28px_rgba(0,0,0,0.2)] animate-pulse',
            )}
            onClick={() => !uploadLoading && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              if (!uploadLoading) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (uploadLoading) return;
              const droppedFile = e.dataTransfer.files?.[0] || null;
              void handleUpload(droppedFile);
            }}
          >
            {uploadLoading ? (
              <>
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-neutral-100 flex items-center justify-center mb-5 sm:mb-6 text-neutral-800">
                  <Loader2 className="w-8 h-8 sm:w-10 sm:h-10 animate-spin" />
                </div>
                <h3 className="text-neutral-900 font-extrabold text-lg sm:text-xl mb-2">发票云端核验中，请稍候...</h3>
                <p className="text-neutral-500 text-xs sm:text-sm">后端正在同步校验发票并写入履约记录</p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-neutral-100 flex items-center justify-center mb-5 sm:mb-6 text-neutral-800">
                  <CloudUpload className="w-8 h-8 sm:w-10 sm:h-10" />
                </div>
                <h3 className="text-neutral-900 font-extrabold text-lg sm:text-xl mb-2">拖拽文件至此</h3>
                <p className="text-neutral-500 text-xs sm:text-sm mb-5 sm:mb-6">
                  支持 PDF, JPG, PNG 格式，最大 16MB（点击或拖拽上传）
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {['发票验证', '物流回单', '结算单据'].map((tag) => (
                    <span
                      key={tag}
                      className="px-3 sm:px-4 py-1.5 bg-white border border-neutral-100 text-[10px] sm:text-[11px] font-bold text-neutral-600 rounded-lg shadow-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          {showGuide ? (
            <div className="bg-white rounded-2xl p-6 mt-6 border border-neutral-100 shadow-xl shadow-neutral-200/40 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-neutral-800 to-neutral-300" />
              <div className="flex items-center gap-2 mb-6">
                <Info className="w-5 h-5 text-neutral-800 shrink-0" />
                <span className="text-sm font-extrabold text-neutral-900 tracking-wide">履约验证指南</span>
              </div>
              <div className="space-y-6 relative before:absolute before:inset-0 before:ml-[11px] before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-neutral-200 before:to-transparent">
                {[
                  {
                    title: '上传凭证',
                    desc: '准备真实交易的增值税发票或物流签收单',
                    icon: CloudUpload,
                    color: 'text-neutral-900 bg-neutral-200 ring-white',
                  },
                  {
                    title: '云端核验',
                    desc: '平台将自动调用国家税务局/物流网 API 交叉核验',
                    icon: ShieldCheck,
                    color: 'text-neutral-700 bg-neutral-100 ring-white',
                  },
                  {
                    title: '履约打标',
                    desc: '核验通过后，该笔交易将在区块链存证，状态变更为「已闭环」',
                    icon: CheckCircle2,
                    color: 'text-neutral-500 bg-neutral-50 ring-white border border-neutral-100',
                  },
                  {
                    title: '解锁奖励',
                    desc: '大幅提升信用分，解锁更多大厂询价特权',
                    icon: Sparkles,
                    color: 'text-neutral-400 bg-white ring-white border border-neutral-100',
                  },
                ].map((step, idx) => (
                  <div key={idx} className="relative flex items-start gap-4">
                    <div
                      className={cn(
                        'w-6 h-6 rounded-full flex items-center justify-center shrink-0 ring-4 mt-0.5 relative z-10',
                        step.color
                      )}
                    >
                      <step.icon className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-neutral-900 mb-1">{step.title}</h4>
                      <p className="text-xs text-neutral-500 leading-relaxed">{step.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>

      {/* Section B: Grid — 履约记录流 + 企业信用黑卡 */}
      <section className="grid grid-cols-12 gap-8 lg:gap-12 pb-4">
        <div className="col-span-12 lg:col-span-8 space-y-6 lg:space-y-8">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-3">
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-black">履约记录流</h2>
            <div className="flex gap-4 sm:gap-6 text-xs sm:text-sm border-b border-neutral-200/80 pb-0">
              {TAB_ITEMS.map(({ key, label }) => {
                const active = activeTab === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key)}
                    className={cn(
                      'pb-2.5 transition-colors border-b-2 -mb-px',
                      active
                        ? 'text-black font-bold border-black'
                        : 'text-gray-400 font-medium border-transparent cursor-pointer hover:text-gray-600',
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-3 sm:gap-4">
            {loading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={`history-skeleton-${i}`}
                    className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-neutral-100/50 animate-pulse"
                  >
                    <div className="h-5 bg-neutral-100 rounded w-2/5 mb-3" />
                    <div className="h-4 bg-neutral-100 rounded w-4/5" />
                  </div>
                ))
              : filteredHistory.map((item, i) => {
                const IconComponent = item.change_type === 'fulfillment' ? Receipt : ShieldCheck;
                return (
              <motion.div
                key={item.id || i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 hover:shadow-xl hover:shadow-neutral-200/50 hover:-translate-y-0.5 transition-all group cursor-pointer border border-neutral-100/50"
              >
                <div className="flex items-start sm:items-center gap-4 sm:gap-8 min-w-0">
                  <div className="w-12 h-12 sm:w-14 sm:h-14 bg-neutral-50 rounded-2xl flex items-center justify-center shrink-0">
                    <IconComponent className="w-5 h-5 sm:w-6 sm:h-6 text-black" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-1.5">
                      <span className="text-base sm:text-lg font-bold text-black">{item.id?.toString().slice(0, 8) || 'EVENT'}</span>
                      <span
                        className={cn(
                          'px-2.5 sm:px-3 py-1 text-[9px] sm:text-[10px] font-black rounded uppercase tracking-tighter',
                          _historyStatus(item) === '已闭环'
                            ? 'bg-black text-white'
                            : 'bg-white border border-black/10 text-neutral-400',
                        )}
                      >
                        {_historyStatus(item)}
                      </span>
                    </div>
                    <div className="text-xs sm:text-sm text-neutral-500 font-medium italic line-clamp-2">
                      {item.reason || item.change_type || '信用分变更记录'}
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between sm:justify-end gap-4 sm:gap-10 border-t sm:border-t-0 border-neutral-100 pt-3 sm:pt-0">
                  <div className="text-left sm:text-right">
                    <div className="text-black font-black text-base sm:text-lg">{_scoreLabel(item)}</div>
                    <div className="text-[9px] sm:text-[10px] text-neutral-400 font-bold uppercase tracking-widest">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString('zh-CN') : 'CREDIT EVENT'}
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-neutral-300 group-hover:text-black transition-colors shrink-0" />
                </div>
              </motion.div>
                );
              })}
            {!loading && history.length === 0 && !isUsingDemoList ? (
              <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-neutral-100/50 text-sm text-neutral-500">
                暂无信用分变更记录
              </div>
            ) : null}
            {isUsingDemoList ? (
              <p className="text-[10px] text-neutral-400 font-medium px-1">
                以下为交互演示数据；上传凭证并核验成功后将显示真实履约记录
              </p>
            ) : null}
            {!loading && sourceHistory.length > 0 && filteredHistory.length === 0 ? (
              <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-neutral-100/50 text-sm text-neutral-500">
                当前筛选下暂无记录，试试「全部记录」
              </div>
            ) : null}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="bg-[#0A0A0B] text-white rounded-2xl p-8 sm:p-10 h-fit relative flex flex-col shadow-xl shadow-neutral-900/20 overflow-hidden border border-neutral-800">
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full pointer-events-none" />
            <div className="mb-8 lg:mb-12 relative">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-neutral-400 fill-neutral-400 shrink-0" />
                <span className="text-[10px] font-black tracking-[0.2em] uppercase text-neutral-400">
                  AI 履约评估面板
                </span>
              </div>
              <h3 className="text-2xl sm:text-3xl font-extrabold">企业信用评估</h3>
            </div>

            <div className="flex flex-col items-center justify-center gap-8 lg:gap-10 mb-8 lg:mb-12">
              <div className="relative w-48 h-48 sm:w-56 sm:h-56 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 224 224">
                  <circle
                    className="text-white/5"
                    cx="112"
                    cy="112"
                    fill="transparent"
                    r="104"
                    stroke="currentColor"
                    strokeWidth="12"
                  />
                  <circle
                    className="text-white"
                    cx="112"
                    cy="112"
                    fill="transparent"
                    r="104"
                    stroke="currentColor"
                    strokeDasharray={653}
                    strokeDashoffset={ringOffset}
                    strokeLinecap="round"
                    strokeWidth="12"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-5xl sm:text-6xl font-black tracking-tighter">{Math.round(creditScore)}</span>
                  <span className="text-[10px] sm:text-[11px] font-black text-neutral-400 uppercase tracking-widest mt-1">
                    当前信用分
                  </span>
                </div>
              </div>

              <div className="text-center px-2 sm:px-4 space-y-4 sm:space-y-6">
                <p className="text-base sm:text-lg lg:text-xl font-medium leading-tight">
                  距离解锁{' '}
                  <span className="text-white font-black underline underline-offset-8 decoration-white/30">
                    专精特新专属通道
                  </span>{' '}
                  还差{' '}
                  <span className="bg-white text-black px-2 sm:px-3 py-1 rounded italic font-black mx-1 inline-block rotate-[-2deg]">
                    {gapTo90}
                  </span>{' '}
                  分
                </p>
                <p className="text-[10px] sm:text-xs text-neutral-400 leading-relaxed font-medium">
                  AI 监测到您的履约真实率处于行业前{' '}
                  <span className="text-white font-bold">2%</span>
                  ，继续保持上传真实凭证以获取绿色审批权限。
                </p>
              </div>
            </div>

            <div className="space-y-3 sm:space-y-4 relative">
              <div className="bg-white/5 border border-white/10 rounded-2xl p-4 sm:p-5 flex items-center justify-between backdrop-blur-md gap-3">
                <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                  <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                    <ShieldCheck className="w-4 h-4 sm:w-5 sm:h-5" />
                  </div>
                  <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wide truncate">
                    身份验证强度：极高
                  </span>
                </div>
                <Info className="w-4 h-4 text-neutral-500 cursor-help shrink-0" />
              </div>
              <button
                type="button"
                className="w-full bg-white text-black py-4 sm:py-5 rounded-full font-black text-xs sm:text-sm hover:bg-neutral-100 transition-all active:scale-[0.98] shadow-lg uppercase tracking-widest"
              >
                生成信用月报
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export type CollaborationModalProps = {
  open: boolean;
  onClose: () => void;
  enterpriseId: number | null;
  currentCreditScore: number;
};

export function CollaborationModal({
  open,
  onClose,
  enterpriseId,
  currentCreditScore,
}: CollaborationModalProps) {
  const [history, setHistory] = useState<CreditHistoryRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [scoreFromApi, setScoreFromApi] = useState<number>(currentCreditScore || 70);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    setScoreFromApi(currentCreditScore || 70);
  }, [currentCreditScore]);

  useEffect(() => {
    if (!open || !enterpriseId) {
      return;
    }
    const cacheKey = `credit_history_${enterpriseId}`;
    setHistoryLoading(true);
    (async () => {
      try {
        const [historyResp, scoreResp] = await Promise.all([
          api.fetchCreditHistory(enterpriseId, { limit: 20 }),
          api.fetchCreditScore(enterpriseId),
        ]);
        setHistory(historyResp.records || []);
        setScoreFromApi(Number(scoreResp.credit_score || 70));
        localStorage.setItem(cacheKey, JSON.stringify(historyResp.records || []));
      } catch {
        try {
          const raw = localStorage.getItem(cacheKey);
          setHistory(raw ? (JSON.parse(raw) as CreditHistoryRecord[]) : []);
        } catch {
          setHistory([]);
        }
      } finally {
        setHistoryLoading(false);
      }
    })();
  }, [open, enterpriseId]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(id);
  }, [toast]);

  const validateFile = (file: File): string | null => {
    const maxSize = 16 * 1024 * 1024;
    const validExt = ['pdf', 'jpg', 'jpeg', 'png'];
    const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : '';
    if (!validExt.includes(ext)) {
      return '仅支持 PDF、JPG、JPEG、PNG 格式文件';
    }
    if (file.size > maxSize) {
      return '文件大小超过 16MB，请压缩后重试';
    }
    return null;
  };

  const handleUploadFile = async (file: File) => {
    if (!enterpriseId) {
      setToast({ type: 'error', message: '缺少企业ID，无法上传发票' });
      return;
    }
    const validationMsg = validateFile(file);
    if (validationMsg) {
      setToast({ type: 'error', message: validationMsg });
      return;
    }

    setUploadLoading(true);
    try {
      const now = new Date();
      const invoiceNo = `INV${now.getTime()}`;
      const invoiceDate = now.toISOString().slice(0, 10);
      const resp = await api.uploadInvoice(file, {
        seller_id: enterpriseId,
        invoice_no: invoiceNo,
        invoice_date: invoiceDate,
        invoice_amount: 1,
        quality_rating: 5,
      });

      setToast({
        type: 'success',
        message: '✅ 发票验证通过！已成功写入履约记录，信用分即将更新。',
      });

      const newRecord: CreditHistoryRecord = {
        id: `FULFILL-${resp.fulfillment_id || Date.now()}`,
        old_score: Math.max(0, Math.round(resolvedScore)),
        new_score: Math.min(100, Math.round(resolvedScore + 10)),
        change_value: 10,
        change_type: 'fulfillment',
        reason: `发票 ${resp.invoice_info?.invoice_no || invoiceNo} 验证通过（Reward Issued）`,
        created_at: new Date().toISOString(),
      };
      setHistory((prev) => [newRecord, ...prev]);
      setScoreFromApi((prev) => Math.min(100, Number(prev || resolvedScore) + 10));
    } catch (error) {
      const message = error instanceof Error ? error.message : '上传失败，请稍后重试';
      setToast({ type: 'error', message });
    } finally {
      setUploadLoading(false);
    }
  };

  const resolvedScore = useMemo(() => {
    const v = Number(scoreFromApi || currentCreditScore || 70);
    if (Number.isNaN(v)) {
      return 70;
    }
    return Math.max(0, Math.min(100, v));
  }, [currentCreditScore, scoreFromApi]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  if (!open) {
    return null;
  }

  // 挂到 body：避免 Layout 内容区 overflow 裁剪，并盖住全局侧栏/顶栏；内容仅 CollaborationWorkspaceBody
  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 md:p-8"
      role="dialog"
      aria-modal="true"
      aria-labelledby="collaboration-modal-title"
    >
      <div
        className="relative w-full max-w-6xl h-[85vh] bg-[#F8FAFC] rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-6 right-6 z-20 bg-white/80 backdrop-blur rounded-full p-2 hover:bg-gray-200 cursor-pointer border border-black/5 shadow-sm text-neutral-700"
          aria-label="关闭"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 id="collaboration-modal-title" className="sr-only">
          合作闭环与验证
        </h2>

        {toast ? (
          <div className="absolute top-5 left-1/2 -translate-x-1/2 z-30">
            <div
              className={cn(
                'px-4 py-3 rounded-2xl shadow-lg text-sm font-semibold flex items-center gap-2 border',
                toast.type === 'success'
                  ? 'bg-blue-50 text-blue-800 border-blue-200'
                  : 'bg-red-50 text-red-800 border-red-200',
              )}
              role="status"
            >
              {toast.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 shrink-0" />
              ) : (
                <CircleAlert className="w-4 h-4 shrink-0" />
              )}
              <span>{toast.message}</span>
            </div>
          </div>
        ) : null}

        <div className="flex-1 min-h-0 overflow-y-auto p-8">
          <CollaborationWorkspaceBody
            creditScore={resolvedScore}
            history={history}
            loading={historyLoading}
            onUploadFile={handleUploadFile}
            uploadLoading={uploadLoading}
          />
        </div>
      </div>
    </div>,
    document.body,
  );
}
