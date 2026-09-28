import { Link, useLocation } from 'react-router-dom';
import { LogOut, Search, Sparkles, User } from 'lucide-react';
import { BrandLogo } from './BrandLogo';
import { EnterpriseNavMenu } from './EnterpriseNavMenu';
import { useAuth } from '@/src/context/AuthContext';

export function PublicSiteHeader({ onLogin }: { onLogin?: () => void }) {
  const location = useLocation();
  const { user, loading, logout, requestLogin } = useAuth();
  const handleLogin = onLogin || (() => requestLogin(`${location.pathname}${location.search}`));

  return (
    <header className="public-site-header sticky top-0 z-40 border-b border-public-border/80 bg-white/95 backdrop-blur-xl">
      <div className="mx-auto grid h-[70px] w-full max-w-[1320px] min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 px-4 md:gap-6 md:px-8">
        <BrandLogo
          subtitle="制造业 AI 找厂平台"
          markClassName="h-9 w-9 rounded-lg"
          titleClassName="text-[18px] font-black text-public-text"
          subtitleClassName="text-[10px] text-public-muted"
        />
        <nav className="hidden min-w-0 items-center justify-center gap-4 overflow-hidden whitespace-nowrap text-sm font-semibold text-public-muted xl:flex 2xl:gap-6" aria-label="公共平台导航">
          <Link className="transition hover:text-public-brand" to="/indisea/">首页</Link>
          <Link className="transition hover:text-public-brand" to="/search">筛选工厂</Link>
          <a className="flex items-center gap-1 transition hover:text-public-brand" href="/aisearch/"><Sparkles className="h-3.5 w-3.5" /> AI 找工厂</a>
          <Link className="transition hover:text-public-brand" to="/agent-market">AI 智能体</Link>
          <EnterpriseNavMenu />
          <Link className="transition hover:text-public-brand" to="/industry-news">行业资讯</Link>
        </nav>
        <div className="flex min-w-0 items-center justify-end gap-2">
          <div className="xl:hidden"><EnterpriseNavMenu /></div>
          <a className="hidden items-center gap-1.5 rounded-full border border-public-border px-3 py-2 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand md:flex" href="/search">
            <Search className="h-3.5 w-3.5" /> 筛选工厂
          </a>
          {loading ? (
            <span className="px-3 py-2 text-xs font-semibold text-public-muted" aria-label="正在同步登录状态">同步中…</span>
          ) : user ? (
            <div className="flex items-center gap-2 rounded-full border border-public-border bg-white px-2 py-1 shadow-sm" data-testid="authenticated-user">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-public-brand text-xs font-black text-white">
                {user.enterpriseName.slice(0, 1) || '企'}
              </span>
              <span className="inline max-w-[150px] truncate text-xs font-bold text-public-text" title={user.enterpriseName}>
                {user.enterpriseName}
              </span>
              <button type="button" onClick={() => void logout()} className="inline-flex h-7 w-7 items-center justify-center rounded-full text-public-muted transition hover:bg-public-bg hover:text-public-brand" title="退出登录" aria-label="退出登录">
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <button type="button" onClick={handleLogin} className="btn-secondary btn-sm inline-flex items-center gap-1.5"><User className="h-3.5 w-3.5" />登录 / 入驻</button>
          )}
        </div>
      </div>
    </header>
  );
}
