import { ArrowRightLeft, LayoutDashboard } from 'lucide-react';
import type { MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';

export function EnterpriseNavMenu({ compact = false }: { compact?: boolean }) {
  const { user, loading, requestLogin } = useAuth();

  const itemClass = compact
    ? 'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1.5 text-xs font-bold text-ink-muted hover:bg-surface-subtle hover:text-brand'
    : 'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-2 text-sm font-semibold text-public-muted transition hover:bg-public-bg hover:text-public-brand';

  const openEnterprisePage = (event: MouseEvent, path: string) => {
    if (!user && !loading) {
      event.preventDefault();
      requestLogin(path);
    }
  };

  return (
    <span className="inline-flex shrink-0 items-center gap-1">
      <Link to={user ? '/dashboard' : '#'} onClick={event => openEnterprisePage(event, '/dashboard')} aria-label="进入企业看板" className={itemClass}>
        <LayoutDashboard className="h-3.5 w-3.5" />企业看板
      </Link>
      <Link to={user ? '/sales-console' : '#'} onClick={event => openEnterprisePage(event, '/sales-console')} aria-label="进入企业协同" className={itemClass}>
        <ArrowRightLeft className="h-3.5 w-3.5" />企业协同
      </Link>
    </span>
  );
}
