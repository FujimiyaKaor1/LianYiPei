import { useState } from 'react';
import { MapPin, Truck, Loader2, ArrowRight } from 'lucide-react';
import { api } from '@/src/services/api';
import { useToast } from '@/src/components/ToastProvider';

export default function LogisticsMap() {
  const { showToast } = useToast();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [result, setResult] = useState<{ distance_km: number; duration_min: number } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCalculate = async () => {
    if (!from || !to) return;
    setLoading(true);
    try {
      const res = await api.getMapDistance({ from, to });
      setResult(res);
    } catch {
      showToast('计算失败，请检查地址', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-lg font-bold tracking-tight text-ink">物流距离计算</h2>
        <p className="text-xs text-ink-muted mt-1">基于高德地图计算供应链节点间的物流距离与预估时间</p>
      </div>

      <div className="card p-6 space-y-5">
        <div>
          <label className="text-xs font-semibold text-ink-soft block mb-1.5">发货地址</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-muted" />
            <input value={from} onChange={(e) => setFrom(e.target.value)}
              className="input pl-10 w-full" placeholder="省 市 区 详细地址" />
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold text-ink-soft block mb-1.5">收货地址</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-muted" />
            <input value={to} onChange={(e) => setTo(e.target.value)}
              className="input pl-10 w-full" placeholder="省 市 区 详细地址" />
          </div>
        </div>
        <button onClick={handleCalculate} disabled={loading || !from || !to}
          className="btn-primary w-full">
          {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> 计算中...</> : <><Truck className="w-4 h-4" /> 计算物流距离</>}
        </button>

        {result && (
          <div className="bg-canvas-muted rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-muted">运输距离</span>
              <span className="text-lg font-bold text-ink">{result.distance_km.toFixed(1)} km</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-ink-muted">预计时间</span>
              <span className="text-lg font-bold text-ink">{Math.floor(result.duration_min / 60)}h {result.duration_min % 60}m</span>
            </div>
            <div className="flex items-center gap-2 pt-2 border-t border-border">
              <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
                <div className="h-full bg-brand rounded-full" style={{ width: `${Math.min(100, result.distance_km / 10 * 100)}%` }} />
              </div>
              <span className="text-[10px] text-ink-muted">碳排估算: {(result.distance_km * 0.15).toFixed(1)} kg/吨</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
