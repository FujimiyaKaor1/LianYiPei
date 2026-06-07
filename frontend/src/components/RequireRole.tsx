import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';
import type { SessionRole } from '@/src/lib/rbac';
import { redirectPathForUnauthorizedRole } from '@/src/lib/rbac';

export function RequireRole({ allow }: { allow: SessionRole[] }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F5F5F7] text-neutral-500 text-sm">
        加载中…
      </div>
    );
  }

  if (!user) {
    // 与 RequireAuth 配合：未登录时不再渲染 null（否则侧栏/布局下主区域全白）
    return <Navigate to="/" replace />;
  }

  if (!allow.includes(user.role as SessionRole)) {
    return <Navigate to={redirectPathForUnauthorizedRole(user.role)} replace />;
  }

  return <Outlet />;
}
