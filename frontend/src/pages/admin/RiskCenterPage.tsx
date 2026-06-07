import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  Play,
  RotateCcw,
  ShieldAlert,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import {
  apiRisk,
  CheckConfig,
  CheckStats,
  CheckHistoryItem,
  AbnormalEnterprise,
} from '@/src/lib/adminApi';
import { useToast } from '@/src/components/ToastProvider';

export default function RiskCenterPage() {
  const { showToast } = useToast();
  const [config, setConfig] = useState<CheckConfig | null>(null);
  const [stats, setStats] = useState<CheckStats | null>(null);
  const [history, setHistory] = useState<CheckHistoryItem[]>([]);
  const [abnormal, setAbnormal] = useState<AbnormalEnterprise[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [restoreReason, setRestoreReason] = useState('');
  const [restoreTarget, setRestoreTarget] = useState<number | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [c, s, h, ab] = await Promise.all([
        apiRisk.getConfig(),
        apiRisk.stats(),
        apiRisk.history(30),
        apiRisk.abnormalList(),
      ]);
      setConfig(c);
      setStats(s);
      setHistory(h.history ?? []);
      setAbnormal(ab.items ?? []);
    } catch {
      showToast('加载失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const handleToggleConfig = async (field: 'enabled' | 'auto_delist_enabled') => {
    if (!config) return;
    const updated = { ...config, [field]: !config[field] };
    try {
      await apiRisk.updateConfig({ [field]: updated[field] });
      setConfig(updated);
      showToast('配置已更新', 'success');
    } catch {
      showToast('更新失败', 'error');
    }
  };

  const handleUpdateSampleSize = async (val: number) => {
    if (!config) return;
    try {
      await apiRisk.updateConfig({ sample_size: val });
      setConfig({ ...config, sample_size: val });
      showToast('样本数量已更新', 'success');
    } catch {
      showToast('更新失败', 'error');
    }
  };

  const handleRunCheck = async () => {
    setRunning(true);
    try {
      const r = await apiRisk.runCheck();
      if ((r as { success?: boolean }).success) {
        showToast('抽查执行完成', 'success');
        void fetchAll();
      } else {
        const msg =
          (r as { error?: string }).error ||
          (r as { message?: string }).message ||
          '执行失败';
        showToast(msg, 'error');
      }
    } catch {
      showToast('执行失败', 'error');
    } finally {
      setRunning(false);
    }
  };

  const handleRestore = async () => {
    if (!restoreTarget || !restoreReason.trim()) {
      showToast('请填写恢复原因', 'warning');
      return;
    }
    setRestoring(restoreTarget);
    try {
      const r = await apiRisk.restore(restoreTarget, restoreReason.trim());
      if ((r as { success?: boolean }).success) {
        showToast('已恢复企业状态', 'success');
        setRestoreTarget(null);
        setRestoreReason('');
        void fetchAll();
      } else {
        showToast((r as { error?: string }).error || '恢复失败', 'error');
      }
    } catch {
      showToast('恢复失败', 'error');
    } finally {
      setRestoring(null);
    }
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
      {/* 统计卡片 */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <RiskStatCard icon={<Activity className="w-5 h-5 text-blue-600" />} label="企业总数" value={stats?.total ?? '-'} color="bg-blue-50" />
        <RiskStatCard icon={<CheckCircle className="w-5 h-5 text-green-600" />} label="正常企业" value={stats?.active ?? '-'} color="bg-green-50" />
        <RiskStatCard icon={<XCircle className="w-5 h-5 text-red-500" />} label="异常企业" value={stats?.abnormal ?? '-'} color="bg-red-50" />
        <RiskStatCard icon={<AlertTriangle className="w-5 h-5 text-yellow-500" />} label="休眠企业" value={stats?.dormant ?? '-'} color="bg-yellow-50" />
      </div>

      {/* 抽查配置 */}
      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <ShieldAlert className="w-4 h-4 text-neutral-500" />
          <h2 className="text-sm font-bold text-neutral-800">抽查配置</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex items-center justify-between rounded-xl border border-neutral-100 p-4">
            <div>
              <p className="text-sm font-semibold text-neutral-800">自动抽查</p>
              <p className="text-xs text-neutral-400 mt-0.5">系统随机抽取企业检查经营状态</p>
            </div>
            <button
              onClick={() => void handleToggleConfig('enabled')}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                config?.enabled ? 'bg-green-500' : 'bg-neutral-200'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                config?.enabled ? 'translate-x-6' : ''
              }`} />
            </button>
          </div>

          <div className="flex items-center justify-between rounded-xl border border-neutral-100 p-4">
            <div>
              <p className="text-sm font-semibold text-neutral-800">自动下架</p>
              <p className="text-xs text-neutral-400 mt-0.5">检测到注销/吊销企业时自动下架产品</p>
            </div>
            <button
              onClick={() => void handleToggleConfig('auto_delist_enabled')}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                config?.auto_delist_enabled ? 'bg-green-500' : 'bg-neutral-200'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                config?.auto_delist_enabled ? 'translate-x-6' : ''
              }`} />
            </button>
          </div>

          <div className="flex items-center gap-4 rounded-xl border border-neutral-100 p-4">
            <div className="flex-1">
              <p className="text-sm font-semibold text-neutral-800">每次抽查数量</p>
              <p className="text-xs text-neutral-400 mt-0.5">每次随机抽取检查的企业数量</p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={config?.sample_size ?? 5}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (!isNaN(v) && v > 0) {
                    setConfig((prev) => prev ? { ...prev, sample_size: v } : prev);
                  }
                }}
                className="w-20 rounded-xl border border-neutral-200 px-2 py-1 text-sm text-center focus:ring-1 focus:ring-primary focus:border-primary outline-none"
              />
              <button
                onClick={() => void handleUpdateSampleSize(config?.sample_size ?? 5)}
                className="rounded-lg bg-primary px-3 py-1 text-xs font-bold text-white hover:opacity-90 transition-opacity"
              >
                保存
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-xl border border-neutral-100 p-4">
            <div>
              <p className="text-sm font-semibold text-neutral-800">手动触发</p>
              <p className="text-xs text-neutral-400 mt-0.5">立即执行一次企业抽查（基于工商API）</p>
            </div>
            <button
              onClick={() => void handleRunCheck()}
              disabled={running}
              className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              <Play className="w-3 h-3" />
              {running ? '执行中…' : '立即执行'}
            </button>
          </div>
        </div>
      </div>

      {/* 异常企业列表 */}
      <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-neutral-100">
          <XCircle className="w-4 h-4 text-red-500" />
          <h2 className="text-sm font-bold text-neutral-800">异常企业</h2>
        </div>
        {abnormal.length === 0 ? (
          <p className="text-sm text-neutral-400 text-center py-8">暂无异常企业</p>
        ) : (
          <div className="divide-y divide-neutral-50">
            {abnormal.map((e) => (
              <div key={e.id} className="flex items-center justify-between px-5 py-3 hover:bg-neutral-50 transition-colors">
                <div>
                  <p className="text-sm font-semibold text-neutral-800">{e.name}</p>
                  <p className="text-xs text-neutral-400">
                    {e.business_status} · 检查时间：{e.checked_at}
                  </p>
                </div>
                <button
                  onClick={() => setRestoreTarget(e.id)}
                  className="flex items-center gap-1.5 rounded-lg border border-yellow-300 bg-yellow-50 px-3 py-1.5 text-xs font-medium text-yellow-700 hover:bg-yellow-100 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  恢复
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 抽查历史 */}
      <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-neutral-500" />
            <h2 className="text-sm font-bold text-neutral-800">抽查历史</h2>
          </div>
          <button
            onClick={() => void fetchAll()}
            className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-800 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            刷新
          </button>
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-neutral-400 text-center py-8">暂无抽查记录</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 bg-neutral-50/50">
                  <th className="text-left px-5 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">企业</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">结果</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">详情</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">检查时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {history.map((h) => (
                  <tr key={h.id} className="hover:bg-neutral-50/50 transition-colors">
                    <td className="px-5 py-3 font-medium text-neutral-800">{h.enterprise_name}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        h.result === 'normal' ? 'bg-green-100 text-green-700' :
                        h.result === 'abnormal' ? 'bg-red-100 text-red-700' :
                        'bg-neutral-100 text-neutral-600'
                      }`}>
                        {h.result === 'normal' ? '正常' : h.result === 'abnormal' ? '异常' : h.result}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-neutral-500 max-w-[200px] truncate">{h.details || '—'}</td>
                    <td className="px-5 py-3 text-xs text-neutral-400">{h.check_time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 恢复弹窗 */}
      {restoreTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-bold text-neutral-900 mb-4">恢复企业状态</h3>
            <p className="text-sm text-neutral-600 mb-3">
              确定将该企业恢复为正常经营状态？
            </p>
            <textarea
              value={restoreReason}
              onChange={(e) => setRestoreReason(e.target.value)}
              placeholder="请输入恢复原因（如：企业已提交补充资质证明）"
              rows={3}
              className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none resize-none"
            />
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setRestoreTarget(null); setRestoreReason(''); }}
                className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => void handleRestore()}
                disabled={restoring === restoreTarget}
                className="rounded-xl bg-yellow-600 px-4 py-2 text-sm font-bold text-white hover:bg-yellow-700 disabled:opacity-50 transition-colors"
              >
                {restoring === restoreTarget ? '恢复中…' : '确认恢复'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RiskStatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl ${color} flex items-center justify-center`}>
          {icon}
        </div>
        <div>
          <p className="text-xs text-neutral-500">{label}</p>
          <p className="text-xl font-black text-neutral-900">{value}</p>
        </div>
      </div>
    </div>
  );
}
