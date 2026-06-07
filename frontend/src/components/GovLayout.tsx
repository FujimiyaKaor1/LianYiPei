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
    <div className="flex min-h-screen w-full bg-[#F5F5F7]">
      <GovSidebar />
      <main className="flex flex-1 flex-col min-w-0">
        <TopBar title={getTitle(location.pathname)} />
        <div className="w-full p-4 md:p-6 pb-12 min-h-0">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
