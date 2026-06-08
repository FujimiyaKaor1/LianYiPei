import React, { useState } from 'react';
import { FileText, Upload, Loader2, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

export default function InvoiceManagement() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [invoiceNo, setInvoiceNo] = useState('');
  const [invoiceAmount, setInvoiceAmount] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadInvoice(file, {
        seller_id: user?.id || 0,
        invoice_no: invoiceNo,
        invoice_date: new Date().toISOString().slice(0, 10),
        invoice_amount: parseFloat(invoiceAmount) || 0,
      });
      showToast('发票上传成功', 'success');
      setFile(null);
      setInvoiceNo('');
      setInvoiceAmount('');
    } catch {
      showToast(NETWORK_ERROR_MESSAGE, 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.type === 'application/pdf' || f.type.startsWith('image/'))) {
      setFile(f);
    } else {
      showToast('仅支持 PDF 或图片格式', 'warning');
    }
  };

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-lg font-bold tracking-tight text-ink">发票上传</h2>
        <p className="text-xs text-ink-muted mt-1">上传交易发票用于履约验证与财务对账</p>
      </div>

      <div className="card p-8">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={cn(
            'border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer',
            dragOver ? 'border-brand bg-brand-soft' : 'border-border hover:border-border-strong',
          )}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input id="file-input" type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)} />
          {file ? (
            <div className="space-y-2">
              <CheckCircle2 className="w-8 h-8 text-success mx-auto" />
              <p className="text-sm font-semibold text-ink">{file.name}</p>
              <p className="text-xs text-ink-muted">{(file.size / 1024).toFixed(1)} KB</p>
              <button onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="text-xs text-error hover:underline">移除</button>
            </div>
          ) : (
            <div className="space-y-2">
              <Upload className="w-8 h-8 text-ink-muted mx-auto" />
              <p className="text-sm font-semibold text-ink">拖拽发票文件到此处</p>
              <p className="text-xs text-ink-muted">或点击选择 PDF / 图片文件</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4 mt-6">
          <div>
            <label className="text-xs font-semibold text-ink-soft block mb-1.5">发票号码</label>
            <input value={invoiceNo} onChange={(e) => setInvoiceNo(e.target.value)}
              className="input w-full" placeholder="如 INV-2024-001" />
          </div>
          <div>
            <label className="text-xs font-semibold text-ink-soft block mb-1.5">发票金额 (¥)</label>
            <input value={invoiceAmount} onChange={(e) => setInvoiceAmount(e.target.value)}
              className="input w-full" placeholder="0.00" type="number" step="0.01" />
          </div>
        </div>

        <button onClick={handleUpload} disabled={!file || uploading}
          className="btn-primary w-full mt-6">
          {uploading ? <><Loader2 className="w-4 h-4 animate-spin" /> 上传中...</> : <><Upload className="w-4 h-4" /> 上传发票</>}
        </button>
      </div>

      <div className="card p-5 flex items-start gap-3">
        <FileText className="w-5 h-5 text-ink-muted mt-0.5 shrink-0" />
        <div>
          <p className="text-xs font-semibold text-ink">发票验证</p>
          <p className="text-[11px] text-ink-muted mt-1">上传的发票将自动进行 OCR 识别和真伪验证，验证结果将在 1-2 分钟内返回。已认证的发票可用于履约闭环和信用分加分。</p>
        </div>
      </div>
    </div>
  );
}
