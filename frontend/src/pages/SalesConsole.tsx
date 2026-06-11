import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  MessageSquare,
  Bolt,
  ArrowRight,
  Factory,
  Cpu,
  FileText,
  RefreshCw,
  Zap,
  Award,
  TrendingUp,
  ShieldCheck,
  ChevronRight,
  Wallet,
  Loader2,
  AlertTriangle,
  X,
  CheckCircle2,
  EyeOff,
  BarChart3,
  ShieldAlert,
  IdCard,
  Building,
  MapPin,
  Sparkles,
  DollarSign,
  Package,
  Clock,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import {
  api,
  type CreditRiskResult,
  type SalesMessageItem,
  type QuoteSubmitPayload,
  type InquiryChatData,
  type ChatMessageData,
  type BusinessInsightsData,
  type EnterpriseProfile,
} from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { motion, AnimatePresence } from 'motion/react';
import { BusinessCardModal, type BusinessCardData } from '@/src/components/BusinessCardModal';
import { IntentQuoteModal } from '@/src/components/IntentQuoteModal';
import { AnalysisReportModal } from '@/src/components/AnalysisReportModal';

/** 演示数据常量 */
const DEMO_INQUIRY_ID = 1;
const DEMO_BUYER_ENTERPRISE_ID = 2;

const LS_INBOX_KEY = 'lyp_sales_inbox_fallback_v1';

function readLsInbox(): SalesMessageItem[] {
  try {
    const raw = localStorage.getItem(LS_INBOX_KEY);
    if (!raw) return [];
    const j = JSON.parse(raw) as { messages?: SalesMessageItem[] };
    return Array.isArray(j?.messages) ? j.messages : [];
  } catch {
    return [];
  }
}

function appendLsInbox(msg: SalesMessageItem) {
  try {
    const prev = readLsInbox();
    localStorage.setItem(
      LS_INBOX_KEY,
      JSON.stringify({ messages: [msg, ...prev].slice(0, 40), updatedAt: new Date().toISOString() }),
    );
  } catch {
    /* ignore quota */
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 工具函数
// ═══════════════════════════════════════════════════════════════════════════

function formatTime(ts?: string | null): string {
  if (!ts) return '--';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '--';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function deriveBuyerName(message: SalesMessageItem): string {
  const raw = (message.title || '').replace(/^新消息[:：]?\s*/g, '').trim();
  return raw || `采购商#${message.id}`;
}

function deriveDemand(message: SalesMessageItem): string {
  const text = (message.content || '').trim();
  if (!text) return '暂无采购需求描述';
  return text;
}

function extractProductName(message: SalesMessageItem): string {
  const content = `${message.link_url || ''} ${message.content || ''}`;
  const m = content.match(/product_name[=:][\s]*([^&?]+)/i);
  if (m && m[1]) return decodeURIComponent(m[1].trim());
  const hit = content.match(/[\u4e00-\u9fa5A-Za-z0-9]{2,20}(减速机|连接器|线束|模块|芯片|组件|模具|传感器|电机|零件)/);
  return hit ? hit[0] : '精密零部件';
}

function extractInquiryId(message: SalesMessageItem): number | null {
  const content = `${message.link_url || ''} ${message.content || ''}`;
  const m =
    content.match(/inquiry\/(\d+)/i) ||
    content.match(/inquiry_id[=:][\s]*(\d+)/i) ||
    content.match(/inquiry_id["':\s]+(\d+)/i) ||
    content.match(/[?&]inquiry_id=(\d+)/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isNaN(n) ? null : n;
}

function extractBuyerId(message: SalesMessageItem): number | null {
  const raw = `${message.link_url || ''} ${message.content || ''}`;
  const m = raw.match(/[?&]buyer_id=(\d+)/i) || raw.match(/buyer_id[=:]\s*(\d+)/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isNaN(n) ? null : n;
}

function extractEnterpriseId(message: SalesMessageItem): number | null {
  const content = `${message.link_url || ''} ${message.content || ''}`;
  const m =
    content.match(/enterprise\/(\d+)/i) ||
    content.match(/enterprise_id[=:][\s]*(\d+)/i) ||
    content.match(/supplier_id[=:][\s]*(\d+)/i) ||
    content.match(/buyer_id[=:][\s]*(\d+)/i);
  return m ? Number(m[1]) : null;
}

function getRiskStyle(risk: CreditRiskResult | null) {
  if (!risk) return { value: '评估中', text: '正在计算风险等级', color: 'text-neutral-500' };
  if (risk.risk_level === '低风险') {
    return { value: '风险较低', text: `信用评级：${risk.level}（${Math.round(risk.credit_score)}分）`, color: 'text-blue-600' };
  }
  if (risk.risk_level === '高风险') {
    return { value: '风险偏高', text: `信用评级：${risk.level}（${Math.round(risk.credit_score)}分）`, color: 'text-red-500' };
  }
  return { value: '风险中等', text: `信用评级：${risk.level}（${Math.round(risk.credit_score)}分）`, color: 'text-amber-500' };
}

// ═══════════════════════════════════════════════════════════════════════════
// AI 商机洞察卡片
// ═══════════════════════════════════════════════════════════════════════════

function InsightCard({
  label,
  value,
  sub,
  icon: Icon,
  progress,
  loading,
  valueClass,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ComponentType<{ className?: string }>;
  progress?: number;
  loading?: boolean;
  valueClass?: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden">
      <div className="px-4 pt-4 pb-2">
        <div className="text-[10px] text-neutral-400 font-medium uppercase tracking-widest mb-1">{label}</div>
        <div className="flex items-end justify-between gap-2">
          <span className={cn('text-2xl font-black text-neutral-900', valueClass)}>
            {loading ? '--' : value}
          </span>
          {Icon && !loading && <Icon className={cn('w-5 h-5', valueClass || 'text-neutral-400')} />}
        </div>
        {sub && <div className="text-[10px] text-neutral-400 mt-1.5 leading-relaxed">{sub}</div>}
        {progress !== undefined && !loading && (
          <div className="mt-2.5 w-full h-1 bg-neutral-100 rounded-full overflow-hidden">
            <div className="h-full bg-brand-solid rounded-full transition-all duration-700" style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 报价 Modal（融合版：含信用分卡点 + InquiryChat 报价）
// ═══════════════════════════════════════════════════════════════════════════

type QuoteFormState = {
  price: string;
  deliveryDays: string;
  remarks: string;
};

function QuoteModal({
  open,
  chatId,
  productName,
  counterpartyLabel,
  isAnonymous,
  onClose,
  onSuccess,
}: {
  open: boolean;
  chatId: number | null;
  productName: string;
  counterpartyLabel: string;
  isAnonymous: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { user } = useAuth();
  const [form, setForm] = useState<QuoteFormState>({ price: '', deliveryDays: '15', remarks: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [creditScore, setCreditScore] = useState<number | null>(null);
  const [creditLoading, setCreditLoading] = useState(false);

  useEffect(() => {
    if (!open || !user?.id) return;
    let cancelled = false;
    setCreditLoading(true);
    api.fetchCreditScore(user.id)
      .then((d) => { if (!cancelled) setCreditScore(Number(d.credit_score) || null); })
      .catch(() => { if (!cancelled) setCreditScore(null); })
      .finally(() => { if (!cancelled) setCreditLoading(false); });
    return () => { cancelled = true; };
  }, [open, user?.id]);

  useEffect(() => {
    if (open) {
      setForm({ price: '', deliveryDays: '15', remarks: '' });
      setError('');
      setSubmitting(false);
    }
  }, [open]);

  if (!open) return null;

  const unitPrice = Number(form.price);
  const deliveryDays = parseInt(form.deliveryDays, 10) || 0;
  const isUnlimited = creditScore !== null && creditScore >= 90;
  const displayScore = creditScore !== null ? Math.round(creditScore) : null;

  const handleSubmit = async () => {
    if (!chatId) return;
    setError('');
    if (!Number.isFinite(unitPrice) || unitPrice <= 0) {
      setError('请填写有效的预估单价（元）');
      return;
    }
    if (deliveryDays < 1) {
      setError('请填写预计交期（天）');
      return;
    }

    setSubmitting(true);
    try {
      // 优先调用 InquiryChat 正式报价接口（含价格指数触发 + 信用分卡点）
      await api.submitFormalQuote(chatId, {
        price: unitPrice,
        quantity: 5000,
        unit: '件',
        delivery_days: deliveryDays,
        remarks: form.remarks.trim(),
      });
      onSuccess();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '报价提交失败';
      if (msg.includes('今日报价次数已达上限') || msg.includes('信用分不足')) {
        setError(msg);
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-brand-solid/50 backdrop-blur-[2px] p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-2xl border border-neutral-200/80 bg-white shadow-[0_24px_64px_rgba(0,0,0,0.14)]"
      >
        <div className="flex items-start justify-between gap-3 border-b border-neutral-100 px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-neutral-400">意向报价</p>
            <h3 className="mt-1 text-base font-semibold text-neutral-900">{productName || '精密零部件'}</h3>
            <p className="mt-0.5 text-xs text-neutral-500">
              {isAnonymous ? '买方：匿名上市车企' : `买方：${counterpartyLabel}`}
            </p>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-neutral-400 transition hover:bg-neutral-100 hover:text-neutral-800"
            onClick={onClose}
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <label className="block">
            <span className="text-xs font-medium text-neutral-600">预估单价（元）<span className="text-red-500">*</span></span>
            <input
              type="number"
              min={0}
              step="0.01"
              inputMode="decimal"
              placeholder="例如 128.50"
              value={form.price}
              onChange={(e) => setForm((p) => ({ ...p, price: e.target.value }))}
              className="mt-1.5 w-full rounded-xl border border-neutral-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-solid focus:ring-2 focus:ring-neutral-900/10"
            />
          </label>

          <label className="block">
            <span className="text-xs font-medium text-neutral-600">预计交期（天）<span className="text-red-500">*</span></span>
            <input
              type="number"
              min={1}
              step={1}
              placeholder="例如 15"
              value={form.deliveryDays}
              onChange={(e) => setForm((p) => ({ ...p, deliveryDays: e.target.value }))}
              className="mt-1.5 w-full rounded-xl border border-neutral-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-solid focus:ring-2 focus:ring-neutral-900/10"
            />
          </label>

          <label className="block">
            <span className="text-xs font-medium text-neutral-600">补充说明（选填）</span>
            <textarea
              placeholder="质保、开票、付款方式等"
              rows={3}
              value={form.remarks}
              onChange={(e) => setForm((p) => ({ ...p, remarks: e.target.value }))}
              className="mt-1.5 w-full resize-none rounded-xl border border-neutral-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-solid focus:ring-2 focus:ring-neutral-900/10 min-h-[80px]"
            />
          </label>

          {error ? (
            <div className="rounded-xl border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-600 leading-relaxed">
              {error}
            </div>
          ) : null}

          <div className="rounded-xl border border-neutral-100 bg-neutral-50 px-3 py-2.5 text-[11px] text-neutral-600">
            {creditLoading ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                正在同步信用分…
              </span>
            ) : (
              <>
                信用分{' '}
                <span className="font-semibold text-neutral-900">
                  {displayScore ?? '--'}
                </span>
                {isUnlimited
                  ? ' · 报价额度充足'
                  : creditScore !== null
                  ? ` · 今日剩余 ${Math.max(0, 3 - Math.floor(creditScore < 70 ? 1 : 0))} 次`
                  : ' · 暂无报价额度'}
              </>
            )}
          </div>

          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleSubmit()}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-solid py-3 text-sm font-semibold text-white transition hover:bg-brand-solid-hover disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                发送中…
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                发送报价
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 主组件
// ═══════════════════════════════════════════════════════════════════════════

/** 左侧消息列表项（旧版 API 消息） */
type ChatThreadItem = {
  id: string;
  title: string;
  content: string;
  created_at?: string | null;
  is_read: boolean;
  apiMessageId?: number;
  link_url?: string;
};

function chatItemToSalesMessageLike(item: ChatThreadItem): SalesMessageItem {
  return {
    id: item.apiMessageId ?? 0,
    type: '',
    title: item.title,
    content: item.content,
    is_read: item.is_read,
    link_url: item.link_url,
  };
}

export default function SalesConsole() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const bootstrapRef = useRef(false);

  // ── Demo Banner ───────────────────────────────────────────────────────────
  const [demoPerspectiveBanner, setDemoPerspectiveBanner] = useState<string | null>(null);
  const [activeInquiryIdFromState, setActiveInquiryIdFromState] = useState<number | null>(null);

  // ── 采购/销售模式切换 ─────────────────────────────────────────────────────
  const [mode, setMode] = useState<'procurement' | 'sales'>('sales');

  // ── 旧版消息列表 ─────────────────────────────────────────────────────────
  const [chatList, setChatList] = useState<ChatThreadItem[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(true);
  const [messageError, setMessageError] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);

  // ── InquiryChat 会话列表（新） ────────────────────────────────────────────
  const [inquiryChats, setInquiryChats] = useState<InquiryChatData[]>([]);
  const [activeInquiryChatId, setActiveInquiryChatId] = useState<number | null>(null);
  const [inquiryChatLoading, setInquiryChatLoading] = useState(false);

  // ── InquiryChat 消息记录 ─────────────────────────────────────────────────
  const [inquiryMessages, setInquiryMessages] = useState<ChatMessageData[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [msgError, setMsgError] = useState('');
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const messageScrollRef = useRef<HTMLDivElement>(null);

  // ── AI 商机洞察 ───────────────────────────────────────────────────────────
  const [insightLoading, setInsightLoading] = useState(false);
  const [insightError, setInsightError] = useState('');
  const [matchScore, setMatchScore] = useState<number>(0);
  const [risk, setRisk] = useState<CreditRiskResult | null>(null);
  const [profitRate, setProfitRate] = useState<number>(10);
  const [businessInsights, setBusinessInsights] = useState<BusinessInsightsData | null>(null);

  // ── 报价 Modal ────────────────────────────────────────────────────────────
  const [showQuoteModal, setShowQuoteModal] = useState(false);
  const [quoteError, setQuoteError] = useState('');
  const [myCreditScore, setMyCreditScore] = useState<number | null>(null);
  const [myCreditLoading, setMyCreditLoading] = useState(false);
  const [quotesTodayCount, setQuotesTodayCount] = useState(5);
  const [quoteSuccessToast, setQuoteSuccessToast] = useState(false);
  const [fallbackBuyerId] = useState<number | null>(null);

  // ── 意向报价弹窗 ──────────────────────────────────────────────────────────
  const [showIntentQuoteModal, setShowIntentQuoteModal] = useState(false);
  const [intentQuoteSellerId, setIntentQuoteSellerId] = useState<number | null>(null);
  const [intentQuoteProfile, setIntentQuoteProfile] = useState<EnterpriseProfile | null>(null);

  // ── 分析报告弹窗 ──────────────────────────────────────────────────────────
  const [showAnalysisReportModal, setShowAnalysisReportModal] = useState(false);

  // ── 名片交换 ──────────────────────────────────────────────────────────────
  const [showCardModal, setShowCardModal] = useState(false);
  const [myCard, setMyCard] = useState<BusinessCardData | undefined>();
  const [theirCard, setTheirCard] = useState<BusinessCardData | undefined>();
  const [cardExchangeLoading, setCardExchangeLoading] = useState(false);
  const [cardExchangeError, setCardExchangeError] = useState('');
  const [sellerAcceptLoading, setSellerAcceptLoading] = useState(false);
  // 保存已交换的名片（关闭弹窗后仍可再次查看）
  const [savedMyCard, setSavedMyCard] = useState<BusinessCardData | undefined>();
  const [savedTheirCard, setSavedTheirCard] = useState<BusinessCardData | undefined>();

  // ═══════════════════════════════════════════════════════════════════════════
  // 引导逻辑：支持 ?chat_id= 和 location.state 两种激活方式
  // ═══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (bootstrapRef.current) return;
    const st = (location.state as any) || {};
    if (st.fromMatching && st.activeInquiryId) {
      setActiveInquiryIdFromState(Number(st.activeInquiryId));
    }
    if (st.demoPerspectiveHint) {
      setDemoPerspectiveBanner(st.demoPerspectiveHint);
    }
    // 从 URL 参数 ?chat_id= 激活指定 InquiryChat 会话
    const chatIdParam = searchParams.get('chat_id');
    if (chatIdParam) {
      const id = Number(chatIdParam);
      if (!Number.isNaN(id) && id > 0) {
        setActiveInquiryChatId(id);
      }
    }
    const desk = searchParams.get('desk');
    if (desk === 'procurement' || desk === 'sales') {
      setMode(desk);
    }
    // 自动打开意向报价单（从匹配页发起匿名询价后跳转过来）
    if (searchParams.get('auto_quote') === '1') {
      setShowQuoteModal(true);
    }
    bootstrapRef.current = true;
    const sp = new URLSearchParams(searchParams);
    sp.delete('chat_id');
    sp.delete('desk');
    sp.delete('panel');
    sp.delete('auto_quote');
    const rest = sp.toString();
    navigate({ pathname: location.pathname, search: rest ? `?${rest}` : '' }, { replace: true, state: {} });
  }, [location.pathname, location.state, navigate, searchParams]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 加载旧版消息列表（基于 /api/messages）
  // ═══════════════════════════════════════════════════════════════════════════
  const mapSalesToThreads = (list: SalesMessageItem[], prefix: string): ChatThreadItem[] =>
    list.map((m, idx) => ({
      id: `${prefix}-${m.id}-${idx}`,
      title: m.title,
      content: m.content,
      created_at: m.created_at,
      is_read: m.is_read,
      apiMessageId: prefix === 'ls' ? undefined : m.id,
      link_url: m.link_url,
    }));

  const loadMessages = useCallback(async () => {
    setLoadingMessages(true);
    setMessageError('');
    try {
      // 按当前 mode 过滤消息：采购模式 → procurement，销售模式 → sales
      const data = await api.fetchSalesMessages({ page: 1, per_page: 20, mode });
      const list = data.messages || [];
      const mapped = mapSalesToThreads(list, 'api');
      const lsRaw = readLsInbox();
      const lsThreads = mapSalesToThreads(lsRaw, 'ls').filter((t) => {
        const url = t.link_url || '';
        if (url.includes('seller_quote=1')) return true;
        const iid = extractInquiryId(chatItemToSalesMessageLike(t));
        if (!iid) return true;
        return !mapped.some((m) => extractInquiryId(chatItemToSalesMessageLike(m)) === iid);
      });
      const next = [...mapped, ...lsThreads];
      setChatList(() => {
        setActiveChatId((aid) => {
          if (activeInquiryIdFromState) {
            const found = next.find(
              (c) => extractInquiryId(chatItemToSalesMessageLike(c)) === activeInquiryIdFromState,
            );
            if (found) return found.id;
          }
          if (aid && next.some((c) => c.id === aid)) return aid;
          return next[0]?.id ?? null;
        });
        return next;
      });
      setUnreadCount(data.unread_count || 0);
    } catch (error) {
      const lsRaw = readLsInbox();
      const fallback = mapSalesToThreads(lsRaw, 'ls');
      if (fallback.length > 0) {
        setChatList(fallback);
        setActiveChatId((aid) => {
          if (aid && fallback.some((c) => c.id === aid)) return aid;
          return fallback[0]?.id ?? null;
        });
        setUnreadCount(0);
        setMessageError('');
      } else {
        setMessageError(error instanceof Error ? error.message : '消息加载失败');
      }
    } finally {
      setLoadingMessages(false);
    }
  }, [mode, activeInquiryIdFromState]);

  // ── 根据 inquiryChats 中已显示的企业名称，过滤 chatList 中的重复条目 ──
  const filteredChatList = useMemo(() => {
    if (!inquiryChats.length) return chatList;
    const inquiryNames = new Set(inquiryChats.map((c) => c.counterparty_name));
    return chatList.filter((thread) => {
      const name = deriveBuyerName(chatItemToSalesMessageLike(thread));
      return !inquiryNames.has(name);
    });
  }, [chatList, inquiryChats]);

  // mode 切换时重新加载消息
  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 加载 InquiryChat 会话列表（新）
  // ═══════════════════════════════════════════════════════════════════════════
  const loadInquiryChats = useCallback(async () => {
    setInquiryChatLoading(true);
    try {
      const listRole = mode === 'procurement' ? 'buyer' : 'seller';
      const data = await api.getInquiryChats({ role: listRole, limit: 50 });
      // 根据 counterparty_name 去重：同一个企业的多个会话只保留最新一个
      const seen = new Set<string>();
      const uniqueChats = (data.chats || []).filter((chat: InquiryChatData) => {
        const key = chat.counterparty_name;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      setInquiryChats(uniqueChats);
      // 若当前无 activeInquiryChatId 且有会话，自动选中第一个
      setActiveInquiryChatId((prev) => {
        if (prev && uniqueChats.some((c: InquiryChatData) => c.id === prev)) return prev;
        return uniqueChats[0]?.id ?? null;
      });
    } catch {
      setInquiryChats([]);
    } finally {
      setInquiryChatLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void loadInquiryChats();
  }, [loadInquiryChats]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 加载 InquiryChat 消息记录
  // ═══════════════════════════════════════════════════════════════════════════
  const loadInquiryMessages = useCallback(async (chatId: number) => {
    setMsgLoading(true);
    setMsgError('');
    try {
      const data = await api.getChatHistory(chatId, { limit: 50 });
      setInquiryMessages(data.messages || []);
    } catch (err) {
      setMsgError(err instanceof Error ? err.message : '加载聊天记录失败');
      setInquiryMessages([]);
    } finally {
      setMsgLoading(false);
    }
  }, []);

  // ═══════════════════════════════════════════════════════════════════════════
  // 加载 AI 商机评估（融合 InquiryChat insights + 本地算分）
  // ═══════════════════════════════════════════════════════════════════════════
  const loadInsights = useCallback(async (chatId: number) => {
    setInsightLoading(true);
    setInsightError('');
    try {
      // 优先取 InquiryChat 专属商机评估
      const data = await api.getBusinessInsights(chatId);
      setBusinessInsights(data);
      setMatchScore(data.match_score);
      setProfitRate(data.profit_rate);
      const score = Number(data.credit_score || 0);
      let riskLevel: CreditRiskResult['risk_level'] = '中风险';
      if (score >= 85) riskLevel = '低风险';
      else if (score < 70) riskLevel = '高风险';
      setRisk({
        credit_score: score,
        level: data.level || '一般',
        risk_level: riskLevel,
        risk_text: data.risk_detail || '',
      });
    } catch (err) {
      setInsightError(err instanceof Error ? err.message : '商机评估加载失败');
      setBusinessInsights(null);
      // 降级为本地算分
      const baseMatch = 65 + (Math.abs(chatId * 17) % 34);
      const baseProfit = 8 + (Math.abs(chatId * 3) % 15);
      setMatchScore(baseMatch);
      setProfitRate(baseProfit);
      setRisk(null);
    } finally {
      setInsightLoading(false);
    }
  }, []);

  // 旧版消息的商机评估（本地模拟）
  const loadLegacyInsights = useCallback(async (thread: ChatThreadItem) => {
    setInsightLoading(true);
    setInsightError('');
    const sm = chatItemToSalesMessageLike(thread);
    const buyerEnt = extractBuyerId(sm) ?? extractEnterpriseId(sm);
    const seed = (thread.apiMessageId ?? 0) * 17 + (buyerEnt ?? 0);
    const baseMatch = 65 + (Math.abs(seed) % 34);
    const baseProfit = 8 + (Math.abs(seed * 3) % 15);
    try {
      const query = deriveDemand(sm).slice(0, 80);
      const [scoreResult, riskResult] = await Promise.all([
        api.fetchOpportunityScore({ query }),
        api.fetchCreditRisk(buyerEnt ?? user?.id ?? 0),
      ]);
      const blended = Math.round((baseMatch + (scoreResult.score || 0)) / 2);
      setMatchScore(Math.max(55, Math.min(99, blended)));
      setRisk(riskResult);
      setProfitRate(Math.max(6, Math.min(22, Math.round(baseProfit + (scoreResult.score || 0) * 0.04))));
    } catch {
      setMatchScore(baseMatch);
      setProfitRate(baseProfit);
      setRisk(null);
    } finally {
      setInsightLoading(false);
    }
  }, [user?.id]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 派生：当前会话（发送消息、输入限制等依赖，须早于 handleSend）
  // ═══════════════════════════════════════════════════════════════════════════
  const activeChatEarly = useMemo(
    () => chatList.find((c) => c.id === activeChatId) ?? null,
    [chatList, activeChatId],
  );

  const activeInquiryChat = useMemo(
    () => inquiryChats.find((c) => c.id === activeInquiryChatId) ?? null,
    [inquiryChats, activeInquiryChatId],
  );

  /** 对方未回复前，每方最多连续发 2 条文字（与后端一致） */
  const pendingOwnTextCountSincePeer = useMemo(() => {
    let lastPeer = -1;
    inquiryMessages.forEach((m, i) => {
      if (m.message_type === 'text' && !m.is_mine) lastPeer = i;
    });
    let n = 0;
    for (let i = lastPeer + 1; i < inquiryMessages.length; i++) {
      const m = inquiryMessages[i];
      if (m.message_type === 'text' && m.is_mine) n++;
    }
    return n;
  }, [inquiryMessages]);
  const textSendBlocked = pendingOwnTextCountSincePeer >= 2;

  const displayMatchPercent = Math.min(100, Math.max(0, matchScore));

  const canExchangeCard = useMemo(() => {
    if (!activeInquiryChatId || !activeInquiryChat) return false;
    if (activeInquiryChat.status !== 'quoted') return false;
    return activeInquiryChat.match_record_status === 'quote_acknowledged';
  }, [activeInquiryChatId, activeInquiryChat]);

  const isSellerInActiveChat = Boolean(
    user?.id && activeInquiryChat && user.id === activeInquiryChat.seller_id,
  );

  const showSellerAcceptQuote = Boolean(
    isSellerInActiveChat
    && activeInquiryChat?.status === 'quoted'
    && activeInquiryChat?.match_record_status === 'quoted',
  );

  const handleSellerAcceptQuote = async () => {
    if (!activeInquiryChatId) return;
    setSellerAcceptLoading(true);
    setMsgError('');
    try {
      await api.sellerAcceptQuote(activeInquiryChatId);
      await loadInquiryChats();
      await loadInquiryMessages(activeInquiryChatId);
    } catch (err) {
      setMsgError(err instanceof Error ? err.message : '确认失败');
    } finally {
      setSellerAcceptLoading(false);
    }
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // activeInquiryChatId 变化时同步加载消息和商机
  // ═══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (activeInquiryChatId) {
      void loadInquiryMessages(activeInquiryChatId);
      void loadInsights(activeInquiryChatId);
    }
  }, [activeInquiryChatId, loadInquiryMessages, loadInsights]);

  // 只滚动聊天容器，避免把整个企业看板带到页面中部。
  useEffect(() => {
    const messageScroll = messageScrollRef.current;
    if (!messageScroll) return;
    messageScroll.scrollTo({
      top: messageScroll.scrollHeight,
      behavior: 'smooth',
    });
  }, [inquiryMessages]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 发送消息（InquiryChat）
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSend = async () => {
    if (!activeInquiryChatId || !inputValue.trim() || sending || textSendBlocked) return;
    const content = inputValue.trim();
    setInputValue('');
    setSending(true);
    const optimistic: ChatMessageData = {
      id: -Date.now(),
      chat_id: activeInquiryChatId,
      sender_id: user?.id ?? null,
      sender_name: user?.name ?? '我',
      content,
      message_type: 'text',
      msg_metadata: null,
      is_mine: true,
      created_at: new Date().toISOString(),
    };
    setInquiryMessages((prev) => [...prev, optimistic]);
    try {
      const data = await api.sendChatMessage(activeInquiryChatId, { content, message_type: 'text' });
      setInquiryMessages((prev) => {
        const without = prev.filter((m) => m.id !== optimistic.id);
        return [...without, data.message];
      });
    } catch (err) {
      setInquiryMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInputValue(content);
      setMsgError(err instanceof Error ? err.message : '发送失败，请重试');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // 切换采购/销售模式
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSwitchMode = (newMode: 'procurement' | 'sales') => {
    // 仅切换收件箱视角（买方会话 / 卖方会话），不修改会话在库里的 mode 字段
    setMode(newMode);
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // 选中旧版消息会话时加载商机
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSelectChat = async (thread: ChatThreadItem) => {
    // 立即切换选中态，避免 UI 卡顿
    setActiveChatId(thread.id);
    // 异步清理 InquiryChat 状态（不影响主线程渲染）
    setTimeout(() => {
      setActiveInquiryChatId(null);
      setInquiryMessages([]);
      setBusinessInsights(null);
    }, 0);
    if (!thread.is_read && thread.apiMessageId) {
      try {
        const result = await api.markSalesMessageRead(thread.apiMessageId);
        setChatList((prev) =>
          prev.map((c) => (c.id === thread.id ? { ...c, is_read: true } : c)),
        );
        setUnreadCount(result.unread_count ?? 0);
      } catch {
        /* ignore */
      }
    }
    void loadLegacyInsights(thread);
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // 选中 InquiryChat 会话
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSelectInquiryChat = (chat: InquiryChatData) => {
    setActiveChatId(null);
    setActiveInquiryChatId(chat.id);
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // 报价 Modal
  // ═══════════════════════════════════════════════════════════════════════════
  const openQuoteModal = () => {
    setQuoteError('');
    setShowQuoteModal(true);
  };

  const handleQuoteSuccess = () => {
    setQuoteSuccessToast(true);
    setTimeout(() => setQuoteSuccessToast(false), 3200);
    if (activeInquiryChatId) {
      void loadInquiryMessages(activeInquiryChatId);
      void loadInsights(activeInquiryChatId);
      void loadInquiryChats();
    }
    setQuotesTodayCount((c) => c + 1);
  };

  // ── 名片交换 ──────────────────────────────────────────────────────────────
  const handleExchangeCard = async () => {
    if (!activeInquiryChatId) return;
    setCardExchangeLoading(true);
    setCardExchangeError('');
    try {
      // 1. 调用名片交换 API
      const result = await api.exchangeBusinessCard(activeInquiryChatId);
      // 2. 加载我的名片
      const myCardData = await api.getEnterpriseProfileMini(user!.id);
      // 3. 设置双方名片数据
      const myCardObj: BusinessCardData = {
        id: myCardData.enterprise.id,
        name: myCardData.enterprise.name,
        address: myCardData.enterprise.address,
        longitude: myCardData.enterprise.longitude,
        latitude: myCardData.enterprise.latitude,
        contact: myCardData.enterprise.contact,
        phone: myCardData.enterprise.phone,
        main_business: myCardData.enterprise.main_business,
        credit_score: myCardData.enterprise.credit_score,
        is_green_factory: myCardData.enterprise.is_green_factory,
        tags: myCardData.enterprise.tags,
      };
      setMyCard(myCardObj);
      setTheirCard(result.card);
      // 同时保存到持久状态，以便关闭后仍可再次查看
      setSavedMyCard(myCardObj);
      setSavedTheirCard(result.card);
      setShowCardModal(true);
      // 刷新会话状态
      void loadInquiryMessages(activeInquiryChatId);
      void loadInquiryChats();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '名片交换失败';
      if (msg.includes('先完成报价')) {
        setCardExchangeError('请先提交正式报价后再交换名片');
      } else {
        setCardExchangeError(msg);
      }
    } finally {
      setCardExchangeLoading(false);
    }
  };

  // ── 再次查看名片 ────────────────────────────────────────────────────────────
  const handleViewSavedCards = () => {
    if (savedMyCard || savedTheirCard) {
      setMyCard(savedMyCard);
      setTheirCard(savedTheirCard);
      setShowCardModal(true);
    }
  };

  // ── 报价 Modal（信用分） ─────────────────────────────────────────────────
  useEffect(() => {
    if (!showQuoteModal || !user?.id) {
      if (!showQuoteModal) setMyCreditScore(null);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setMyCreditLoading(true);
      try {
        const data = await api.fetchCreditScore(user.id);
        if (!cancelled) setMyCreditScore(Number(data.credit_score) || null);
      } catch {
        if (!cancelled) setMyCreditScore(null);
      } finally {
        if (!cancelled) setMyCreditLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [showQuoteModal, user?.id]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 派生状态
  // ═══════════════════════════════════════════════════════════════════════════
  const activeChat = activeChatEarly;

  const selectedMessage = useMemo(
    () => (activeChat ? chatItemToSalesMessageLike(activeChat) : null),
    [activeChat],
  );

  const riskStyleLocal = getRiskStyle(risk);
  const buyerName = selectedMessage ? deriveBuyerName(selectedMessage) : '采购商';
  const demandText = selectedMessage ? deriveDemand(selectedMessage) : '请选择左侧消息查看详情';
  const displayCreditScore = myCreditScore != null ? Math.round(myCreditScore) : 93;

  /** 当前会话可收藏的对方企业 ID（销售→买方，采购→卖方；匿名会话不展示） */
  const counterpartyEnterpriseId = useMemo(() => {
    if (!user?.id) return null;
    if (activeInquiryChatId && activeInquiryChat) {
      if (activeInquiryChat.is_anonymous) return null;
      if (user.id === activeInquiryChat.seller_id) return activeInquiryChat.buyer_id;
      if (user.id === activeInquiryChat.buyer_id) return activeInquiryChat.seller_id;
      return null;
    }
    if (activeChatId && selectedMessage) {
      const bid = extractBuyerId(selectedMessage);
      const eid = extractEnterpriseId(selectedMessage);
      const cand = bid ?? eid;
      if (cand && cand !== user.id) return cand;
    }
    return null;
  }, [user?.id, activeInquiryChatId, activeInquiryChat, activeChatId, selectedMessage]);

  // ═══════════════════════════════════════════════════════════════════════════
  // 渲染：判断当前选中的是哪种会话
  // ═══════════════════════════════════════════════════════════════════════════
  const hasActiveLegacyChat = activeChatId !== null;
  // 必须是 activeInquiryChatId 存在 AND activeInquiryChat 数据已加载（不为null）
  const hasActiveInquiryChat = activeInquiryChatId !== null && activeInquiryChat !== null;
  const hasAnyActiveChat = hasActiveLegacyChat || hasActiveInquiryChat;

  // ═══════════════════════════════════════════════════════════════════════════
  // 安全派生值（避免空值断言导致的渲染崩溃）
  // ═══════════════════════════════════════════════════════════════════════════
  const safeActiveInquiryChat = hasActiveInquiryChat ? activeInquiryChat : null;

  return (
    <div className="grid grid-cols-12 gap-6 relative">
      {/* Demo Banner */}
      {demoPerspectiveBanner ? (
        <div className="col-span-12 flex items-start justify-between gap-3 rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50 to-white px-4 py-3 text-sm text-indigo-950 shadow-sm animate-in fade-in slide-in-from-top-2 duration-300">
          <p className="leading-relaxed pr-2">{demoPerspectiveBanner}</p>
          <button
            type="button"
            onClick={() => setDemoPerspectiveBanner(null)}
            className="shrink-0 rounded-lg p-1 text-indigo-400 hover:bg-indigo-100/80 hover:text-indigo-700 transition-colors"
            aria-label="关闭提示"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : null}

      {/* Success Toast */}
      <AnimatePresence>
        {quoteSuccessToast && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="fixed bottom-8 left-1/2 z-[70] -translate-x-1/2 rounded-full bg-brand-solid px-5 py-2.5 text-sm font-medium text-white shadow-lg"
          >
            ✅ 意向报价已成功发送
          </motion.div>
        )}
      </AnimatePresence>

      {/* 报价 Modal */}
      <QuoteModal
        open={showQuoteModal}
        chatId={activeInquiryChatId}
        productName={activeInquiryChat?.product_name || activeChat ? extractProductName(selectedMessage || { id: 0, type: '', title: '', content: '', is_read: true }) : ''}
        counterpartyLabel={activeInquiryChat?.counterparty_name || ''}
        isAnonymous={activeInquiryChat?.is_anonymous ?? false}
        onClose={() => setShowQuoteModal(false)}
        onSuccess={handleQuoteSuccess}
      />

      {/* 名片交换弹窗 */}
      <BusinessCardModal
        open={showCardModal}
        myCard={myCard || savedMyCard}
        theirCard={theirCard || savedTheirCard}
        onClose={() => {
          setShowCardModal(false);
        }}
      />

      {/* 意向报价弹窗 */}
      {showIntentQuoteModal && intentQuoteSellerId && (
        <IntentQuoteModal
          open={showIntentQuoteModal}
          sellerId={intentQuoteSellerId}
          productName={activeInquiryChat?.product_name || extractProductName(selectedMessage || { id: 0, type: '', title: '', content: '', is_read: true })}
          enterpriseProfile={intentQuoteProfile || undefined}
          chatId={activeInquiryChatId || undefined}
          matchRecordId={activeInquiryChat?.match_record_id}
          onClose={() => {
            setShowIntentQuoteModal(false);
            setIntentQuoteSellerId(null);
            setIntentQuoteProfile(null);
          }}
          onSuccess={() => {
            // 刷新消息列表
            if (activeInquiryChatId) {
              void loadInquiryMessages(activeInquiryChatId);
            }
          }}
        />
      )}

      {/* 分析报告弹窗 */}
      <AnalysisReportModal
        open={showAnalysisReportModal}
        onClose={() => setShowAnalysisReportModal(false)}
      />

      {/* ═══════════════════════════════════════════════════════════════════
          模块 A：三栏主体区（会话列表 + 聊天 + AI 洞察）
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="col-span-12 bg-white rounded-[24px] border border-neutral-100 shadow-[0_4px_40px_rgba(0,0,0,0.03)] overflow-hidden flex flex-col h-[520px]">

        {/* ── 顶部栏：采购/销售模式切换 ────────────────────────────────── */}
        <div className="px-6 py-3 border-b border-neutral-100 flex items-center justify-between gap-3 flex-wrap bg-white/50">
          <div className="flex items-center gap-3 min-w-0 flex-wrap">
            <MessageSquare className="w-4 h-4 text-primary shrink-0" />
            <span className="text-sm font-bold truncate">
              {safeActiveInquiryChat
                ? `与 ${safeActiveInquiryChat.is_anonymous ? '匿名上市车企' : safeActiveInquiryChat.counterparty_name} 的对话`
                : hasActiveLegacyChat
                ? `与 ${buyerName} 的对话`
                : '对话消息'}
            </span>
            {safeActiveInquiryChat?.is_anonymous && (
              <span className="inline-flex items-center gap-1 text-[9px] text-amber-600 bg-amber-50 border border-amber-100 rounded px-1.5 py-0.5">
                <EyeOff className="w-2.5 h-2.5" />
                匿名询价
              </span>
            )}
            {safeActiveInquiryChat && (
              <span className={cn(
                'shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold',
                safeActiveInquiryChat.status === 'active'
                  ? 'bg-blue-50 text-blue-600'
                  : safeActiveInquiryChat.status === 'quoted'
                  ? 'bg-blue-50 text-blue-600'
                  : safeActiveInquiryChat.status === 'contracted'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-neutral-100 text-neutral-500',
              )}>
                {safeActiveInquiryChat.status === 'active' ? '询价中' : safeActiveInquiryChat.status === 'quoted' ? '已报价' : safeActiveInquiryChat.status === 'contracted' ? '已合作' : '已关闭'}
              </span>
            )}
          </div>

          {/* 采购/销售模式切换 Toggle */}
          <div className="flex flex-col items-end gap-1 shrink-0">
            <div className="flex items-center gap-1 rounded-full bg-neutral-100 p-1">
              {(['procurement', 'sales'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => handleSwitchMode(m)}
                  className={cn(
                    'px-4 py-1.5 rounded-full text-xs font-bold transition-all duration-200',
                    mode === m
                      ? 'bg-white text-neutral-900 shadow-sm'
                      : 'text-neutral-500 hover:text-neutral-700',
                  )}
                >
                  {m === 'procurement' ? '采购模式' : '销售模式'}
                </button>
              ))}
            </div>
            <span className="text-[10px] text-neutral-400 max-w-[220px] text-right leading-snug">
              {mode === 'procurement'
                ? '查看我作为买方参与的会话与询盘'
                : '查看我作为卖方收到的意向与报价'}
            </span>
          </div>
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* ── 左侧：会话列表（双来源：旧 API 消息 + InquiryChat）──────── */}
          <div className="w-72 border-r border-neutral-50 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-neutral-50">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider">对话消息</h3>
                <button
                  type="button"
                  onClick={() => { void loadMessages(); void loadInquiryChats(); }}
                  className="p-1 rounded text-neutral-400 hover:text-neutral-700 transition-colors"
                  title="刷新"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>

              {/* InquiryChat 会话列表 */}
              {inquiryChatLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="p-3 rounded-xl border border-neutral-100 animate-pulse">
                      <div className="h-3 bg-neutral-100 rounded w-3/5 mb-2" />
                      <div className="h-2 bg-neutral-100 rounded w-2/5" />
                    </div>
                  ))}
                </div>
              ) : inquiryChats.length > 0 ? (
                <div className="space-y-1 mb-3">
                  {inquiryChats.map((chat) => (
                    <button
                      key={chat.id}
                      type="button"
                      onClick={() => handleSelectInquiryChat(chat)}
                      className={cn(
                        'w-full text-left p-2.5 rounded-xl flex items-center gap-2.5 transition-colors border',
                        activeInquiryChatId === chat.id
                          ? 'bg-neutral-50 border-neutral-200'
                          : 'hover:bg-neutral-50 border-transparent',
                      )}
                    >
                      <div className={cn(
                        'w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs shrink-0',
                        activeInquiryChatId === chat.id
                          ? 'bg-brand-solid text-white'
                          : 'bg-neutral-100 text-neutral-500',
                      )}>
                        {chat.counterparty_name.charAt(0)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className="text-xs font-semibold truncate">{chat.counterparty_name}</span>
                          {chat.latest_message_at && (
                            <span className="text-[9px] text-neutral-400 shrink-0">{formatTime(chat.latest_message_at)}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 mt-0.5">
                          {chat.is_anonymous && (
                            <span className="inline-flex items-center gap-0.5 text-[9px] text-amber-600 bg-amber-50 rounded px-1 py-0.5">
                              <EyeOff className="w-2 h-2" />
                              匿名
                            </span>
                          )}
                          <span className="text-[9px] text-neutral-400 truncate">
                            {chat.latest_message || chat.product_name || '暂无消息'}
                          </span>
                        </div>
                      </div>
                      {activeInquiryChatId === chat.id && (
                        <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                      )}
                    </button>
                  ))}
                </div>
              ) : null}

              {/* 分隔线 */}
              {(inquiryChats.length > 0 && chatList.length > 0) && (
                <div className="text-[9px] text-neutral-300 font-semibold uppercase tracking-widest mb-2">站内消息</div>
              )}

              {/* 旧版消息列表 */}
              {loadingMessages ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="p-3 rounded-xl border border-neutral-100 animate-pulse">
                      <div className="h-3 bg-neutral-100 rounded w-3/5 mb-2" />
                      <div className="h-2 bg-neutral-100 rounded w-2/5" />
                    </div>
                  ))}
                </div>
              ) : messageError ? (
                <div className="rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-500">
                  <div className="flex items-center gap-2 mb-2"><AlertTriangle className="w-3 h-3" />{messageError}</div>
                  <button onClick={() => void loadMessages()} className="text-[10px] px-2 py-1 rounded bg-white border border-red-200">重试</button>
                </div>
              ) : !filteredChatList.length && !inquiryChats.length ? (
                <div className="p-4 text-xs text-neutral-400 rounded-xl border border-dashed border-neutral-200 text-center">
                  暂无消息
                </div>
              ) : (
                <div className="space-y-1 max-h-[240px] overflow-y-auto no-scrollbar pr-1">
                  {filteredChatList.map((thread) => {
                    const label = deriveBuyerName(chatItemToSalesMessageLike(thread));
                    return (
                      <button
                        key={thread.id}
                        type="button"
                        onClick={() => void handleSelectChat(thread)}
                        className={cn(
                          'w-full text-left p-2.5 rounded-xl flex items-center gap-2.5 transition-colors border',
                          activeChatId === thread.id
                            ? 'bg-neutral-50 border-neutral-200'
                            : 'hover:bg-neutral-50 border-transparent',
                        )}
                      >
                        <div className={cn(
                          'w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs shrink-0',
                          thread.is_read ? 'bg-neutral-100 text-neutral-400' : 'bg-primary/10 text-primary',
                        )}>
                          {label.slice(0, 1)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs truncate font-semibold">{label}</div>
                          <div className="text-[9px] text-neutral-400 truncate">
                            {thread.is_read ? '已读' : '未读'} · {formatTime(thread.created_at)}
                          </div>
                        </div>
                        {!thread.is_read && activeChatId !== thread.id ? (
                          <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                        ) : null}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ── 中间：聊天消息流 ─────────────────────────────────────────── */}
          <div className="flex-1 flex flex-col bg-surface-container-low/30 min-w-0">
            <div ref={messageScrollRef} className="flex-1 p-6 space-y-5 overflow-y-auto no-scrollbar min-h-0">
              {!hasAnyActiveChat ? (
                <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-neutral-200 bg-white/40 px-6 text-center">
                  <MessageSquare className="h-10 w-10 text-neutral-300" aria-hidden />
                  <p className="text-sm font-medium text-neutral-500">请从左侧选择一条会话</p>
                  <p className="text-xs text-neutral-400">选择后将展示与对方的加密对话与 AI 建议</p>
                </div>
              ) : hasActiveInquiryChat ? (
                // ── InquiryChat 消息流 ──────────────────────────────────────
                msgLoading ? (
                  <div className="flex items-center justify-center py-12 gap-2 text-xs text-neutral-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    加载聊天记录…
                  </div>
                ) : msgError ? (
                  <div className="rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-500">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-3 h-3" />
                      {msgError}
                    </div>
                    <button
                      type="button"
                      onClick={() => activeInquiryChatId && void loadInquiryMessages(activeInquiryChatId)}
                      className="text-[10px] px-2 py-1 rounded bg-white border border-red-200"
                    >
                      重试
                    </button>
                  </div>
                ) : inquiryMessages.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                    <MessageSquare className="h-10 w-10 text-neutral-200" />
                    <p className="text-sm text-neutral-400">暂无消息记录，发起询价后即可开始对话</p>
                  </div>
                ) : (
                  inquiryMessages.map((msg) => {
                    // 解析意向报价事件
                    const isIntentQuoteSent = msg.message_type === 'system' && 
                      (msg.msg_metadata as Record<string, unknown>)?.event === 'intent_quote_sent';
                    const intentQuoteData = isIntentQuoteSent ? msg.msg_metadata as Record<string, unknown> : null;
                    const quoteId = intentQuoteData?.quote_id as number | undefined;
                    
                    // 渲染意向报价卡片
                    if (isIntentQuoteSent && intentQuoteData) {
                      return (
                        <div key={msg.id} className="flex justify-center my-3">
                          <div className="w-full max-w-sm rounded-2xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white shadow-lg overflow-hidden">
                            <div className="bg-blue-500 px-4 py-2 flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-white" />
                                <span className="text-sm font-bold text-white">意向报价单</span>
                              </div>
                              <span className="text-[10px] text-blue-100">待对方确认</span>
                            </div>
                            <div className="p-4 space-y-3">
                              <div className="flex items-start gap-3">
                                <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                                  <Building className="w-5 h-5 text-blue-600" />
                                </div>
                                <div className="flex-1">
                                  <p className="text-sm font-bold text-neutral-900">
                                    {msg.content.split('】')[0].replace('【', '') || '采购方'}
                                  </p>
                                  <p className="text-xs text-neutral-500 mt-0.5">发起了意向报价</p>
                                </div>
                              </div>
                              <div className="bg-white rounded-xl p-3 space-y-2 border border-blue-100">
                                {msg.content.split('\n').slice(1).filter(line => line.trim()).map((line, i) => {
                                  const [label, ...valueParts] = line.split('：');
                                  const value = valueParts.join('：');
                                  return (
                                    <div key={i} className="flex items-center justify-between text-sm">
                                      <span className="text-neutral-500">{label}</span>
                                      <span className="font-semibold text-neutral-900">{value || '-'}</span>
                                    </div>
                                  );
                                })}
                              </div>
                              {quoteId && mode === 'sales' && (
                                <div className="flex gap-2 pt-1">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSellerAcceptLoading(true);
                                      api.acceptIntentQuote(quoteId)
                                        .then(() => {
                                          if (activeInquiryChatId) {
                                            void loadInquiryMessages(activeInquiryChatId);
                                          }
                                        })
                                        .catch((err) => {
                                          showToast('同意报价失败，请重试', 'error');
                                          console.error('acceptIntentQuote failed:', err);
                                        })
                                        .finally(() => setSellerAcceptLoading(false));
                                    }}
                                    disabled={sellerAcceptLoading}
                                    className="flex-1 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-white rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-1.5"
                                  >
                                    {sellerAcceptLoading ? (
                                      <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 处理中...</>
                                    ) : (
                                      <><CheckCircle2 className="w-3.5 h-3.5" /> 同意意向报价</>
                                    )}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      api.rejectIntentQuote(quoteId)
                                        .then(() => {
                                          if (activeInquiryChatId) {
                                            void loadInquiryMessages(activeInquiryChatId);
                                          }
                                        })
                                        .catch((err) => {
                                          showToast('操作失败，请重试', 'error');
                                          console.error('rejectIntentQuote failed:', err);
                                        });
                                    }}
                                    className="px-4 py-2 border border-neutral-200 text-neutral-600 rounded-xl text-sm font-medium hover:bg-neutral-50 transition-colors"
                                  >
                                    婉拒
                                  </button>
                                </div>
                              )}
                              <p className="text-[10px] text-neutral-400 text-center pt-1">
                                {formatTime(msg.created_at)}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    
                    if (msg.message_type === 'system') {
                      return (
                        <div key={msg.id} className="flex justify-center">
                          <div className="rounded-full bg-neutral-100 px-4 py-1.5 text-[10px] text-neutral-400">
                            {msg.content}
                          </div>
                        </div>
                      );
                    }
                    return (
                      <div
                        key={msg.id}
                        className={cn('flex items-start gap-3', msg.is_mine ? 'flex-row-reverse' : '')}
                      >
                        <div className={cn(
                          'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0',
                          msg.is_mine ? 'bg-brand-solid text-white' : 'bg-neutral-200 text-neutral-600',
                        )}>
                          {msg.is_mine ? '我' : msg.sender_name.charAt(0)}
                        </div>
                        <div className={cn('max-w-[70%] min-w-0', msg.is_mine ? 'items-end' : 'items-start', 'flex flex-col')}>
                          <div className={cn(
                            'px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm',
                            msg.is_mine
                              ? 'bg-brand-solid text-white rounded-tr-none'
                              : 'bg-white text-neutral-700 rounded-tl-none border border-neutral-100',
                          )}>
                            {msg.content}
                          </div>
                          <div className={cn('mt-1 text-[10px] text-neutral-400', msg.is_mine ? 'text-right' : '')}>
                            {!msg.is_mine && `${msg.sender_name} · `}{formatTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )
              ) : (
                // ── 旧版消息（意向报价风格）───────────────────────────────
                <>
                  <div className="flex items-start gap-4 max-w-[80%]">
                    <div className="w-8 h-8 rounded-full bg-brand-solid shrink-0" />
                    <div className="p-4 bg-white rounded-2xl rounded-tl-none shadow-sm border border-neutral-100">
                      <p className="text-sm text-neutral-700 leading-relaxed">{demandText}</p>
                      <span className="text-[10px] text-neutral-400 mt-2 block">
                        {formatTime(activeChat?.created_at)}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-start justify-end gap-4 max-w-[85%]">
                      <div className="p-5 bg-primary text-white rounded-3xl rounded-tr-none shadow-xl relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl -mr-16 -mt-16 rounded-full" />
                        <div className="flex items-center gap-2 mb-2 relative">
                          <Bolt className="w-4 h-4 text-blue-400 fill-blue-400" />
                          <span className="text-xs font-bold tracking-widest uppercase">链小易 AI Agent</span>
                        </div>
                        <p className="text-sm leading-relaxed opacity-90 relative">
                          已为您提取商机：
                          <span className="underline underline-offset-4 decoration-blue-400 font-bold">
                            {extractProductName(selectedMessage || { id: 0, type: '', title: '', content: '', is_read: true })}
                          </span>
                          。根据实时库存与排产计划分析：当前产能可评估，建议结合价格指数后快速报价。
                        </p>
                        <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between gap-3 relative">
                          <span className="text-xs font-medium">是否一键生成意向报价单？</span>
                          <button
                            type="button"
                            onClick={openQuoteModal}
                            className="shrink-0 bg-white text-primary px-4 py-1.5 rounded-full text-[10px] font-bold hover:bg-neutral-100 transition-colors"
                          >
                            立即生成
                          </button>
                        </div>
                      </div>
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0">
                        <Zap className="w-4 h-4 text-white" />
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* ── 输入区（仅 InquiryChat 会话可用）─────────────────────── */}
            {hasActiveInquiryChat && (
              <div className="px-6 py-4 bg-white border-t border-neutral-100 space-y-3">
                {showSellerAcceptQuote && !showCardModal && (
                  <div className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-xl bg-amber-50 border border-amber-100 text-xs text-amber-900">
                    <span>已提交正式报价，请先确认同意该意向报价，再与对方交换名片。</span>
                    <button
                      type="button"
                      onClick={() => void handleSellerAcceptQuote()}
                      disabled={sellerAcceptLoading}
                      className="ml-auto shrink-0 flex items-center gap-1 px-3 py-1.5 bg-amber-600 text-white rounded-lg text-[10px] font-bold hover:bg-amber-700 disabled:opacity-50"
                    >
                      {sellerAcceptLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                      {sellerAcceptLoading ? '确认中…' : '同意意向报价'}
                    </button>
                  </div>
                )}
                {/* 名片交换状态提示 */}
                {canExchangeCard && !showCardModal && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-50 border border-blue-100 text-xs text-blue-700">
                    <IdCard className="w-4 h-4 shrink-0" />
                    <span>卖方已同意意向报价，可交换名片达成合作</span>
                    <button
                      type="button"
                      onClick={() => void handleExchangeCard()}
                      disabled={cardExchangeLoading}
                      className="ml-auto shrink-0 flex items-center gap-1 px-3 py-1 bg-blue-600 text-white rounded-lg text-[10px] font-bold hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                      {cardExchangeLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <IdCard className="w-3 h-3" />}
                      {cardExchangeLoading ? '交换中…' : '交换名片'}
                    </button>
                  </div>
                )}
                {/* 已交换名片 - 再次查看按钮 */}
                {(savedMyCard || savedTheirCard) && !showCardModal && !canExchangeCard && (
                  <button
                    type="button"
                    onClick={handleViewSavedCards}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-neutral-50 border border-neutral-200 text-xs text-neutral-600 hover:bg-neutral-100 hover:border-neutral-300 transition-colors w-full"
                  >
                    <IdCard className="w-4 h-4" />
                    <span>已交换名片</span>
                    <span className="ml-auto font-medium">点击再次查看</span>
                  </button>
                )}
                {cardExchangeError ? (
                  <div className="px-3 py-2 rounded-xl bg-red-50 border border-red-100 text-xs text-red-600">
                    {cardExchangeError}
                  </div>
                ) : null}
                {textSendBlocked ? (
                  <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                    对方未回复前，您最多连续发送 2 条文字消息，请等待对方回复后再发。
                  </p>
                ) : null}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="输入消息内容，按 Enter 发送…"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={sending || textSendBlocked}
                    className="flex-1 rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-2.5 text-sm outline-none focus:border-brand-solid focus:ring-2 focus:ring-neutral-900/10 transition-colors disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={() => void handleSend()}
                    disabled={sending || !inputValue.trim() || textSendBlocked}
                    className="shrink-0 rounded-xl bg-brand-solid px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-solid-hover disabled:opacity-50"
                  >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : '发送'}
                  </button>
                  {isSellerInActiveChat && (
                    <button
                      type="button"
                      onClick={openQuoteModal}
                      className="shrink-0 flex items-center gap-1.5 rounded-xl bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition hover:bg-primary/20"
                    >
                      <FileText className="w-4 h-4" />
                      正式报价单
                    </button>
                  )}
                  {mode === 'procurement' && counterpartyEnterpriseId && (
                    <button
                      type="button"
                      onClick={() => {
                        // 打开意向报价弹窗
                        const targetId = counterpartyEnterpriseId;
                        if (targetId) {
                          api.getEnterprisePublicProfile(targetId)
                            .then((res) => setIntentQuoteProfile(res.profile))
                            .catch(() => {});
                          setIntentQuoteSellerId(targetId);
                        }
                        setShowIntentQuoteModal(true);
                      }}
                      className="shrink-0 flex items-center gap-1.5 rounded-xl bg-blue-50 border border-blue-200 px-4 py-2.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
                    >
                      <DollarSign className="w-4 h-4" />
                      发起意向报价
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ── 右侧：AI 商机洞察面板 ───────────────────────────────────── */}
          <div className="w-64 border-l border-neutral-50 p-5 flex flex-col gap-4 bg-neutral-50/30 overflow-y-auto no-scrollbar">
            <div className="space-y-1">
              <h4 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">AI 实时商机评估</h4>
              <div className="text-lg font-bold">商机洞察</div>
            </div>
            <div className="space-y-4">
              {[
                {
                  label: '匹配度',
                  value: `${displayMatchPercent}%`,
                  icon: ShieldCheck,
                  color: displayMatchPercent >= 75 ? 'text-blue-500' : 'text-amber-500',
                  progress: displayMatchPercent,
                  loading: insightLoading,
                },
                {
                  label: '预计利润率',
                  value: `${profitRate}%`,
                  sub: profitRate >= 12 ? '+2.1%' : '+0.8%',
                  subText: '基于当前需求估算',
                  loading: insightLoading,
                },
                {
                  label: '客户风险评估',
                  value: riskStyleLocal.value,
                  subText: riskStyleLocal.text,
                  loading: insightLoading,
                  valueClass: riskStyleLocal.color,
                },
              ].map((item, i) => (
                <div key={i} className="p-4 bg-white rounded-2xl shadow-sm border border-neutral-100">
                  <div className="text-[10px] text-neutral-400 mb-1">{item.label}</div>
                  <div className="flex items-end justify-between">
                    <span className={cn('text-2xl font-black text-primary', item.valueClass)}>
                      {item.loading ? '--' : item.value}
                    </span>
                    {item.icon && <item.icon className={cn('w-5 h-5', item.color)} />}
                    {item.sub && <span className="text-[10px] text-blue-500 font-bold">{item.sub}</span>}
                  </div>
                  {item.subText && <p className="text-[10px] text-neutral-400 mt-2">{item.subText}</p>}
                  {item.label === '匹配度' && !item.loading && (
                    <div className="mt-2 w-full h-1 bg-neutral-100 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-solid" style={{ width: `${item.progress || 0}%` }}></div>
                    </div>
                  )}
                </div>
              ))}
              {insightError ? (
                <div className="text-[10px] text-red-500 bg-red-50 border border-red-100 rounded-xl p-2">
                  商机评估加载失败：{insightError}
                </div>
              ) : null}
            </div>

            {/* 已交换名片入口 */}
            {(savedMyCard || savedTheirCard) && (
              <button
                type="button"
                onClick={handleViewSavedCards}
                className="flex items-center gap-3 p-4 bg-gradient-to-r from-blue-50 to-teal-50 border border-blue-100 rounded-2xl hover:from-blue-100 hover:to-teal-100 transition-all"
              >
                <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center">
                  <IdCard className="w-5 h-5 text-white" />
                </div>
                <div className="text-left flex-1">
                  <div className="text-sm font-bold text-blue-700">名片已交换</div>
                  <div className="text-[10px] text-blue-600">点击查看双方名片</div>
                </div>
                <ChevronRight className="w-4 h-4 text-blue-400" />
              </button>
            )}

            <button
              type="button"
              onClick={() => setShowAnalysisReportModal(true)}
              className="mt-auto w-full py-3 bg-white border border-neutral-200 rounded-xl text-xs font-bold hover:bg-neutral-50 transition-colors"
            >
              查看详细分析报告
            </button>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          模块 B：意向合作漏斗（保留原有模块）
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="col-span-8 bg-white rounded-[24px] border border-neutral-100 shadow-[0_4px_40px_rgba(0,0,0,0.03)] p-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="font-bold text-lg">意向合作漏斗</h2>
            <p className="text-xs text-neutral-400 mt-1">当前进行中的 48 个合作项目</p>
          </div>
          <button
            onClick={() => navigate('/orders')}
            className="text-xs font-bold text-neutral-400 hover:text-primary transition-colors flex items-center gap-1"
          >
            全部动态 <ArrowRight className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-4">
          {[
            { name: '某大型通讯企业', project: '5G 基站精密连接器采购', status: '意向报价中', amount: '¥ 458,000.00', date: '截止日期：明天', icon: Factory, color: 'text-blue-500', bg: 'bg-blue-50' },
            { name: '东莞泰科电子', project: '高频线束定制打样', status: '线下打样中', amount: '待定', date: '进度：样品已寄出', icon: Cpu, color: 'text-orange-500', bg: 'bg-orange-50' },
            { name: '华南仪器厂', project: '年度传感模块框架协议', status: '待签电子合同', amount: '¥ 2,240,000.00', date: '生效期：2024Q3', icon: FileText, color: 'text-blue-500', bg: 'bg-blue-50' },
          ].map((item, i) => (
            <div key={i} className="group flex items-center justify-between gap-3 p-4 hover:bg-surface-container-low rounded-2xl transition-all border border-transparent hover:border-neutral-100">
              <div className="flex items-center gap-4 min-w-0 flex-1 cursor-pointer">
                <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center shrink-0', item.bg, item.color)}>
                  <item.icon className="w-6 h-6" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-sm font-bold truncate">{item.name}</h4>
                  <p className="text-xs text-neutral-400 truncate">项目：{item.project}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 sm:gap-6 shrink-0">
                <span className={cn('px-3 py-1 rounded-full text-[10px] font-bold whitespace-nowrap', item.bg, item.color)}>{item.status}</span>
                <div className="text-right hidden sm:block">
                  <div className="text-xs font-bold">{item.amount}</div>
                  <div className="text-[10px] text-neutral-400">{item.date}</div>
                </div>
                <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-primary hidden sm:block" />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════
          模块 C：企业资产画像 + 快速特权（保留原有模块）
      ═══════════════════════════════════════════════════════════════════ */}
      <section className="col-span-4 flex flex-col gap-6">
        <div className="bg-gradient-to-br from-brand-solid via-brand-solid-hover to-brand-deep rounded-[24px] p-8 text-white relative overflow-hidden shadow-xl">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 blur-3xl rounded-full"></div>
          <div className="relative z-10">
            <h3 className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-4">企业资产画像</h3>
            <div className="flex items-center justify-between mb-8">
              <div>
                <div className="text-4xl font-black">92</div>
                <div className="text-xs text-neutral-400 mt-1">履约信用分</div>
              </div>
              <div className="bg-white/10 px-4 py-2 rounded-xl backdrop-blur-md">
                <div className="text-[10px] text-neutral-300">行业排名</div>
                <div className="text-sm font-bold">超越 88% 同行</div>
              </div>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">信用额度：</span>
                <span className="font-bold">¥ 5,000,000.00</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-400">本月回款：</span>
                <span className="font-bold text-blue-400">¥ 842,500.00</span>
              </div>
            </div>
            <button
              onClick={() => navigate('/orders')}
              className="mt-8 w-full py-4 bg-white text-primary rounded-xl text-sm font-bold flex items-center justify-center gap-2 hover:bg-neutral-100 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              一键同步 SaaS 订单系统
            </button>
          </div>
        </div>

        <div className="bg-white rounded-[24px] border border-neutral-100 shadow-[0_4px_40px_rgba(0,0,0,0.03)] p-6">
          <h4 className="text-xs font-bold text-neutral-400 uppercase tracking-wider mb-4">快速特权</h4>
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: TrendingUp, label: '优先抢单', path: '/matching' },
              { icon: Wallet, label: '账期保理', path: '/assets' },
              { icon: Award, label: '优质商机', path: '/enterprise-directory' },
              { icon: Zap, label: 'AI 营销', path: '/sales-console' },
            ].map((item, i) => (
              <button
                key={i}
                onClick={() => navigate(item.path)}
                className="p-4 bg-surface-container-low rounded-2xl flex flex-col gap-2 items-center text-center hover:bg-neutral-100 transition-colors group"
              >
                <item.icon className="w-5 h-5 text-primary group-hover:scale-110 transition-transform" />
                <span className="text-[10px] font-bold">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
