import { useEffect, useRef, useState } from 'react';
import { ChevronDown, LayoutDashboard, ShieldAlert, SlidersHorizontal, UsersRound } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/src/context/AuthContext';

const ITEMS = [
  { label: '企业看板', path: '/dashboard', icon: LayoutDashboard },
  { label: '销售控制台', path: '/sales-console', icon: UsersRound },
  { label: '风险监测', path: '/risk', icon: ShieldAlert },
  { label: '名录筛选', path: '/workspace/enterprise-directory', icon: SlidersHorizontal },
];

export function EnterpriseNavMenu({ compact = false }: { compact?: boolean }) {
  const { user, loading, requestLogin } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const go = (path: string) => {
    setOpen(false);
    if (!user && !loading) requestLogin(path);
  };

  return (
    <div ref={ref} className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
        onKeyDown={event => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setOpen(true); }
        }}
        className={compact ? 'inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-bold text-ink-muted hover:bg-surface-subtle hover:text-brand' : 'inline-flex items-center gap-1.5 rounded-md px-2 py-2 text-sm font-semibold text-public-muted transition hover:bg-public-bg hover:text-public-brand'}
      >
        企业看板 <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div role="menu" className={compact ? 'absolute right-0 top-full z-50 mt-2 w-44 rounded-md border border-border bg-surface p-1.5 shadow-elevation-3' : 'absolute left-0 top-full z-50 mt-2 w-48 rounded-lg border border-public-border bg-white p-1.5 shadow-public'}>
          {ITEMS.map(({ label, path, icon: Icon }) => {
            const active = location.pathname === path;
            return (
              <Link
                key={path}
                to={user ? path : '#'}
                role="menuitem"
                onClick={event => {
                  if (!user && !loading) { event.preventDefault(); go(path); }
                  else setOpen(false);
                }}
                className={compact ? `flex items-center gap-2 rounded px-2.5 py-2 text-xs font-semibold ${active ? 'bg-brand-soft text-brand' : 'text-ink-soft hover:bg-surface-subtle hover:text-ink'}` : `flex items-center gap-2 rounded-md px-3 py-2.5 text-xs font-semibold ${active ? 'bg-public-brand-soft text-public-brand' : 'text-public-muted hover:bg-public-bg hover:text-public-brand'}`}
              >
                <Icon className="h-3.5 w-3.5" />{label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
