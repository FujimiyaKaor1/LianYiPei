import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard,
  Network, 
  Settings, 
  Wallet, 
  Users,
  Package,
  Activity,
  CalendarDays,
  SlidersHorizontal,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { isPublicGuestPath } from '@/src/lib/rbac';
import { BrandLogo } from './BrandLogo';

export const navGroups = [
  {
    label: '首页',
    items: [
      { icon: LayoutDashboard, label: '企业看板', path: '/dashboard' },
    ],
  },
  {
    label: '供需协同',
    items: [
      { icon: Network, label: '供需匹配', path: '/matching' },
    ],
  },
  {
    label: '资源协同',
    items: [
      { icon: SlidersHorizontal, label: '名录筛选', path: '/workspace/enterprise-directory' },
      { icon: Users, label: '集采拼单', path: '/group-purchase' },
    ],
  },
  {
    label: '履约运营',
    items: [
      { icon: Activity, label: '履约看板', path: '/fulfillment' },
      { icon: CalendarDays, label: '产能日历', path: '/capacity-calendar' },
      { icon: Package, label: '订单工作流', path: '/orders' },
    ],
  },
  {
    label: '系统',
    items: [
      { icon: Wallet, label: '资产管理', path: '/assets' },
      { icon: Settings, label: '设置', path: '/settings' },
    ],
  },
];

export function EnterpriseTopNav() {
  const { user, loading, requestLogin } = useAuth();
  const navItems = navGroups.flatMap((group) => group.items);

  return (
    <nav
      className="flex min-h-[56px] flex-shrink-0 items-center gap-2 overflow-x-auto border-b border-border bg-surface/92 px-4 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur-xl md:px-6"
      aria-label="企业工作台导航"
    >
      {navItems.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          onClick={(event) => {
            if (!user && !loading && !isPublicGuestPath(item.path)) {
              event.preventDefault();
              requestLogin(item.path);
            }
          }}
          className={({ isActive }) => cn(
            'inline-flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-semibold transition-colors',
            isActive
              ? 'bg-brand-solid text-white shadow-elevation-1'
              : 'text-ink-muted hover:bg-surface-subtle hover:text-brand',
          )}
        >
          <item.icon className="h-4 w-4" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  const { user, loading, requestLogin } = useAuth();
  const displayName = user?.enterpriseName?.trim() || '未登录';
  const initial = displayName !== '未登录' ? displayName.slice(0, 1) : '?';

  return (
    <aside className="sidebar-width sticky top-0 flex h-screen flex-shrink-0 flex-col border-r border-white/10 bg-sidebar-bg text-sidebar-text">
      {/* Logo */}
      <div className="sidebar-logo-row flex h-[84px] flex-shrink-0 items-center border-b border-sidebar-divider px-5">
        <BrandLogo sidebar subtitle="供应链经营工作台" />
      </div>

      {/* Navigation */}
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-5">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="sidebar-group-label px-3 pb-2 text-[10px] font-bold text-sidebar-text/70">
                {group.label}
              </div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={(event) => {
                      if (!user && !loading && !isPublicGuestPath(item.path)) {
                        event.preventDefault();
                        requestLogin(item.path);
                      }
                    }}
                    className={({ isActive }) => cn(
                      "group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-150",
                      isActive
                        ? "bg-sidebar-item-active text-sidebar-text-active font-semibold shadow-elevation-1"
                        : "text-sidebar-text hover:bg-sidebar-item-hover hover:text-sidebar-text-active"
                    )}
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          className={cn(
                            "absolute left-0 top-2 bottom-2 w-0.5 rounded-full transition-opacity",
                            isActive ? "bg-brand opacity-100" : "opacity-0",
                          )}
                        />
                        <item.icon className="h-4.5 w-4.5 shrink-0" />
                        <span className="sidebar-nav-label truncate">{item.label}</span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      {/* User profile at bottom */}
      <div className="flex-shrink-0 border-t border-sidebar-divider p-3">
        <button
          type="button"
          onClick={() => !user && !loading && requestLogin()}
          className="sidebar-account-button flex w-full items-center gap-3 rounded-md border border-sidebar-divider bg-sidebar-panel/70 px-3 py-2.5 text-left transition-colors hover:bg-sidebar-panel disabled:opacity-70"
          disabled={loading}
          aria-label={user ? `当前用户 ${displayName}` : '点击登录'}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-xs font-bold text-white">
            {initial}
          </div>
          <div className="sidebar-user-copy flex-1 min-w-0">
            <p className="text-xs font-semibold text-sidebar-text-active truncate" title={displayName}>
              {loading ? '…' : displayName}
            </p>
            <p className="text-[10px] text-sidebar-text mt-0.5">
              {user ? '履约认证企业' : '点击登录'}
            </p>
          </div>
        </button>
      </div>
    </aside>
  );
}
