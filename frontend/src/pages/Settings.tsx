import React, { useEffect, useState } from 'react';
import {
  User,
  Bell,
  Shield,
  Globe,
  ChevronRight,
  LogOut,
  Loader2,
  AlertTriangle,
  Save,
  MessageCircle,
  Send,
} from 'lucide-react';
import { motion } from 'motion/react';
import { cn } from '@/src/lib/utils';
import { useToast } from '@/src/components/ToastProvider';
import { api, ApiError, type UserSettingsData, NETWORK_ERROR_MESSAGE } from '@/src/services/api';
export default function Settings() {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState(0);
  const [data, setData] = useState<UserSettingsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState('');

  // WeChat
  const [wechatPref, setWechatPref] = useState<'all' | 'urgent_only' | 'off'>('all');
  const [wechatSaving, setWechatSaving] = useState(false);
  const [wechatMsg, setWechatMsg] = useState('');
  /** 测试推送：ok=微信成功，warn=仅站内送达，error=请求失败 */
  const [wechatTestFeedback, setWechatTestFeedback] = useState<'ok' | 'warn' | 'error' | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  // 手动绑定 OpenID（Demo 模式）
  const [bindOpenid, setBindOpenid] = useState('ozMV629-Tobt2qzP_wO698vS-HBM');
  const [bindLoading, setBindLoading] = useState(false);
  const [bindMsg, setBindMsg] = useState('');

  // Form State
  const [formData, setFormData] = useState<Partial<UserSettingsData>>({});

  const loadData = async () => {
    setIsLoading(true);
    setErrorText('');
    try {
      const res = await api.getUserSettings();
      setData(res.settings || null);
      setFormData(res.settings || {});
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : NETWORK_ERROR_MESSAGE);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleSave = async () => {
    if (!data) return;
    setIsSaving(true);
    try {
      await api.updateUserSettings(formData);
      showToast('设置已成功保存！', 'success');
      setData(prev => ({ ...prev!, ...formData }));
    } catch (error) {
      showToast(error instanceof Error ? error.message : '保存失败', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveWechat = async () => {
    setWechatSaving(true);
    setWechatMsg('');
    try {
      await api.setWechatPreference(wechatPref);
      setWechatMsg('偏好设置已保存');
    } catch {
      setWechatMsg('保存失败，请重试');
    } finally {
      setWechatSaving(false);
    }
  };

  const handleBindOpenId = async () => {
    if (!bindOpenid.trim()) {
      setBindMsg('请输入 OpenID');
      return;
    }
    setBindLoading(true);
    setBindMsg('');
    try {
      const res = await api.bindWechatOpenId(bindOpenid.trim());
      setBindMsg(res.success ? '绑定成功' : `绑定失败：${res.message}`);
    } catch (e) {
      setBindMsg(e instanceof ApiError ? e.message : '绑定失败，请检查网络或后端是否已重启');
    } finally {
      setBindLoading(false);
    }
  };

  const handleTestPush = async () => {
    setTestLoading(true);
    setWechatMsg('');
    setWechatTestFeedback(null);
    try {
      const res = await api.testWechatPush();
      let msg = res.message || '测试推送已处理';
      if (res.wechat_ok === false && res.wechat_detail) {
        msg = `${msg} ${res.wechat_detail}`;
      }
      if (res.wechat_ok === false) {
        const lines: string[] = [];
        if (res.wechat_config_appid_prefix) {
          lines.push(`当前使用的 AppID（前缀）：${res.wechat_config_appid_prefix}`);
        }
        if (res.wechat_attempted_template_id) {
          lines.push(`本次请求的模板 ID：${res.wechat_attempted_template_id}`);
        }
        if (res.wechat_private_template_ids?.length) {
          lines.push('微信接口登记的模板 ID（请与 .env 中 WECHAT_TEMPLATE_ID 比对）：');
          res.wechat_private_template_ids.forEach((id) => lines.push(`  • ${id}`));
        }
        if (res.wechat_template_list_api_error) {
          lines.push(`拉取模板列表失败：${JSON.stringify(res.wechat_template_list_api_error)}`);
        }
        if (lines.length) {
          msg = `${msg}\n\n${lines.join('\n')}`;
        }
      }
      setWechatMsg(msg);
      if (res.wechat_ok === false)
        setWechatTestFeedback('warn');
      else
        setWechatTestFeedback('ok');
    } catch (e) {
      setWechatMsg(e instanceof ApiError ? e.message : '推送失败，请检查配置与后端日志');
      setWechatTestFeedback('error');
    } finally {
      setTestLoading(false);
    }
  };

  const handleLogout = async () => {
    if (confirm('确定要退出登录吗？')) {
      try {
        await api.logout();
        window.location.href = '/login';
      } catch (err) {
        showToast('退出登录失败，请重试', 'error');
        console.error(err);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-neutral-300">
        <Loader2 className="w-8 h-8 animate-spin mb-4 text-neutral-400" />
      </div>
    );
  }

  if (errorText || !data) {
    return (
      <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-8 text-xs text-red-600 font-medium flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-8 h-8 opacity-80" />
        {errorText || "无法加载企业设置数据"}
        <button onClick={() => void loadData()} className="mt-2 text-white bg-red-500 hover:bg-red-600 px-4 py-2 rounded-lg font-bold">重新加载</button>
      </div>
    );
  }

  const hasChanges = 
    formData.name !== data.name ||
    formData.phone !== data.phone ||
    formData.email !== data.email ||
    formData.business_scope !== data.business_scope;

  return (
    <div className="max-w-5xl mx-auto w-full space-y-12">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
        {/* Sidebar Settings Nav */}
        <div className="col-span-1 lg:col-span-4 space-y-2">
          {[
            { icon: User, label: '个人账户' },
            { icon: Shield, label: '安全与隐私' },
            { icon: Bell, label: '通知偏好（微信）' },
            { icon: Globe, label: '语言与地区' },
          ].map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActiveTab(i)}
              className={cn(
                'w-full flex items-center gap-4 px-6 py-4 rounded-2xl text-sm font-bold transition-all',
                activeTab === i ? 'bg-brand-solid text-white shadow-lg' : 'text-neutral-500 hover:bg-neutral-100',
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </button>
          ))}
          <div className="pt-6 mt-6 border-t border-neutral-100">
            <button 
              onClick={() => void handleLogout()}
              className="w-full flex items-center gap-4 px-6 py-4 rounded-2xl text-sm font-bold text-red-500 transition-all"
            >
              <LogOut className="w-5 h-5" />
              退出登录
            </button>
          </div>
        </div>

        {/* Settings Content */}
        <div className="col-span-1 lg:col-span-8 space-y-10">
          {/* Tab 0: Account */}
          {activeTab === 0 && (
            <section className="space-y-6">
              <h3 className="text-xl font-bold">个人账户设置</h3>
              <div className="bg-white rounded-[2rem] border border-neutral-100 shadow-sm p-8 space-y-8">
                <div className="flex items-center gap-8 pb-8 border-b border-neutral-50">
                  <div className="w-24 h-24 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-400 relative group cursor-pointer font-black text-2xl overflow-hidden shrink-0">
                    {data?.name.slice(0, 1)}
                    <div className="absolute inset-0 bg-brand-solid/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-[10px] font-bold">更换头像</div>
                  </div>
                  <div className="flex-1">
                    <h4 className="text-lg font-bold">{data?.name} · {data?.role === 'buyer' ? '采购商' : data?.role === 'supplier' ? '供应商' : '企业账户'}</h4>
                    <p className="text-xs text-neutral-400 mt-1">{data?.email}</p>
                  </div>
                </div>
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">显示名称</label>
                      <input type="text" value={formData.name || ''} onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                        className="w-full bg-neutral-50 border-none rounded-xl p-4 text-sm font-medium focus:ring-1 focus:ring-black transition-all outline-none" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">联系电话</label>
                      <input type="text" value={formData.phone || ''} onChange={e => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                        className="w-full bg-neutral-50 border-none rounded-xl p-4 text-sm font-medium focus:ring-1 focus:ring-black transition-all outline-none" />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">联系邮箱</label>
                      <input type="text" value={formData.email || ''} onChange={e => setFormData(prev => ({ ...prev, email: e.target.value }))}
                        className="w-full bg-neutral-50 border-none rounded-xl p-4 text-sm font-medium focus:ring-1 focus:ring-black transition-all outline-none" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">企业简介</label>
                    <textarea rows={4} value={formData.business_scope || ''} onChange={e => setFormData(prev => ({ ...prev, business_scope: e.target.value }))}
                      className="w-full bg-neutral-50 border-none rounded-xl p-4 text-sm font-medium focus:ring-1 focus:ring-black transition-all outline-none resize-none leading-relaxed" />
                  </div>
                  {hasChanges && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end pt-4">
                      <button onClick={() => void handleSave()} disabled={isSaving}
                        className="px-6 py-3 bg-brand-solid text-white rounded-xl text-sm font-bold shadow-lg shadow-brand-solid/20 hover:bg-brand-solid-hover hover:-translate-y-0.5 transition-all disabled:opacity-50 flex items-center gap-2">
                        {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        {isSaving ? '正在保存...' : '保存更改'}
                      </button>
                    </motion.div>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* Tab 1: Security */}
          {activeTab === 1 && (
            <section className="space-y-6">
              <h3 className="text-xl font-bold">安全设置</h3>
              <div className="bg-white rounded-[2rem] border border-neutral-100 shadow-sm divide-y divide-neutral-50">
                {[
                  { title: '双重身份验证', desc: '开启后，登录时需要验证码。', status: '已开启', color: 'text-blue-500' },
                  { title: '登录日志', desc: '查看最近的账户登录活动。', status: '查看', color: 'text-black font-bold' },
                  { title: 'API 密钥管理', desc: '管理用于外部集成的 API 密钥。', status: '管理', color: 'text-black font-bold' },
                ].map((item, i) => (
                  <div key={i} className="p-8 flex items-center justify-between hover:bg-neutral-50/50 transition-colors cursor-pointer group">
                    <div>
                      <h4 className="text-sm font-bold">{item.title}</h4>
                      <p className="text-xs text-neutral-400 mt-1">{item.desc}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={cn("text-xs", item.color)}>{item.status}</span>
                      <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-black transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Tab 2: WeChat Notifications */}
          {activeTab === 2 && (
            <section className="space-y-6">
              <h3 className="text-xl font-bold">微信推送设置</h3>
              <div className="bg-white rounded-[2rem] border border-neutral-100 shadow-sm p-8 space-y-6">
                <div className="flex items-start gap-4 pb-6 border-b border-neutral-50">
                  <div className="w-12 h-12 rounded-xl bg-neutral-100 flex items-center justify-center shrink-0">
                    <MessageCircle className="w-6 h-6 text-neutral-600" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold mb-1">微信消息推送</h4>
                    <p className="text-xs text-neutral-400 leading-relaxed">绑定微信账号后，平台将实时推送预警、合作邀请等重要消息。</p>
                  </div>
                </div>

                {/* OpenID 手动绑定区域（Demo 专用） */}
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 space-y-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold text-amber-800">微信测试号绑定（Demo 模式）</span>
                    <span className="text-[10px] bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full font-bold">手动填入 OpenID</span>
                  </div>
                  <p className="text-[11px] text-amber-600 leading-relaxed">
                    在下方输入您的微信 OpenID 并点击「保存绑定」，即可接收来自平台的微信模板消息推送。
                    无需扫码授权，适合 Demo 场景快速验证。请完整复制 OpenID，中间不要有空格（若误粘贴空格，保存时会自动去除）。
                  </p>
                  <div className="flex gap-3 items-start">
                    <div className="flex-1 space-y-1">
                      <label className="text-[10px] font-bold text-amber-700 uppercase tracking-wider">
                        微信测试号 OpenID（Demo 专用）
                      </label>
                      <input
                        type="text"
                        value={bindOpenid}
                        onChange={e => setBindOpenid(e.target.value)}
                        disabled={bindLoading}
                        placeholder="ozMV629-Tobt2qzP_wO698vS-HBM"
                        className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm font-mono focus:ring-2 focus:ring-amber-400 outline-none transition-all disabled:opacity-50"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleBindOpenId()}
                      disabled={bindLoading}
                      className="mt-[22px] shrink-0 flex items-center gap-2 px-5 py-2.5 bg-amber-500 text-white rounded-xl text-sm font-bold hover:bg-amber-600 transition-all disabled:opacity-50"
                    >
                      {bindLoading
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <Save className="w-4 h-4" />}
                      保存绑定
                    </button>
                  </div>
                  {bindMsg && (
                    <p className={cn(
                      'text-xs font-medium px-3 py-2 rounded-lg',
                      bindMsg.includes('成功') ? 'bg-blue-50 text-blue-700 border border-blue-100' : 'bg-red-50 text-red-600 border border-red-100'
                    )}>
                      {bindMsg}
                    </p>
                  )}
                </div>

                {/* Push Preference */}
                <div className="space-y-3">
                  <label className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest">推送偏好</label>
                  {([
                    ['all', '全部消息', '接收所有类型推送（预警、合作邀请、系统通知）'],
                    ['urgent_only', '仅紧急消息', '只接收高危预警级别的推送'],
                    ['off', '关闭推送', '不接收任何微信推送'],
                  ] as ['all' | 'urgent_only' | 'off', string, string][]).map(([val, label, desc]) => (
                    <label key={val} className={cn(
                      'flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-all',
                      wechatPref === val ? 'border-brand-solid bg-neutral-50' : 'border-neutral-100 hover:border-neutral-200',
                    )}>
                      <input type="radio" name="pref" value={val} checked={wechatPref === val} onChange={() => setWechatPref(val)}
                        className="mt-0.5 accent-black shrink-0" />
                      <div>
                        <p className="text-sm font-bold">{label}</p>
                        <p className="text-[11px] text-neutral-400 mt-0.5">{desc}</p>
                      </div>
                    </label>
                  ))}
                </div>

                {wechatMsg && (
                  <p className={cn(
                    'text-xs font-medium whitespace-pre-wrap break-all',
                    wechatTestFeedback === 'error' && 'text-red-500',
                    wechatTestFeedback === 'warn' && 'text-amber-600',
                    wechatTestFeedback === 'ok' && 'text-blue-600',
                    wechatTestFeedback === null && 'text-neutral-600',
                  )}>
                    {wechatMsg}
                  </p>
                )}

                <div className="flex gap-3 pt-2">
                  <button onClick={() => void handleSaveWechat()} disabled={wechatSaving}
                    className="flex items-center gap-2 px-5 py-3 bg-brand-solid text-white rounded-xl text-sm font-bold hover:bg-brand-solid-hover transition-all disabled:opacity-50">
                    {wechatSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    保存偏好
                  </button>
                  <button onClick={() => void handleTestPush()} disabled={testLoading}
                    className="flex items-center gap-2 px-5 py-3 bg-white border border-neutral-200 rounded-xl text-sm font-bold hover:border-brand-solid transition-all disabled:opacity-50">
                    {testLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    发送测试推送
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* Tab 3: Language placeholder */}
          {activeTab === 3 && (
            <section className="space-y-6">
              <h3 className="text-xl font-bold">语言与地区</h3>
              <div className="bg-white rounded-[2rem] border border-neutral-100 shadow-sm p-8">
                <p className="text-sm text-neutral-400">语言设置功能即将上线</p>
              </div>
            </section>
          )}

        </div>
      </div>
    </div>
  );
}
