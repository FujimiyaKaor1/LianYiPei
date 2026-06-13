import React, { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';
import type { SessionRole } from '@/src/lib/rbac';
import { GUEST_HOME_PATH, redirectPathForUnauthorizedRole } from '@/src/lib/rbac';

export function RequireRole({ allow }: { allow: SessionRole[] }) {
  const { user, loading, requestLogin } = useAuth();
  const location = useLocation();
  const nextPath = `${location.pathname}${location.search}`;

  useEffect(() => {
    if (!loading && !user) {
      requestLogin(nextPath);
    }
  }, [loading, user, requestLogin, nextPath]);

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

  if (!allow.includes(user.role as SessionRole)) {
    return <Navigate to={redirectPathForUnauthorizedRole(user.role)} replace />;
  }

  return <Outlet />;
}
