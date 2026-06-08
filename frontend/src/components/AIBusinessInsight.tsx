/**
 * AI商机洞察消息组件
 * 
 * 功能：
 * 1. 显示AI商机洞察消息卡片
 * 2. 显示DeepSeek企业画像
 * 3. 提供意向报价按钮
 */
import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Loader2,
  Building,
  MapPin,
  ShieldCheck,
  Leaf,
  Award,
  Clock,
  ChevronRight,
  X,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api, type BusinessInsightMessage, type EnterpriseProfile } from '@/src/services/api';

export interface AIBusinessInsightProps {
  enterpriseId: number;
  productName: string;
  onGenerateQuote?: (enterpriseId: number, profile: EnterpriseProfile) => void;
  className?: string;
}

export function AIBusinessInsightCard({
  enterpriseId,
  productName,
  onGenerateQuote,
  className,
}: AIBusinessInsightProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [insight, setInsight] = useState<BusinessInsightMessage | null>(null);

  useEffect(() => {
    if (!enterpriseId || !productName) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    api.getBusinessInsight({
      enterprise_id: enterpriseId,
      product_name: productName,
    })
      .then((res) => {
        if (!cancelled) {
          setInsight(res.insight);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enterpriseId, productName]);

  if (loading) {
    return (
      <div className={cn('bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-5 border border-blue-100', className)}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-blue-900">AI商机洞察</span>
          <Loader2 className="w-4 h-4 animate-spin text-blue-400 ml-auto" />
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-blue-100/50 rounded animate-pulse" />
          <div className="h-4 bg-blue-100/50 rounded animate-pulse w-4/5" />
          <div className="h-4 bg-blue-100/50 rounded animate-pulse w-3/5" />
        </div>
      </div>
    );
  }

  if (error || !insight) {
    return (
      <div className={cn('bg-neutral-50 rounded-2xl p-5 border border-neutral-200', className)}>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-neutral-200 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-neutral-400" />
          </div>
          <span className="text-sm font-bold text-neutral-600">AI商机洞察</span>
        </div>
        <p className="text-xs text-neutral-400">暂无法获取商机洞察</p>
      </div>
    );
  }

  const profile = insight.enterprise_profile;

  return (
    <div className={cn('bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl border border-blue-100 overflow-hidden', className)}>
      {/* 头部 */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-blue-900">AI商机洞察</span>
          <div className="ml-auto px-2 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded-full">
            DeepSeek
          </div>
        </div>

        {/* 摘要 */}
        <p className="text-sm text-blue-900 leading-relaxed mb-4">
          {insight.insight_summary}
        </p>

        {/* 企业画像 */}
        <div className="bg-white/80 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2 mb-3">
            <Building className="w-4 h-4 text-blue-500" />
            <span className="text-xs font-bold text-neutral-700">{profile.name}</span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div className="flex items-center gap-1.5">
              <MapPin className="w-3 h-3 text-neutral-400" />
              <span className="text-neutral-600">
                {profile.province}{profile.city}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-3 h-3 text-blue-500" />
              <span className="text-neutral-600">
                信用 {profile.credit_score}分 ({profile.credit_level})
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Award className="w-3 h-3 text-amber-500" />
              <span className="text-neutral-600">
                {profile.green_level}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-blue-400" />
              <span className="text-neutral-600">
                {profile.capacity_status}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-blue-100 flex items-center justify-between">
            <span className="text-[10px] text-neutral-500">
              {profile.patent_count}项专利 · {profile.cooperation_risk}
            </span>
            {profile.green_level !== '未认证' && (
              <span className="flex items-center gap-1 text-[10px] text-blue-600 font-bold">
                <Leaf className="w-3 h-3" />
                绿色认证
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 底部操作 */}
      {insight.actions?.generate_quote?.enabled && onGenerateQuote && (
        <div className="px-5 pb-5">
          <button
            type="button"
            onClick={() => onGenerateQuote(enterpriseId, profile)}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl flex items-center justify-center gap-2 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {insight.actions.generate_quote.label}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * 消息气泡内的AI洞察小卡片
 */
export interface AIInsightBubbleProps {
  enterpriseId: number;
  productName: string;
  onGenerateQuote?: (enterpriseId: number) => void;
}

export function AIInsightBubble({ enterpriseId, productName, onGenerateQuote }: AIInsightBubbleProps) {
  const [loading, setLoading] = useState(true);
  const [insight, setInsight] = useState<BusinessInsightMessage | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    if (!enterpriseId || !productName) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    api.getBusinessInsight({
      enterprise_id: enterpriseId,
      product_name: productName,
    })
      .then((res) => {
        if (!cancelled) setInsight(res.insight);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enterpriseId, productName]);

  if (loading) {
    return (
      <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="w-3 h-3 text-blue-500" />
          <span className="text-[10px] font-bold text-blue-700">AI商机洞察</span>
          <Loader2 className="w-3 h-3 animate-spin text-blue-400 ml-auto" />
        </div>
        <div className="h-3 bg-blue-100/50 rounded animate-pulse w-4/5" />
      </div>
    );
  }

  if (!insight) return null;

  return (
    <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-3 h-3 text-blue-500" />
        <span className="text-[10px] font-bold text-blue-700">AI商机洞察</span>
        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          className="ml-auto text-[10px] text-blue-500 hover:text-blue-700"
        >
          {showDetails ? '收起' : '详情'}
        </button>
      </div>

      <p className="text-[11px] text-neutral-700 leading-relaxed mb-2">
        {insight.insight_summary}
      </p>

      {showDetails && (
        <div className="mt-2 pt-2 border-t border-blue-100 space-y-1.5">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-neutral-500">企业：</span>
            <span className="text-neutral-700 font-medium">{insight.enterprise_name}</span>
          </div>
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-neutral-500">产能：</span>
            <span className="text-neutral-700">{insight.enterprise_profile.capacity_status}</span>
          </div>
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-neutral-500">信用：</span>
            <span className="text-neutral-700">
              {insight.enterprise_profile.credit_score}分 ({insight.enterprise_profile.credit_level})
            </span>
          </div>
        </div>
      )}

      {onGenerateQuote && insight.actions?.generate_quote?.enabled && (
        <button
          type="button"
          onClick={() => onGenerateQuote(enterpriseId)}
          className="mt-2 w-full py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-bold rounded-lg flex items-center justify-center gap-1 transition-colors"
        >
          <Sparkles className="w-3 h-3" />
          {insight.actions.generate_quote.label}
        </button>
      )}
    </div>
  );
}
