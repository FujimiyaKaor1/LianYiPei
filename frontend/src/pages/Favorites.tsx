import React, { useEffect, useState } from 'react';
import {
  Star,
  MapPin,
  ShieldCheck,
  ChevronRight,
  Search,
  Filter,
  Grid,
  List as ListIcon,
  Factory,
  Loader2,
  AlertTriangle,
  RefreshCw,
  X,
  Building,
  Leaf,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { api, type FavoriteSupplierItem, NETWORK_ERROR_MESSAGE } from '@/src/services/api';
import { cn } from '@/src/lib/utils';

export type FavoritesContentProps = {
  /** 嵌入销售控制台时紧凑样式 + 关闭条 */
  embedded?: boolean;
  onClose?: () => void;
  className?: string;
};

export function FavoritesContent({ embedded, onClose, className }: FavoritesContentProps) {
  const [favorites, setFavorites] = useState<FavoriteSupplierItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');
  const [isRemoving, setIsRemoving] = useState<number | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      // 优先使用新API，失败则降级到旧API
      try {
        const res = await api.getFavorites();
        setFavorites(res.favorites || []);
      } catch {
        // 降级到旧API
        const legacyRes = await api.getFavoritesLegacy();
        // 旧API返回格式不同，需要转换
        const legacyFavorites: FavoriteSupplierItem[] = (legacyRes.favorites || []).map((f: any) => ({
          id: f.id,
          supplier_id: f.supplier_id || f.id,
          supplier_name: f.name || f.supplier_name || '未知企业',
          supplier_province: f.province || f.supplier_province || '',
          supplier_city: f.city || f.supplier_city || '',
          supplier_industry: f.industry || f.supplier_industry || '',
          capacity: f.capacity || 0,
          credit_score: f.score || f.credit_score || 70,
          is_green_factory: f.is_green_factory || false,
          patent_count: f.patent_count || 0,
          match_score: f.match_score || f.match || null,
          product_name: f.product_name || '',
          notes: f.notes || '',
          created_at: f.created_at || null,
        }));
        setFavorites(legacyFavorites);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleRemoveFavorite = async (item: FavoriteSupplierItem) => {
    setIsRemoving(item.supplier_id);
    try {
      await api.removeFavoriteById(item.supplier_id);
      setFavorites((prev) => prev.filter((f) => f.supplier_id !== item.supplier_id));
    } catch (error) {
      alert(error instanceof Error ? error.message : '取消收藏失败');
    } finally {
      setIsRemoving(null);
    }
  };

  const outer = embedded
    ? cn('w-full', className)
    : cn('space-y-10 max-w-7xl mx-auto w-full font-sans antialiased text-neutral-900 pb-10', className);

  return (
    <div className={outer}>
      {embedded && onClose ? (
        <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <Star className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-bold text-neutral-900">优质客商</h3>
            <span className="text-[10px] text-neutral-400">收藏的上下游企业</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : null}

      <div className={cn('flex justify-between items-center', embedded ? 'pt-0' : 'pt-2')}>
        <div className="flex gap-4 flex-wrap">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              type="text"
              placeholder="搜索收藏的客商..."
              className="bg-white border-none rounded-xl py-2 pl-10 pr-4 text-xs w-64 shadow-sm focus:ring-1 focus:ring-black outline-none transition-all"
            />
          </div>
          <button
            type="button"
            className="px-4 py-2 bg-white border border-neutral-100 rounded-xl text-xs font-bold flex items-center gap-2 shadow-sm hover:bg-neutral-50 transition-colors"
          >
            <Filter className="w-3 h-3" />
            筛选
          </button>
        </div>
        <div className="flex gap-4 items-center">
          <button
            type="button"
            onClick={() => void loadData()}
            disabled={isLoading}
            className="p-2 text-neutral-600 hover:text-black hover:bg-neutral-100 rounded-full transition-colors disabled:opacity-40"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          </button>
          <div className="flex bg-white border border-neutral-100 rounded-xl p-1 shadow-sm">
            <button type="button" className="p-1.5 bg-neutral-100 rounded-lg">
              <Grid className="w-4 h-4 text-black" />
            </button>
            <button type="button" className="p-1.5 hover:bg-neutral-50 rounded-lg transition-colors">
              <ListIcon className="w-4 h-4 text-neutral-400" />
            </button>
          </div>
        </div>
      </div>

      {errorText && (
        <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-3 text-xs text-red-600 font-medium flex items-center gap-2 mt-4">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {errorText}
          <button
            type="button"
            onClick={() => void loadData()}
            className="ml-auto text-red-500 hover:text-red-700 underline font-bold"
          >
            重试
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-24 text-neutral-300">
          <Loader2 className="w-8 h-8 animate-spin mb-4 text-neutral-400" />
        </div>
      ) : favorites.length === 0 ? (
        <div
          className={cn(
            'flex flex-col items-center justify-center bg-white rounded-[2.5rem] border border-neutral-100 shadow-sm text-neutral-400',
            embedded ? 'py-16' : 'py-32',
          )}
        >
          <Star className="w-12 h-12 mb-4 text-neutral-200" />
          <h3 className="text-lg font-bold text-neutral-800 mb-2">暂无收藏客商</h3>
          <p className="text-xs px-6 text-center">
            在企业看板对话中点击星标「收藏该企业」，或在智能匹配、找工厂中收藏合适客商。
          </p>
        </div>
      ) : (
        <div
          className={cn(
            'grid gap-8',
            embedded ? 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3' : 'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3',
          )}
        >
          {favorites.map((item, i) => (
            <motion.div
              key={item.supplier_id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.05 }}
              className="bg-white rounded-[2.5rem] p-8 border border-neutral-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all group relative overflow-hidden flex flex-col"
            >
              <div className="absolute top-6 right-6">
                <button
                  type="button"
                  onClick={() => handleRemoveFavorite(item)}
                  disabled={isRemoving === item.supplier_id}
                  className="p-2 hover:bg-neutral-50 rounded-full transition-colors disabled:opacity-50"
                  title="取消收藏"
                >
                  {isRemoving === item.supplier_id ? (
                    <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
                  ) : (
                    <Star className="w-5 h-5 text-orange-400 fill-orange-400 hover:fill-neutral-200 hover:text-neutral-300 transition-colors" />
                  )}
                </button>
              </div>

              <div className="flex items-center gap-6 mb-8 mt-2">
                <div className="w-16 h-16 bg-neutral-50 rounded-2xl flex items-center justify-center text-neutral-300 group-hover:text-black group-hover:bg-neutral-100 transition-colors">
                  <Building className="w-8 h-8" />
                </div>
                <div>
                  <h4 className="font-bold text-lg text-neutral-900 group-hover:text-black transition-colors">
                    {item.supplier_name}
                  </h4>
                  <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-widest mt-1">
                    {item.supplier_industry || item.supplier_city || '未知行业'}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mb-8">
                {item.is_green_factory && (
                  <span className="px-2 py-0.5 bg-green-50 text-green-600 text-[10px] font-black rounded uppercase tracking-widest flex items-center gap-1">
                    <Leaf className="w-3 h-3" />
                    绿色工厂
                  </span>
                )}
                {item.patent_count && item.patent_count > 0 && (
                  <span className="px-2 py-0.5 bg-neutral-100/80 text-[10px] font-black text-neutral-500 rounded uppercase tracking-widest">
                    {item.patent_count}项专利
                  </span>
                )}
                {item.product_name && (
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-black rounded uppercase tracking-widest">
                    {item.product_name}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 mb-8 mt-auto">
                <div className="p-4 bg-neutral-50 rounded-2xl flex flex-col justify-between">
                  <div className="text-[9px] text-neutral-400 font-bold uppercase tracking-widest mb-1">履约信用分</div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-black text-neutral-900">{Math.round(item.credit_score || 70)}</span>
                    <ShieldCheck className="w-4 h-4 text-green-500" />
                  </div>
                </div>
                <div className="p-4 bg-neutral-50 rounded-2xl flex flex-col justify-between">
                  <div className="text-[9px] text-neutral-400 font-bold uppercase tracking-widest mb-1">系统匹配度</div>
                  <div className="text-xl font-black text-neutral-900">
                    {item.match_score ? `${Math.round(item.match_score)}%` : '--'}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-6 border-t border-neutral-50">
                <span className="flex items-center gap-1.5 text-[11px] font-bold text-neutral-400">
                  <MapPin className="w-3.5 h-3.5" />
                  {item.supplier_province || ''}{item.supplier_city || ''}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    // 跳转到销售控制台创建会话
                    window.location.href = `/sales-console?supplier_id=${item.supplier_id}`;
                  }}
                  className="text-[11px] font-black uppercase tracking-widest text-black flex items-center gap-1 group-hover:translate-x-1 transition-transform"
                >
                  联系供应商 <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

/** 独立页：兼容旧书签 /favorites，跳转至企业看板并打开面板 */
export default function Favorites() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate('/sales-console?panel=favorites', { replace: true });
  }, [navigate]);
  return (
    <div className="flex items-center justify-center py-24 text-sm text-neutral-400">正在进入企业看板…</div>
  );
}
