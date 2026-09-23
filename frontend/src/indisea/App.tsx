import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/src/context/AuthContext';
import CustomCursor from './CustomCursor';
import HomePage from './HomePage';
import HomepageMotion from './HomepageMotion';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';
import { LoginModal } from '@/src/components/LoginModal';
import { SiteFooter, type Theme } from './SiteChrome';
import './homepage.css';

const storageKey = 'indisea-theme';

export default function App() {
  const { requestLogin } = useAuth();
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem(storageKey) === 'dark' ? 'dark' : 'light');
  const [loading, setLoading] = useState(true);
  useEffect(() => { document.body.classList.add('indisea-body'); return () => document.body.classList.remove('indisea-body'); }, []);
  useEffect(() => { window.localStorage.setItem(storageKey, theme); }, [theme]);
  const switchTheme = () => setTheme((value) => value === 'light' ? 'dark' : 'light');
  const finishLoading = useCallback(() => setLoading(false), []);
  return <div className="indisea-site" data-theme={theme}><HomepageMotion loading={loading} onLoadingComplete={finishLoading} /><div className={`indisea-loader ${loading ? '' : 'is-done'}`} data-loader aria-hidden="true"><div><span data-loader-count>000</span><i>链易配</i></div><b data-loader-progress /></div><CustomCursor /><PublicSiteHeader onLogin={() => requestLogin('/indisea/')} /><HomePage /><SiteFooter /><LoginModal /></div>;
}
