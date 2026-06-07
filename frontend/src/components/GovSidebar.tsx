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
    <aside className="w-64 h-screen sticky top-0 flex-shrink-0 flex flex-col border-r border-gray-200 bg-white">
      <div className="h-16 flex-shrink-0 flex items-center px-6 border-b border-gray-100">
        <ShieldCheck className="w-5 h-5 mr-2 text-neutral-700" />
        <h1 className="text-lg font-black tracking-tighter text-primary">链易配</h1>
        <span className="ml-2 text-[9px] text-neutral-400 font-medium tracking-widest uppercase">
          产业监管
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-1">
        {govNavItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/gov'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group',
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
          className="w-full text-left flex items-center gap-3 p-3 rounded-xl bg-gray-50 hover:bg-gray-100/80 transition-colors disabled:opacity-70"
          disabled={loading}
        >
          <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-sm font-bold text-neutral-600 shrink-0">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold truncate" title={displayName}>
              {loading ? '…' : displayName}
            </p>
            <div className="flex items-center gap-1 text-[10px] text-neutral-500">
              <ShieldCheck className="w-3 h-3 text-neutral-600 shrink-0" />
              <span>{user ? '政府监管' : '点击登录'}</span>
            </div>
          </div>
        </button>
      </div>
    </aside>
  );
}
