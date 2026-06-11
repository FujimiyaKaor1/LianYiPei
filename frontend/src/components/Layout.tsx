import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { AISidebar } from './AISidebar';
import { TopBar } from './TopBar';

export function Layout() {
  const location = useLocation();

  const getTitle = (path: string) => {
    switch (path) {
      case '/': return '控制面板';
      case '/dashboard': return '企业看板';
      case '/enterprise-directory': return '企业名录筛选';
      case '/matching': return '智能供需匹配';
      case '/analytics':
      case '/sales-console':
        return '销售控制台';
      case '/risk': return '风险监测';
      case '/orders': return '订单工作流';
      case '/assets': return '资产管理';
      case '/settings': return '系统设置';
      case '/group-purchase': return '集采拼单大厅';
      case '/quote-pool': return '报价池';
      case '/fulfillment': return '履约看板';
      case '/capacity-calendar': return '产能日历';
      default: return '链易配';
    }
  };

  return (
    <div className="app-shell flex min-h-screen w-full">
      <Sidebar />
      <main className="flex h-screen min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar title={getTitle(location.pathname)} />
        <div data-scroll-root className="min-h-0 w-full flex-1 overflow-auto p-4 pb-12 md:p-6">
          <Outlet />
        </div>
      </main>
      <AISidebar />
    </div>
  );
}
