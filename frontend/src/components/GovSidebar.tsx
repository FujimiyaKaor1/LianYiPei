import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ShieldAlert,
  Landmark,
  Award,
  ShieldCheck,
  Network,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';
import { BrandLogo } from './BrandLogo';

/** 顺序突出「质量把关 → 风险预警 → 产业链视图 → 招商」 */
const govNavItems = [
  { icon: LayoutDashboard, label: '监管首页', path: '/gov' },
  { icon: Award, label: '质量标签', path: '/gov/labels' },
  { icon: ShieldAlert, label: '预警中心', path: '/gov/alerts' },
  { icon: Network, label: '产业链图谱', path: '/gov/supply-chain' },
  { icon: Landmark, label: '招商决策', path: '/gov/recruitment' },
];

export function GovSidebar() {
  const { user, loading, setIsLoginModalOpen } = useAuth();
  const displayName = user?.enterpriseName?.trim() || '未登录';
  const initial = displayName !== '未登录' ? displayName.slice(0, 1) : '?';

  return (
    <aside className="sidebar-width sticky top-0 flex h-screen flex-shrink-0 flex-col border-r border-white/10 bg-sidebar-bg text-sidebar-text">
      <div className="sidebar-logo-row flex h-[72px] flex-shrink-0 items-center gap-3 border-b border-sidebar-divider px-5">
        <BrandLogo sidebar subtitle="产业监管驾驶舱" />
      </div>

      <nav className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {govNavItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/gov'}
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
            <span className="sidebar-nav-label text-sm">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="flex-shrink-0 border-t border-sidebar-divider p-3">
        <button
          type="button"
          onClick={() => !user && !loading && setIsLoginModalOpen(true)}
          className="sidebar-account-button flex w-full items-center gap-3 rounded-md border border-sidebar-divider bg-sidebar-panel/70 px-3 py-2.5 text-left transition-colors hover:bg-sidebar-panel disabled:opacity-70"
          disabled={loading}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-sm font-bold text-white">
            {initial}
          </div>
          <div className="sidebar-user-copy flex-1 min-w-0">
            <p className="truncate text-xs font-bold text-sidebar-text-active" title={displayName}>
              {loading ? '…' : displayName}
            </p>
            <div className="flex items-center gap-1 text-[10px] text-sidebar-text">
              <ShieldCheck className="h-3 w-3 shrink-0 text-brand-muted" />
              <span>{user ? '政府监管' : '点击登录'}</span>
            </div>
          </div>
        </button>
      </div>
    </aside>
  );
}
