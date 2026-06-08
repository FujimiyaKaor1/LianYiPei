import React, { useEffect, useState } from 'react';
import { Bell, History, LogOut, Search, User } from 'lucide-react';
import { useAuth } from '@/src/context/AuthContext';
import { useToast } from '@/src/components/ToastProvider';
import { api } from '@/src/services/api';

interface TopBarProps {
  title: string;
  showSearch?: boolean;
}

export function TopBar({ title, showSearch = true }: TopBarProps) {
  const { user, loading, logout, setIsLoginModalOpen } = useAuth();
  const { showToast } = useToast();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    api.getAlerts({ per_page: 1 } as any).then(r => {
      setUnreadCount(r.total || 0);
    }).catch(() => {});
  }, [user]);

  return (
    <header className="h-16 flex-shrink-0 flex justify-between items-center px-6 border-b border-border bg-canvas">
      <h2 className="text-[18px] font-semibold tracking-tight text-ink">{title}</h2>

      <div className="flex items-center gap-4">
        {showSearch && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-muted" />
            <input
              type="text"
              placeholder="搜索合同、商机或客户..."
              className="input-search w-64"
            />
          </div>
        )}

        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-xs text-ink-muted px-2">…</span>
          ) : user ? (
            <div className="flex items-center gap-2">
              <span
                className="text-xs text-ink-soft max-w-[160px] truncate font-medium"
                title={user.enterpriseName}
              >
                {user.enterpriseName}
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="btn-ghost btn-sm gap-1.5"
              >
                <LogOut className="w-3.5 h-3.5" />
                退出
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsLoginModalOpen(true)}
              className="btn-primary btn-sm gap-1.5"
            >
              <User className="w-3.5 h-3.5" />
              用户登录
            </button>
          )}

          <button
            className="w-9 h-9 flex items-center justify-center rounded-md hover:bg-canvas-muted transition-colors relative"
            onClick={() => showToast(unreadCount > 0 ? `${unreadCount} 条未读预警` : '暂无新预警', 'info')}
          >
            <Bell className="w-5 h-5 text-ink-soft" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 min-w-[18px] h-[18px] flex items-center justify-center bg-error text-white text-[10px] font-bold rounded-full border-2 border-canvas px-1">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          <button
            className="w-9 h-9 flex items-center justify-center rounded-md hover:bg-canvas-muted transition-colors"
            onClick={() => showToast('操作历史功能即将上线', 'info')}
          >
            <History className="w-5 h-5 text-ink-soft" />
          </button>
        </div>
      </div>
    </header>
  );
}
