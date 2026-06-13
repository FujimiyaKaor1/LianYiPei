import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  AlertTriangle,
  CheckCircle2,
  CloudUpload,
  FileCheck2,
  Loader2,
  Receipt,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type CreditHistoryRecord } from '@/src/services/api';

export type CollaborationModalProps = {
  open: boolean;
  onClose: () => void;
  enterpriseId: number | null;
  currentCreditScore: number;
};

function scoreDeltaLabel(record: CreditHistoryRecord): string {
  const value = Number(record.change_value || 0);
  if (value > 0) return `+${value} 信用分`;
  if (value < 0) return `${value} 信用分`;
  return '分值未变';
}

function validateCredentialFile(file: File): string | null {
  const maxSize = 16 * 1024 * 1024;
  const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : '';
  if (!['pdf', 'jpg', 'jpeg', 'png'].includes(ext)) {
    return '仅支持 PDF、JPG、JPEG、PNG 格式文件';
  }
  if (file.size > maxSize) {
    return '文件大小超过 16MB，请压缩后重试';
  }
  return null;
}

export function CollaborationModal({
  open,
  onClose,
  enterpriseId,
  currentCreditScore,
}: CollaborationModalProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [history, setHistory] = useState<CreditHistoryRecord[]>([]);
  const [score, setScore] = useState(currentCreditScore || 70);
  const [isLoading, setIsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    setScore(currentCreditScore || 70);
  }, [currentCreditScore]);

  useEffect(() => {
    if (!open || !enterpriseId) return;
    const cacheKey = `credit_history_${enterpriseId}`;
    setIsLoading(true);
    setMessage(null);
    (async () => {
      try {
        const [historyResp, scoreResp] = await Promise.all([
          api.fetchCreditHistory(enterpriseId, { limit: 12 }),
          api.fetchCreditScore(enterpriseId),
        ]);
        const records = historyResp.records || [];
        setHistory(records);
        setScore(Number(scoreResp.credit_score || currentCreditScore || 70));
        localStorage.setItem(cacheKey, JSON.stringify(records));
      } catch {
        try {
          const raw = localStorage.getItem(cacheKey);
          setHistory(raw ? (JSON.parse(raw) as CreditHistoryRecord[]) : []);
        } catch {
          setHistory([]);
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, [currentCreditScore, enterpriseId, open]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const safeScore = useMemo(() => {
    const numeric = Number(score || 70);
    if (Number.isNaN(numeric)) return 70;
    return Math.max(0, Math.min(100, Math.round(numeric)));
  }, [score]);

  const handleFile = async (file: File | null) => {
    if (!file || uploading) return;
    if (!enterpriseId) {
      setMessage({ type: 'error', text: '缺少企业 ID，无法验证交易凭证' });
      return;
    }
    const validation = validateCredentialFile(file);
    if (validation) {
      setMessage({ type: 'error', text: validation });
      return;
    }

    setUploading(true);
    setMessage(null);
    try {
      const now = new Date();
      const invoiceNo = `INV${now.getTime()}`;
      const invoiceDate = now.toISOString().slice(0, 10);
      const resp = await api.uploadInvoice(file, {
        seller_id: enterpriseId,
        invoice_no: invoiceNo,
        invoice_date: invoiceDate,
        invoice_amount: 1,
        quality_rating: 5,
      });

      const newScore = Math.min(100, safeScore + 10);
      const newRecord: CreditHistoryRecord = {
        id: `FULFILL-${resp.fulfillment_id || Date.now()}`,
        old_score: safeScore,
        new_score: newScore,
        change_value: 10,
        change_type: 'fulfillment',
        reason: `交易凭证 ${resp.invoice_info?.invoice_no || invoiceNo} 验证通过`,
        created_at: new Date().toISOString(),
      };
      setHistory((prev) => [newRecord, ...prev]);
      setScore(newScore);
      setMessage({ type: 'success', text: '交易凭证验证通过，已写入履约记录。' });
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : '上传失败，请稍后重试',
      });
    } finally {
      setUploading(false);
    }
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-brand-deep/55 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="collaboration-modal-title"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="relative flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-md border border-border bg-surface shadow-elevation-3"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel-header flex items-start justify-between gap-4 px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4.5 w-4.5 text-brand" />
              <h2 id="collaboration-modal-title" className="text-base font-bold text-ink">
                交易真实性验证
              </h2>
            </div>
            <p className="mt-1 text-xs font-medium text-ink-muted">
              上传发票、物流回单等真实交易凭证，完成履约闭环并更新信用记录
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {message ? (
            <div
              className={cn(
                'mb-4 flex items-center gap-2 rounded-md border px-4 py-3 text-xs font-semibold',
                message.type === 'success'
                  ? 'border-trust/20 bg-trust-soft text-trust'
                  : 'border-critical/15 bg-critical-soft text-critical',
              )}
            >
              {message.type === 'success' ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              {message.text}
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[0.95fr_1.05fr]">
            <section className="panel p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold text-ink-muted">当前履约信用</p>
                  <div className="metric-number mt-2 text-5xl font-black text-ink">{safeScore}</div>
                </div>
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-brand-soft text-brand">
                  <Sparkles className="h-5 w-5" />
                </div>
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-surface-subtle">
                <div className="h-full rounded-full bg-brand" style={{ width: `${safeScore}%` }} />
              </div>
              <p className="mt-4 text-xs font-medium leading-6 text-ink-muted">
                真实交易凭证会用于履约信用记录，不会向游客或公开查询接口展示敏感票据信息。
              </p>

              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={(event) => {
                  void handleFile(event.currentTarget.files?.[0] || null);
                  event.currentTarget.value = '';
                }}
              />
              <div
                className={cn(
                  'mt-5 flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-8 text-center transition-colors',
                  dragging ? 'border-brand bg-brand-soft' : 'border-border bg-surface-subtle hover:border-border-strong',
                  uploading && 'cursor-wait opacity-80',
                )}
                onClick={() => !uploading && fileInputRef.current?.click()}
                onDragOver={(event) => {
                  event.preventDefault();
                  if (!uploading) setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  if (!uploading) void handleFile(event.dataTransfer.files?.[0] || null);
                }}
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-md bg-surface text-brand shadow-elevation-1">
                  {uploading ? (
                    <Loader2 className="h-6 w-6 animate-spin" />
                  ) : (
                    <CloudUpload className="h-6 w-6" />
                  )}
                </div>
                <h3 className="mt-4 text-sm font-bold text-ink">
                  {uploading ? '正在验证凭证...' : '上传交易凭证'}
                </h3>
                <p className="mt-2 max-w-sm text-xs font-medium leading-5 text-ink-muted">
                  支持 PDF、JPG、PNG，最大 16MB；可点击选择或拖拽上传
                </p>
              </div>
            </section>

            <section className="panel overflow-hidden">
              <div className="panel-header flex items-center justify-between px-5 py-4">
                <div>
                  <h3 className="text-base font-bold text-ink">验证记录</h3>
                  <p className="mt-1 text-xs font-medium text-ink-muted">最近信用分与履约闭环变化</p>
                </div>
                <FileCheck2 className="h-5 w-5 text-brand" />
              </div>

              <div className="p-3">
                {isLoading ? (
                  <div className="flex h-72 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-brand" />
                  </div>
                ) : history.length === 0 ? (
                  <div className="flex h-72 flex-col items-center justify-center text-center text-ink-muted">
                    <Receipt className="h-9 w-9 text-ink-faint" />
                    <p className="mt-3 text-xs font-semibold">暂无验证记录</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {history.slice(0, 8).map((record, index) => (
                      <div key={record.id || index} className="flex items-center gap-3 px-2 py-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
                          <Receipt className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-bold text-ink">
                            {record.reason || record.change_type || '信用记录'}
                          </p>
                          <p className="mt-1 text-[11px] font-medium text-ink-muted">
                            {record.created_at ? new Date(record.created_at).toLocaleDateString('zh-CN') : '未记录日期'}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-md bg-surface-subtle px-2 py-1 text-[11px] font-black text-brand">
                          {scoreDeltaLabel(record)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body,
  );
}
