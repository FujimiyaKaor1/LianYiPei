import React, { useState, useEffect } from 'react';
import {
  Landmark, AlertTriangle, Plus,
  RefreshCw, Building2, Clock, CheckCircle2,
  X, ArrowRight, Database,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type RecruitmentGap, type RecruitmentTask, type RecommendedEnterprise } from '@/src/services/api';

const URGENCY_COLORS: Record<string, string> = {
  critical: 'bg-neutral-900 text-white border-neutral-900 shadow-sm',
  high: 'bg-neutral-600 text-white border-neutral-600',
  medium: 'bg-neutral-200 text-neutral-800 border-neutral-300',
  low: 'bg-neutral-50 text-neutral-500 border-neutral-200',
};
const URGENCY_LABELS: Record<string, string> = { critical: '极紧迫', high: '紧迫', medium: '一般', low: '低' };

const GAP_TYPE_LABELS: Record<string, string> = {
  supplier_shortage: '供应商不足',
  localization_shortage: '本地化不足',
  unmatched: '历史未匹配',
  graph_gap: '图谱缺口',
};

function urgencyKey(gap: RecruitmentGap): string {
  if (gap.urgency) return gap.urgency;
  const m: Record<string, string> = { 紧急: 'critical', 较高: 'high', 一般: 'medium' };
  return m[gap.urgency_label || ''] || 'low';
}

const STATUS_COLS = [
  { key: 'pending', label: '待处理', color: 'bg-neutral-300' },
  { key: 'contacted', label: '已联系', color: 'bg-neutral-500' },
  { key: 'negotiating', label: '洽谈中', color: 'bg-neutral-700' },
  { key: 'signed', label: '已签约', color: 'bg-neutral-900' },
];

type Tab = 'gaps' | 'tasks';

export default function GovRecruitment() {
  const [tab, setTab] = useState<Tab>('gaps');
  const [gaps, setGaps] = useState<RecruitmentGap[]>([]);
  const [tasks, setTasks] = useState<RecruitmentTask[]>([]);
  const [gapsLoading, setGapsLoading] = useState(true);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [neo4jEnriched, setNeo4jEnriched] = useState(false);
  const [error, setError] = useState(false);
  const [selectedGap, setSelectedGap] = useState<RecruitmentGap | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendedEnterprise[]>([]);
  const [recLoading, setRecLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createGap, setCreateGap] = useState<RecruitmentGap | null>(null);
  const [createLoading, setCreateLoading] = useState(false);
  const [taskUpdateLoading, setTaskUpdateLoading] = useState<number | null>(null);

  const loadTasks = async () => {
    setTasksLoading(true);
    try {
      const tasksRes = await api.getRecruitmentTasks();
      setTasks(tasksRes.tasks || []);
    } catch {
      setTasks([]);
    } finally {
      setTasksLoading(false);
    }
  };

  const loadGaps = async (includeNeo4j: boolean) => {
    setGapsLoading(true);
    setError(false);
    try {
      const gapsRes = await api.getRecruitmentGaps(
        { includeNeo4j },
        { timeoutMs: includeNeo4j ? 120_000 : 35_000 },
      );
      setGaps(gapsRes.gaps || []);
      setNeo4jEnriched(includeNeo4j);
    } catch {
      setError(true);
      setGaps([]);
    } finally {
      setGapsLoading(false);
    }
  };

  const refreshAll = async () => {
    await Promise.all([loadTasks(), loadGaps(neo4jEnriched)]);
  };

  useEffect(() => {
    void loadTasks();
    void loadGaps(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅首屏快速路径，不随 neo4jEnriched 重复拉取
  }, []);

  const handleRecommend = async (gap: RecruitmentGap) => {
    setSelectedGap(gap);
    setRecLoading(true);
    try {
      const res = await api.recommendEnterprises({ product_name: gap.product_name, gap_type: gap.gap_type });
      setRecommendations(res.enterprises || []);
    } catch { setRecommendations([]); }
    finally { setRecLoading(false); }
  };

  const handleCreateTask = async (gap: RecruitmentGap) => {
    setCreateGap(gap);
    setShowCreateModal(true);
  };

  const submitCreateTask = async () => {
    if (!createGap) return;
    setCreateLoading(true);
    try {
      await api.createRecruitmentTask({
        target_product: createGap.product_name,
        task_name: `招商任务-${createGap.product_name}`,
        priority: urgencyKey(createGap) === 'critical' || urgencyKey(createGap) === 'high' ? 'high' : 'normal',
      });
      setShowCreateModal(false);
      await refreshAll();
    } catch { /* ignore */ }
    finally { setCreateLoading(false); }
  };

  const moveTask = async (task: RecruitmentTask, newStatus: string) => {
    setTaskUpdateLoading(task.id);
    try {
      await api.updateRecruitmentTask(task.id, { status: newStatus });
      setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: newStatus } : t));
    } catch { /* ignore */ }
    finally { setTaskUpdateLoading(null); }
  };

  const PRIORITY_COLORS: Record<string, string> = {
    high: 'bg-neutral-800 text-white shadow-sm',
    urgent: 'bg-black text-white shadow-md',
    normal: 'bg-neutral-100 text-neutral-600',
    low: 'bg-neutral-50 text-neutral-400',
  };

  return (
    <div className="max-w-7xl mx-auto space-y-5">

      {/* Tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {([['gaps', '产业链缺口分析', gaps.length], ['tasks', '招商任务看板', tasks.length]] as [Tab, string, number][]).map(([key, label, count]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all',
              tab === key ? 'bg-black text-white shadow-lg shadow-black/10' : 'bg-white border border-neutral-200 text-neutral-600 hover:border-neutral-400',
            )}
          >
            {label}
            <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-bold', tab === key ? 'bg-white/20 text-white' : 'bg-neutral-100 text-neutral-500')}>
              {(key === 'gaps' && gapsLoading) || (key === 'tasks' && tasksLoading) ? '…' : count}
            </span>
          </button>
        ))}
        {tab === 'gaps' && !neo4jEnriched && !gapsLoading && (
          <button
            type="button"
            onClick={() => void loadGaps(true)}
            className="flex items-center gap-1.5 rounded-xl border border-neutral-200 bg-white px-3 py-2 text-xs font-bold text-neutral-600 hover:border-black"
          >
            <Database className="h-3.5 w-3.5" />
            合并 Neo4j 图谱缺口（较慢）
          </button>
        )}
        {tab === 'gaps' && neo4jEnriched && (
          <span className="text-[10px] font-medium text-blue-600">已合并 Neo4j 图谱缺口</span>
        )}
        <button type="button" onClick={() => void refreshAll().catch(() => {})} className="ml-auto p-2 hover:bg-neutral-100 rounded-lg transition-colors" title="刷新">
          <RefreshCw className={cn('w-4 h-4 text-neutral-400', (gapsLoading || tasksLoading) && 'animate-spin')} />
        </button>
      </div>

      {/* === GAPS TAB === */}
      <AnimatePresence mode="wait">
        {tab === 'gaps' && (
          <motion.div key="gaps" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-4">
            {gapsLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse rounded-2xl border border-neutral-100 bg-white p-6">
                    <div className="mb-4 h-4 w-1/3 rounded bg-neutral-100" />
                    <div className="grid grid-cols-3 gap-4">
                      <div className="h-16 rounded-xl bg-neutral-50" />
                      <div className="h-16 rounded-xl bg-neutral-50" />
                      <div className="h-16 rounded-xl bg-neutral-50" />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!gapsLoading && error ? (
              <div className="bg-white rounded-2xl border p-12 flex flex-col items-center">
                <p className="text-sm text-neutral-500 mb-4">缺口数据加载失败</p>
                <button type="button" onClick={() => void loadGaps(neo4jEnriched)} className="flex items-center gap-1.5 px-4 py-2 bg-neutral-100 rounded-lg text-xs font-bold"><RefreshCw className="w-3.5 h-3.5" /> 重试</button>
              </div>
            ) : !gapsLoading && gaps.length === 0 ? (
              <div className="bg-white rounded-2xl border p-16 flex flex-col items-center">
                <CheckCircle2 className="w-8 h-8 text-neutral-300 mb-3" />
                <p className="text-sm text-neutral-500">当前无产业链缺口，供应链链条健康</p>
              </div>
            ) : !gapsLoading ? gaps.map((gap, i) => (
              <motion.div
                key={gap.product_name}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 bg-neutral-100 rounded-xl flex items-center justify-center shrink-0">
                      <AlertTriangle className="w-5 h-5 text-neutral-600" />
                    </div>
                    <div>
                      <h3 className="text-base font-black tracking-tight">{gap.product_name}</h3>
                      <p className="text-xs text-neutral-500 mt-0.5">{gap.gap_type_label || GAP_TYPE_LABELS[gap.gap_type] || gap.gap_type}</p>
                    </div>
                  </div>
                  <span className={cn('text-[9px] font-bold px-2 py-1 rounded border', URGENCY_COLORS[urgencyKey(gap)] || URGENCY_COLORS.low)}>
                    {gap.urgency_label || URGENCY_LABELS[urgencyKey(gap)] || urgencyKey(gap)}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-4">
                  {[
                    { label: '现有供应商', value: gap.supplier_count },
                    { label: '本地化比例', value: `${(gap.local_ratio * 100).toFixed(0)}%` },
                    { label: '影响企业数', value: gap.affected_enterprises ?? gap.affected_enterprise_count ?? '—' },
                  ].map(m => (
                    <div key={m.label} className="text-center p-3 bg-neutral-50 rounded-xl">
                      <p className="text-[9px] font-bold text-neutral-400 uppercase tracking-widest mb-1">{m.label}</p>
                      <p className="text-lg font-black">{m.value}</p>
                    </div>
                  ))}
                </div>

                {gap.suggestion && (
                  <p className="text-xs text-neutral-500 mb-4 bg-neutral-50 rounded-lg p-3">
                    {gap.suggestion.description || (
                      <>
                        建议招募 <strong>{gap.suggestion.enterprise_type}</strong>
                        {(gap.suggestion.estimated_investment || gap.suggestion.investment_scale) &&
                          `，预计投资 ${gap.suggestion.estimated_investment || gap.suggestion.investment_scale}`}
                      </>
                    )}
                  </p>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={() => void handleRecommend(gap)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-white border border-neutral-200 rounded-lg text-xs font-bold hover:border-black transition-all"
                  >
                    <Building2 className="w-3.5 h-3.5" /> 推荐潜在企业
                  </button>
                  <button
                    onClick={() => void handleCreateTask(gap)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-black text-white rounded-lg text-xs font-bold hover:bg-neutral-800 transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" /> 创建招商任务
                  </button>
                </div>

                {/* Recommendation Results */}
                <AnimatePresence>
                  {selectedGap?.product_name === gap.product_name && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                      className="mt-4 border-t border-neutral-100 pt-4 overflow-hidden"
                    >
                      <p className="text-xs font-bold text-neutral-700 mb-3">推荐潜在招商企业</p>
                      {recLoading ? (
                        <div className="flex items-center gap-2 text-xs text-neutral-400">正在检索…</div>
                      ) : recommendations.length === 0 ? (
                        <p className="text-xs text-neutral-400">暂无推荐企业</p>
                      ) : (
                        <div className="space-y-2">
                          {recommendations.map((ent, idx) => (
                            <div key={idx} className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl">
                              <div>
                                <p className="text-xs font-bold">{ent.name}</p>
                                <p className="text-[10px] text-neutral-500">{ent.location} · {ent.main_products}</p>
                              </div>
                              <span className="text-[10px] font-bold text-black bg-neutral-200 px-2 py-0.5 rounded">
                                匹配 {ent.match_score}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )) : null}
          </motion.div>
        )}

        {/* === TASKS KANBAN TAB === */}
        {tab === 'tasks' && (
          <motion.div key="tasks" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            {tasksLoading && (
              <div className="mb-4 grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-48 animate-pulse rounded-2xl bg-neutral-100" />
                ))}
              </div>
            )}
            <div className={cn('grid grid-cols-4 gap-4', tasksLoading && 'pointer-events-none opacity-40')}>
              {STATUS_COLS.map(col => {
                const colTasks = tasks.filter(t => t.status === col.key);
                return (
                  <div key={col.key} className="bg-neutral-50 rounded-2xl border border-neutral-100 p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <span className={cn('w-2 h-2 rounded-full', col.color)} />
                      <span className="text-xs font-bold text-neutral-700">{col.label}</span>
                      <span className="ml-auto text-[10px] font-bold text-neutral-400 bg-neutral-200 px-1.5 py-0.5 rounded">{colTasks.length}</span>
                    </div>
                    <div className="space-y-2">
                      {colTasks.length === 0 && (
                        <p className="text-[10px] text-neutral-400 text-center py-4">暂无任务</p>
                      )}
                      {colTasks.map(task => (
                        <div key={task.id} className="bg-white rounded-xl border border-neutral-100 p-3 shadow-sm">
                          <p className="text-xs font-bold mb-1">{task.task_name}</p>
                          <p className="text-[10px] text-neutral-500 mb-2">{task.target_product}</p>
                          {task.deadline && (
                            <div className="flex items-center gap-1 text-[9px] text-neutral-400 mb-2">
                              <Clock className="w-3 h-3" />
                              {new Date(task.deadline).toLocaleDateString('zh-CN')}
                            </div>
                          )}
                          <span className={cn('text-[8px] font-bold px-1.5 py-0.5 rounded', PRIORITY_COLORS[task.priority] || PRIORITY_COLORS.normal)}>
                            {task.priority === 'high' || task.priority === 'urgent' ? '高优先级' : '普通'}
                          </span>
                          {/* Move buttons */}
                          <div className="flex gap-1 mt-2">
                            {STATUS_COLS.filter(c => c.key !== col.key).slice(0, 1).map(nextCol => (
                              <button
                                key={nextCol.key}
                                onClick={() => void moveTask(task, nextCol.key)}
                                disabled={taskUpdateLoading === task.id}
                                className="flex items-center gap-0.5 text-[8px] font-bold text-neutral-500 hover:text-black transition-colors"
                              >
                                {taskUpdateLoading === task.id ? <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-neutral-400" /> : <ArrowRight className="w-3 h-3" />}
                                {nextCol.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Task Modal */}
      <AnimatePresence>
        {showCreateModal && createGap && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
            onClick={e => e.target === e.currentTarget && setShowCreateModal(false)}
          >
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-black">创建招商任务</h3>
                <button onClick={() => setShowCreateModal(false)}><X className="w-5 h-5 text-neutral-400 hover:text-black" /></button>
              </div>
              <div className="space-y-3 mb-5">
                <div className="p-3 bg-neutral-50 rounded-xl">
                  <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-1">目标产品缺口</p>
                  <p className="text-sm font-bold">{createGap.product_name}</p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs text-neutral-500">
                  <div className="p-3 bg-neutral-50 rounded-xl">
                    <p className="text-[9px] font-bold text-neutral-400 mb-1">建议企业类型</p>
                    <p className="font-medium text-neutral-700">{createGap.suggestion?.enterprise_type || '制造企业'}</p>
                  </div>
                  <div className="p-3 bg-neutral-50 rounded-xl">
                    <p className="text-[9px] font-bold text-neutral-400 mb-1">紧迫程度</p>
                    <p className={cn('font-bold', ['critical', 'high'].includes(urgencyKey(createGap)) ? 'text-black' : 'text-neutral-500')}>
                      {createGap.urgency_label || URGENCY_LABELS[urgencyKey(createGap)] || urgencyKey(createGap)}
                    </p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => void submitCreateTask()}
                disabled={createLoading}
                className="w-full py-3 bg-black text-white rounded-xl text-sm font-bold hover:bg-neutral-800 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {createLoading ? <span className="inline-block h-4 w-4 animate-pulse rounded-full bg-white/80" /> : <Plus className="w-4 h-4" />}
                确认创建
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
