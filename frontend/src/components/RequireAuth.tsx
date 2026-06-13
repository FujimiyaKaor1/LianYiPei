import React, { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';
import { GUEST_HOME_PATH } from '@/src/lib/rbac';

/**
 * 路由守卫：未登录时触发登录弹窗（Cookie 会话由 /api/session 判定）。
 */
export function RequireAuth() {
  const { user, loading, requestLogin } = useAuth();
  const location = useLocation();
  const nextPath = `${location.pathname}${location.search}`;

  useEffect(() => {
    if (!loading && !user) {
      requestLogin(nextPath);
    }
  }, [user, loading, requestLogin, nextPath]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F5F5F7] text-neutral-500 text-sm">
        加载中…
      </div>
    );
  }

  if (!user) {
    return <Navigate to={GUEST_HOME_PATH} replace />;
  }

  return <Outlet />;
}
