import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  Save,
  Plus,
  Trash2,
  AlertCircle,
} from 'lucide-react';
import { apiRules, CreditRule, AlertThreshold } from '@/src/lib/adminApi';
import { useToast } from '@/src/components/ToastProvider';

export default function RuleConfigPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<'credit' | 'threshold'>('credit');
  const [creditRules, setCreditRules] = useState<CreditRule[]>([]);
  const [thresholds, setThresholds] = useState<AlertThreshold[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingChanges, setPendingChanges] = useState<Record<string, number>>({});
  const [changeReason, setChangeReason] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [newRuleType, setNewRuleType] = useState('');
  const [newRuleScore, setNewRuleScore] = useState('');
  const [newRuleModal, setNewRuleModal] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [cr, th] = await Promise.all([
        apiRules.getCreditRules(),
        apiRules.getAlertThresholds(),
      ]);
      setCreditRules(cr?.rules ?? []);
      setThresholds(th?.thresholds ?? []);
    } catch {
      showToast('加载失败', 'error');
      setCreditRules([]);
      setThresholds([]);
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { void fetchData(); }, [fetchData]);

  const markChange = (id: number, val: number) => {
    setPendingChanges((prev) => ({ ...prev, [id]: val }));
  };

  const handleSaveAll = async () => {
    if (!changeReason.trim()) {
      showToast('请填写变更原因', 'warning');
      return;
    }
    setActionLoading(true);
    let ok = true;
    for (const [idStr, val] of Object.entries(pendingChanges)) {
      const id = parseInt(idStr);
      const r = await apiRules.updateCreditRule(id, { score_change: val as number, change_reason: changeReason.trim() });
      if (!(r as { success?: boolean }).success) {
        ok = false;
        showToast(`规则 ${id} 更新失败`, 'error');
      }
    }
    setActionLoading(false);
    if (ok) {
      showToast('配置已保存', 'success');
      setPendingChanges({});
      setConfirmOpen(false);
      setChangeReason('');
      void fetchData();
    }
  };

  const handleAddRule = async () => {
    if (!newRuleType.trim() || !newRuleScore.trim()) {
      showToast('请填写完整', 'warning');
      return;
    }
    if (!changeReason.trim()) {
      showToast('请先填写变更原因', 'warning');
      return;
    }
    setActionLoading(true);
    const r = await apiRules.addCreditRule({
      rule_type: newRuleType.trim(),
      score_change: parseFloat(newRuleScore),
      change_reason: changeReason.trim(),
    });
    setActionLoading(false);
    if ((r as { success?: boolean }).success) {
      showToast('规则已添加', 'success');
      setNewRuleModal(false);
      setNewRuleType('');
      setNewRuleScore('');
      void fetchData();
    } else {
      showToast((r as { error?: string }).error || '添加失败', 'error');
    }
  };

  const handleDeleteRule = async (id: number) => {
    if (!changeReason.trim()) {
      showToast('请先填写变更原因', 'warning');
      return;
    }
    if (!confirm('确定删除该规则？')) return;
    setActionLoading(true);
    const r = await apiRules.deleteCreditRule(id, changeReason.trim());
    setActionLoading(false);
    if ((r as { success?: boolean }).success) {
      showToast('规则已删除', 'success');
      void fetchData();
    } else {
      showToast((r as { error?: string }).error || '删除失败', 'error');
    }
  };

  const handleSaveThreshold = async (id: number, val: number) => {
    const th = thresholds.find((t) => t.id === id);
    if (!th) return;
    setActionLoading(true);
    const r = await apiRules.upsertAlertThreshold({ dimension: th.dimension, threshold_value: val });
    setActionLoading(false);
    if ((r as { success?: boolean }).success) {
      showToast('阈值已保存', 'success');
    } else {
      showToast((r as { error?: string }).error || '保存失败', 'error');
    }
  };

  const dimensionLabel: Record<string, string> = {
    import_threshold: '进口预警阈值',
    interprovincial_threshold: '跨省预警阈值',
    local: '本地预警阈值',
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Tab */}
      <div className="flex gap-2">
        {[
          { key: 'credit', label: '信用分规则' },
          { key: 'threshold', label: '预警阈值' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as 'credit' | 'threshold')}
            className={`rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
              tab === t.key
                ? 'bg-brand-solid text-white'
                : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 变更原因输入 */}
      <div className="rounded-2xl border border-yellow-200 bg-yellow-50 p-4">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-4 h-4 text-yellow-600" />
          <span className="text-xs font-bold text-yellow-700">变更原因（必填，所有修改操作均需记录）</span>
        </div>
        <input
          type="text"
          value={changeReason}
          onChange={(e) => setChangeReason(e.target.value)}
          placeholder="请输入本次修改的原因，如：调整权重比例以提升撮合准确率"
          className="w-full rounded-xl border border-yellow-200 px-3 py-2 text-sm focus:ring-1 focus:ring-yellow-400 focus:border-yellow-400 outline-none transition-shadow bg-white"
        />
      </div>

      {/* 信用分规则 */}
      {tab === 'credit' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setNewRuleModal(true)}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-3 h-3" />
              新增规则
            </button>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 bg-neutral-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">规则类型</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">分值变更</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">当前分值</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {creditRules.map((rule) => {
                  const pending = pendingChanges[rule.id];
                  return (
                    <tr key={rule.id} className="hover:bg-neutral-50/50 transition-colors">
                      <td className="px-4 py-3">
                        <span className="font-medium text-neutral-800">{rule.rule_type}</span>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          defaultValue={rule.score_change}
                          onChange={(e) => markChange(rule.id, parseFloat(e.target.value))}
                          className="w-28 rounded-xl border border-neutral-200 px-2 py-1 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-semibold ${pending != null ? (pending >= 0 ? 'text-blue-600' : 'text-red-500') : 'text-neutral-900'}`}>
                          {pending != null ? pending : rule.score_change}
                          {pending != null && pending !== rule.score_change && (
                            <span className="text-xs ml-1 text-neutral-400">
                              ({pending - rule.score_change >= 0 ? '+' : ''}{(pending - rule.score_change).toFixed(1)})
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => void handleDeleteRule(rule.id)}
                          disabled={actionLoading}
                          className="rounded-lg p-1.5 hover:bg-red-50 text-neutral-400 hover:text-red-500 disabled:opacity-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {Object.keys(pendingChanges).length > 0 && (
            <div className="flex justify-end">
              <button
                onClick={() => setConfirmOpen(true)}
                className="flex items-center gap-2 rounded-xl bg-brand-solid px-5 py-2.5 text-sm font-bold text-white hover:bg-brand-solid-hover transition-colors shadow-md"
              >
                <Save className="w-4 h-4" />
                保存全部修改
              </button>
            </div>
          )}
        </div>
      )}

      {/* 预警阈值 */}
      {tab === 'threshold' && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 bg-neutral-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">维度</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">当前阈值</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">调整</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {thresholds.map((th) => (
                  <tr key={th.id} className="hover:bg-neutral-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <span className="font-medium text-neutral-800">
                        {dimensionLabel[th.dimension] ?? th.dimension}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-semibold text-neutral-900">{th.threshold_value}</span>
                    </td>
                    <td className="px-4 py-3">
                      <ThresholdSlider
                        value={th.threshold_value}
                        onSave={(val) => void handleSaveThreshold(th.id, val)}
                        disabled={actionLoading}
                      />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        disabled={actionLoading}
                        onClick={() => void handleSaveThreshold(th.id, th.threshold_value)}
                        className="rounded-lg bg-primary px-3 py-1 text-xs font-bold text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                      >
                        保存
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 保存确认弹窗 */}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-solid/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-bold text-neutral-900 mb-2">确认保存</h3>
            <p className="text-sm text-neutral-600 mb-4">
              共 {Object.keys(pendingChanges).length} 条规则将被修改。变更原因：<strong>{changeReason}</strong>
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmOpen(false)}
                className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => void handleSaveAll()}
                disabled={actionLoading}
                className="rounded-xl bg-brand-solid px-4 py-2 text-sm font-bold text-white hover:bg-brand-solid-hover disabled:opacity-50 transition-colors"
              >
                {actionLoading ? '保存中…' : '确认保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 新增规则弹窗 */}
      {newRuleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-solid/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-bold text-neutral-900 mb-4">新增信用分规则</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">规则类型</label>
                <input
                  type="text"
                  value={newRuleType}
                  onChange={(e) => setNewRuleType(e.target.value)}
                  placeholder="如：授权数据加分"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">分值变更</label>
                <input
                  type="number"
                  value={newRuleScore}
                  onChange={(e) => setNewRuleScore(e.target.value)}
                  placeholder="如：10"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button
                onClick={() => setNewRuleModal(false)}
                className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => void handleAddRule()}
                disabled={actionLoading}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {actionLoading ? '添加中…' : '确认添加'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ThresholdSlider({
  value,
  onSave,
  disabled,
}: {
  value: number;
  onSave: (v: number) => void;
  disabled: boolean;
}) {
  const [local, setLocal] = useState(value);

  const pct = Math.min(100, Math.max(0, (local / (value * 2 || 100)) * 100));

  return (
    <div className="flex items-center gap-2">
      <input
        type="range"
        min={0}
        max={value * 2 || 100}
        step={1}
        value={local}
        onChange={(e) => setLocal(parseFloat(e.target.value))}
        className="flex-1 h-1.5 rounded-full appearance-none bg-neutral-200 cursor-pointer"
        style={{ accentColor: '#1a1a1a' }}
      />
      <span className="text-xs font-semibold w-10 text-right">{local}</span>
    </div>
  );
}
