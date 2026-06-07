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
    <div className="flex min-h-screen w-full bg-[#F5F5F7]">
      <aside className="w-64 h-screen sticky top-0 flex-shrink-0 flex flex-col border-r border-gray-200 bg-white">
        <div className="h-16 flex-shrink-0 flex items-center px-6 border-b border-gray-100">
          <LayoutDashboard className="w-5 h-5 mr-2 text-neutral-700" />
          <h1 className="text-lg font-black tracking-tighter text-primary">链易配</h1>
          <span className="ml-2 text-[9px] text-neutral-400 font-medium tracking-widest uppercase">
            管理后台
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1">
          {adminNavItems.map((item) => (
            <NavLink
              key={item.path + item.label}
              to={item.path}
              end={item.path === '/admin/dashboard'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200',
                  isActive
                    ? 'bg-neutral-900 text-white font-bold shadow-sm'
                    : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900',
                )
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="text-sm">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flex-shrink-0 p-4 border-t border-gray-100">
          <button
            type="button"
            onClick={() => !user && !loading && setIsLoginModalOpen(true)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left hover:bg-neutral-100 transition-colors"
            disabled={loading}
          >
            <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
              {loading ? '…' : initial}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-neutral-900 truncate">{loading ? '加载中…' : displayName}</div>
              <div className="text-[10px] text-neutral-400">{roleLabel}</div>
            </div>
          </button>
        </div>
      </aside>

      <main className="flex flex-1 flex-col min-w-0">
        <TopBar title={getTitle(location.pathname)} />
        <div className="w-full p-4 md:p-6 pb-12 min-h-0 flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
