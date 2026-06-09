import React, { useState, useEffect } from 'react';
import {
  ShieldAlert, Search, Loader2, RefreshCw,
  AlertCircle, CheckCircle2, Clock, UserCheck, ArrowRight,
  ChevronRight, Send, FileText, X, Zap
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type AlertData, type WorkflowStatsData } from '@/src/services/api';

const LEVEL_COLORS: Record<string, string> = {
  red: 'bg-brand-solid text-white border-brand-solid shadow-sm',
  yellow: 'bg-neutral-200 text-neutral-800 border-neutral-300',
  blue: 'bg-neutral-50 text-neutral-500 border-neutral-200',
};
const LEVEL_LABELS: Record<string, string> = { red: '高危', yellow: '中级', blue: '低级' };

type WorkflowPanel = {
  alertId: number;
  mode: 'assign' | 'submit';
  workflowId?: number;
};

export default function GovAlerts() {
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [stats, setStats] = useState<WorkflowStatsData | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [activeId, setActiveId] = useState<number | null>(null);
  const [panel, setPanel] = useState<WorkflowPanel | null>(null);

  // Assign form
  const [assignTo, setAssignTo] = useState('');
  const [deadline, setDeadline] = useState('');
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignResult, setAssignResult] = useState('');

  // Submit form
  const [notes, setNotes] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);

  const load = () => {
    setError(false);
    setAlertsLoading(true);
    api
      .getAlerts({ page: 1, per_page: 100 }, { timeoutMs: 45_000 })
      .then((res) => setAlerts(res.alerts || []))
      .catch(() => {
        setError(true);
        setAlerts([]);
      })
      .finally(() => setAlertsLoading(false));

    setStatsLoading(true);
    api
      .getWorkflowStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = alerts.filter(a => {
    if (levelFilter && a.level !== levelFilter) return false;
    if (search && !a.product_name.includes(search) && !a.message.includes(search)) return false;
    return true;
  });

  const activeAlert = alerts.find(a => a.id === activeId);

  const handleAssign = async () => {
    if (!panel || !assignTo) return;
    setAssignLoading(true);
    setAssignResult('');
    try {
      const res = await api.assignAlert(panel.alertId, {
        assigned_to: parseInt(assignTo),
        deadline: deadline || undefined,
      });
      setAssignResult(`✓ 派单成功，工作流ID: ${res.workflow_id}`);
      setPanel(null);
    } catch (e: any) {
      setAssignResult(`✗ 派单失败: ${e?.message || '请检查处理人ID'}`);
    } finally {
      setAssignLoading(false);
    }
  };

  const handleSubmitWorkflow = async () => {
    if (!panel?.workflowId || !notes) return;
    setSubmitLoading(true);
    try {
      await api.submitWorkflow(panel.workflowId, { handling_notes: notes });
      setPanel(null);
      setNotes('');
    } catch { /* ignore */ }
    finally { setSubmitLoading(false); }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-5">

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {statsLoading ? (
          [1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="animate-pulse rounded-xl border border-neutral-100 bg-white p-4 shadow-sm">
              <div className="mb-2 h-3 w-16 rounded bg-neutral-100" />
              <div className="h-7 w-12 rounded bg-neutral-100" />
            </div>
          ))
        ) : stats ? (
          [
            { label: '全部工作流', value: stats.total, color: '' },
            { label: '待处理', value: stats.pending, color: 'text-neutral-900' },
            { label: '处理中', value: stats.processing, color: 'text-neutral-600' },
            { label: '已完成', value: stats.completed, color: 'text-neutral-400' },
            { label: '完成率', value: `${(stats.completion_rate * 100).toFixed(0)}%`, color: 'text-black' },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-xl border border-neutral-100 shadow-sm p-4">
              <p className="text-[9px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{s.label}</p>
              <p className={cn('text-xl font-black tracking-tight', s.color)}>{s.value}</p>
            </div>
          ))
        ) : null}
      </div>

      {/* Main Panel: Master-Detail */}
      <div className="flex gap-5 h-[calc(100vh-18rem)] min-h-[500px]">

        {/* Alert List */}
        <div className="w-80 shrink-0 flex flex-col bg-white rounded-2xl border border-neutral-100 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-neutral-100 shrink-0 space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400" />
              <input
                value={search} onChange={e => setSearch(e.target.value)}
                placeholder="搜索预警..."
                className="w-full pl-9 pr-3 py-2 bg-neutral-50 border border-neutral-100 rounded-lg text-xs focus:outline-none focus:border-neutral-300"
              />
            </div>
            <div className="flex gap-1">
              {[['', '全部'], ['red', '高危'], ['yellow', '中级'], ['blue', '低级']].map(([val, label]) => (
                <button
                  key={val}
                  onClick={() => setLevelFilter(val)}
                  className={cn('px-2 py-1 rounded-md text-[9px] font-bold transition-all', levelFilter === val ? 'bg-brand-solid text-white shadow-md' : 'bg-neutral-50 border border-neutral-200 text-neutral-500 hover:bg-neutral-100')}
                >
                  {label}
                </button>
              ))}
              <button onClick={() => void load()} className="ml-auto p-1 hover:bg-neutral-100 rounded transition-colors">
                <RefreshCw className="w-3 h-3 text-neutral-400" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
            {alertsLoading ? (
              [1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="animate-pulse rounded-xl border border-neutral-100 bg-neutral-50 px-3.5 py-3">
                  <div className="mb-2 h-3 w-10 rounded bg-neutral-200" />
                  <div className="mb-1 h-3 w-full rounded bg-neutral-200" />
                  <div className="h-3 w-4/5 rounded bg-neutral-100" />
                </div>
              ))
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-40 text-neutral-400">
                <AlertCircle className="w-6 h-6 mb-2 text-neutral-300" />
                <p className="text-xs">加载失败</p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-neutral-400">
                <CheckCircle2 className="w-6 h-6 mb-2 text-blue-300" />
                <p className="text-xs">暂无符合条件的预警</p>
              </div>
            ) : filtered.map((a, i) => (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.02 }}
                onClick={() => { setActiveId(a.id); setAssignResult(''); }}
                className={cn(
                  'cursor-pointer px-3.5 py-3 rounded-xl border transition-all',
                  activeId === a.id ? 'bg-brand-solid border-brand-solid text-white' : 'bg-white border-neutral-100 hover:border-neutral-200',
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={cn('text-[8px] font-bold px-1.5 py-0.5 rounded border', activeId === a.id ? 'bg-white/20 text-white border-white/20' : LEVEL_COLORS[a.level])}>
                    {LEVEL_LABELS[a.level]}
                  </span>
                </div>
                <p className={cn('text-xs font-bold leading-snug', activeId === a.id ? 'text-white' : '')}>{a.product_name}</p>
                <p className={cn('text-[10px] truncate mt-0.5', activeId === a.id ? 'text-white/60' : 'text-neutral-400')}>{a.message.slice(0, 50)}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="flex-1 min-w-0 bg-white rounded-2xl border border-neutral-100 shadow-sm flex flex-col overflow-hidden">
          {activeAlert ? (
            <>
              <div className="px-8 py-6 border-b border-neutral-100 shrink-0">
                <div className="flex items-center justify-between mb-2">
                  <span className={cn('text-[9px] font-bold px-2 py-1 rounded border', LEVEL_COLORS[activeAlert.level])}>
                    预警等级：{LEVEL_LABELS[activeAlert.level]}
                  </span>
                  <span className="text-[10px] text-neutral-400">ID: WRN-{String(activeAlert.id).padStart(8, '0')}</span>
                </div>
                <h2 className="text-xl font-black tracking-tight">{activeAlert.product_name}</h2>
              </div>

              <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">
                <div className="bg-neutral-50 rounded-xl p-5 space-y-3">
                  <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">风险详情</p>
                  <p className="text-sm text-neutral-700 leading-relaxed">{activeAlert.message}</p>
                  {activeAlert.suggestion && (
                    <p className="text-xs text-neutral-500 border-t border-neutral-100 pt-3">{activeAlert.suggestion}</p>
                  )}
                </div>

                {/* Assign Result Toast */}
                <AnimatePresence>
                  {assignResult && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className={cn('px-4 py-3 rounded-xl text-xs font-medium border', assignResult.startsWith('✓') ? 'bg-neutral-100 border-neutral-300 text-neutral-800' : 'bg-neutral-50 border-neutral-200 text-neutral-600')}>
                      {assignResult}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Assign Panel */}
                <AnimatePresence>
                  {panel?.alertId === activeAlert.id && panel.mode === 'assign' && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                      className="bg-white rounded-xl border border-neutral-200 p-5 space-y-4 overflow-hidden"
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-bold">派单给专员</p>
                        <button onClick={() => setPanel(null)}><X className="w-4 h-4 text-neutral-400 hover:text-black" /></button>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">处理人企业 ID</label>
                          <input value={assignTo} onChange={e => setAssignTo(e.target.value)}
                            placeholder="输入企业 ID..."
                            className="w-full bg-neutral-50 rounded-lg p-3 text-sm focus:outline-none focus:ring-1 focus:ring-black" />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">截止时间（可选）</label>
                          <input type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)}
                            className="w-full bg-neutral-50 rounded-lg p-3 text-sm focus:outline-none focus:ring-1 focus:ring-black" />
                        </div>
                      </div>
                      <button onClick={() => void handleAssign()} disabled={!assignTo || assignLoading}
                        className="flex items-center gap-2 px-4 py-2.5 bg-brand-solid text-white rounded-lg text-xs font-bold hover:bg-brand-solid-hover transition-all disabled:opacity-50">
                        {assignLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        确认派单
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Action Bar */}
              <div className="px-8 py-4 border-t border-neutral-100 bg-neutral-50/50 shrink-0 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPanel(panel?.alertId === activeAlert.id && panel.mode === 'assign' ? null : { alertId: activeAlert.id, mode: 'assign' })}
                    className="flex items-center gap-1.5 px-4 py-2 bg-white border border-neutral-200 rounded-lg text-xs font-bold hover:border-brand-solid transition-all"
                  >
                    <UserCheck className="w-3.5 h-3.5" /> 派单给专员
                  </button>
                </div>
                <div className="text-[10px] text-neutral-400">
                  {activeAlert.created_at ? new Date(activeAlert.created_at).toLocaleString('zh-CN') : ''}
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-neutral-400">
              <ShieldAlert className="w-10 h-10 mb-3 text-neutral-200" />
              <p className="text-xs">点击左侧预警查看详情并处置</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
