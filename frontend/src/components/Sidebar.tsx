import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Network, 
  BarChart3, 
  ShieldAlert, 
  Settings, 
  Wallet, 
  Users,
  Package,
  Receipt,
  Activity,
  CalendarDays,
  SlidersHorizontal,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import { useAuth } from '@/src/context/AuthContext';

const navItems = [
  { icon: LayoutDashboard, label: '控制面板', path: '/' },
  { icon: SlidersHorizontal, label: '企业名录筛选', path: '/enterprise-directory' },
  { icon: Network, label: '供需匹配', path: '/matching' },
  { icon: Users, label: '集采拼单', path: '/group-purchase' },
  { icon: Receipt, label: '报价池', path: '/quote-pool' },
  { icon: BarChart3, label: '企业看板', path: '/sales-console' },
  { icon: Activity, label: '履约看板', path: '/fulfillment' },
  { icon: CalendarDays, label: '产能日历', path: '/capacity-calendar' },
  { icon: ShieldAlert, label: '风险监测', path: '/risk' },
  { icon: Package, label: '订单工作流', path: '/orders' },
  { icon: Wallet, label: '资产管理', path: '/assets' },
  { icon: Settings, label: '设置', path: '/settings' },
];

export function Sidebar() {
  const { user, loading, setIsLoginModalOpen } = useAuth();
  const displayName = user?.enterpriseName?.trim() || '未登录';
  const initial = displayName !== '未登录' ? displayName.slice(0, 1) : '?';

  return (
    <aside className="w-64 h-full flex-shrink-0 flex flex-col border-r border-gray-200 bg-white">
      <div className="h-16 flex-shrink-0 flex items-center px-6 border-b border-gray-100">
        <h1 className="text-xl font-black tracking-tighter text-primary">链易配</h1>
        <span className="ml-2 text-[10px] text-neutral-400 font-medium tracking-widest uppercase">企业工作台</span>
      </div>
      
      <nav className="flex-1 overflow-y-auto p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group",
              isActive 
                ? "bg-gray-100 text-primary font-bold" 
                : "text-neutral-500 hover:bg-gray-50 hover:text-primary"
            )}
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
              <ShieldAlert className="w-3 h-3 text-green-600 shrink-0" />
              <span>{user ? '履约认证企业' : '点击登录'}</span>
            </div>
          </div>
        </button>
      </div>
    </aside>
  );
}
