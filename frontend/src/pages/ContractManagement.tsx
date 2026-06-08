import { useEffect, useState } from 'react';
import { FileText, Loader2, AlertTriangle, RefreshCw, Download, CheckCircle2, Clock, PenTool, ArrowRight } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, type ContractItem, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-neutral-100 text-neutral-600' },
  pending_sign: { label: '待签署', color: 'bg-yellow-100 text-yellow-700' },
  signed: { label: '已签署', color: 'bg-blue-100 text-blue-700' },
  fulfilled: { label: '已履约', color: 'bg-blue-100 text-blue-700' },
};

export default function ContractManagement() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [contracts, setContracts] = useState<ContractItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [signingId, setSigningId] = useState<number | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getContractsList();
      setContracts(res.contracts || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadData(); }, []);

  const handleSign = async (contractId: number) => {
    setSigningId(contractId);
    try {
      await api.signContract(contractId, {
        signature_type: 'electronic',
        timestamp: new Date().toISOString(),
      });
      showToast('签署成功', 'success');
      void loadData();
    } catch {
      showToast('签署失败，请重试', 'error');
    } finally {
      setSigningId(null);
    }
  };

  const handleDownload = (contractId: number) => {
    showToast(`正在下载合同 #${contractId}...`, 'info');
  };

  if (!user) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-ink">电子合同</h2>
          <p className="text-xs text-ink-muted mt-1">管理与签署产业链供需合同</p>
        </div>
        <button onClick={() => void loadData()} disabled={loading} className="btn-ghost btn-sm">
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      {/* Loading / Error / Empty */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-ink-muted" /></div>
      ) : error ? (
        <div className="card p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-warning mx-auto mb-2" />
          <p className="text-sm text-ink-soft">{error}</p>
        </div>
      ) : contracts.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="w-10 h-10 text-ink-muted mx-auto mb-3" />
          <p className="text-sm font-semibold text-ink-soft">暂无合同</p>
          <p className="text-xs text-ink-muted mt-1">完成供需匹配后将自动生成电子合同</p>
        </div>
      ) : (
        <div className="space-y-3">
          {contracts.map((c) => (
            <div key={c.id} className="card p-5 hover:border-border-hover transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="w-4 h-4 text-ink-muted shrink-0" />
                    <span className="text-sm font-semibold text-ink">{c.contract_no || `合同 #${c.id}`}</span>
                    <span className={cn('badge text-[10px]', STATUS_MAP[c.status]?.color)}>
                      {STATUS_MAP[c.status]?.label || c.status}
                    </span>
                  </div>
                  <p className="text-xs text-ink-soft">{c.product_name}</p>
                  <div className="flex items-center gap-4 mt-2 text-[10px] text-ink-muted">
                    <span>买方: {c.buyer_name}</span>
                    <span>卖方: {c.seller_name}</span>
                    <span className="font-semibold text-ink">¥ {c.total_amount?.toLocaleString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {c.status === 'pending_sign' && (
                    <button
                      onClick={() => handleSign(c.id)}
                      disabled={signingId === c.id}
                      className="btn-primary btn-sm gap-1.5"
                    >
                      {signingId === c.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <PenTool className="w-3 h-3" />
                      )}
                      签署
                    </button>
                  )}
                  {c.status === 'signed' && (
                    <button onClick={() => handleDownload(c.id)} className="btn-secondary btn-sm gap-1.5">
                      <Download className="w-3 h-3" />
                      下载
                    </button>
                  )}
                  <ArrowRight className="w-4 h-4 text-ink-muted" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats footer */}
      {contracts.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {Object.entries(STATUS_MAP).map(([key, { label, color }]) => {
            const count = contracts.filter((c) => c.status === key).length;
            return (
              <div key={key} className="card p-3 text-center">
                <p className="text-lg font-bold text-ink">{count}</p>
                <span className={cn('badge text-[10px]', color)}>{label}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
