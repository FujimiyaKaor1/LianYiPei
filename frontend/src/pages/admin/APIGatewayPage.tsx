import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  KeyRound,
  Globe,
  Eye,
  EyeOff,
  Plus,
  X,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import {
  apiGateway,
  ExternalInterfaceConfig,
  ApiKey,
} from '@/src/lib/adminApi';
import { useToast } from '@/src/components/ToastProvider';

/** 后端 EXTERNAL_INTERFACES 为扁平字段，与 SPA 的 name/enabled/status/config 对齐 */
function normalizeExternalInterface(raw: Record<string, unknown>): ExternalInterfaceConfig {
  const type = String(raw.interface_type ?? '');
  const config: Record<string, unknown> = {};
  for (const k of [
    'base_url',
    'auth_type',
    'api_key',
    'client_id',
    'client_secret',
    'timeout_seconds',
    'max_retries',
    'field_mapping',
    'is_enabled',
  ] as const) {
    if (raw[k] !== undefined && raw[k] !== null) {
      config[k] = raw[k];
    }
  }
  return {
    interface_type: type,
    name: String(raw.interface_name ?? type),
    enabled: Boolean(raw.is_enabled),
    status: String(raw.last_check_status ?? 'unknown'),
    config,
  };
}

function apiKeyDisplaySecret(k: ApiKey): string {
  const s = (k.key_value || k.key_preview || '').trim();
  return s || '—';
}

export default function APIGatewayPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<'interfaces' | 'keys'>('interfaces');
  const [interfaces, setInterfaces] = useState<ExternalInterfaceConfig[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState<string | null>(null);
  const [configModal, setConfigModal] = useState<ExternalInterfaceConfig | null>(null);
  const [configForm, setConfigForm] = useState<Record<string, string>>({});
  const [keyModal, setKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [iface, keys] = await Promise.all([
        apiGateway.listInterfaces(),
        apiGateway.listApiKeys(),
      ]);
      const rawList = (iface.data ?? []) as unknown[];
      setInterfaces(
        rawList
          .filter((x): x is Record<string, unknown> => x !== null && typeof x === 'object')
          .map((row) => normalizeExternalInterface(row)),
      );
      setApiKeys(keys.api_keys ?? []);
    } catch {
      showToast('加载失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { void fetchData(); }, [fetchData]);

  const handleCheck = async (type: string) => {
    setChecking(type);
    try {
      const r = await apiGateway.checkInterface(type);
      if ((r as { success?: boolean }).success) {
        showToast(`${type} 连接正常`, 'success');
      } else {
        showToast((r as { error?: string }).error || `${type} 连接失败`, 'error');
      }
    } catch {
      showToast(`${type} 连接失败`, 'error');
    } finally {
      setChecking(null);
    }
  };

  const handleCheckAll = async () => {
    setChecking('all');
    try {
      await apiGateway.checkAllInterfaces();
      showToast('全部接口检查完成', 'success');
      void fetchData();
    } catch {
      showToast('检查失败', 'error');
    } finally {
      setChecking(null);
    }
  };

  const openConfig = (iface: ExternalInterfaceConfig) => {
    setConfigModal(iface);
    const c = iface.config as Record<string, unknown>;
    const str: Record<string, string> = {};
    Object.entries(c).forEach(([k, v]) => {
      if (v === null || v === undefined) str[k] = '';
      else if (typeof v === 'object') str[k] = JSON.stringify(v);
      else str[k] = String(v);
    });
    setConfigForm(str);
  };

  const handleSaveConfig = async () => {
    if (!configModal) return;
    setActionLoading(true);
    try {
      const payload: Record<string, unknown> = { ...configForm };
      const ts = payload.timeout_seconds;
      const mr = payload.max_retries;
      if (ts !== undefined && ts !== '') {
        const n = parseInt(String(ts), 10);
        if (!Number.isNaN(n)) payload.timeout_seconds = n;
      }
      if (mr !== undefined && mr !== '') {
        const n = parseInt(String(mr), 10);
        if (!Number.isNaN(n)) payload.max_retries = n;
      }
      const r = await apiGateway.updateInterface(configModal.interface_type, payload);
      if ((r as { success?: boolean }).success) {
        showToast('配置已保存', 'success');
        setConfigModal(null);
        void fetchData();
      } else {
        showToast((r as { message?: string }).message || '保存失败', 'error');
      }
    } catch {
      showToast('保存失败', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      showToast('请输入 Key 名称', 'warning');
      return;
    }
    setActionLoading(true);
    try {
      const r = await apiGateway.createApiKey(newKeyName.trim()) as { success?: boolean; key_value?: string; error?: string };
      if (r.success) {
        setCreatedKey(r.key_value ?? null);
        showToast('API Key 已生成', 'success');
        void fetchData();
      } else {
        showToast(r.error || '创建失败', 'error');
      }
    } catch {
      showToast('创建失败', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisableKey = async (id: number) => {
    try {
      const r = await apiGateway.disableApiKey(id);
      if ((r as { success?: boolean }).success) {
        showToast('Key 已禁用', 'success');
        void fetchData();
      } else {
        showToast((r as { error?: string }).error || '操作失败', 'error');
      }
    } catch {
      showToast('操作失败', 'error');
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
      {/* Tab */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {[
            { key: 'interfaces', label: '外部数据源', icon: Globe },
            { key: 'keys', label: 'API Key 管理', icon: KeyRound },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key as 'interfaces' | 'keys')}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
                tab === t.key
                  ? 'bg-neutral-900 text-white'
                  : 'bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
              }`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'interfaces' && (
          <button
            onClick={() => void handleCheckAll()}
            disabled={checking === 'all'}
            className="flex items-center gap-2 rounded-xl border border-neutral-200 bg-white px-4 py-2 text-xs font-medium text-neutral-600 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${checking === 'all' ? 'animate-spin' : ''}`} />
            {checking === 'all' ? '检查中…' : '检查全部'}
          </button>
        )}
      </div>

      {/* 外部数据源 */}
      {tab === 'interfaces' && (
        <div className="space-y-4">
          {interfaces.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-neutral-300 bg-white p-12 text-center">
              <Globe className="w-8 h-8 text-neutral-300 mx-auto mb-3" />
              <p className="text-sm text-neutral-500">暂无外部接口配置</p>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {interfaces.map((iface) => (
                <div key={iface.interface_type} className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                        iface.status === 'ok' || iface.status === 'available'
                          ? 'bg-green-500'
                          : iface.status === 'error'
                          ? 'bg-red-500'
                          : 'bg-neutral-300'
                      }`} />
                      <div>
                        <h3 className="font-bold text-neutral-900">{iface.name || iface.interface_type}</h3>
                        <p className="text-xs text-neutral-400">{iface.interface_type}</p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => void handleCheck(iface.interface_type)}
                        disabled={checking === iface.interface_type}
                        className="rounded-lg p-1.5 hover:bg-neutral-100 text-neutral-400 hover:text-neutral-700 disabled:opacity-50 transition-colors"
                        title="测试连接"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${checking === iface.interface_type ? 'animate-spin' : ''}`} />
                      </button>
                      <button
                        onClick={() => openConfig(iface)}
                        className="rounded-lg p-1.5 hover:bg-neutral-100 text-neutral-400 hover:text-neutral-700 transition-colors"
                        title="配置"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-neutral-500">状态</span>
                      <span className={`font-medium ${
                        iface.status === 'ok' || iface.status === 'available'
                          ? 'text-green-600'
                          : iface.status === 'error'
                          ? 'text-red-500'
                          : 'text-neutral-400'
                      }`}>
                        {iface.status === 'ok' || iface.status === 'available' ? '正常'
                          : iface.status === 'error' ? '异常'
                          : iface.status || '未知'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-neutral-500">启用状态</span>
                      <span className={`font-medium ${iface.enabled ? 'text-green-600' : 'text-neutral-400'}`}>
                        {iface.enabled ? '已启用' : '已禁用'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* API Key 管理 */}
      {tab === 'keys' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => { setKeyModal(true); setCreatedKey(null); setNewKeyName(''); }}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-3 h-3" />
              新建 Key
            </button>
          </div>

          <div className="rounded-2xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 bg-neutral-50/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">Key 名称</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden md:table-cell">Key 值</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide hidden lg:table-cell">创建时间</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">状态</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-neutral-500 uppercase tracking-wide">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {apiKeys.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-neutral-400 text-sm">暂无 API Key</td>
                  </tr>
                ) : (
                  apiKeys.map((key) => (
                    <tr key={key.id} className="hover:bg-neutral-50/50 transition-colors">
                      <td className="px-4 py-3 font-medium text-neutral-800">{key.key_name}</td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <code className="text-xs bg-neutral-100 rounded px-2 py-0.5 font-mono text-neutral-600">
                          {(() => {
                            const s = apiKeyDisplaySecret(key);
                            return s.length > 22 ? `${s.slice(0, 20)}…` : s;
                          })()}
                        </code>
                      </td>
                      <td className="px-4 py-3 text-neutral-400 text-xs hidden lg:table-cell">{key.created_at}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          key.is_active ? 'bg-green-100 text-green-700' : 'bg-neutral-100 text-neutral-500'
                        }`}>
                          {key.is_active ? '启用' : '禁用'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => void handleDisableKey(key.id)}
                          disabled={!key.is_active}
                          className="rounded-lg p-1.5 hover:bg-red-50 text-neutral-400 hover:text-red-500 disabled:opacity-30 transition-colors"
                          title={key.is_active ? '禁用' : '已禁用'}
                        >
                          {key.is_active ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 配置弹窗 */}
      {configModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold text-neutral-900">配置 {configModal.name || configModal.interface_type}</h3>
              <button onClick={() => setConfigModal(null)} className="rounded-full p-1 hover:bg-neutral-100">
                <X className="w-4 h-4 text-neutral-400" />
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(configForm).map(([k, v]) => (
                <div key={k}>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">{k}</label>
                  <input
                    type="text"
                    value={v}
                    onChange={(e) => setConfigForm((prev) => ({ ...prev, [k]: e.target.value }))}
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button
                onClick={() => setConfigModal(null)}
                className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => void handleSaveConfig()}
                disabled={actionLoading}
                className="rounded-xl bg-neutral-900 px-4 py-2 text-sm font-bold text-white hover:bg-neutral-800 disabled:opacity-50 transition-colors"
              >
                {actionLoading ? '保存中…' : '保存配置'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 新建 Key 弹窗 */}
      {keyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            {createdKey ? (
              <>
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <h3 className="text-base font-bold text-neutral-900">Key 已生成</h3>
                </div>
                <div className="rounded-xl bg-neutral-900 p-4 break-all">
                  <p className="text-xs text-neutral-400 mb-1">API Key（请妥善保管，仅显示一次）</p>
                  <p className="text-sm font-mono text-green-400">{createdKey}</p>
                </div>
                <div className="flex justify-end mt-5">
                  <button
                    onClick={() => { setKeyModal(false); setCreatedKey(null); setNewKeyName(''); }}
                    className="rounded-xl bg-neutral-900 px-4 py-2 text-sm font-bold text-white hover:bg-neutral-800 transition-colors"
                  >
                    完成
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-bold text-neutral-900">新建 API Key</h3>
                  <button onClick={() => setKeyModal(false)} className="rounded-full p-1 hover:bg-neutral-100">
                    <X className="w-4 h-4 text-neutral-400" />
                  </button>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Key 名称</label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="如：银行接口专用 Key"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  />
                </div>
                <div className="flex justify-end gap-3 mt-5">
                  <button
                    onClick={() => setKeyModal(false)}
                    className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-50 transition-colors"
                  >
                    取消
                  </button>
                  <button
                    onClick={() => void handleCreateKey()}
                    disabled={actionLoading}
                    className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {actionLoading ? '生成中…' : '生成'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
