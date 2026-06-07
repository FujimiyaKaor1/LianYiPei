import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, ScrollText } from 'lucide-react';
import { apiAudit, OperationLog } from '@/src/lib/adminApi';

const SENSITIVE_OPS = new Set([
  'update', 'delete', 'approve', 'reject', 'reset',
  'generate_demo', 'clear_demo', 'disable',
]);

export default function AuditLogPage() {
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiAudit.list();
      setLogs(r.logs ?? []);
      setTotal(r.total ?? 0);
    } catch {
      /* silently fail */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchLogs(); }, [fetchLogs]);

  const formatTime = (t: string) => {
    try {
      return new Date(t).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
    } catch {
      return t;
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-neutral-500" />
          <h2 className="text-sm font-bold text-neutral-800">操作日志</h2>
          {total > 0 && (
            <span className="text-xs text-neutral-400">共 {total} 条记录</span>
          )}
        </div>
        <button
          onClick={() => void fetchLogs()}
          className="flex items-center gap-1.5 rounded-xl border border-neutral-200 bg-white px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <RefreshCw className="w-5 h-5 animate-spin text-neutral-400" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center">
            <ScrollText className="w-8 h-8 text-neutral-200 mx-auto mb-3" />
            <p className="text-sm text-neutral-400">暂无操作日志</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 bg-neutral-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">时间</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作用户</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作类型</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden xl:table-cell">对象</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">详情</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden lg:table-cell">IP地址</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {logs.map((log) => {
                  const isSensitive = SENSITIVE_OPS.has(log.operation.toLowerCase());
                  return (
                    <tr
                      key={log.id}
                      className={`hover:bg-neutral-50/50 transition-colors ${isSensitive ? 'bg-red-50/30' : ''}`}
                    >
                      <td className="px-4 py-3 text-xs text-neutral-400 whitespace-nowrap">
                        {formatTime(log.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-medium text-neutral-800">{log.user_name || `用户 #${log.user_id}`}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          isSensitive
                            ? 'bg-red-100 text-red-700'
                            : 'bg-neutral-100 text-neutral-600'
                        }`}>
                          {log.operation}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-neutral-500 hidden xl:table-cell">
                        {log.target_type}
                        {log.target_id != null ? ` #${log.target_id}` : ''}
                      </td>
                      <td className="px-4 py-3 text-xs text-neutral-600 max-w-[300px] truncate" title={log.details}>
                        {log.details || '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-neutral-400 hidden lg:table-cell">
                        {log.ip_address || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
