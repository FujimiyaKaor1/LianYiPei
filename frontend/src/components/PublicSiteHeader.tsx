import { Link } from 'react-router-dom';
import { Search, Sparkles } from 'lucide-react';
import { BrandLogo } from './BrandLogo';
import { EnterpriseNavMenu } from './EnterpriseNavMenu';

export function PublicSiteHeader({ onLogin }: { onLogin?: () => void }) {
  return (
    <header className="public-site-header sticky top-0 z-40 border-b border-public-border/80 bg-white/95 backdrop-blur-xl">
      <div className="mx-auto flex h-[70px] max-w-[1320px] items-center gap-6 px-4 md:px-8">
        <BrandLogo
          subtitle="制造业 AI 找厂平台"
          markClassName="h-9 w-9 rounded-lg"
          titleClassName="text-[18px] font-black text-public-text"
          subtitleClassName="text-[10px] text-public-muted"
        />
        <nav className="hidden flex-1 items-center gap-6 text-sm font-semibold text-public-muted lg:flex" aria-label="公共平台导航">
          <Link className="transition hover:text-public-brand" to="/">首页</Link>
          <Link className="transition hover:text-public-brand" to="/aia">搜索工厂</Link>
          <Link className="flex items-center gap-1 transition hover:text-public-brand" to="/aia"><Sparkles className="h-3.5 w-3.5" /> AI 找工厂</Link>
          <Link className="transition hover:text-public-brand" to="/agent-market">AI 智能体</Link>
          <EnterpriseNavMenu />
          <Link className="transition hover:text-public-brand" to="/industry-news">行业资讯</Link>
          <a className="transition hover:text-public-brand" href="/#services">开放平台</a>
          <a className="transition hover:text-public-brand" href="/#services">服务</a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <div className="lg:hidden"><EnterpriseNavMenu /></div>
          <Link className="hidden items-center gap-1.5 rounded-full border border-public-border px-3 py-2 text-xs font-bold text-public-muted transition hover:border-public-brand hover:text-public-brand md:flex" to="/aia">
            <Search className="h-3.5 w-3.5" /> 搜索工厂
          </Link>
          <button type="button" onClick={onLogin} className="btn-secondary btn-sm">登录 / 入驻</button>
        </div>
      </div>
    </header>
  );
}
