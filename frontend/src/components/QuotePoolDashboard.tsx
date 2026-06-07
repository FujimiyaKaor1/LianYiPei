import React, { useState, useEffect, useMemo } from 'react';
import { 
  TrendingUp, 
  Plus, 
  BarChart3, 
  Target, 
  Clock, 
  Users,
  Award,
  ArrowUp,
  ArrowDown
} from 'lucide-react';
import { motion } from 'motion/react';
import ReactECharts from 'echarts-for-react';
import { api, type QuoteSubmitPayload, type QuoteSubmitResponse } from '@/src/services/api';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';

interface PriceIndexData {
  product_name: string;
  median_price: number;
  mean_price: number;
  price_range: [number, number];
  sample_count: number;
  last_updated: string;
  data_source?: string;
  prices?: number[]; // 用于图表
}

interface QuoteItem {
  id: number;
  product_name: string;
  price: number;
  quantity?: number;
  unit?: string;
  status: string;
  created_at: string;
}

const POPULAR_PRODUCTS = [
  '精密轴承',
  '不锈钢板材',
  '电子元器件',
  '工业传感器',
  '液压油缸',
];

const mockPriceHistory = {
  '精密轴承': [1180, 1195, 1210, 1205, 1220, 1235, 1218],
  '不锈钢板材': [4850, 4920, 4780, 4950, 4880, 5020, 4985],
  '电子元器件': [125, 132, 128, 135, 142, 138, 145],
};

export function QuotePoolDashboard() {
  const { user } = useAuth();
  const [selectedProduct, setSelectedProduct] = useState(POPULAR_PRODUCTS[0]);
  const [priceIndex, setPriceIndex] = useState<PriceIndexData | null>(null);
  const [loading, setLoading] = useState(false);
  const [myQuotes, setMyQuotes] = useState<QuoteItem[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // 报价表单
  const [formData, setFormData] = useState({
    price: 1250,
    quantity: 500,
    unit: '件',
    delivery_days: 15,
    remarks: '',
  });

  const creditScore = user?.creditScore || 78;

  // 获取价格指数
  const fetchPriceIndex = async (product: string) => {
    setLoading(true);
    try {
      const data = await api.fetchPriceIndex(product);
      setPriceIndex({
        ...data,
        prices: mockPriceHistory[product as keyof typeof mockPriceHistory] || [1200, 1220, 1190, 1250, 1215],
      });
    } catch (err) {
      console.error('获取价格指数失败', err);
      // 使用模拟数据
      setPriceIndex({
        product_name: product,
        median_price: 1220,
        mean_price: 1235,
        price_range: [1150, 1320],
        sample_count: 28,
        last_updated: new Date().toISOString(),
        prices: mockPriceHistory[product as keyof typeof mockPriceHistory] || [1200, 1220, 1190, 1250, 1215],
      });
    } finally {
      setLoading(false);
    }
  };

  // 获取我的报价
  const fetchMyQuotes = async () => {
    try {
      const resp = await api.fetchQuotes({ page: 1 });
      setMyQuotes(resp.quotes || []);
    } catch (e) {
      console.error(e);
      setMyQuotes([]);
    }
  };

  useEffect(() => {
    fetchPriceIndex(selectedProduct);
    fetchMyQuotes();
  }, [selectedProduct]);

  const handleSubmitQuote = async () => {
    if (!formData.price || formData.price <= 0) {
      alert('请输入有效报价');
      return;
    }

    setSubmitting(true);
    try {
      const payload: QuoteSubmitPayload = {
        inquiry_id: 999, // 模拟询盘ID
        price: formData.price,
        product_name: selectedProduct,
        quantity: formData.quantity,
        unit: formData.unit,
        delivery_days: formData.delivery_days,
        remarks: formData.remarks,
      };

      const result = await api.submitQuote(payload);
      
      alert(`报价提交成功！剩余今日报价次数：${result.remaining_quotes_today}`);
      
      // 重置表单并刷新列表
      setFormData({
        price: Math.round(formData.price * 0.98), // 模拟略微调整
        quantity: formData.quantity,
        unit: formData.unit,
        delivery_days: formData.delivery_days,
        remarks: '',
      });
      fetchMyQuotes();
      fetchPriceIndex(selectedProduct);
    } catch (error: any) {
      alert(error.message || '提交失败，请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  // ECharts 配置 - 价格指数图
  const priceChartOption = useMemo(() => {
    if (!priceIndex?.prices) return {};

    const dates = Array.from({ length: priceIndex.prices.length }, (_, i) => 
      `第${i + 1}周`
    );

    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['中位价', '均价'] },
      xAxis: {
        type: 'category',
        data: dates,
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
          data: priceIndex.prices.map(p => Math.round(p * 0.98)),
          itemStyle: { color: '#3b82f6' },
        },
        {
          name: '均价',
          type: 'line',
          data: priceIndex.prices,
          smooth: true,
          lineStyle: { color: '#f59e0b', width: 3 },
          symbol: 'circle',
          symbolSize: 6,
        },
      ],
      grid: { left: '8%', right: '8%', bottom: '8%', top: '12%' },
    };
  }, [priceIndex]);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-black tracking-tighter flex items-center gap-3">
            <BarChart3 className="w-9 h-9 text-blue-600" />
            报价池 · 价格信号中心
          </h1>
          <p className="text-neutral-500 mt-1">市场真实报价汇聚 · 形成行业价格锚点</p>
        </div>
        
        <div className="flex items-center gap-4 bg-white rounded-2xl px-5 py-3 border border-neutral-200">
          <div className="flex items-center gap-2">
            <Award className="w-5 h-5 text-amber-500" />
            <span className="font-medium">当前信用分</span>
          </div>
          <div className="text-3xl font-black text-emerald-600">{creditScore}</div>
          <div className="text-xs px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full font-medium">
            {creditScore >= 80 ? '优秀' : creditScore >= 70 ? '良好' : '一般'}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* 产品选择 + 价格指数 */}
        <div className="col-span-12 lg:col-span-8 bg-white rounded-3xl shadow-sm border border-neutral-100 overflow-hidden">
          <div className="p-6 border-b flex items-center justify-between bg-neutral-50">
            <div className="flex gap-2">
              {POPULAR_PRODUCTS.map((product) => (
                <button
                  key={product}
                  onClick={() => setSelectedProduct(product)}
                  className={cn(
                    "px-5 py-2 text-sm font-medium rounded-2xl transition-all",
                    selectedProduct === product 
                      ? "bg-blue-600 text-white shadow" 
                      : "bg-white hover:bg-neutral-100 border border-neutral-200"
                  )}
                >
                  {product}
                </button>
              ))}
            </div>
            
            <div className="flex items-center gap-2 text-sm text-neutral-500">
              <Clock className="w-4 h-4" />
              最后更新: {priceIndex?.last_updated ? new Date(priceIndex.last_updated).toLocaleTimeString() : '刚刚'}
            </div>
          </div>

          <div className="p-6">
            <div className="flex justify-between items-center mb-6">
              <div>
                <div className="text-sm text-neutral-500">当前产品</div>
                <div className="text-2xl font-semibold">{selectedProduct}</div>
              </div>
              
              <div className="text-right">
                <div className="text-sm text-neutral-500">市场中位价</div>
                <div className="text-4xl font-black text-blue-600">
                  ¥{priceIndex?.median_price?.toLocaleString() || '1,220'}
                </div>
                <div className="text-xs text-emerald-600 flex items-center gap-1 justify-end">
                  <ArrowUp className="w-3 h-3" /> 较上周 +2.1%
                </div>
              </div>
            </div>

            <ReactECharts 
              option={priceChartOption} 
              style={{ height: '360px' }}
              className="w-full"
            />
          </div>
        </div>

        {/* 快捷报价 */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-white rounded-3xl p-6 border border-neutral-100 shadow-sm">
            <div className="flex items-center gap-3 mb-5">
              <Target className="w-6 h-6 text-blue-600" />
              <div>
                <div className="font-semibold">提交意向报价</div>
                <div className="text-xs text-neutral-500">今日剩余 {Math.max(0, 5 - (myQuotes.length % 6))} 次</div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-neutral-500 block mb-1">报价单价 (元)</label>
                <input
                  type="number"
                  value={formData.price}
                  onChange={(e) => setFormData({...formData, price: parseInt(e.target.value) || 0})}
                  className="w-full px-4 py-3 border border-neutral-200 rounded-2xl focus:outline-none focus:border-blue-500 text-2xl font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-medium text-neutral-500 block mb-1">数量</label>
                  <input
                    type="number"
                    value={formData.quantity}
                    onChange={(e) => setFormData({...formData, quantity: parseInt(e.target.value) || 0})}
                    className="w-full px-4 py-3 border border-neutral-200 rounded-2xl focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-neutral-500 block mb-1">单位</label>
                  <select 
                    value={formData.unit}
                    onChange={(e) => setFormData({...formData, unit: e.target.value})}
                    className="w-full px-4 py-3 border border-neutral-200 rounded-2xl focus:outline-none focus:border-blue-500"
                  >
                    <option value="件">件</option>
                    <option value="吨">吨</option>
                    <option value="套">套</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleSubmitQuote}
                disabled={submitting}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-bold rounded-2xl flex items-center justify-center gap-2 transition-all active:scale-[0.985] disabled:opacity-70"
              >
                {submitting ? '提交中...' : '提交报价到意向池'}
                <Plus className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* 市场概况卡片 */}
          <div className="bg-white rounded-3xl p-6 border border-neutral-100">
            <div className="flex items-center justify-between mb-4">
              <div className="font-medium">本品类概况</div>
              <TrendingUp className="w-5 h-5 text-emerald-500" />
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-neutral-50 rounded-2xl p-4">
                <div className="text-xs text-neutral-500">样本量</div>
                <div className="text-3xl font-black mt-1">{priceIndex?.sample_count || 28}</div>
              </div>
              <div className="bg-neutral-50 rounded-2xl p-4">
                <div className="text-xs text-neutral-500">价格区间</div>
                <div className="text-xl font-semibold mt-1">
                  ¥{(priceIndex?.price_range?.[0] || 1150)} - ¥{(priceIndex?.price_range?.[1] || 1320)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 我的报价记录 */}
      <div className="bg-white rounded-3xl p-6 border border-neutral-100">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <BarChart3 className="w-5 h-5" /> 我的报价记录
          </h3>
          <div className="text-sm text-neutral-500">共 {myQuotes.length} 条</div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-xs text-neutral-500">
                <th className="pb-3 font-medium">产品</th>
                <th className="pb-3 font-medium">报价</th>
                <th className="pb-3 font-medium">数量</th>
                <th className="pb-3 font-medium">状态</th>
                <th className="pb-3 font-medium">提交时间</th>
              </tr>
            </thead>
            <tbody className="text-sm divide-y">
              {myQuotes.length > 0 ? (
                myQuotes.map(q => (
                  <tr key={q.id} className="hover:bg-neutral-50">
                    <td className="py-4 font-medium">{q.product_name}</td>
                    <td className="py-4 font-mono">¥{q.price}</td>
                    <td className="py-4 text-neutral-500">{q.quantity || '-'}</td>
                    <td className="py-4">
                      <span className="inline-block px-3 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-700">
                        {q.status === 'active' ? '有效' : '已采纳'}
                      </span>
                    </td>
                    <td className="py-4 text-neutral-500 text-xs">{new Date(q.created_at).toLocaleDateString()}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-neutral-400">
                    暂无报价记录，立即提交第一条意向报价
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
