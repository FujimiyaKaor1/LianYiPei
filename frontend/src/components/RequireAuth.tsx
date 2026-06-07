import React, { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';

/**
 * 路由守卫：未登录时触发登录弹窗（Cookie 会话由 /api/session 判定）。
 */
export function RequireAuth() {
  const { user, loading, setIsLoginModalOpen } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!loading && !user) {
      setIsLoginModalOpen(true);
    }
  }, [user, loading, setIsLoginModalOpen, location.pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F5F5F7] text-neutral-500 text-sm">
        加载中…
      </div>
    );
  }

  // 无论是否登录都渲染 Outlet，未登录时通过 useEffect 打开全局弹窗覆盖在上面
  return <Outlet />;
}
