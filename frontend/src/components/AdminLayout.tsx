import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  UserCheck,
  SlidersHorizontal,
  ShieldAlert,
  ScrollText,
  Monitor,
  Newspaper,
  PanelLeftClose,
  PanelLeftOpen,
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
  { icon: ScrollText, label: '审计日志', path: '/admin/dashboard/audit' },
  { icon: Newspaper, label: '行业资讯', path: '/admin/dashboard/news' },
];

export function AdminLayout() {
  const location = useLocation();
  const { user, loading, setIsLoginModalOpen } = useAuth();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const displayName = user?.enterpriseName?.trim() || '未登录';
  const initial = displayName !== '未登录' ? displayName.slice(0, 1) : '?';
  const roleLabel = '平台管理员';

  const getTitle = (path: string) => {
    if (path === '/admin/dashboard' || path === '/admin/dashboard/') return '管理控制台';
    if (path.includes('/overview')) return '控制台大屏';
    if (path.includes('/onboarding')) return '入驻审核';
    if (path.includes('/rules')) return '规则配置';
    if (path.includes('/risk')) return '风控中心';
    if (path.includes('/audit')) return '审计日志';
    if (path.includes('/news')) return '行业资讯';
    return '管理后台';
  };

  return (
    <div className="app-shell flex min-h-screen w-full">
      <aside
        className={cn(
          'sticky top-0 flex h-screen flex-shrink-0 flex-col border-r border-white/10 bg-sidebar-bg text-sidebar-text transition-[width] duration-200',
          isSidebarCollapsed ? 'sidebar-collapsed-width sidebar-collapsed' : 'sidebar-width',
        )}
      >
        <div
          className={cn(
            'sidebar-logo-row relative flex h-[84px] flex-shrink-0 items-center gap-3 border-b border-sidebar-divider px-5',
            isSidebarCollapsed && 'justify-center px-3',
          )}
        >
          <BrandLogo
            sidebar
            subtitle="平台管理控制台"
            copyClassName={isSidebarCollapsed ? 'hidden' : undefined}
          />
          <button
            type="button"
            onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
            aria-label={isSidebarCollapsed ? '展开导航栏' : '收起导航栏'}
            aria-expanded={!isSidebarCollapsed}
            title={isSidebarCollapsed ? '展开导航栏' : '收起导航栏'}
            className={cn(
              'absolute inline-flex h-7 w-7 items-center justify-center rounded-md text-sidebar-text transition-colors hover:bg-sidebar-item-hover hover:text-sidebar-text-active',
              isSidebarCollapsed ? 'right-1 top-2' : 'right-3 top-1/2 -translate-y-1/2',
            )}
          >
            {isSidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        <nav className={cn('scrollbar-thin flex-1 space-y-1 overflow-y-auto py-4', isSidebarCollapsed ? 'px-2' : 'px-3')}>
          {adminNavItems.map((item) => (
            <NavLink
              key={item.path + item.label}
              to={item.path}
              end={item.path === '/admin/dashboard'}
              className={({ isActive }) =>
                cn(
                  'relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-150',
                  isSidebarCollapsed && 'justify-center gap-0 px-0',
                  isActive
                    ? 'bg-sidebar-item-active text-sidebar-text-active font-semibold shadow-elevation-1'
                    : 'text-sidebar-text hover:bg-sidebar-item-hover hover:text-sidebar-text-active',
                )
              }
            >
              <item.icon className="h-4.5 w-4.5" />
              <span className={cn('sidebar-nav-label', isSidebarCollapsed && 'hidden')}>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className={cn('flex-shrink-0 border-t border-sidebar-divider p-3', isSidebarCollapsed && 'px-2')}>
          <button
            type="button"
            onClick={() => !user && !loading && setIsLoginModalOpen(true)}
            className={cn(
              'sidebar-account-button flex w-full items-center gap-3 rounded-md border border-sidebar-divider bg-sidebar-panel/70 px-3 py-2.5 text-left transition-colors hover:bg-sidebar-panel',
              isSidebarCollapsed && 'justify-center gap-0 px-0',
            )}
            aria-label={isSidebarCollapsed ? `当前用户 ${displayName}` : undefined}
            title={isSidebarCollapsed ? `${displayName} · ${roleLabel}` : undefined}
            disabled={loading}
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-sm font-bold text-white">
              {loading ? '…' : initial}
            </div>
            <div className={cn('sidebar-user-copy min-w-0 flex-1', isSidebarCollapsed && 'hidden')}>
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
