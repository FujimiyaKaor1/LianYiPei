import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Award,
  Building,
  ChevronRight,
  Filter,
  Grid,
  Leaf,
  Loader2,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
  Star,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/src/lib/utils';
import { api, NETWORK_ERROR_MESSAGE, type FavoriteSupplierItem } from '@/src/services/api';

function normalizeLegacyFavorite(item: any): FavoriteSupplierItem {
  const rawMatch = item.match_score ?? item.match ?? null;
  const parsedMatch =
    typeof rawMatch === 'string' ? Number(rawMatch.replace('%', '')) : Number(rawMatch);
  return {
    id: Number(item.id || item.supplier_id || 0),
    supplier_id: Number(item.supplier_id || item.id || 0),
    supplier_name: item.supplier_name || item.name || '未知企业',
    supplier_province: item.supplier_province || item.province || '',
    supplier_city: item.supplier_city || item.city || item.location || '',
    supplier_industry: item.supplier_industry || item.industry || '',
    capacity: Number(item.capacity || 0),
    credit_score: Number(item.credit_score || item.score || 70),
    is_green_factory: Boolean(item.is_green_factory),
    patent_count: Number(item.patent_count || 0),
    match_score: Number.isFinite(parsedMatch) ? parsedMatch : null,
    product_name: item.product_name || '',
    notes: item.notes || '',
    created_at: item.created_at || null,
  };
}

export default function Favorites() {
  const navigate = useNavigate();
  const [favorites, setFavorites] = useState<FavoriteSupplierItem[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorText, setErrorText] = useState('');
  const [isRemoving, setIsRemoving] = useState<number | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      try {
        const res = await api.getFavorites();
        setFavorites(res.favorites || []);
      } catch {
        const legacyRes = await api.getFavoritesLegacy();
        setFavorites((legacyRes.favorites || []).map(normalizeLegacyFavorite));
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

  const filteredFavorites = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return favorites;
    return favorites.filter((item) => {
      const haystack = [
        item.supplier_name,
        item.supplier_industry,
        item.supplier_province,
        item.supplier_city,
        item.product_name,
        item.notes,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(keyword);
    });
  }, [favorites, query]);

  const handleRemoveFavorite = async (item: FavoriteSupplierItem) => {
    setIsRemoving(item.supplier_id);
    try {
      await api.removeFavoriteById(item.supplier_id);
      setFavorites((prev) => prev.filter((fav) => fav.supplier_id !== item.supplier_id));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : '取消收藏失败');
    } finally {
      setIsRemoving(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4">
      <section className="panel overflow-hidden">
        <div className="panel-header flex flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Star className="h-4.5 w-4.5 fill-amber-400 text-amber-400" />
              <h1 className="text-base font-bold text-ink">收藏客商</h1>
            </div>
            <p className="mt-1 text-xs font-medium text-ink-muted">
              管理已收藏的供应商与上下游合作对象
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索收藏客商"
                className="h-9 w-full rounded-md border border-border bg-surface px-9 text-xs font-medium outline-none transition-shadow focus:border-brand focus:ring-2 focus:ring-brand-soft sm:w-64"
              />
            </div>
            <button type="button" className="btn-secondary btn-sm gap-1.5">
              <Filter className="h-3.5 w-3.5" />
              筛选
            </button>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={isLoading}
              className="btn-secondary btn-sm gap-1.5 disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
              刷新
            </button>
          </div>
        </div>

        {errorText ? (
          <div className="mx-5 mt-4 flex items-center gap-2 rounded-md border border-critical/15 bg-critical-soft px-4 py-3 text-xs font-semibold text-critical">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {errorText}
          </div>
        ) : null}

        {isLoading ? (
          <div className="flex h-72 flex-col items-center justify-center text-ink-muted">
            <Loader2 className="h-7 w-7 animate-spin text-brand" />
            <p className="mt-3 text-xs font-medium">正在加载收藏客商...</p>
          </div>
        ) : filteredFavorites.length === 0 ? (
          <div className="flex h-72 flex-col items-center justify-center px-6 text-center text-ink-muted">
            <div className="flex h-14 w-14 items-center justify-center rounded-md bg-surface-subtle text-ink-faint">
              <Star className="h-7 w-7" />
            </div>
            <h3 className="mt-4 text-base font-bold text-ink">
              {favorites.length === 0 ? '暂无收藏客商' : '没有匹配的收藏客商'}
            </h3>
            <p className="mt-2 max-w-md text-xs font-medium leading-6">
              在供需匹配或企业名录中收藏合适客商后，会在这里集中管理和继续沟通。
            </p>
            <button type="button" onClick={() => navigate('/matching')} className="btn-primary mt-4 gap-2">
              去供需匹配
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
            {filteredFavorites.map((item, index) => (
              <motion.article
                key={`${item.supplier_id}-${item.product_name || index}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.03 }}
                className="card-hover flex min-h-[250px] flex-col p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
                      <Building className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h2 className="truncate text-sm font-bold text-ink" title={item.supplier_name}>
                        {item.supplier_name}
                      </h2>
                      <p className="mt-1 truncate text-[11px] font-semibold text-ink-muted">
                        {item.supplier_industry || item.supplier_city || '未知行业'}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleRemoveFavorite(item)}
                    disabled={isRemoving === item.supplier_id}
                    className="rounded-md p-2 text-amber-500 transition-colors hover:bg-surface-subtle disabled:opacity-50"
                    aria-label="取消收藏"
                  >
                    {isRemoving === item.supplier_id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Star className="h-4 w-4 fill-current" />
                    )}
                  </button>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  {item.is_green_factory ? (
                    <span className="inline-flex items-center gap-1 rounded-md bg-trust-soft px-2 py-1 text-[10px] font-bold text-trust">
                      <Leaf className="h-3 w-3" />
                      绿色工厂
                    </span>
                  ) : null}
                  {item.patent_count > 0 ? (
                    <span className="rounded-md border border-border bg-surface-subtle px-2 py-1 text-[10px] font-bold text-ink-muted">
                      {item.patent_count} 项专利
                    </span>
                  ) : null}
                  {item.product_name ? (
                    <span className="rounded-md bg-brand-soft px-2 py-1 text-[10px] font-bold text-brand">
                      {item.product_name}
                    </span>
                  ) : null}
                </div>

                <div className="mt-5 grid grid-cols-2 gap-2">
                  <div className="rounded-md border border-border bg-surface-subtle p-3">
                    <div className="text-[10px] font-bold uppercase text-ink-muted">履约信用</div>
                    <div className="metric-number mt-1 flex items-center gap-1 text-xl font-black text-ink">
                      {Math.round(item.credit_score || 70)}
                      <ShieldCheck className="h-4 w-4 text-trust" />
                    </div>
                  </div>
                  <div className="rounded-md border border-border bg-surface-subtle p-3">
                    <div className="text-[10px] font-bold uppercase text-ink-muted">匹配度</div>
                    <div className="metric-number mt-1 flex items-center gap-1 text-xl font-black text-ink">
                      {item.match_score != null ? `${Math.round(Number(item.match_score))}%` : '--'}
                      <Award className="h-4 w-4 text-brand" />
                    </div>
                  </div>
                </div>

                {item.notes ? (
                  <p className="mt-4 line-clamp-2 text-xs font-medium leading-5 text-ink-muted">
                    {item.notes}
                  </p>
                ) : null}

                <div className="mt-auto flex items-center justify-between gap-3 border-t border-border pt-4">
                  <span className="flex min-w-0 items-center gap-1 text-[11px] font-semibold text-ink-muted">
                    <MapPin className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">
                      {item.supplier_province || ''}
                      {item.supplier_city || ''}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => navigate(`/sales-console?supplier_id=${item.supplier_id}`)}
                    className="inline-flex shrink-0 items-center gap-1 text-[11px] font-black text-brand"
                  >
                    联系客商
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </motion.article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
