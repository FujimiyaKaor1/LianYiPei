import React, { useCallback, useEffect, useState } from 'react';
import {
  Plus,
  FileText,
  CheckCircle,
  Zap,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type OrderItem, type OrderStatistics, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

type ColumnKey = 'pending' | 'in_progress' | 'completed';

const COLUMNS: { id: ColumnKey; title: string }[] = [
  { id: 'pending', title: '待排产' },
  { id: 'in_progress', title: '生产中' },
  { id: 'completed', title: '已交付' },
];

const FALLBACK_MOCK_ORDERS: OrderItem[] = [
  {
    id: 9001,
    order_no: 'ORD-DEMO-9001',
    product_name: '驱动电机总成',
    quantity: 1200,
    unit: '台',
    customer_name: '华东新能源',
    order_date: '2026-04-01',
    delivery_date: '2026-04-18',
    actual_delivery_date: null,
    status: 'pending',
    notes: '演示兜底数据',
  },
  {
    id: 9002,
    order_no: 'ORD-DEMO-9002',
    product_name: '控制器壳体',
    quantity: 3600,
    unit: '件',
    customer_name: '智行汽车',
    order_date: '2026-03-28',
    delivery_date: '2026-04-10',
    actual_delivery_date: null,
    status: 'in_progress',
    notes: '演示兜底数据',
  },
  {
    id: 9003,
    order_no: 'ORD-DEMO-9003',
    product_name: '精密轴承',
    quantity: 5000,
    unit: '套',
    customer_name: '南方工控',
    order_date: '2026-03-15',
    delivery_date: '2026-03-30',
    actual_delivery_date: '2026-03-29',
    status: 'completed',
    notes: '演示兜底数据',
  },
];

const TOAST_MESSAGE = '订单状态已更新，产能日历已同步。';

function getInitials(name: string): string {
  if (!name) return '??';
  return name.slice(0, 2).toUpperCase();
}

function getBgForId(id: number): string {
  const bgs = ['bg-slate-800', 'bg-slate-700', 'bg-zinc-600', 'bg-neutral-600', 'bg-neutral-500'];
  return bgs[id % bgs.length];
}

function getDeadlineText(order: OrderItem): { text: string; overdue: boolean } {
  if (order.status === 'completed') {
    const d = order.actual_delivery_date || order.delivery_date;
    return { text: d ? `${d} 归档` : '已完成', overdue: false };
  }
  if (!order.delivery_date) return { text: '未设定交期', overdue: false };
  const now = new Date();
  const target = new Date(order.delivery_date);
  const diffMs = target.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return { text: `逾期 ${Math.abs(diffDays)} 天`, overdue: true };
  if (diffDays === 0) return { text: '交货：今日', overdue: false };
  if (diffDays === 1) return { text: '交货：明日', overdue: false };
  return { text: `距交货 ${diffDays} 天`, overdue: false };
}

function estimateProgress(order: OrderItem): number {
  if (order.status === 'completed') return 100;
  if (order.status !== 'in_progress') return 0;
  if (!order.order_date || !order.delivery_date) return 50;
  const start = new Date(order.order_date).getTime();
  const end = new Date(order.delivery_date).getTime();
  const now = Date.now();
  if (end <= start) return 50;
  const progress = ((now - start) / (end - start)) * 100;
  return Math.min(95, Math.max(5, Math.round(progress)));
}

function SkeletonCard() {
  return (
    <div className="card animate-pulse space-y-2.5 p-4">
      <div className="flex justify-between">
        <div className="h-3 bg-neutral-100 rounded w-20" />
        <div className="h-4 bg-neutral-100 rounded w-16" />
      </div>
      <div className="h-4 bg-neutral-100 rounded w-3/4" />
      <div className="h-0.5 bg-neutral-100 rounded-full w-full" />
      <div className="flex justify-between pt-2">
        <div className="h-6 w-6 bg-neutral-100 rounded-full" />
        <div className="h-3 bg-neutral-100 rounded w-16" />
      </div>
    </div>
  );
}

const Avatar = ({ initials, bg = 'bg-slate-800' }: { initials: string; bg?: string }) => (
  <div
    className={cn(
      'flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white text-[9px] font-bold text-white',
      bg,
    )}
  >
    {initials}
  </div>
);

function nextStatus(current: OrderItem['status']): OrderItem['status'] | null {
  if (current === 'pending') return 'in_progress';
  if (current === 'in_progress') return 'completed';
  return null;
}

function prevStatus(current: OrderItem['status']): OrderItem['status'] | null {
  if (current === 'completed') return 'in_progress';
  if (current === 'in_progress') return 'pending';
  return null;
}

export default function OrderPipeline() {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [stats, setStats] = useState<OrderStatistics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [movingId, setMovingId] = useState<number | null>(null);
  const [errorText, setErrorText] = useState('');
  const [fallbackMode, setFallbackMode] = useState(false);
  const [usingClientMock, setUsingClientMock] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = useCallback(() => {
    setToastMsg(TOAST_MESSAGE);
    window.setTimeout(() => setToastMsg(null), 3200);
  }, []);

  const isDemoOrder = (o: OrderItem) => o.id >= 9000;

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    setFallbackMode(false);
    setUsingClientMock(false);
    try {
      const [ordersRes, statsRes] = await Promise.all([
        api.getOrders(),
        api.getOrderStatistics(),
      ]);
      const list = ordersRes.orders || [];
      if (list.length === 0) {
        setUsingClientMock(true);
        setFallbackMode(true);
        setOrders(FALLBACK_MOCK_ORDERS);
        setStats({
          total: FALLBACK_MOCK_ORDERS.length,
          pending: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'pending').length,
          in_progress: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'in_progress').length,
          completed: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'completed').length,
          cancelled: 0,
        });
      } else {
        setOrders(list);
        setStats(statsRes.statistics || null);
      }
    } catch (error) {
      console.error('OrderPipeline loadData failed:', error);
      setErrorText('');
      setFallbackMode(true);
      setUsingClientMock(true);
      setOrders(FALLBACK_MOCK_ORDERS);
      setStats({
        total: FALLBACK_MOCK_ORDERS.length,
        pending: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'pending').length,
        in_progress: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'in_progress').length,
        completed: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'completed').length,
        cancelled: FALLBACK_MOCK_ORDERS.filter((o) => o.status === 'cancelled').length,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const recomputeStats = useCallback((list: OrderItem[]) => {
    setStats({
      total: list.length,
      pending: list.filter((o) => o.status === 'pending').length,
      in_progress: list.filter((o) => o.status === 'in_progress').length,
      completed: list.filter((o) => o.status === 'completed').length,
      cancelled: list.filter((o) => o.status === 'cancelled').length,
    });
  }, []);

  const moveOrderToStatus = async (order: OrderItem, newStatus: OrderItem['status']) => {
    if (newStatus === order.status) return;
    setMovingId(order.id);
    const today = new Date().toISOString().slice(0, 10);

    const applyLocal = (list: OrderItem[]) =>
      list.map((o) => {
        if (o.id !== order.id) return o;
        return {
          ...o,
          status: newStatus,
          actual_delivery_date: newStatus === 'completed' ? today : o.actual_delivery_date,
        };
      });

    try {
      if (usingClientMock || isDemoOrder(order) || fallbackMode) {
        setOrders((prev) => {
          const next = applyLocal(prev);
          recomputeStats(next);
          return next;
        });
        showToast();
        return;
      }

      await api.updateOrderStatus(
        order.id,
        newStatus,
        newStatus === 'completed' ? today : undefined,
      );
      await loadData();
      showToast();
    } catch (error) {
      console.error('moveOrderToStatus failed:', error);
      setOrders((prev) => {
        const next = applyLocal(prev);
        recomputeStats(next);
        return next;
      });
      setUsingClientMock(true);
      showToast();
    } finally {
      setMovingId(null);
    }
  };

  const handleCreateOrder = async () => {
    if (isSubmitting || isLoading) return;
    const now = new Date();
    const orderDate = now.toISOString().slice(0, 10);
    const delivery = new Date(now.getTime() + 1000 * 60 * 60 * 24 * 10).toISOString().slice(0, 10);
    setIsSubmitting(true);
    try {
      await api.createOrder({
        product_name: '新建演示订单',
        quantity: 1000,
        unit: '件',
        customer_name: '演示客户',
        order_date: orderDate,
        delivery_date: delivery,
        notes: '由订单看板快捷创建',
      });
      await loadData();
    } catch (error) {
      console.error('OrderPipeline handleCreateOrder failed:', error);
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAutoSchedule = async () => {
    if (isSubmitting || isLoading) return;
    const pendingOrders = orders.filter((o) => o.status === 'pending');
    if (pendingOrders.length === 0) {
      setErrorText('当前没有待排产订单');
      window.setTimeout(() => setErrorText(''), 2500);
      return;
    }
    setIsSubmitting(true);
    try {
      if (usingClientMock || fallbackMode) {
        setOrders((prev) => {
          const next = prev.map((o) => (o.status === 'pending' ? { ...o, status: 'in_progress' as const } : o));
          recomputeStats(next);
          return next;
        });
        showToast();
        return;
      }
      await Promise.all(pendingOrders.map((order) => api.updateOrderStatus(order.id, 'in_progress')));
      await loadData();
      showToast();
    } catch (error) {
      console.error('OrderPipeline handleAutoSchedule failed:', error);
      setOrders((prev) => {
        const next = prev.map((o) => (o.status === 'pending' ? { ...o, status: 'in_progress' as const } : o));
        recomputeStats(next);
        return next;
      });
      setUsingClientMock(true);
      showToast();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExportReport = () => {
    api.exportOrders();
  };

  const groupedOrders: Record<ColumnKey, OrderItem[]> = {
    pending: orders.filter((o) => o.status === 'pending'),
    in_progress: orders.filter((o) => o.status === 'in_progress'),
    completed: orders.filter((o) => o.status === 'completed'),
  };

  const totalActive = (stats?.pending || 0) + (stats?.in_progress || 0);

  return (
    <div className="panel relative mx-auto flex h-[calc(100vh-6rem)] max-h-[900px] w-full max-w-[1440px] flex-col overflow-hidden font-sans antialiased">
      <AnimatePresence>
        {toastMsg ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="fixed bottom-24 left-1/2 z-[100] max-w-[min(92vw,420px)] -translate-x-1/2 rounded-md bg-sidebar-bg px-5 py-3 text-center text-sm font-medium text-white shadow-elevation-3"
          >
            {toastMsg}
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="panel-header flex shrink-0 items-start justify-between px-6 py-5 md:px-8">
        <div>
          <h1 className="text-xl font-black leading-tight text-ink">
            订单工作流与产能联动
          </h1>
          <p className="mt-1 text-[11px] font-semibold text-ink-muted">
            三列看板对接 /api/orders · 推进状态同步产能日历
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => void loadData()}
            disabled={isLoading}
            className="rounded-md border border-border bg-surface p-1.5 text-ink-muted transition-colors hover:border-border-hover hover:text-ink disabled:opacity-40"
            title="刷新订单"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', isLoading && 'animate-spin')} />
          </button>
          <div className="text-right">
            <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-0.5">
              当前在制订单
            </div>
            <div className="metric-number flex items-baseline gap-1 text-3xl font-black leading-none text-ink">
              {isLoading ? (
                <Loader2 className="w-6 h-6 animate-spin text-neutral-300" />
              ) : (
                <>
                  {totalActive}
                  <span className="text-sm font-bold text-ink-muted">笔</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {errorText ? (
        <div className="mx-6 mb-3 flex shrink-0 items-center gap-2 rounded-md border border-critical/20 bg-critical-soft px-4 py-2.5 text-xs font-semibold text-critical md:mx-8">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          {errorText}
          <button
            type="button"
            onClick={() => void loadData()}
            className="ml-auto text-[10px] font-bold underline hover:text-critical"
          >
            重试
          </button>
        </div>
      ) : null}

      {fallbackMode ? (
        <div className="mx-6 mb-3 flex shrink-0 items-center gap-2 rounded-md border border-risk/20 bg-risk-soft px-4 py-2.5 text-xs font-semibold text-risk md:mx-8">
          <Zap className="w-3.5 h-3.5 shrink-0" />
          {usingClientMock && orders.some(isDemoOrder)
            ? '接口无数据或演示模式：已加载高质量 Mock 订单，仍可体验状态流转。'
            : '后端接口暂不可用，已自动切换到演示数据模式。'}
          <button
            type="button"
            onClick={() => void loadData()}
            className="ml-auto text-[10px] font-bold underline hover:text-risk"
          >
            重试连接
          </button>
        </div>
      ) : null}

      <div className="scrollbar-thin flex min-h-0 flex-1 gap-4 overflow-x-auto overflow-y-hidden px-4 pb-20 md:px-8">
        {COLUMNS.map((col) => {
          const cards = groupedOrders[col.id];
          return (
            <div key={col.id} className="flex min-w-[240px] flex-1 flex-col gap-3 md:max-w-[360px]">
              <div className="flex items-center justify-between shrink-0 pt-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold uppercase text-ink-muted">
                    {col.title}
                  </span>
                  <span className="rounded bg-surface-container px-1.5 py-0.5 text-[9px] font-bold text-ink-muted">
                    {isLoading ? '·' : cards.length}
                  </span>
                </div>
                <button
                  type="button"
                  className="flex h-5 w-5 items-center justify-center rounded text-ink-muted transition-colors hover:bg-surface-container hover:text-ink"
                  aria-label="列操作"
                >
                  <Plus className="w-3 h-3" />
                </button>
              </div>

              <div className="scrollbar-thin flex-1 space-y-2.5 overflow-y-auto pr-1">
                {isLoading ? (
                  Array.from({ length: col.id === 'pending' ? 3 : col.id === 'in_progress' ? 2 : 1 }).map((_, i) => (
                    <SkeletonCard key={i} />
                  ))
                ) : (
                  <AnimatePresence>
                    {cards.map((card, i) => {
                      const deadline = getDeadlineText(card);
                      const progress = estimateProgress(card);
                      const nxt = nextStatus(card.status);
                      const prv = prevStatus(card.status);

                      return (
                        <motion.div
                          key={card.id}
                          layout
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -8 }}
                          transition={{ delay: i * 0.04 }}
                          className={cn(
                            'card p-4',
                            'transition-all hover:border-border-hover hover:shadow-elevation-2',
                            card.status === 'completed' && 'opacity-[0.72]',
                          )}
                        >
                          <div className="flex justify-between items-start mb-2.5">
                            <span className="font-mono text-[10px] text-ink-muted">
                              {card.order_no}
                            </span>
                            {card.status === 'in_progress' ? (
                              <span className="rounded-[4px] bg-brand-soft px-1.5 py-0.5 text-[9px] font-bold text-brand">
                                进度 {progress}%
                              </span>
                            ) : null}
                            {card.status === 'completed' ? (
                              <CheckCircle className="h-3.5 w-3.5 text-trust" />
                            ) : null}
                          </div>

                          <div className="mb-3">
                            <h4
                              className={cn(
                                'text-sm font-bold leading-snug text-ink',
                                card.status === 'completed' && 'line-through text-ink-muted',
                              )}
                            >
                              {card.product_name}{' '}
                              <span className="font-medium text-neutral-400">
                                × {card.quantity?.toLocaleString()} {card.unit}
                              </span>
                            </h4>
                          </div>

                          {card.status === 'in_progress' ? (
                            <div className="mb-3">
                              <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container">
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${progress}%` }}
                                  transition={{ duration: 0.6, ease: 'easeOut' }}
                                  className="h-full rounded-full bg-brand"
                                />
                              </div>
                            </div>
                          ) : null}

                          <div className="flex items-center justify-between gap-2 border-t border-border pt-2.5">
                            <div className="flex items-center -space-x-1.5 min-w-0">
                              <Avatar initials={getInitials(card.customer_name)} bg={getBgForId(card.id)} />
                              <span
                                className={cn(
                                  'text-[10px] font-bold truncate ml-1',
                                  deadline.overdue ? 'text-critical' : 'text-ink-muted',
                                )}
                              >
                                {deadline.text}
                              </span>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              {prv ? (
                                <button
                                  type="button"
                                  disabled={movingId === card.id}
                                  onClick={() => void moveOrderToStatus(card, prv)}
                                  className="rounded-md border border-border p-1.5 text-ink-muted hover:bg-surface-subtle hover:text-ink disabled:opacity-40"
                                  title="回退一列"
                                >
                                  <ChevronLeft className="w-3.5 h-3.5" />
                                </button>
                              ) : null}
                              {nxt ? (
                                <button
                                  type="button"
                                  disabled={movingId === card.id}
                                  onClick={() => void moveOrderToStatus(card, nxt)}
                                  className="rounded-md border border-brand bg-brand p-1.5 text-white hover:bg-brand-hover disabled:opacity-40"
                                  title="推进一列"
                                >
                                  {movingId === card.id ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  ) : (
                                    <ChevronRight className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="absolute bottom-4 inset-x-0 flex justify-center pointer-events-none md:bottom-6">
        <div className="pointer-events-auto flex max-w-[calc(100%-1rem)] items-center gap-0.5 rounded-md border border-border bg-white px-2 py-2 shadow-elevation-3 sm:px-5 sm:py-3">
          <button
            type="button"
            onClick={() => void handleCreateOrder()}
            disabled={isLoading || isSubmitting}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[11px] font-bold text-ink-muted transition-all hover:bg-surface-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 sm:px-4"
          >
            <Plus className="w-3 h-3" />
            新建订单
          </button>
          <div className="mx-1 h-4 w-px bg-border" />
          <button
            type="button"
            onClick={() => void handleAutoSchedule()}
            disabled={isLoading || isSubmitting}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[11px] font-bold text-ink-muted transition-all hover:bg-surface-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 sm:px-4"
          >
            <Zap className="w-3 h-3" />
            智能排产
          </button>
          <div className="mx-1 h-4 w-px bg-border" />
          <button
            type="button"
            onClick={handleExportReport}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-[11px] font-bold text-ink-muted transition-all hover:bg-surface-subtle hover:text-ink sm:px-4"
          >
            <FileText className="w-3 h-3" />
            导出报表
          </button>
        </div>
      </div>
    </div>
  );
}
