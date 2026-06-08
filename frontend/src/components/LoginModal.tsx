import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useAuth } from '@/src/context/AuthContext';
import { loginHomePathForRole } from '@/src/lib/rbac';
import { cn } from '@/src/lib/utils';

type ModalMode = 'login' | 'register';

export function LoginModal() {
  const navigate = useNavigate();
  const { isLoginModalOpen, setIsLoginModalOpen, refresh } = useAuth();

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
    setRegisterSuccess(null);
    setError(null);
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

      const fromRedirect =
        typeof payload.redirect === 'string' && payload.redirect.startsWith('/');
      const target = fromRedirect
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
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 pointer-events-auto">
      <div
        className={cn(
          'relative z-[1001] w-full rounded-2xl bg-white shadow-2xl border border-black/5 animate-in fade-in zoom-in duration-200 pointer-events-auto flex flex-col max-h-[min(92vh,720px)]',
          mode === 'register' ? 'max-w-lg' : 'max-w-sm',
        )}
      >
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-2 text-neutral-400 hover:text-neutral-900 hover:bg-neutral-100 rounded-full transition-colors z-10"
          aria-label="关闭"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-8 pb-4 shrink-0">
          <h1 className="text-xl font-black text-primary tracking-tight">链易配</h1>
          <h2 className="text-lg font-bold text-neutral-900 mt-4">
            {mode === 'login' ? '用户登录' : '企业注册'}
          </h2>
          <p className="text-xs text-neutral-500 mt-1">
            {mode === 'login'
              ? '使用企业名称与账号密码登录'
              : '填写企业信息提交后，将由管理员审核，通过后方可登录'}
          </p>
        </div>

        <div className="px-8 pb-8 flex-1 min-h-0 overflow-y-auto no-scrollbar">
          {mode === 'login' ? (
            <form onSubmit={(e) => void handleSubmitLogin(e)} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">企业名称</label>
                <input
                  type="text"
                  autoComplete="username"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-shadow"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={submitting}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">密码</label>
                <input
                  type="password"
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-neutral-200 px-3 py-2 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none transition-shadow"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={submitting}
                  required
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
                {submitting ? '登录中…' : '登录'}
              </button>

              <p className="text-center text-xs text-neutral-500 pt-1">
                还没有账号？{' '}
                <button
                  type="button"
                  className="font-bold text-primary underline-offset-2 hover:underline"
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
