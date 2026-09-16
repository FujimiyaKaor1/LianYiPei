import { LayoutDashboard } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';

export function EnterpriseNavMenu({ compact = false }: { compact?: boolean }) {
  const { user, loading, requestLogin } = useAuth();

  return (
    <Link
      to={user ? '/dashboard' : '#'}
      onClick={event => {
        if (!user && !loading) {
          event.preventDefault();
          requestLogin('/dashboard');
        }
      }}
      aria-label="进入企业看板"
      className={compact ? 'inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-bold text-ink-muted hover:bg-surface-subtle hover:text-brand' : 'inline-flex items-center gap-1.5 rounded-md px-2 py-2 text-sm font-semibold text-public-muted transition hover:bg-public-bg hover:text-public-brand'}
    >
      <LayoutDashboard className="h-3.5 w-3.5" />企业看板
    </Link>
  );
}
