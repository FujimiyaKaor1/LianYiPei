import React, { useState, useEffect } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight, Loader2, Package, RefreshCw, Settings2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { api } from '@/src/services/api';

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

interface DayInfo { utilization: number; order_count: number; orders_count?: number; date?: string }

/** 合并按「日序号」与「YYYY-MM-DD」两种 key 的后端数据，保证格子能命中 dateStr */
function normalizeCapacityDays(raw: Record<string, DayInfo> | undefined): Record<string, DayInfo> {
  if (!raw || typeof raw !== 'object') return {};
  const out: Record<string, DayInfo> = { ...raw };
  for (const v of Object.values(raw)) {
    if (v && typeof v === 'object' && v.date) {
      out[v.date] = v;
    }
  }
  return out;
}

export default function CapacityCalendar() {
  const { user, loading: authLoading, setIsLoginModalOpen } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [days, setDays] = useState<Record<string, DayInfo>>({});
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(false);
  const [loadErrorMessage, setLoadErrorMessage] = useState('');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dateOrders, setDateOrders] = useState<any[]>([]);
  const [dateLoading, setDateLoading] = useState(false);

  const loadCalendar = async (y: number, m: number) => {
    setFetching(true);
    setError(false);
    setLoadErrorMessage('');
    try {
      const res = await api.getCapacityCalendar(y, m);
      setDays(normalizeCapacityDays(res.days));
    } catch (e) {
      setError(true);
      setLoadErrorMessage(e instanceof Error ? e.message : '加载失败');
    } finally {
      setFetching(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setIsLoginModalOpen(true); return; }
    void loadCalendar(year, month);
  }, [authLoading, user, year, month]);

  const prevMonth = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12); }
    else setMonth(m => m - 1);
    setSelectedDate(null);
  };

  const nextMonth = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1); }
    else setMonth(m => m + 1);
    setSelectedDate(null);
  };

  const handleDateClick = async (dateStr: string) => {
    setSelectedDate(dateStr);
    setDateLoading(true);
    try {
      const res = await api.getOrdersByDate(dateStr);
      setDateOrders(res.orders || []);
    } catch {
      setDateOrders([]);
    } finally {
      setDateLoading(false);
    }
  };

  // Build calendar grid
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  const startOffset = (firstDay.getDay() + 6) % 7; // Monday-based
  const totalDays = lastDay.getDate();
  const cells: (number | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= totalDays; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const getColor = (util: number) => {
    if (util >= 80) return 'bg-red-100 text-red-700 border-red-200';
    if (util >= 50) return 'bg-amber-50 text-amber-700 border-amber-200';
    if (util > 0) return 'bg-blue-50 text-blue-700 border-blue-200';
    return 'bg-neutral-50 text-neutral-400 border-neutral-100';
  };

  if (authLoading) {
    return <div className="flex items-center justify-center py-32"><Loader2 className="w-6 h-6 animate-spin text-neutral-300" /></div>;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={prevMonth} className="w-9 h-9 flex items-center justify-center rounded-lg border border-neutral-200 hover:bg-neutral-100 transition-all">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <h2 className="text-xl font-black tracking-tight">{year} 年 {month} 月</h2>
          <button onClick={nextMonth} className="w-9 h-9 flex items-center justify-center rounded-lg border border-neutral-200 hover:bg-neutral-100 transition-all">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-bold">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-blue-100 border border-blue-200" /> &lt;50%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-amber-50 border border-amber-200" /> 50-80%</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-100 border border-red-200" /> &gt;80%</span>
        </div>
      </div>

      {error ? (
        <div className="bg-white rounded-2xl border border-neutral-100 p-8 flex flex-col items-center max-w-md mx-auto">
          <CalendarDays className="w-10 h-10 text-neutral-300 mb-3" strokeWidth={1.25} />
          <p className="text-sm text-neutral-500 mb-1 text-center">无法加载产能日历</p>
          {loadErrorMessage ? <p className="text-[11px] text-neutral-400 mb-4 text-center">{loadErrorMessage}</p> : null}
          <button type="button" onClick={() => void loadCalendar(year, month)} className="flex items-center gap-1.5 px-4 py-2 bg-brand-solid text-white rounded-lg text-xs font-bold hover:bg-brand-solid-hover">
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6">
          {fetching ? (
            <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-neutral-300" /></div>
          ) : (
            <>
              {/* Weekday Headers */}
              <div className="grid grid-cols-7 gap-2 mb-2">
                {WEEKDAYS.map(w => (
                  <div key={w} className="text-center text-[10px] font-bold text-neutral-400 uppercase tracking-widest py-2">{w}</div>
                ))}
              </div>
              {/* Calendar Grid */}
              <div className="grid grid-cols-7 gap-2">
                {cells.map((day, i) => {
                  if (day === null) return <div key={`empty-${i}`} className="aspect-square" />;
                  const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                  const info = days[dateStr] || days[String(day)] || null;
                  const util = info?.utilization ?? 0;
                  const oc = info?.order_count ?? info?.orders_count ?? 0;
                  const isSelected = selectedDate === dateStr;
                  const isToday = year === now.getFullYear() && month === now.getMonth() + 1 && day === now.getDate();

                  return (
                    <motion.button
                      key={dateStr}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => void handleDateClick(dateStr)}
                      className={cn(
                        'aspect-square rounded-xl border flex flex-col items-center justify-center gap-0.5 transition-all relative',
                        getColor(util),
                        isSelected && 'ring-2 ring-black ring-offset-1',
                        isToday && 'font-black',
                      )}
                    >
                      <span className="text-sm font-bold">{day}</span>
                      {info && <span className="text-[8px] font-medium">{util}%</span>}
                      {info && oc > 0 && (
                        <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-brand-solid/30" />
                      )}
                    </motion.button>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* Date Detail Panel */}
      <AnimatePresence>
        {selectedDate && (
          <motion.div
            initial={{ opacity: 0, y: 16, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: 16, height: 0 }}
            className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6 overflow-hidden"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold">{selectedDate} 订单明细</h3>
              <button onClick={() => setSelectedDate(null)} className="text-[10px] font-bold text-neutral-400 hover:text-black transition-colors">关闭</button>
            </div>
            {dateLoading ? (
              <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-neutral-300" /></div>
            ) : dateOrders.length === 0 ? (
              <p className="text-xs text-neutral-400 text-center py-8">该日暂无订单</p>
            ) : (
              <div className="divide-y divide-neutral-50">
                {dateOrders.map((order: any, i: number) => (
                  <div key={order.id || i} className="flex items-center justify-between py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-neutral-100 rounded-lg flex items-center justify-center">
                        <Package className="w-4 h-4 text-neutral-500" />
                      </div>
                      <div>
                        <p className="text-xs font-medium">{order.product_name}</p>
                        <p className="text-[10px] text-neutral-400">{order.customer_name} · {order.quantity} {order.unit}</p>
                      </div>
                    </div>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-[9px] font-bold',
                      order.status === 'completed' ? 'bg-blue-50 text-blue-600' :
                      order.status === 'in_progress' ? 'bg-blue-50 text-blue-600' :
                      'bg-neutral-100 text-neutral-500',
                    )}>
                      {order.status === 'completed' ? '已完成' : order.status === 'in_progress' ? '进行中' : order.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
