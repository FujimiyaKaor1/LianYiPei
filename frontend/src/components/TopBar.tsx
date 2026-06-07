import React from 'react';
import { Bell, History, LogOut, Search, User } from 'lucide-react';
import { useAuth } from '@/src/context/AuthContext';

interface TopBarProps {
  title: string;
  showSearch?: boolean;
}

export function TopBar({ title, showSearch = true }: TopBarProps) {
  const { user, loading, logout, setIsLoginModalOpen } = useAuth();

  return (
    <header className="h-16 flex-shrink-0 flex justify-between items-center px-6 border-b border-gray-200 bg-white">
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>

      <div className="flex items-center gap-4">
        {showSearch && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              type="text"
              placeholder="搜索合同、商机或客户..."
              className="bg-gray-100 border-none rounded-lg py-2 pl-10 pr-4 text-xs w-64 focus:ring-1 focus:ring-gray-300 transition-all"
            />
          </div>
        )}

        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-xs text-neutral-400 px-2">…</span>
          ) : user ? (
            <div className="flex items-center gap-2">
              <span
                className="text-xs text-neutral-600 max-w-[160px] truncate font-medium"
                title={user.enterpriseName}
              >
                {user.enterpriseName}
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium text-neutral-600 border border-neutral-200 hover:bg-neutral-50 transition-all"
              >
                <LogOut className="w-4 h-4" />
                退出
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsLoginModalOpen(true)}
              className="bg-primary text-white px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-2 hover:opacity-90 transition-all"
            >
              <User className="w-4 h-4" />
              用户登录
            </button>
          )}

          <button className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors relative">
            <Bell className="w-5 h-5 text-neutral-600" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
          </button>

          <button className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors">
            <History className="w-5 h-5 text-neutral-600" />
          </button>
        </div>
      </div>
    </header>
  );
}
