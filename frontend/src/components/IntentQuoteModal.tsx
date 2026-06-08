/**
 * 意向报价弹窗组件
 * 
 * 功能：
 * 1. 创建意向报价
 * 2. 获取AI报价建议
 * 3. 发送意向报价
 */
import React, { useState, useEffect } from 'react';
import {
  Loader2,
  X,
  Sparkles,
  CheckCircle,
  AlertTriangle,
  DollarSign,
  Package,
  Clock,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { api, type AIQuoteSuggestion, type EnterpriseProfile } from '@/src/services/api';

export interface IntentQuoteModalProps {
  open: boolean;
  sellerId: number;
  productName: string;
  enterpriseProfile?: EnterpriseProfile;
  chatId?: number;
  matchRecordId?: number;
  onClose: () => void;
  onSuccess?: () => void;
}

export function IntentQuoteModal({
  open,
  sellerId,
  productName,
  enterpriseProfile,
  chatId,
  matchRecordId,
  onClose,
  onSuccess,
}: IntentQuoteModalProps) {
  // 表单状态
  const [quantity, setQuantity] = useState('100');
  const [unit, setUnit] = useState('件');
  const [targetPrice, setTargetPrice] = useState('');
  const [budgetRange, setBudgetRange] = useState('');
  const [remarks, setRemarks] = useState('');

  // 状态
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AIQuoteSuggestion | null>(null);
  const [step, setStep] = useState<'form' | 'confirm' | 'success'>('form');

  // 重置表单
  useEffect(() => {
    if (open) {
      setQuantity('100');
      setUnit('件');
      setTargetPrice('');
      setBudgetRange('');
      setRemarks('');
      setError(null);
      setStep('form');
      setAiSuggestion(null);
    }
  }, [open]);

  // 获取AI建议
  const handleGetAISuggestion = async () => {
    setAiLoading(true);
    try {
      const res = await api.getAIQuoteSuggestion({
        seller_id: sellerId,
        product_name: productName,
        quantity: parseInt(quantity) || undefined,
      });
      setAiSuggestion(res.suggestion);
      if (res.suggestion.suggested_price) {
        setTargetPrice(String(res.suggestion.suggested_price));
        setBudgetRange(`${res.suggestion.price_range.min}-${res.suggestion.price_range.max}`);
      }
    } catch (err) {
      console.error('AI建议失败:', err);
    } finally {
      setAiLoading(false);
    }
  };

  // 提交意向报价
  const handleSubmit = async () => {
    if (!targetPrice) {
      setError('请填写目标单价');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. 创建意向报价
      const createRes = await api.createIntentQuote({
        seller_id: sellerId,
        product_name: productName,
        chat_id: chatId,
        match_record_id: matchRecordId,
        quantity: parseInt(quantity) || undefined,
        unit,
        target_price: parseFloat(targetPrice),
        budget_range: budgetRange || undefined,
      });

      // 2. 如果有AI建议，应用到意向报价
      if (aiSuggestion) {
        try {
          await api.applyAIQuoteSuggestion(createRes.quote_id, aiSuggestion);
        } catch {
          // 忽略AI建议应用失败
        }
      }

      // 3. 发送意向报价
      await api.sendIntentQuote(createRes.quote_id);

      setStep('success');
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-[2px] p-4">
      <div className="w-full max-w-lg rounded-2xl border border-neutral-200/80 bg-white shadow-[0_24px_64px_rgba(0,0,0,0.14)] max-h-[90vh] overflow-y-auto">
        {/* 头部 */}
        <div className="sticky top-0 bg-white flex items-start justify-between gap-3 border-b border-neutral-100 px-6 py-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <DollarSign className="w-4 h-4 text-blue-600" />
              <h3 className="text-base font-bold text-neutral-900">发起意向报价</h3>
            </div>
            <p className="text-xs text-neutral-500">
              {enterpriseProfile?.name || '供应商'} · {productName}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="px-6 py-5 space-y-5">
          {step === 'success' ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-8 h-8 text-blue-600" />
              </div>
              <h4 className="text-lg font-bold text-neutral-900 mb-2">意向报价已发送</h4>
              <p className="text-sm text-neutral-500 mb-6">
                供应商收到报价后会通知您，请耐心等待回复
              </p>
              <button
                type="button"
                onClick={onClose}
                className="px-6 py-2.5 bg-neutral-900 text-white rounded-xl text-sm font-semibold hover:bg-neutral-800 transition-colors"
              >
                完成
              </button>
            </div>
          ) : (
            <>
              {/* AI建议区块 */}
              {aiSuggestion ? (
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="w-4 h-4 text-blue-500" />
                    <span className="text-xs font-bold text-blue-700">AI报价建议</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-neutral-500">建议单价</span>
                      <p className="font-bold text-blue-700 mt-0.5">
                        ¥{aiSuggestion.suggested_price.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <span className="text-neutral-500">参考区间</span>
                      <p className="font-medium text-neutral-700 mt-0.5">
                        ¥{aiSuggestion.price_range.min.toFixed(2)} - ¥{aiSuggestion.price_range.max.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <span className="text-neutral-500">预计交期</span>
                      <p className="font-medium text-neutral-700 mt-0.5">
                        {aiSuggestion.delivery_estimate}
                      </p>
                    </div>
                    <div>
                      <span className="text-neutral-500">产能状态</span>
                      <p className={cn(
                        'font-medium mt-0.5',
                        aiSuggestion.capacity_available ? 'text-blue-600' : 'text-amber-600'
                      )}>
                        {aiSuggestion.capacity_available ? '产能充足' : '产能紧张'}
                      </p>
                    </div>
                  </div>
                  <p className="text-[10px] text-neutral-500 mt-3 pt-3 border-t border-blue-100">
                    {aiSuggestion.basis}
                  </p>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleGetAISuggestion()}
                  disabled={aiLoading}
                  className="w-full py-3 bg-blue-50 hover:bg-blue-100 border border-blue-100 rounded-xl text-xs font-semibold text-blue-700 flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {aiLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      正在获取AI建议...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      获取AI智能报价建议
                    </>
                  )}
                </button>
              )}

              {/* 表单 */}
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1.5">
                      数量 <span className="text-red-500">*</span>
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="number"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                        className="flex-1 rounded-xl border border-neutral-200 px-3 py-2.5 text-sm outline-none focus:border-neutral-900"
                        placeholder="数量"
                      />
                      <select
                        value={unit}
                        onChange={(e) => setUnit(e.target.value)}
                        className="rounded-xl border border-neutral-200 px-2 py-2.5 text-sm outline-none focus:border-neutral-900 bg-white"
                      >
                        <option>件</option>
                        <option>套</option>
                        <option>个</option>
                        <option>台</option>
                        <option>箱</option>
                        <option>吨</option>
                        <option>千克</option>
                        <option>米</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1.5">
                      目标单价(元) <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={targetPrice}
                      onChange={(e) => setTargetPrice(e.target.value)}
                      className="w-full rounded-xl border border-neutral-200 px-3 py-2.5 text-sm outline-none focus:border-neutral-900"
                      placeholder="¥0.00"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1.5">
                    预算区间(元)
                  </label>
                  <input
                    type="text"
                    value={budgetRange}
                    onChange={(e) => setBudgetRange(e.target.value)}
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2.5 text-sm outline-none focus:border-neutral-900"
                    placeholder="如：45-55"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1.5">
                    备注说明
                  </label>
                  <textarea
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    rows={3}
                    className="w-full resize-none rounded-xl border border-neutral-200 px-3 py-2.5 text-sm outline-none focus:border-neutral-900"
                    placeholder="质量要求、交期要求、付款方式等..."
                  />
                </div>
              </div>

              {/* 错误提示 */}
              {error && (
                <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 py-3 border border-neutral-200 text-neutral-700 rounded-xl text-sm font-semibold hover:bg-neutral-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => void handleSubmit()}
                  disabled={loading}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      发送中...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      发送意向报价
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 名片交换按钮组件
 */
export interface CardExchangeButtonProps {
  eligible: boolean;
  lockedReason?: string;
  onClick: () => void;
  loading?: boolean;
}

export function CardExchangeButton({
  eligible,
  lockedReason,
  onClick,
  loading,
}: CardExchangeButtonProps) {
  if (!eligible) {
    return (
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-neutral-200 bg-neutral-50 text-neutral-400 rounded-lg text-xs font-medium cursor-not-allowed"
        title={lockedReason || '需要先完成意向报价'}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2.081M5 12h1.999M5 16h2.081" />
        </svg>
        名片交换 🔒
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => void onClick()}
      disabled={loading}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-blue-200 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-100 transition-colors disabled:opacity-50"
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2.081M5 12h1.999M5 16h2.081" />
        </svg>
      )}
      名片交换
    </button>
  );
}
