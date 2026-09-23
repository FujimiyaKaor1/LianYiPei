import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, Home, LogOut, Moon, Search, Sun, User } from 'lucide-react';
import { useAuth } from '@/src/context/AuthContext';
import { useTheme } from '@/src/context/ThemeContext';
import { useToast } from '@/src/components/ToastProvider';
import { api } from '@/src/services/api';
import { GUEST_HOME_PATH } from '@/src/lib/rbac';
import { BrandLogo } from './BrandLogo';

interface TopBarProps {
  title: string;
  showSearch?: boolean;
}

export function TopBar({ title, showSearch = true }: TopBarProps) {
  const { user, loading, logout, requestLogin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { showToast } = useToast();
  const [unreadCount, setUnreadCount] = useState(0);
  const [globalSearch, setGlobalSearch] = useState('');
  const dateLabel = new Date().toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  });

  useEffect(() => {
    if (!user) return;
    api.getAlerts({ per_page: 1 } as any).then(r => {
      setUnreadCount(r.total || 0);
    }).catch(() => {});
  }, [user]);

  const currentPath = `${location.pathname}${location.search}`;
  const submitGlobalSearch = () => {
    const query = globalSearch.trim();
    if (query) navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <header className="sticky top-0 z-30 flex h-[72px] flex-shrink-0 items-center justify-between border-b border-border bg-surface/86 px-6 backdrop-blur-xl">
      <div className="flex min-w-0 items-center gap-4">
        <BrandLogo
          subtitle="供应链经营工作台"
          titleClassName="text-ink"
          subtitleClassName="text-ink-muted"
        />
        <div className="min-w-0 border-l border-border pl-4">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-[20px] font-bold text-ink">{title}</h2>
            <span className="rounded-md border border-trust/20 bg-trust-soft px-2 py-0.5 text-[10px] font-bold text-trust">
              Live
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-[11px] font-medium text-ink-muted">
            <span>运营日历 {dateLabel}</span>
            <span className="h-1 w-1 rounded-full bg-ink-faint" />
            <span>数据同步中枢</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {showSearch && (
          <div className="relative hidden lg:block">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              placeholder="搜索企业、产品或工厂..."
              value={globalSearch}
              onChange={(event) => setGlobalSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  submitGlobalSearch();
                }
              }}
              className="input-search h-9 w-72 pl-9"
            />
          </div>
        )}

        <div className="flex items-center gap-2">
          <Link
            to={GUEST_HOME_PATH}
            className="btn-secondary btn-sm hidden gap-1.5 sm:inline-flex"
            aria-label="回到首页"
          >
            <Home className="h-3.5 w-3.5" />
            回到首页
          </Link>

          {loading ? (
            <span className="text-xs text-ink-muted px-2">…</span>
          ) : user ? (
            <div className="hidden items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5 shadow-elevation-1 xl:flex">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-solid text-[11px] font-bold text-white">
                {user.enterpriseName?.slice(0, 1) || '企'}
              </div>
              <div className="min-w-0">
                <span
                  className="block max-w-[160px] truncate text-xs font-semibold text-ink"
                  title={user.enterpriseName}
                >
                  {user.enterpriseName}
                </span>
                <span className="block text-[10px] font-medium text-ink-muted">已连接企业账号</span>
              </div>
              <button
                type="button"
                onClick={() => void logout()}
                className="btn-ghost btn-sm h-8 gap-1.5 px-2"
                title="退出登录"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => requestLogin(currentPath)}
              className="btn-primary btn-sm gap-1.5"
            >
              <User className="w-3.5 h-3.5" />
              用户登录
            </button>
          )}

          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-ink-soft shadow-elevation-1 transition-colors hover:border-border-hover hover:text-ink"
            onClick={toggleTheme}
            aria-pressed={theme === 'dark'}
            title={theme === 'dark' ? '切换浅色模式' : '切换深色模式'}
          >
            {theme === 'dark' ? (
              <Sun className="h-4.5 w-4.5" />
            ) : (
              <Moon className="h-4.5 w-4.5" />
            )}
          </button>

          <button
            className="relative flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-ink-soft shadow-elevation-1 transition-colors hover:border-border-hover hover:text-ink"
            onClick={() => {
              if (!user) {
                requestLogin(currentPath);
                return;
              }
              showToast(unreadCount > 0 ? `${unreadCount} 条未读预警` : '暂无新预警', 'info');
            }}
            title="预警通知"
          >
            <Bell className="h-4.5 w-4.5" />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-surface bg-critical px-1 text-[10px] font-bold text-white">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

        </div>
      </div>

      {showSearch && (
        <div className="absolute left-3 right-3 top-[76px] z-40 lg:hidden">
          <div className="relative rounded-lg border border-border bg-surface p-1 shadow-elevation-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              placeholder="搜索企业、产品或工厂..."
              value={globalSearch}
              onChange={(event) => setGlobalSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  submitGlobalSearch();
                }
              }}
              aria-label="移动端全局搜索"
              className="input-search h-10 w-full pl-9"
            />
          </div>
        </div>
      )}
    </header>
  );
}
