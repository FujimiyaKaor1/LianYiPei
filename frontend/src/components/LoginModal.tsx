import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { FileUp, X } from 'lucide-react';
import { useAuth } from '@/src/context/AuthContext';
import { canRoleAccessPath, loginHomePathForRole } from '@/src/lib/rbac';
import { cn } from '@/src/lib/utils';
import { BrandLogo } from './BrandLogo';

type ModalMode = 'login' | 'register';

export function LoginModal() {
  const navigate = useNavigate();
  const { isLoginModalOpen, pendingLoginPath, setIsLoginModalOpen, refresh } = useAuth();

  const [mode, setMode] = useState<ModalMode>('login');

  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [regName, setRegName] = useState('');
  const [regAddress, setRegAddress] = useState('');
  const [regProvince, setRegProvince] = useState('');
  const [regCity, setRegCity] = useState('');
  const [regBusinessScope, setRegBusinessScope] = useState('');
  const [regIndustryCode, setRegIndustryCode] = useState('');
  const [regRegisteredCapital, setRegRegisteredCapital] = useState('');
  const [regContact, setRegContact] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regLongitude, setRegLongitude] = useState('');
  const [regLatitude, setRegLatitude] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regPassword2, setRegPassword2] = useState('');
  const [regCreditCode, setRegCreditCode] = useState('');
  const [regLegalRepresentative, setRegLegalRepresentative] = useState('');
  const [materialStatus, setMaterialStatus] = useState('');
  const [registrationMaterialFile, setRegistrationMaterialFile] = useState<File | null>(null);
  const [registrationMaterialReady, setRegistrationMaterialReady] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null);

  const handleClose = () => {
    setIsLoginModalOpen(false);
  };

  const resetRegisterForm = () => {
    setRegName('');
    setRegAddress('');
    setRegProvince('');
    setRegCity('');
    setRegBusinessScope('');
    setRegIndustryCode('');
    setRegRegisteredCapital('');
    setRegContact('');
    setRegPhone('');
    setRegLongitude('');
    setRegLatitude('');
    setRegPassword('');
    setRegPassword2('');
    setRegCreditCode('');
    setRegLegalRepresentative('');
    setMaterialStatus('');
    setRegistrationMaterialFile(null);
    setRegistrationMaterialReady(false);
    setRegisterSuccess(null);
    setError(null);
  };

  const handleRegistrationMaterial = async (file: File) => {
    setSubmitting(true); setError(null); setMaterialStatus('正在识别营业执照…');
    try {
      const body = new FormData(); body.set('file', file);
      const response = await fetch('/auth/register/preview-material', { method: 'POST', body });
      const payload = await response.json().catch(() => null) as { ok?: boolean; error?: string; draft?: { fields?: Record<string, { value?: unknown }>; clarifying_questions?: string[] } } | null;
      if (!response.ok || !payload?.ok || !payload.draft) throw new Error(payload?.error || '营业执照识别失败');
      const fields = payload.draft.fields || {};
      const value = (key: string) => fields[key]?.value;
      if (typeof value('name') === 'string') setRegName(String(value('name')));
      if (typeof value('address') === 'string') {
        const address = String(value('address')); setRegAddress(address);
        const region = address.match(/^(.+?省)?(.+?市)/); if (region) { setRegProvince((region[1] || '').replace(/省$/, '')); setRegCity((region[2] || '').replace(/市$/, '')); }
      }
      if (typeof value('business_scope') === 'string') setRegBusinessScope(String(value('business_scope')));
      if (typeof value('registered_capital') === 'number') setRegRegisteredCapital(String(value('registered_capital')));
      if (typeof value('unified_social_credit_code') === 'string') setRegCreditCode(String(value('unified_social_credit_code')));
      if (typeof value('legal_representative') === 'string') setRegLegalRepresentative(String(value('legal_representative')));
      const ready = !payload.draft.clarifying_questions?.length;
      setRegistrationMaterialFile(file);
      setRegistrationMaterialReady(ready);
      setMaterialStatus(ready ? '已从营业执照自动填报，请核对后点击“确认材料并提交申请”。' : `已自动填报；还需确认：${payload.draft.clarifying_questions?.join('、')}`);
    } catch (err) { setError(err instanceof Error ? err.message : '营业执照识别失败'); setMaterialStatus(''); }
    finally { setSubmitting(false); }
  };

  const handleSubmitMaterialRegistration = async () => {
    if (!registrationMaterialFile || !registrationMaterialReady) {
      setError('请先上传一份字段完整的营业执照材料');
      return;
    }
    if (regPassword.length < 6 || regPassword !== regPassword2) {
      setError('请设置至少 6 位密码，并确认两次输入一致');
      return;
    }
    setError(null); setRegisterSuccess(null); setSubmitting(true);
    try {
      const body = new FormData();
      body.set('file', registrationMaterialFile);
      body.set('password', regPassword);
      body.set('password2', regPassword2);
      body.set('confirm', 'true');
      const response = await fetch('/auth/register/submit-material', { method: 'POST', credentials: 'include', body });
      const payload = (await response.json().catch(() => null)) as { ok?: boolean; error?: string; message?: string } | null;
      if (!response.ok || !payload?.ok) throw new Error(payload?.error || '入驻申请提交失败');
      setRegisterSuccess(payload.message || '入驻申请已提交，等待管理员审核。');
      setRegistrationMaterialFile(null); setRegistrationMaterialReady(false); setMaterialStatus('');
      setRegPassword(''); setRegPassword2('');
    } catch (err) { setError(err instanceof Error ? err.message : '入驻申请提交失败'); }
    finally { setSubmitting(false); }
  };

  const handleSubmitLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body = new FormData();
      body.set('name', name.trim());
      body.set('password', password);

      const response = await fetch('/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-Login-Modal': '1' },
        body,
      });

      const payload = (await response.json().catch(() => null)) as
        | { ok?: boolean; error?: string; redirect?: string; role?: string }
        | null;

      if (!response.ok || !payload?.ok) {
        setError(
          (payload && typeof payload.error === 'string' && payload.error) ||
            '登录失败，请检查企业名称与密码',
        );
        return;
      }

      setName('');
      setPassword('');
      await refresh();

      const fromPending =
        pendingLoginPath && canRoleAccessPath(payload.role, pendingLoginPath);
      const fromRedirect =
        typeof payload.redirect === 'string' && payload.redirect.startsWith('/');
      const target = fromPending
        ? pendingLoginPath
        : fromRedirect
        ? payload.redirect!
        : loginHomePathForRole(payload.role);

      setIsLoginModalOpen(false);
      void navigate(target, { replace: true });
    } catch {
      setError('无法连接服务器，请确认后端已启动');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setRegisterSuccess(null);
    setSubmitting(true);
    try {
      const body = new FormData();
      body.set('name', regName.trim());
      body.set('address', regAddress.trim());
      body.set('province', regProvince.trim());
      body.set('city', regCity.trim());
      body.set('business_scope', regBusinessScope.trim());
      body.set('industry_code', regIndustryCode.trim());
      body.set('registered_capital', regRegisteredCapital.trim());
      body.set('contact', regContact.trim());
      body.set('phone', regPhone.trim());
      body.set('longitude', regLongitude.trim());
      body.set('latitude', regLatitude.trim());
      body.set('password', regPassword);
      body.set('password2', regPassword2);
      body.set('unified_social_credit_code', regCreditCode.trim());
      body.set('legal_representative', regLegalRepresentative.trim());

      const response = await fetch('/auth/register', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-Login-Modal': '1' },
        body,
      });

      const payload = (await response.json().catch(() => null)) as
        | { ok?: boolean; error?: string; message?: string }
        | null;

      if (!response.ok || !payload?.ok) {
        setError(
          (payload && typeof payload.error === 'string' && payload.error) || '注册失败，请稍后重试',
        );
        return;
      }

      const msg =
        (payload && typeof payload.message === 'string' && payload.message) ||
        '注册成功，请等待管理员审核。';
      setRegName('');
      setRegAddress('');
      setRegProvince('');
      setRegCity('');
      setRegBusinessScope('');
      setRegIndustryCode('');
      setRegRegisteredCapital('');
      setRegContact('');
      setRegPhone('');
      setRegLongitude('');
      setRegLatitude('');
      setRegPassword('');
      setRegPassword2('');
      setRegCreditCode('');
      setRegLegalRepresentative('');
      setMaterialStatus('');
      setRegistrationMaterialFile(null);
      setRegistrationMaterialReady(false);
      setError(null);
      setRegisterSuccess(msg);
    } catch {
      setError('无法连接服务器，请确认后端已启动');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isLoginModalOpen) return null;

  return createPortal(
    <div className="pointer-events-auto fixed inset-0 z-[1000] flex items-center justify-center bg-brand-deep/55 p-4 backdrop-blur-sm">
      <div
        className={cn(
          'pointer-events-auto relative z-[1001] flex max-h-[min(92vh,720px)] w-full flex-col rounded-md border border-border bg-white shadow-elevation-3 animate-in fade-in zoom-in duration-200',
          mode === 'register' ? 'max-w-lg' : 'max-w-sm',
        )}
      >
        <button
          onClick={handleClose}
          className="absolute right-4 top-4 z-10 rounded-md p-2 text-ink-muted transition-colors hover:bg-surface-subtle hover:text-ink"
          aria-label="关闭"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-8 pb-4 shrink-0">
          <BrandLogo
            subtitle={mode === 'login' ? '供应链经营工作台' : '企业入驻与履约协同'}
            markClassName="h-11 w-11 border-brand/20"
            titleClassName="text-xl font-black text-brand"
            subtitleClassName="text-xs text-ink-muted"
          />
          <h2 className="mt-4 text-lg font-bold text-ink">
            {mode === 'login' ? '用户登录' : '企业注册'}
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            {mode === 'login'
              ? '使用企业名称与账号密码登录'
              : '填写企业信息提交后，将由管理员审核，通过后方可登录'}
          </p>
        </div>

        <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-8 pb-8">
          {mode === 'login' ? (
            <form onSubmit={(e) => void handleSubmitLogin(e)} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-ink-muted">企业名称</label>
                <input
                  type="text"
                  autoComplete="username"
                  className="w-full rounded-md border border-border px-3 py-2 text-sm outline-none transition-shadow focus:border-brand focus:ring-2 focus:ring-brand-soft"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={submitting}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-ink-muted">密码</label>
                <input
                  type="password"
                  autoComplete="current-password"
                  className="w-full rounded-md border border-border px-3 py-2 text-sm outline-none transition-shadow focus:border-brand focus:ring-2 focus:ring-brand-soft"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                  required
                />
              </div>

              {error ? (
                <p className="rounded-md bg-critical-soft px-3 py-2 text-xs text-critical">{error}</p>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="btn-primary w-full disabled:opacity-50"
              >
                {submitting ? '登录中…' : '登录'}
              </button>

              <p className="pt-1 text-center text-xs text-ink-muted">
                还没有账号？{' '}
                <button
                  type="button"
                  className="font-bold text-brand underline-offset-2 hover:underline"
                  onClick={() => {
                    setMode('register');
                    setError(null);
                  }}
                >
                  注册
                </button>
              </p>
            </form>
          ) : registerSuccess ? (
            <div className="space-y-4">
              <p className="text-sm text-blue-800 bg-blue-50 border border-blue-100 rounded-xl px-3 py-3">
                {registerSuccess}
              </p>
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setRegisterSuccess(null);
                }}
                className="w-full rounded-xl bg-primary text-white text-sm font-bold py-2.5 hover:opacity-95"
              >
                返回登录
              </button>
            </div>
          ) : (
            <form onSubmit={(e) => void handleSubmitRegister(e)} className="space-y-3">
              <label className="block cursor-pointer rounded-xl border border-dashed border-primary/40 bg-primary/5 p-3 text-xs text-neutral-700 hover:border-primary">
                <span className="flex items-center gap-2 font-bold text-primary"><FileUp className="h-4 w-4" />上传营业执照自动填报</span>
                <span className="mt-1 block text-[11px] text-neutral-500">支持 PDF、DOCX、PNG、JPG；仅生成草稿，提交前由你核对。</span>
                <input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" className="hidden" disabled={submitting} onChange={event => { const file = event.currentTarget.files?.[0]; if (file) void handleRegistrationMaterial(file); event.currentTarget.value = ''; }} />
              </label>
              {materialStatus && <p className="rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">{materialStatus}</p>}
              {registrationMaterialReady && <button type="button" onClick={() => void handleSubmitMaterialRegistration()} disabled={submitting} className="w-full rounded-xl border border-primary bg-primary/5 px-3 py-2.5 text-sm font-bold text-primary hover:bg-primary/10 disabled:opacity-50">确认材料并提交入驻申请</button>}
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">
                  企业名称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  disabled={submitting}
                  required
                  autoComplete="organization"
                />
              </div>
              {(regCreditCode || regLegalRepresentative) && <div className="grid grid-cols-2 gap-3 rounded-xl bg-neutral-50 p-3"><label><span className="text-[10px] text-neutral-500">统一社会信用代码</span><input value={regCreditCode} onChange={event => setRegCreditCode(event.target.value.toUpperCase())} maxLength={18} className="mt-1 w-full rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-xs font-bold" /></label><label><span className="text-[10px] text-neutral-500">法定代表人</span><input value={regLegalRepresentative} onChange={event => setRegLegalRepresentative(event.target.value)} className="mt-1 w-full rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-xs font-bold" /></label></div>}
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">企业地址</label>
                <input
                  type="text"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  value={regAddress}
                  onChange={(e) => setRegAddress(e.target.value)}
                  disabled={submitting}
                  placeholder="省市区与详细地址"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">省份</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regProvince}
                    onChange={(e) => setRegProvince(e.target.value)}
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">城市</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regCity}
                    onChange={(e) => setRegCity(e.target.value)}
                    disabled={submitting}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">经营范围</label>
                <textarea
                  rows={2}
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none resize-none"
                  value={regBusinessScope}
                  onChange={(e) => setRegBusinessScope(e.target.value)}
                  disabled={submitting}
                  placeholder="主营业务简述"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">行业代码</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regIndustryCode}
                    onChange={(e) => setRegIndustryCode(e.target.value)}
                    disabled={submitting}
                    placeholder="如国标行业编码"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">注册资金（万元）</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regRegisteredCapital}
                    onChange={(e) => setRegRegisteredCapital(e.target.value)}
                    disabled={submitting}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">联系人</label>
                  <input
                    type="text"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regContact}
                    onChange={(e) => setRegContact(e.target.value)}
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">联系电话</label>
                  <input
                    type="tel"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regPhone}
                    onChange={(e) => setRegPhone(e.target.value)}
                    disabled={submitting}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">经度</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regLongitude}
                    onChange={(e) => setRegLongitude(e.target.value)}
                    disabled={submitting}
                    placeholder="选填"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">纬度</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                    value={regLatitude}
                    onChange={(e) => setRegLatitude(e.target.value)}
                    disabled={submitting}
                    placeholder="选填"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">
                  登录密码 <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  disabled={submitting}
                  required
                  minLength={6}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">
                  确认密码 <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                  value={regPassword2}
                  onChange={(e) => setRegPassword2(e.target.value)}
                  disabled={submitting}
                  required
                  minLength={6}
                />
              </div>

              {error ? (
                <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-xl bg-primary text-white text-sm font-bold py-2.5 hover:opacity-95 disabled:opacity-50 transition-opacity"
              >
                {submitting ? '提交中…' : '提交注册（待管理员审核）'}
              </button>

              <p className="text-center text-xs text-neutral-500">
                已有账号？{' '}
                <button
                  type="button"
                  className="font-bold text-primary underline-offset-2 hover:underline"
                  onClick={() => {
                    setMode('login');
                    setError(null);
                    resetRegisterForm();
                  }}
                >
                  返回登录
                </button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
