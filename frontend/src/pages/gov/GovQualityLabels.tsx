import React, { useState, useEffect } from 'react';
import {
  Award, BadgeCheck, ShieldCheck, Search, Plus,
  Loader2, RefreshCw, X, CheckCircle2, AlertCircle,
  Building2, CalendarCheck, Hash
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { api, type QualityLabelItem } from '@/src/services/api';

type LabelType = 'green' | 'inspection';

interface GrantFormState {
  type: LabelType;
  enterprise_id: string;
  label_name: string;
  certificate_no: string;
  valid_days: string;
  inspection_notes: string;
}

const defaultForm: GrantFormState = {
  type: 'green',
  enterprise_id: '',
  label_name: '',
  certificate_no: '',
  valid_days: '365',
  inspection_notes: '',
};

export default function GovQualityLabels() {
  const [queryId, setQueryId] = useState('');
  const [labels, setLabels] = useState<QualityLabelItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<GrantFormState>(defaultForm);
  const [grantLoading, setGrantLoading] = useState(false);
  const [grantResult, setGrantResult] = useState<{ success: boolean; message: string } | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResult, setSyncResult] = useState('');
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!queryId) return;
    setLoading(true);
    setSearched(true);
    setLabels([]);
    try {
      const res = await api.getEnterpriseLabels(parseInt(queryId));
      setLabels(res.labels || []);
    } catch {
      setLabels([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGrant = async () => {
    setGrantLoading(true);
    setGrantResult(null);
    try {
      let res;
      if (form.type === 'green') {
        res = await api.grantGreenLabel({
          enterprise_id: parseInt(form.enterprise_id),
          label_name: form.label_name || undefined,
          certificate_no: form.certificate_no || undefined,
          valid_days: form.valid_days ? parseInt(form.valid_days) : undefined,
        });
      } else {
        res = await api.grantInspection({
          enterprise_id: parseInt(form.enterprise_id),
          label_name: form.label_name || undefined,
          certificate_no: form.certificate_no || undefined,
          valid_days: form.valid_days ? parseInt(form.valid_days) : undefined,
          inspection_notes: form.inspection_notes || undefined,
        });
      }
      setGrantResult(res);
    } catch (e: any) {
      setGrantResult({ success: false, message: e?.message || '颁发失败，请检查参数' });
    } finally {
      setGrantLoading(false);
    }
  };

  const handleRevoke = async (labelId: number) => {
    if (!confirm('确认撤销此标签？')) return;
    try {
      await api.revokeLabel(labelId, '政府管理员手动撤销');
      setLabels(prev => prev.filter(l => l.id !== labelId));
    } catch { /* ignore */ }
  };

  const handleSync = async () => {
    if (!queryId) return;
    setSyncLoading(true);
    setSyncResult('');
    try {
      const res = await api.syncThirdPartyRating({ enterprise_id: parseInt(queryId) });
      setSyncResult(res.success ? `同步成功，评级：${res.rating || '已更新'}` : `同步失败：${res.message}`);
    } catch {
      setSyncResult('同步失败，请检查网络');
    } finally {
      setSyncLoading(false);
    }
  };

  const STATUS_STYLE: Record<string, string> = {
    active: 'bg-brand-solid text-white border-brand-solid shadow-sm',
    expired: 'bg-neutral-100 text-neutral-400 border-neutral-200',
    revoked: 'bg-neutral-50 text-neutral-500 border-neutral-300',
  };
  const STATUS_LABEL: Record<string, string> = { active: '有效', expired: '已过期', revoked: '已撤销' };

  return (
    <div className="max-w-5xl mx-auto space-y-6">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-brand-solid to-brand-deep text-white p-7 rounded-[2rem] relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 p-8 opacity-5"><Award className="w-40 h-40" /></div>
        <div className="flex items-center gap-2 mb-2">
          <Award className="w-4 h-4 text-white/60" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/50">质量标签管理</span>
        </div>
        <h1 className="text-xl font-black tracking-tight mb-1">政府绿标 & 验厂认证管理</h1>
        <p className="text-xs text-white/50 max-w-lg">
          政府端核心职责之一是对<strong className="text-white/75">企业端上架产品与履约质量</strong>把关：通过绿标、验厂与第三方评级同步，将合规信号反馈到匹配与预警，降低劣质供应与虚假产能风险。
        </p>
      </motion.div>

      {/* Query Panel */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className="bg-white rounded-2xl border border-neutral-100 shadow-sm p-6"
      >
        <h3 className="text-sm font-bold mb-4">企业标签查询</h3>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              value={queryId}
              onChange={e => setQueryId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && void handleSearch()}
              placeholder="输入企业 ID 查询标签..."
              className="w-full pl-10 pr-4 py-3 bg-neutral-50 border border-neutral-100 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-black focus:border-brand-solid transition-all"
            />
          </div>
          <button
            onClick={() => void handleSearch()}
            disabled={!queryId || loading}
            className="px-5 py-3 bg-brand-solid text-white rounded-xl text-sm font-bold hover:bg-brand-solid-hover transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            查询
          </button>
          <button
            onClick={() => void handleSync()}
            disabled={!queryId || syncLoading}
            className="px-5 py-3 bg-white border border-neutral-200 rounded-xl text-sm font-bold hover:border-brand-solid transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {syncLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            同步第三方
          </button>
        </div>
        {syncResult && (
          <p className={cn('text-xs mt-3 font-medium', syncResult.startsWith('同步成功') ? 'text-black font-bold' : 'text-neutral-500')}>
            {syncResult}
          </p>
        )}

        {/* Label Results */}
        {searched && (
          <div className="mt-5">
            {loading ? (
              <div className="flex items-center justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-neutral-300" /></div>
            ) : labels.length === 0 ? (
              <div className="flex flex-col items-center py-8 text-neutral-400">
                <AlertCircle className="w-6 h-6 mb-2 text-neutral-300" />
                <p className="text-xs">该企业暂无质量标签</p>
              </div>
            ) : (
              <div className="space-y-2">
                {labels.map(label => (
                  <div key={label.id} className="flex items-center gap-4 p-4 bg-neutral-50 rounded-xl">
                    <div className="w-9 h-9 bg-neutral-100 rounded-lg flex items-center justify-center shadow-sm shrink-0">
                      {label.label_type === 'government_green' ? <BadgeCheck className="w-5 h-5 text-black" /> : <ShieldCheck className="w-5 h-5 text-neutral-700" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-bold">{label.label_name}</p>
                        <span className={cn('text-[8px] font-bold px-1.5 py-0.5 rounded border', STATUS_STYLE[label.status] || STATUS_STYLE.active)}>
                          {STATUS_LABEL[label.status] || label.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-neutral-400 mt-0.5">
                        颁发机构：{label.issuer_name} · 有效期至 {label.valid_until}
                      </p>
                    </div>
                    {label.status === 'active' && (
                      <button
                        onClick={() => void handleRevoke(label.id)}
                        className="text-[10px] font-bold text-neutral-500 hover:text-black px-2 py-1 rounded-md hover:bg-neutral-200 transition-all"
                      >
                        撤销
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </motion.div>

      {/* Grant Button */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="flex gap-3"
      >
        <button
          onClick={() => { setForm({ ...defaultForm, type: 'green' }); setShowModal(true); setGrantResult(null); }}
          className="flex items-center gap-2 px-5 py-3 bg-brand-solid text-white rounded-xl text-sm font-bold hover:bg-brand-solid-hover transition-all shadow-lg shadow-brand-solid/10"
        >
          <BadgeCheck className="w-4 h-4" /> 颁发政府绿标
        </button>
        <button
          onClick={() => { setForm({ ...defaultForm, type: 'inspection' }); setShowModal(true); setGrantResult(null); }}
          className="flex items-center gap-2 px-5 py-3 bg-white border border-neutral-200 rounded-xl text-sm font-bold hover:border-brand-solid transition-all"
        >
          <ShieldCheck className="w-4 h-4" /> 颁发验厂标签
        </button>
      </motion.div>

      {/* Grant Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-brand-solid/50 z-50 flex items-center justify-center p-4"
            onClick={e => e.target === e.currentTarget && setShowModal(false)}
          >
            <motion.div initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-lg"
            >
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-base font-black flex items-center gap-2">
                  {form.type === 'green' ? <BadgeCheck className="w-5 h-5 text-black" /> : <ShieldCheck className="w-5 h-5 text-neutral-700" />}
                  {form.type === 'green' ? '颁发政府绿标' : '颁发验厂标签'}
                </h3>
                <button onClick={() => setShowModal(false)}><X className="w-5 h-5 text-neutral-400 hover:text-black" /></button>
              </div>

              <div className="space-y-4 mb-5">
                {[
                  { key: 'enterprise_id', label: '企业 ID', icon: Building2, placeholder: '输入目标企业 ID' },
                  { key: 'label_name', label: '标签名称（可选）', icon: Award, placeholder: form.type === 'green' ? '政府绿色认证' : '链主验厂通过' },
                  { key: 'certificate_no', label: '证书编号（可选）', icon: Hash, placeholder: '如：CERT-2024-00001' },
                  { key: 'valid_days', label: '有效天数', icon: CalendarCheck, placeholder: '365' },
                ].map(f => (
                  <div key={f.key} className="space-y-1.5">
                    <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">{f.label}</label>
                    <div className="relative">
                      <f.icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                      <input
                        value={(form as any)[f.key]}
                        onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                        placeholder={f.placeholder}
                        className="w-full pl-10 pr-4 py-3 bg-neutral-50 border border-neutral-100 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-black focus:border-brand-solid transition-all"
                      />
                    </div>
                  </div>
                ))}
                {form.type === 'inspection' && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">验厂备注（可选）</label>
                    <textarea
                      value={form.inspection_notes}
                      onChange={e => setForm(prev => ({ ...prev, inspection_notes: e.target.value }))}
                      placeholder="验厂情况说明..."
                      rows={3}
                      className="w-full px-4 py-3 bg-neutral-50 border border-neutral-100 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-black focus:border-brand-solid transition-all resize-none"
                    />
                  </div>
                )}
              </div>

              {/* Grant Result */}
              <AnimatePresence>
                {grantResult && (
                  <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    className={cn('mb-4 p-3 rounded-xl text-xs font-bold flex items-center gap-2 border', grantResult.success ? 'bg-neutral-100 border-neutral-300 text-black' : 'bg-neutral-50 border-neutral-200 text-neutral-500')}
                  >
                    {grantResult.success ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                    {grantResult.message}
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                onClick={() => void handleGrant()}
                disabled={!form.enterprise_id || grantLoading}
                className="w-full py-3 bg-brand-solid text-white rounded-xl text-sm font-bold hover:bg-brand-solid-hover transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {grantLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BadgeCheck className="w-4 h-4" />}
                确认颁发
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
