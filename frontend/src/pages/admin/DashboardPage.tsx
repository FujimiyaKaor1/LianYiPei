import React, { useEffect, useState, useCallback } from 'react';
import {
  Building2,
  PackageSearch,
  AlertTriangle,
  Activity,
  Database,
  Cpu,
  RefreshCw,
  Play,
  Trash2,
  CheckCircle,
} from 'lucide-react';
import { apiDashboard, DashboardStats, SchedulerStatus, DataQuality, Alert } from '@/src/lib/adminApi';
import { useToast } from '@/src/components/ToastProvider';

export default function DashboardPage() {
  const { showToast } = useToast();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [quality, setQuality] = useState<DataQuality | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [demoLoading, setDemoLoading] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, sc, q, a] = await Promise.all([
        apiDashboard.stats(),
        apiDashboard.schedulerStatus(),
        apiDashboard.dataQuality(),
        apiDashboard.alerts(),
      ]);
      setStats(s);
      setScheduler(sc);
      setQuality(q);
      setAlerts(a);
    } catch {
      showToast('数据加载失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const handleGenerateDemo = async () => {
    setDemoLoading(true);
    try {
      const r = await apiDashboard.generateDemo(10);
      if ((r as { success?: boolean }).success) {
        showToast('演示数据已生成', 'success');
        void fetchAll();
      } else {
        showToast((r as { error?: string }).error || '生成失败', 'error');
      }
    } catch {
      showToast('生成失败', 'error');
    } finally {
      setDemoLoading(false);
    }
  };

  const handleClearDemo = async () => {
    if (!confirm('确定清理所有演示数据？')) return;
    try {
      const r = await apiDashboard.clearDemo();
      if ((r as { success?: boolean }).success) {
        showToast(`已清理 ${(r as { deleted?: number }).deleted} 条演示数据`, 'success');
        void fetchAll();
      } else {
        showToast((r as { error?: string }).error || '清理失败', 'error');
      }
    } catch {
      showToast('清理失败', 'error');
    }
  };

  const handleRunAlerts = async () => {
    try {
      const r = await apiDashboard.runAlerts();
      if ((r as { success?: boolean }).success) {
        showToast('预警生成完成', 'success');
        void fetchAll();
      } else {
        showToast((r as { error?: string }).error || '执行失败', 'error');
      }
    } catch {
      showToast('执行失败', 'error');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Building2 className="w-5 h-5 text-blue-600" />}
          label="企业总数"
          value={stats?.enterprise_count ?? '-'}
          color="bg-blue-50"
        />
        <StatCard
          icon={<PackageSearch className="w-5 h-5 text-blue-600" />}
          label="供需发布"
          value={`${stats?.supply_count ?? '-'}/${stats?.demand_count ?? '-'}`}
          sub="供应/需求"
          color="bg-blue-50"
        />
        <StatCard
          icon={<AlertTriangle className="w-5 h-5 text-red-500" />}
          label="活跃预警"
          value={stats?.alert_count ?? '-'}
          color="bg-red-50"
        />
        <StatCard
          icon={<Activity className="w-5 h-5 text-blue-600" />}
          label="交易记录"
          value={stats?.transaction_count ?? '-'}
          color="bg-blue-50"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 数据健康 */}
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-4 h-4 text-neutral-500" />
            <h2 className="text-sm font-bold text-neutral-800">数据健康</h2>
          </div>
          {quality ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">企业总数</span>
                <span className="text-sm font-semibold">{quality.total_enterprises}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">休眠企业</span>
                <span className="text-sm font-semibold">{quality.dormant_count}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">休眠率</span>
                <span className={`text-sm font-semibold ${quality.dormant_rate > 20 ? 'text-red-500' : 'text-blue-600'}`}>
                  {quality.dormant_rate}%
                </span>
              </div>
              <div className="w-full bg-neutral-100 rounded-full h-1.5">
                <div
                  className="h-1.5 rounded-full bg-blue-500 transition-all"
                  style={{ width: `${quality.complete_rate}%` }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">资料完整率</span>
                <span className="text-sm font-semibold">{quality.complete_rate}%</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-neutral-400">暂无数据</p>
          )}
        </div>

        {/* 系统运行状态 */}
        <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-4 h-4 text-neutral-500" />
            <h2 className="text-sm font-bold text-neutral-800">系统运行状态</h2>
          </div>
          {scheduler ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${scheduler.running ? 'bg-blue-500' : 'bg-red-500'}`} />
                <span className="text-sm font-medium">{scheduler.running ? '调度器运行中' : '调度器已停止'}</span>
              </div>
              {scheduler.jobs.map((job) => (
                <div key={job.id} className="flex items-center justify-between text-xs">
                  <span className="text-neutral-600">{job.name}</span>
                  <span className="text-neutral-400">
                    {job.next_run ? `下次: ${job.next_run}` : '未配置'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-neutral-400">暂无数据</p>
          )}
        </div>
      </div>

      {/* 最新预警 */}
      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-neutral-500" />
          <h2 className="text-sm font-bold text-neutral-800">最新预警</h2>
        </div>
        {alerts.length === 0 ? (
          <p className="text-xs text-neutral-400 text-center py-4">暂无预警</p>
        ) : (
          <div className="space-y-2">
            {alerts.slice(0, 6).map((a) => (
              <div key={a.id} className="flex items-center gap-3 text-xs">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  a.level === 'red' ? 'bg-red-500' : a.level === 'yellow' ? 'bg-yellow-400' : 'bg-blue-500'
                }`} />
                <span className="flex-1 text-neutral-700 truncate">{a.message}</span>
                <span className="text-neutral-400 flex-shrink-0">{a.created_at}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 快捷操作 */}
      <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-neutral-500" />
          <h2 className="text-sm font-bold text-neutral-800">快捷操作</h2>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => void handleGenerateDemo()}
            disabled={demoLoading}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Play className="w-3 h-3" />
            {demoLoading ? '生成中…' : '生成演示数据'}
          </button>
          <button
            onClick={() => void handleClearDemo()}
            className="flex items-center gap-2 rounded-xl bg-brand-solid-hover px-4 py-2 text-xs font-bold text-white hover:bg-brand-solid-hover transition-colors"
          >
            <Trash2 className="w-3 h-3" />
            清理演示数据
          </button>
          <button
            onClick={() => void handleRunAlerts()}
            className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-xs font-bold text-white hover:bg-red-700 transition-colors"
          >
            <AlertTriangle className="w-3 h-3" />
            触发预警生成
          </button>
          <button
            onClick={() => void fetchAll()}
            className="flex items-center gap-2 rounded-xl border border-neutral-200 px-4 py-2 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            刷新数据
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl ${color} flex items-center justify-center`}>
          {icon}
        </div>
        <div>
          <p className="text-xs text-neutral-500">{label}</p>
          <p className="text-lg font-bold text-neutral-900">{value}</p>
          {sub && <p className="text-[10px] text-neutral-400">{sub}</p>}
        </div>
      </div>
    </div>
  );
}
