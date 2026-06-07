import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  CheckCircle,
  XCircle,
  RotateCcw,
  Eye,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import {
  apiVerification,
  VerificationItem,
  VerificationPage as VerificationPageData,
  VerificationStats,
  VerificationDetail,
} from '@/src/lib/adminApi';
import { useToast } from '@/src/components/ToastProvider';

type StatusFilter = 'pending' | 'approved' | 'rejected' | 'all';

export default function VerificationPage() {
  const { showToast } = useToast();
  const [data, setData] = useState<VerificationPageData | null>(null);
  const [stats, setStats] = useState<VerificationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<StatusFilter>('pending');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<VerificationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rejectModal, setRejectModal] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchList = useCallback(
    async (page = 1) => {
      setLoading(true);
      try {
        const [d, s] = await Promise.all([
          apiVerification.list({ status: filter, page, per_page: 20 }),
          apiVerification.stats(),
        ]);
        setData(d ?? { items: [], total: 0, page: 1, per_page: 20, pages: 0 });
        setStats(s ?? { total: 0, pending: 0, approved: 0, rejected: 0 });
      } catch {
        showToast('加载失败', 'error');
        setData(null);
        setStats(null);
      } finally {
        setLoading(false);
      }
    },
    [filter, showToast],
  );

  useEffect(() => { void fetchList(); }, [fetchList]);

  const fetchDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const d = await apiVerification.detail(id);
      setDetail(d);
    } catch {
      showToast('详情加载失败', 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRowClick = (item: VerificationItem) => {
    setSelectedId(item.id);
    void fetchDetail(item.id);
  };

  const handleApprove = async (id: number) => {
    setActionLoading(id);
    try {
      const r = await apiVerification.approve(id);
      if ((r as { success?: boolean }).success) {
        showToast('已通过审核', 'success');
        void fetchList(data?.page ?? 1);
      } else {
        showToast((r as { error?: string }).error || '操作失败', 'error');
      }
    } catch {
      showToast('操作失败', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async () => {
    if (!rejectModal || !rejectReason.trim()) {
      showToast('请填写驳回原因', 'warning');
      return;
    }
    setActionLoading(rejectModal);
    try {
      const r = await apiVerification.reject(rejectModal, rejectReason.trim());
      if ((r as { success?: boolean }).success) {
        showToast('已驳回申请', 'success');
        setRejectModal(null);
        setRejectReason('');
        void fetchList(data?.page ?? 1);
      } else {
        showToast((r as { error?: string }).error || '操作失败', 'error');
      }
    } catch {
      showToast('操作失败', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReset = async (id: number) => {
    if (!confirm('确定重置该企业审核状态？')) return;
    setActionLoading(id);
    try {
      const r = await apiVerification.reset(id);
      if ((r as { success?: boolean }).success) {
        showToast('已重置为待审核', 'success');
        void fetchList(data?.page ?? 1);
      } else {
        showToast((r as { error?: string }).error || '操作失败', 'error');
      }
    } catch {
      showToast('操作失败', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const statusLabel: Record<StatusFilter, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
    all: '全部',
  };

  const statusColor: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
  };

  return (
    <div className="space-y-5">
      {/* 统计卡片 */}
      <div className="grid gap-4 sm:grid-cols-4">
        {stats && (
          <>
            <StatChip label="全部" value={stats.total} active={filter === 'all'} onClick={() => setFilter('all')} />
            <StatChip label="待审核" value={stats.pending} active={filter === 'pending'} color="text-yellow-600" onClick={() => setFilter('pending')} />
            <StatChip label="已通过" value={stats.approved} active={filter === 'approved'} color="text-green-600" onClick={() => setFilter('approved')} />
            <StatChip label="已驳回" value={stats.rejected} active={filter === 'rejected'} color="text-red-600" onClick={() => setFilter('rejected')} />
          </>
        )}
      </div>

      {/* 筛选栏 */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {(['pending', 'approved', 'rejected', 'all'] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === s
                  ? 'bg-neutral-900 text-white'
                  : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
              }`}
            >
              {statusLabel[s]}
            </button>
          ))}
        </div>
        <button
          onClick={() => void fetchList()}
          className="flex items-center gap-1.5 rounded-xl border border-neutral-200 bg-white px-3 py-1.5 text-xs font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          刷新
        </button>
      </div>

      {/* 列表 */}
      <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">企业名称</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden md:table-cell">联系人</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden lg:table-cell">注册地址</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">状态</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden sm:table-cell">注册时间</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-neutral-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
                    加载中…
                  </td>
                </tr>
              ) : data?.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-neutral-400 text-sm">暂无数据</td>
                </tr>
              ) : (
                data?.items.map((item) => (
                  <tr
                    key={item.id}
                    className={`hover:bg-neutral-50 transition-colors cursor-pointer ${selectedId === item.id ? 'bg-blue-50/50' : ''}`}
                    onClick={() => handleRowClick(item)}
                  >
                    <td className="px-4 py-3">
                      <span className="font-semibold text-neutral-900">{item.name}</span>
                      <p className="text-xs text-neutral-400 md:hidden">{item.contact}</p>
                    </td>
                    <td className="px-4 py-3 text-neutral-600 hidden md:table-cell">{item.contact}</td>
                    <td className="px-4 py-3 text-neutral-500 text-xs max-w-[200px] truncate hidden lg:table-cell">{item.address || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor[item.verification_status]}`}>
                        {statusLabel[item.verification_status as keyof typeof statusLabel] ?? item.verification_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-neutral-400 text-xs hidden sm:table-cell">{item.registered_at}</td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleRowClick(item)}
                          title="查看详情"
                          className="rounded-lg p-1.5 hover:bg-neutral-100 text-neutral-400 hover:text-neutral-700 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {item.verification_status === 'pending' && (
                          <button
                            onClick={() => handleApprove(item.id)}
                            disabled={actionLoading === item.id}
                            title="通过"
                            className="rounded-lg p-1.5 hover:bg-green-50 text-neutral-400 hover:text-green-600 disabled:opacity-50 transition-colors"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {item.verification_status === 'pending' && (
                          <button
                            onClick={() => setRejectModal(item.id)}
                            title="驳回"
                            className="rounded-lg p-1.5 hover:bg-red-50 text-neutral-400 hover:text-red-500 transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {item.verification_status !== 'pending' && (
                          <button
                            onClick={() => handleReset(item.id)}
                            disabled={actionLoading === item.id}
                            title="重置"
                            className="rounded-lg p-1.5 hover:bg-yellow-50 text-neutral-400 hover:text-yellow-600 disabled:opacity-50 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 分页 */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-neutral-100">
            <span className="text-xs text-neutral-400">
              第 {data.page} / {data.pages} 页，共 {data.total} 条
            </span>
            <div className="flex gap-2">
              <button
                disabled={data.page <= 1}
                onClick={() => void fetchList(data.page - 1)}
                className="flex items-center gap-1 rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium hover:bg-neutral-50 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-3 h-3" />
                上一页
              </button>
              <button
                disabled={data.page >= data.pages}
                onClick={() => void fetchList(data.page + 1)}
                className="flex items-center gap-1 rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium hover:bg-neutral-50 disabled:opacity-30 transition-colors"
              >
                下一页
                <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 详情抽屉 */}
      {selectedId && (
        <DetailDrawer
          detail={detail}
          loading={detailLoading}
          onClose={() => { setSelectedId(null); setDetail(null); }}
        />
      )}

      {/* 驳回弹窗 */}
      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-neutral-900">驳回原因</h3>
              <button
                onClick={() => { setRejectModal(null); setRejectReason(''); }}
                className="rounded-full p-1 hover:bg-neutral-100"
              >
                <X className="w-4 h-4 text-neutral-400" />
              </button>
            </div>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="请输入驳回原因（如：营业执照模糊、信息不完整）"
              rows={4}
              className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-shadow resize-none"
            />
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => { setRejectModal(null); setRejectReason(''); }}
                className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => void handleReject()}
                disabled={actionLoading === rejectModal}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {actionLoading === rejectModal ? '提交中…' : '确认驳回'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatChip({
  label,
  value,
  active,
  color,
  onClick,
}: {
  label: string;
  value: number;
  active: boolean;
  color?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-2xl border p-4 text-left transition-all ${
        active
          ? 'border-neutral-900 bg-neutral-900 text-white shadow-md'
          : 'border-neutral-200 bg-white hover:border-neutral-300'
      }`}
    >
      <p className={`text-xs ${active ? 'text-neutral-300' : 'text-neutral-500'}`}>{label}</p>
      <p className={`text-2xl font-black mt-1 ${active ? 'text-white' : color ?? 'text-neutral-900'}`}>{value}</p>
    </button>
  );
}

function DetailDrawer({
  detail,
  loading,
  onClose,
}: {
  detail: VerificationDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-md bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
          <h3 className="text-base font-bold text-neutral-900">企业详情</h3>
          <button onClick={onClose} className="rounded-full p-1 hover:bg-neutral-100">
            <X className="w-4 h-4 text-neutral-400" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex justify-center py-12">
              <RefreshCw className="w-5 h-5 animate-spin text-neutral-400" />
            </div>
          ) : detail ? (
            <div className="space-y-4">
              <InfoRow label="企业名称" value={detail.name} />
              <InfoRow label="联系电话" value={detail.phone} />
              <InfoRow label="联系人" value={detail.contact} />
              <InfoRow label="地址" value={detail.address} />
              <InfoRow label="注册资本" value={detail.registered_capital != null ? `${detail.registered_capital} 万元` : '—'} />
              <InfoRow label="信用评分" value={detail.credit_score?.toString() ?? '—'} />
              <InfoRow label="业务范围" value={detail.business_scope || '—'} />
              <InfoRow label="注册时间" value={detail.registered_at} />
              <InfoRow label="审核状态" value={detail.verification_status} />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-neutral-400 uppercase tracking-wide">{label}</span>
      <span className="text-sm text-neutral-800">{value || '—'}</span>
    </div>
  );
}
