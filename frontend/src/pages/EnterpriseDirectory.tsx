import React, { useCallback, useEffect, useState } from 'react';
import { Building2, ChevronDown, ChevronUp, Inbox, MapPin, Search } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { DIRECTORY_INDUSTRIES, DIRECTORY_PROVINCES } from '@/src/lib/enterpriseDirectoryFilters';
import { api, type EnterpriseDirectoryItem } from '@/src/services/api';

function useDebounced<T>(value: T, ms: number): T {
  const [d, setD] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setD(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return d;
}

function FilterTagRow({
  title,
  value,
  options,
  onChange,
  dense,
}: {
  title: string;
  value: string;
  options: { key: string; label: string }[];
  onChange: (key: string) => void;
  dense?: boolean;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-bold text-neutral-400 tracking-wide">{title}</p>
      <div className={cn('flex flex-wrap gap-2.5', dense && 'max-h-48 overflow-y-auto pr-1 scrollbar-hide')}>
        {options.map((o) => {
          const selected = value === o.key;
          return (
            <button
              key={o.key || '__all__'}
              type="button"
              onClick={() => onChange(o.key)}
              className={cn(
                'px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border',
                selected
                  ? 'bg-neutral-900 text-white border-neutral-900 shadow-sm'
                  : 'bg-white text-neutral-600 border-neutral-100 hover:bg-neutral-50 hover:border-neutral-200',
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function EnterpriseDirectory() {
  const [province, setProvince] = useState('');
  const [industry, setIndustry] = useState('');
  const [keyword, setKeyword] = useState('');
  const debouncedQ = useDebounced(keyword, 320);
  const [minCredit, setMinCredit] = useState<number | ''>('');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [rows, setRows] = useState<EnterpriseDirectoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.fetchEnterpriseDirectory({
        province: province || undefined,
        industry: industry || undefined,
        q: debouncedQ.trim() || undefined,
        min_credit: minCredit === '' ? undefined : minCredit,
        limit: 120,
      });
      setRows(res.enterprises || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [province, industry, debouncedQ, minCredit]);

  useEffect(() => {
    void load();
  }, [load]);

  const clearAll = () => {
    setProvince('');
    setIndustry('');
    setKeyword('');
    setMinCredit('');
  };

  const hasFilters = Boolean(province || industry || keyword.trim() || minCredit !== '');

  return (
    <div className="flex flex-col lg:flex-row gap-8 items-start max-w-[1400px] mx-auto px-2 h-[calc(100vh-140px)] overflow-hidden">
      {/* 左侧筛选（参考产业目录类站点，改为纵向侧栏） */}
      <aside className="w-full lg:w-72 h-full shrink-0 flex flex-col rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-neutral-100 bg-neutral-50/80">
          <h2 className="text-sm font-bold text-neutral-800">筛选条件</h2>
          <p className="text-[11px] text-neutral-500 mt-0.5">按地区与行业缩小合作企业范围</p>
        </div>
        <div className="flex-1 min-h-0 p-5 space-y-6 overflow-y-auto scrollbar-hide">
          <FilterTagRow title="省份地区" value={province} options={DIRECTORY_PROVINCES} onChange={setProvince} />
          <FilterTagRow
            title="服务行业"
            value={industry}
            options={DIRECTORY_INDUSTRIES}
            onChange={setIndustry}
            dense
          />

          <div>
            <p className="text-[11px] font-bold text-neutral-400 mb-1.5">关键词</p>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="企业名称 / 经营范围"
                className="w-full pl-9 pr-3 py-2.5 text-xs rounded-xl border border-neutral-200 focus:outline-none focus:ring-2 focus:ring-neutral-900/5 focus:border-neutral-400 transition-all"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            className="w-full flex items-center justify-center gap-1.5 py-2.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-50 rounded-xl transition-colors border border-dashed border-neutral-300"
          >
            {advancedOpen ? (
              <>
                收起高级筛选
                <ChevronUp className="w-4 h-4" />
              </>
            ) : (
              <>
                展开高级筛选
                <ChevronDown className="w-4 h-4" />
              </>
            )}
          </button>

          {advancedOpen && (
            <div className="space-y-3 pt-1 border-t border-neutral-100">
              <div>
                <p className="text-[11px] font-bold text-neutral-400 mb-1.5">最低信用分</p>
                <select
                  value={minCredit === '' ? '' : String(minCredit)}
                  onChange={(e) => {
                    const v = e.target.value;
                    setMinCredit(v === '' ? '' : Number(v));
                  }}
                  className="w-full py-2.5 px-3 text-xs rounded-xl border border-neutral-200 bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900/5"
                >
                  <option value="">不限</option>
                  <option value="60">≥ 60</option>
                  <option value="70">≥ 70</option>
                  <option value="80">≥ 80</option>
                  <option value="90">≥ 90</option>
                </select>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={clearAll}
            disabled={!hasFilters}
            className={cn(
              'w-full py-2.5 rounded-xl text-sm font-bold transition-colors',
              hasFilters
                ? 'bg-neutral-900 text-white hover:bg-neutral-800 shadow-sm active:scale-[0.98]'
                : 'bg-neutral-100 text-neutral-400 cursor-not-allowed',
            )}
          >
            清空筛选条件
          </button>
        </div>
      </aside>

      {/* 右侧结果 */}
      <section className="flex-1 min-w-0 h-full flex flex-col space-y-4">
        <div className="shrink-0 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-neutral-500">
            {loading ? '加载中…' : (
              <>
                发现 <span className="text-neutral-900 font-bold">{rows.length}</span> 家合作企业
              </>
            )}
          </p>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto scrollbar-hide pr-1">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 text-red-700 text-sm px-4 py-3 mb-4">{error}</div>
          )}

          {!loading && !error && rows.length === 0 && (
            <div className="rounded-3xl border border-neutral-200 bg-white py-20 px-6 text-center shadow-sm">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-neutral-50 text-neutral-400 mb-6">
                <Inbox className="w-10 h-10" />
              </div>
              <h3 className="text-lg font-bold text-neutral-800 mb-2">未找到符合条件的企业</h3>
              <p className="text-sm text-neutral-500 max-w-md mx-auto mb-8">
                建议尝试放宽地区或行业条件，或检查搜索关键词。
              </p>
              <button
                type="button"
                onClick={clearAll}
                className="inline-flex items-center justify-center px-10 py-3.5 rounded-2xl bg-neutral-900 text-white text-sm font-bold hover:bg-neutral-800 transition-all active:scale-[0.98]"
              >
                重置所有筛选
              </button>
            </div>
          )}

          {rows.length > 0 && (
            <ul className="grid gap-6 sm:grid-cols-1 xl:grid-cols-2 pb-8 px-1">
            {rows.map((ent) => (
              <li
                key={ent.id}
                className="group relative rounded-3xl border border-transparent bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_30px_rgb(0,0,0,0.06)] hover:-translate-y-1 transition-all duration-300"
              >
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-neutral-50 text-neutral-400 group-hover:bg-neutral-900 group-hover:text-white flex items-center justify-center shrink-0 transition-colors duration-300">
                    <Building2 className="w-6 h-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-lg font-semibold text-neutral-800 truncate group-hover:text-neutral-900 transition-colors" title={ent.name}>
                        {ent.name}
                      </h3>
                      <div className="shrink-0 bg-emerald-50 text-emerald-600 px-2.5 py-0.5 rounded-full font-bold text-[10px] tracking-tight uppercase">
                        信用 {Math.round(ent.credit_score)}
                      </div>
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-neutral-400">
                      <span className="inline-flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5" />
                        <span>
                          {[ent.province, ent.city].filter(Boolean).join(' ') || ent.address || '地区未填'}
                        </span>
                      </span>
                      {ent.industry_code ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-1 h-1 rounded-full bg-neutral-200" />
                          <span className="font-medium">{ent.industry_code}</span>
                        </div>
                      ) : null}
                    </div>

                    {ent.business_scope ? (
                      <p className="text-sm text-neutral-500 mt-4 line-clamp-2 leading-relaxed group-hover:text-neutral-600 transition-colors">
                        {ent.business_scope}
                      </p>
                    ) : (
                      <p className="text-sm text-neutral-300 mt-4 italic">暂无经营范围描述</p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        </div>
      </section>
    </div>
  );
}
