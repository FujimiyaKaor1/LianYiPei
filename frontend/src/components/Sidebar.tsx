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
  FileText,
  Truck,
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
  { icon: FileText, label: '电子合同', path: '/contracts' },
  { icon: Receipt, label: '发票管理', path: '/invoice' },
  { icon: Truck, label: '物流距离', path: '/logistics' },
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
    <aside className="sidebar-width sticky top-0 h-screen flex-shrink-0 flex flex-col bg-sidebar-bg">
      {/* Logo */}
      <div className="h-16 flex-shrink-0 flex items-center px-5 border-b border-sidebar-divider">
        <div className="w-8 h-8 rounded-md bg-brand flex items-center justify-center mr-3 shrink-0">
          <span className="text-white text-sm font-extrabold">链</span>
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-bold tracking-tighter text-sidebar-text-active leading-tight">链易配</h1>
          <span className="text-[10px] text-sidebar-text font-medium tracking-wide">企业工作台</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5 scrollbar-hide">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-150 text-sm",
              isActive 
                ? "bg-sidebar-item-active text-sidebar-text-active font-semibold" 
                : "text-sidebar-text hover:bg-sidebar-item-hover hover:text-sidebar-text-active"
            )}
          >
            <item.icon className="w-4.5 h-4.5 shrink-0" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User profile at bottom */}
      <div className="flex-shrink-0 p-3 border-t border-sidebar-divider">
        <button
          type="button"
          onClick={() => !user && !loading && setIsLoginModalOpen(true)}
          className="w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-sidebar-item-hover transition-colors disabled:opacity-70"
          disabled={loading}
          aria-label={user ? `当前用户 ${displayName}` : '点击登录'}
        >
          <div className="w-8 h-8 rounded-full bg-sidebar-item-active flex items-center justify-center text-xs font-bold text-sidebar-text-active shrink-0">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
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
