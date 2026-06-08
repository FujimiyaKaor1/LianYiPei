import { useEffect, useState } from 'react';
import { Search, Loader2, AlertTriangle, RefreshCw, CheckCircle2, Clock, XCircle, UserCheck, ArrowRight } from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api, type WorkflowItem, type WorkflowStatsData, NETWORK_ERROR_MESSAGE } from '@/src/services/api';

const STATUS_MAP: Record<string, { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: '待处理', color: 'bg-yellow-100 text-yellow-700', icon: Clock },
  processing: { label: '处理中', color: 'bg-blue-100 text-blue-700', icon: Loader2 },
  completed: { label: '已完成', color: 'bg-blue-100 text-blue-700', icon: CheckCircle2 },
  rejected: { label: '已驳回', color: 'bg-red-100 text-red-700', icon: XCircle },
};

export default function AlertWorkflow() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [stats, setStats] = useState<WorkflowStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [wfRes, statsRes] = await Promise.all([
        api.getMyWorkflows(filter || undefined),
        api.getWorkflowStats(),
      ]);
      setWorkflows(wfRes.workflows || []);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadData(); }, [filter]);

  const handleStart = async (id: number) => {
    try {
      await api.startWorkflow(id);
      showToast('已开始处理', 'success');
      void loadData();
    } catch { showToast('操作失败', 'error'); }
  };

  const handleSubmit = async (id: number) => {
    const notes = prompt('请输入处理说明：');
    if (!notes) return;
    try {
      await api.submitWorkflow(id, { handling_notes: notes });
      showToast('已提交审核', 'success');
      void loadData();
    } catch { showToast('提交失败', 'error'); }
  };

  if (!user) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-ink">预警工作流</h2>
          <p className="text-xs text-ink-muted mt-1">预警任务的派发、处理与审核流转</p>
        </div>
        <button onClick={() => void loadData()} disabled={loading} className="btn-ghost btn-sm">
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: '总计', value: stats.total, color: 'text-ink' },
            { label: '待处理', value: stats.pending, color: 'text-yellow-600' },
            { label: '处理中', value: stats.processing, color: 'text-blue-600' },
            { label: '已完成', value: stats.completed, color: 'text-blue-600' },
            { label: '已驳回', value: stats.rejected, color: 'text-red-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="card p-4 text-center">
              <p className={cn('text-2xl font-bold', color)}>{value ?? '-'}</p>
              <p className="text-[10px] text-ink-muted mt-1 font-medium">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2">
        {['', 'pending', 'processing', 'completed', 'rejected'].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={cn(
              'px-4 py-1.5 rounded-full text-xs font-semibold transition-colors',
              filter === s ? 'bg-ink text-on-brand' : 'bg-canvas-muted text-ink-soft hover:bg-border',
            )}
          >
            {s ? STATUS_MAP[s]?.label : '全部'}
          </button>
        ))}
      </div>

      {/* Workflow List */}
      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-ink-muted" /></div>
      ) : error ? (
        <div className="card p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-warning mx-auto mb-2" />
          <p className="text-sm text-ink-soft">{error}</p>
        </div>
      ) : workflows.length === 0 ? (
        <div className="card p-12 text-center">
          <CheckCircle2 className="w-10 h-10 text-ink-muted mx-auto mb-3" />
          <p className="text-sm font-semibold text-ink-soft">暂无工作流任务</p>
          <p className="text-xs text-ink-muted mt-1">所有预警任务已处理完毕</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => {
            const status = STATUS_MAP[wf.status] || STATUS_MAP.pending;
            const StatusIcon = status.icon;
            return (
              <div key={wf.id} className="card p-5 flex items-center gap-4 hover:border-border-hover transition-colors">
                <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center shrink-0', status.color)}>
                  <StatusIcon className={cn('w-5 h-5', wf.status === 'processing' && 'animate-spin')} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">工作流 #{wf.id}</span>
                    <span className={cn('badge text-[10px]', status.color)}>{status.label}</span>
                  </div>
                  <p className="text-xs text-ink-muted mt-0.5">预警 #{wf.alert_id}</p>
                  {wf.handling_notes && (
                    <p className="text-xs text-ink-soft mt-1 truncate">{wf.handling_notes}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {wf.status === 'pending' && (
                    <button onClick={() => handleStart(wf.id)} className="btn-primary btn-sm">
                      开始处理
                    </button>
                  )}
                  {wf.status === 'processing' && (
                    <button onClick={() => handleSubmit(wf.id)} className="btn-primary btn-sm">
                      提交审核
                    </button>
                  )}
                  <ArrowRight className="w-4 h-4 text-ink-muted" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
