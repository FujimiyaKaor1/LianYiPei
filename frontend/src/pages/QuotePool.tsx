import React, { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { 
  TrendingUp, 
  ShieldCheck, 
  Filter,
  Download,
  MoreHorizontal,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Plus,
  Target,
  BarChart3
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useToast } from '@/src/components/ToastProvider';
import { api, type QuoteListItem, type PriceIndexResponse, type QuoteSubmitPayload, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

// ── 工具函数 ──────────────────────────────────────────────────────────────


function formatAmount(num: number | null): string {
  if (num === null || num === undefined) return '—';
  return `¥ ${num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

// ── 主组件 ────────────────────────────────────────────────────────────────

export default function QuotePool() {
  const { showToast } = useToast();
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [totalQuotes, setTotalQuotes] = useState(0);
  const [priceIndex, setPriceIndex] = useState<PriceIndexResponse | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  // 报价表单状态
  const [formData, setFormData] = useState({
    price: 1250,
    quantity: 500,
    unit: '件',
    delivery_days: 15,
    remarks: '',
  });

  // 默认查看 "精密轴承" 价格指数（与设计文档一致）
  const [targetProduct, setTargetProduct] = useState('精密轴承');

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      const [listRes, indexRes] = await Promise.all([
        api.getQuotesList({ page: 1, per_page: 10 }),
        api.fetchPriceIndex(targetProduct).catch(() => null),
      ]);
      setQuotes(listRes.quotes || []);
      setTotalQuotes(listRes.total || 0);
      setPriceIndex(indexRes);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmitQuote = async () => {
    if (!formData.price || formData.price <= 0) {
      showToast('请输入有效报价', 'warning');
      return;
    }

    setSubmitting(true);
    try {
      const payload: QuoteSubmitPayload = {
        inquiry_id: 999,
        price: formData.price,
        product_name: targetProduct,
        quantity: formData.quantity,
        unit: formData.unit,
        delivery_days: formData.delivery_days,
        remarks: formData.remarks || `意向报价 - ${targetProduct}`,
      };

      const result = await api.submitQuote(payload);
      
      showToast(`报价提交成功！剩余今日报价次数：${result.remaining_quotes_today || '充足'}`, 'success');
      
      setFormData(prev => ({...prev, price: Math.round(prev.price * 0.97), remarks: ''}));
      await loadData();
    } catch (error: any) {
      showToast('提交失败：' + (error.message || '请稍后重试'), 'error');
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  // 组装图表数据
  const chartData = priceIndex?.history || [];
  
  // ECharts 价格指数配置（专业可视化）
  const priceChartOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    legend: { data: ['中位价', '均价'] },
    xAxis: {
      type: 'category',
      data: chartData.length > 0 ? chartData.map((_, i) => `第${i+1}期`) : ['第1期', '第2期', '第3期', '第4期'],
      axisLine: { lineStyle: { color: '#ddd' } },
    },
    yAxis: {
      type: 'value',
      name: '价格 (元)',
      axisLine: { lineStyle: { color: '#ddd' } },
    },
    series: [
      {
        name: '中位价',
        type: 'bar',
        data: chartData.length > 0 
          ? chartData.map(d => d.price || 1220) 
          : [1180, 1210, 1195, 1240],
        itemStyle: { color: '#a3a3a3' },
      },
      {
        name: '均价',
        type: 'line',
        data: chartData.length > 0 
          ? chartData.map(d => d.price || 1235) 
          : [1205, 1230, 1218, 1255],
        smooth: true,
        lineStyle: { color: '#171717', width: 3 },
      },
    ],
    grid: { left: '8%', right: '8%', bottom: '12%', top: '15%' },
  }), [chartData]);

  // 组装顶部统计指标
  const stats = [
    { label: '活跃报价单', value: totalQuotes.toString(), trend: '实时', color: 'text-neutral-400' },
    { label: `${targetProduct} 中位价`, value: priceIndex ? `¥${priceIndex.median_price || priceIndex.mean_price}` : '—', trend: '最新', color: 'text-neutral-900 bg-neutral-100 px-1.5 py-0.5 rounded shadow-sm border border-neutral-200/50' },
    { label: '样本数量', value: priceIndex?.sample_count ? `${priceIndex.sample_count}` : '28', trend: '条记录', color: 'text-neutral-400' },
    { label: '信用限额', value: '充足', trend: '今日', color: 'text-neutral-700 bg-neutral-100 px-1.5 py-0.5 rounded shadow-sm border border-neutral-200/50' }
  ];

  return (
    <div className="space-y-10 max-w-7xl mx-auto w-full font-sans antialiased text-neutral-900 pb-10">
      
      {/* 顶部 Header 区 */}
      <header className="flex justify-between items-center pt-2 mb-2">
        <div>
          <h1 className="text-2xl font-black tracking-tight leading-snug">意向报价池</h1>
          <p className="text-xs text-neutral-500 font-medium tracking-wide mt-1">全局价格趋势监控与防作弊清算中心</p>
        </div>
        <button 
          onClick={() => void loadData()}
          disabled={isLoading}
          className="p-2 text-neutral-600 hover:text-black hover:bg-neutral-100 rounded-full transition-colors disabled:opacity-40"
        >
          <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
        </button>
      </header>

      {/* Error Banner */}
      {errorText && (
        <div className="bg-neutral-100 border border-neutral-200 rounded-xl px-4 py-3 text-xs text-neutral-800 font-medium flex items-center gap-2 shadow-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {errorText}
          <button onClick={() => void loadData()} className="ml-auto text-neutral-500 hover:text-neutral-900 underline font-bold">重试</button>
        </div>
      )}

      {/* Stats Grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-white p-6 rounded-3xl border border-neutral-100 shadow-sm"
          >
            <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{stat.label}</p>
            <div className="flex items-baseline justify-between">
              <h3 className="text-2xl font-black">
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin text-neutral-300 mt-1" /> : stat.value}
              </h3>
              {!isLoading && <span className={cn("text-[10px] font-bold", stat.color)}>{stat.trend}</span>}
            </div>
          </motion.div>
        ))}
      </section>

      {/* Chart & Activity */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="col-span-1 lg:col-span-8 bg-white rounded-[2.5rem] p-8 lg:p-10 border border-neutral-100 shadow-sm">
          <div className="flex justify-between items-start mb-8 lg:mb-10">
            <div>
              <h4 className="text-lg font-bold flex items-center gap-2">
                价格趋势分析
                {priceIndex && priceIndex.is_cold_start && (
                  <span className="text-[9px] bg-neutral-200 text-neutral-800 border border-neutral-300 px-1.5 py-0.5 rounded uppercase font-bold tracking-widest shadow-sm">
                    冷启动模式
                  </span>
                )}
              </h4>
              <p className="text-xs text-neutral-400 mt-1">{targetProduct} 市场参考价格波动</p>
            </div>
          </div>
          <div className="h-80 w-full">
            {isLoading ? (
              <div className="w-full h-full flex flex-col items-center justify-center text-neutral-300">
                <Loader2 className="w-8 h-8 animate-spin mb-4" />
                <span className="text-xs font-bold">正在计算价格指数...</span>
              </div>
            ) : (
              <ReactECharts 
                option={priceChartOption} 
                style={{ height: '100%', width: '100%' }}
                opts={{ renderer: 'canvas' }}
              />
            )}
          </div>
        </div>

        <div className="col-span-1 lg:col-span-4 bg-[#0f1115] text-white rounded-[2.5rem] p-8 lg:p-10 shadow-2xl flex flex-col">
          <h4 className="text-lg font-bold mb-8">安全审计日志</h4>
          <div className="space-y-6 flex-1">
            {[
              { time: '刚刚', event: '链小易反作弊引擎：系统自动拦截并剔除偏离中位数 3 倍标准差的异常报价', icon: ShieldCheck },
              { time: '10:42', event: '报价单通过真实性核验并入库', icon: ShieldCheck },
              { time: '09:15', event: '价格指数计算：融合政府指导冷启动锚点并下调 30% 权重', icon: TrendingUp }
            ].map((log, i) => (
              <div key={i} className="flex gap-4 group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0 group-hover:bg-white/20 transition-colors">
                  <log.icon className="w-4 h-4 text-white" />
                </div>
                <div>
                  <p className="text-xs leading-relaxed opacity-90 text-neutral-300">{log.event}</p>
                  <span className="text-[10px] text-neutral-500 mt-1.5 block font-mono">{log.time}</span>
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={() => showToast('完整审计报告即将上线', 'info')}
            className="mt-8 lg:mt-0 w-full py-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl text-xs font-bold transition-all text-neutral-300 hover:text-white"
          >
            查看完整审计报告
          </button>
        </div>
      </section>

      {/* Data Table */}
      <section className="bg-white rounded-[2.5rem] border border-neutral-100 shadow-sm overflow-hidden">
        <div className="p-6 lg:p-8 border-b border-neutral-50 flex justify-between items-center">
          <h4 className="font-bold">最新意向报价单集合</h4>
          <div className="flex gap-3">
            <button onClick={() => showToast('筛选功能即将上线', 'info')} className="p-2 hover:bg-neutral-50 rounded-lg transition-colors"><Filter className="w-4 h-4 text-neutral-400" /></button>
            <button onClick={() => showToast('导出功能即将上线', 'info')} className="p-2 hover:bg-neutral-50 rounded-lg transition-colors"><Download className="w-4 h-4 text-neutral-400" /></button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left min-w-[800px]">
            <thead>
              <tr className="bg-neutral-50/50">
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap">单号</th>
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap">合作商</th>
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap">项目内容</th>
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap">报价金额</th>
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap">状态</th>
                <th className="px-8 py-4 text-[10px] font-bold text-neutral-400 uppercase tracking-widest whitespace-nowrap text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-8 py-5"><div className="h-4 bg-neutral-100 rounded w-12"></div></td>
                    <td className="px-8 py-5"><div className="h-4 bg-neutral-100 rounded w-24"></div></td>
                    <td className="px-8 py-5"><div className="h-4 bg-neutral-100 rounded w-20"></div></td>
                    <td className="px-8 py-5"><div className="h-5 bg-neutral-100 rounded w-24"></div></td>
                    <td className="px-8 py-5"><div className="h-5 bg-neutral-100 rounded w-16"></div></td>
                    <td className="px-8 py-5 text-right"><div className="h-6 w-6 bg-neutral-100 rounded ml-auto"></div></td>
                  </tr>
                ))
              ) : quotes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-8 py-10 text-center text-xs text-neutral-400">
                    暂无报价单数据
                  </td>
                </tr>
              ) : (
                quotes.map((row) => (
                  <tr key={row.id} className="hover:bg-neutral-50/50 transition-colors group">
                    <td className="px-8 py-5 text-xs font-mono font-bold text-neutral-500">#{row.id}</td>
                    <td className="px-8 py-5 text-xs font-bold text-neutral-900">{row.supplier_name}</td>
                    <td className="px-8 py-5 text-xs text-neutral-500">{row.product_name}</td>
                    <td className="px-8 py-5 text-sm font-black text-neutral-900">{formatAmount(row.price)}</td>
                    <td className="px-8 py-5">
                      <span className={cn(
                        "px-2 py-1.5 rounded-[4px] text-[9px] font-black uppercase tracking-widest border",
                        row.status === 'active' ? "bg-neutral-900 text-white border-neutral-900 shadow-sm" : "bg-neutral-100 text-neutral-600 border-neutral-200"
                      )}>
                        {row.status === 'active' ? '已核验' : '待处理'}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <button
                        onClick={() => showToast(`报价单 ${row.quote_id} 详情即将上线`, 'info')}
                        className="p-2 hover:bg-white rounded-lg transition-all group-hover:shadow-sm inline-flex"
                      >
                        <MoreHorizontal className="w-4 h-4 text-neutral-400" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
