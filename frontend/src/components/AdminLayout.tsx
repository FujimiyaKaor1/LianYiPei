import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  UserCheck,
  SlidersHorizontal,
  ShieldAlert,
  KeyRound,
  ScrollText,
  Monitor,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { TopBar } from './TopBar';
import { BrandLogo } from './BrandLogo';

const adminNavItems = [
  { icon: LayoutDashboard, label: '管理首页', path: '/admin/dashboard' },
  { icon: Monitor, label: '控制台大屏', path: '/admin/dashboard/overview' },
  { icon: UserCheck, label: '入驻审核', path: '/admin/dashboard/onboarding' },
  { icon: SlidersHorizontal, label: '规则配置', path: '/admin/dashboard/rules' },
  { icon: ShieldAlert, label: '风控中心', path: '/admin/dashboard/risk' },
  { icon: KeyRound, label: 'API管理', path: '/admin/dashboard/api-management' },
  { icon: ScrollText, label: '审计日志', path: '/admin/dashboard/audit' },
];

export function AdminLayout() {
  const location = useLocation();
  const { user, loading, setIsLoginModalOpen } = useAuth();
  const displayName = user?.enterpriseName?.trim() || '未登录';
  const initial = displayName !== '未登录' ? displayName.slice(0, 1) : '?';
  const isGov = user?.role === 'government';
  const roleLabel = isGov ? '政府监管' : '平台管理员';

  const getTitle = (path: string) => {
    if (path === '/admin/dashboard' || path === '/admin/dashboard/') return '管理控制台';
    if (path.includes('/overview')) return '控制台大屏';
    if (path.includes('/onboarding')) return '入驻审核';
    if (path.includes('/rules')) return '规则配置';
    if (path.includes('/risk')) return '风控中心';
    if (path.includes('/api-management')) return 'API管理';
    if (path.includes('/audit')) return '审计日志';
    return '管理后台';
  };

  return (
    <div className="app-shell flex min-h-screen w-full">
      <aside className="sidebar-width sticky top-0 flex h-screen flex-shrink-0 flex-col border-r border-white/10 bg-sidebar-bg text-sidebar-text">
        <div className="sidebar-logo-row flex h-[72px] flex-shrink-0 items-center gap-3 border-b border-sidebar-divider px-5">
          <BrandLogo sidebar subtitle="平台管理控制台" />
        </div>

        <nav className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {adminNavItems.map((item) => (
            <NavLink
              key={item.path + item.label}
              to={item.path}
              end={item.path === '/admin/dashboard'}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-150',
                  isActive
                    ? 'bg-sidebar-item-active text-sidebar-text-active font-semibold shadow-elevation-1'
                    : 'text-sidebar-text hover:bg-sidebar-item-hover hover:text-sidebar-text-active',
                )
              }
            >
              <item.icon className="h-4.5 w-4.5" />
              <span className="sidebar-nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flex-shrink-0 border-t border-sidebar-divider p-3">
          <button
            type="button"
            onClick={() => !user && !loading && setIsLoginModalOpen(true)}
            className="sidebar-account-button flex w-full items-center gap-3 rounded-md border border-sidebar-divider bg-sidebar-panel/70 px-3 py-2.5 text-left transition-colors hover:bg-sidebar-panel"
            disabled={loading}
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-sm font-bold text-white">
              {loading ? '…' : initial}
            </div>
            <div className="sidebar-user-copy min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-sidebar-text-active">{loading ? '加载中…' : displayName}</div>
              <div className="text-[10px] text-sidebar-text">{roleLabel}</div>
            </div>
          </button>
        </div>
      </aside>

      <main className="flex min-h-screen min-w-0 flex-1 flex-col">
        <TopBar title={getTitle(location.pathname)} />
        <div data-scroll-root className="min-h-0 w-full flex-1 overflow-auto p-4 pb-12 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
