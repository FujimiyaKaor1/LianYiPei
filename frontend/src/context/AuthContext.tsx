import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  UNAUTHORIZED_EVENT,
  clearAuthSessionStorage,
} from '@/src/lib/authEvents';

export type AuthUser = {
  id: number;
  /** 与数据库 Enterprise.name 一致 */
  name: string;
  enterpriseName: string;
  /** 来自 /api/session：'admin' | 'government' | 'enterprise' */
  role: string;
};

type SessionUserPayload = {
  id: number;
  name?: string;
  enterprise_name?: string;
  role: string;
};

function normalizeUser(u: SessionUserPayload): AuthUser {
  const raw = (u.enterprise_name || u.name || '').trim();
  return {
    id: u.id,
    name: raw,
    enterpriseName: raw,
    role: u.role,
  };
}

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  isLoginModalOpen: boolean;
  setIsLoginModalOpen: (open: boolean) => void;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function AuthProviderInner({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/session', { credentials: 'include' });
      if (!response.ok) {
        setUser(null);
        return;
      }
      const data = (await response.json()) as {
        authenticated?: boolean;
        user?: SessionUserPayload | null;
      };
      if (data.authenticated && data.user?.id != null) {
        setUser(normalizeUser(data.user));
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/logout', { method: 'POST', credentials: 'include' });
    } catch {
      /* 网络失败仍退出前端态 */
    }
    clearAuthSessionStorage();
    setUser(null);
    setIsLoginModalOpen(true);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setIsLoginModalOpen(true);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const value = useMemo(
    () => ({ user, loading, isLoginModalOpen, setIsLoginModalOpen, refresh, logout }),
    [user, loading, isLoginModalOpen, setIsLoginModalOpen, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <AuthProviderInner>{children}</AuthProviderInner>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
