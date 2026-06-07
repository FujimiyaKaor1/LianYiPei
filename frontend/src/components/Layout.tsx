import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { AISidebar } from './AISidebar';
import { TopBar } from './TopBar';

export function Layout() {
  const location = useLocation();
  const isHomePage = location.pathname === '/';

  const getTitle = (path: string) => {
    switch (path) {
      case '/': return '控制面板';
      case '/enterprise-directory': return '企业名录筛选';
      case '/matching': return '智能供需匹配';
      case '/analytics':
      case '/sales-console':
        return '销售控制台';
      case '/risk': return '风险监测';
      case '/orders': return '订单工作流';
      case '/favorites': return '优质客商';
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
    <div className="flex min-h-screen w-full bg-[#F5F5F7]">
      <Sidebar />
      <main className="flex flex-1 flex-col min-w-0">
        <TopBar title={getTitle(location.pathname)} />
        <div className="w-full p-4 md:p-6 pb-12 min-h-0">
          <Outlet />
        </div>
      </main>
      {isHomePage && <AISidebar />}
    </div>
  );
}
