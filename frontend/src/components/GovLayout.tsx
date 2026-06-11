import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { GovSidebar } from './GovSidebar';
import { TopBar } from './TopBar';

export function GovLayout() {
  const location = useLocation();

  const getTitle = (path: string) => {
    if (path === '/gov' || path === '/gov/') return '产业监管首页';
    if (path.startsWith('/gov/alerts')) return '预警中心';
    if (path.startsWith('/gov/recruitment')) return '招商决策看板';
    if (path.startsWith('/gov/supply-chain')) return '产业链图谱';
    if (path.startsWith('/gov/labels')) return '质量标签管理';
    return '产业监管平台';
  };

  return (
    <div className="app-shell flex min-h-screen w-full">
      <GovSidebar />
      <main className="flex h-screen min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar title={getTitle(location.pathname)} />
        <div data-scroll-root className="min-h-0 w-full flex-1 overflow-auto p-4 pb-12 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
