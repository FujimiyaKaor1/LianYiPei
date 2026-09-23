import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react';
import { companyLinks, homepageLinks } from './homepageLinks';

export type Theme = 'light' | 'dark';

export function SectionLabel({ children }: { children: ReactNode }) {
  return <p className="indisea-kicker">{children}</p>;
}

function ArrowIcon({ direction = 'up' }: { direction?: 'up' | 'down' }) {
  return (
    <svg className={`indisea-arrow indisea-arrow--${direction}`} viewBox="0 0 20 20" aria-hidden="true">
      <path d="M4 10h11M10.5 5.5 15 10l-4.5 4.5" />
    </svg>
  );
}

export function TalkButton({ className = '', href = '/search', label = '开始找厂' }: { className?: string; href?: string; label?: string }) {
  return (
    <a className={`indisea-pill ${className}`} href={href}>
      <span>{label}</span><ArrowIcon />
    </a>
  );
}

export function BrandLogo({ inverse = false, wordmark = false }: { inverse?: boolean; wordmark?: boolean }) {
  if (wordmark) return <span className="indisea-wordmark">链易配</span>;
  return <span className={`indisea-brand-logo ${inverse ? 'is-inverse' : ''}`}><img src={`${import.meta.env.BASE_URL}lianyipei-logo.png`} alt="" /><span className="indisea-brand-logo__copy"><strong>链易配</strong><small>制造业 AI 找厂平台</small></span></span>;
}

function ThemeIcon({ theme }: { theme: Theme }) {
  if (theme === 'light') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" /><circle cx="12" cy="12" r="4" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.1A8 8 0 0 1 8.9 4 8 8 0 1 0 20 15.1Z" /></svg>;
}

type MenuProps = {
  open: boolean;
  onClose: () => void;
  theme: Theme;
  onThemeChange: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

function SiteMenu({ open, onClose, theme, onThemeChange, triggerRef }: MenuProps) {
  const dialog = useRef<HTMLDivElement>(null);
  const [tone, setTone] = useState(1);

  useEffect(() => {
    if (!open) return;
    const root = dialog.current;
    const inside = root ? Array.from(root.querySelectorAll('a,button:not([tabindex="-1"])')) as HTMLElement[] : [];
    const focusable = triggerRef.current ? [triggerRef.current, ...inside] : inside;
    inside[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, open, triggerRef]);

  return (
    <div id="indisea-site-menu" className="indisea-menu" data-open={open} data-menu-theme={theme === 'light' ? 'dark' : 'light'} role="dialog" aria-modal="true" aria-hidden={!open} aria-label="Site menu" ref={dialog}>
      <div className="indisea-menu__nav">
        <nav aria-label="Main navigation">
          {homepageLinks.map((link, index) => (
            <a key={link.label} href={link.href} tabIndex={open ? 0 : -1} onClick={onClose} data-index={index + 1} style={{ '--menu-index': index } as CSSProperties}
              onMouseEnter={() => setTone(index + 1)} onFocus={() => setTone(index + 1)}
              {...(link.kind === 'external' ? { target: '_blank', rel: 'noreferrer' } : {})}>
              <span>0{index + 1}</span>{link.label}
            </a>
          ))}
        </nav>
        <button className="indisea-theme" type="button" onClick={onThemeChange} tabIndex={open ? 0 : -1} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
          <ThemeIcon theme={theme} />
        </button>
      </div>
      <div className="indisea-menu__aside" aria-hidden="true">
        <i data-tone={tone} />
      </div>
      <div className="indisea-menu__contact">
        <div><SectionLabel>平台入口</SectionLabel><a tabIndex={open ? 0 : -1} href="/search">公开找厂</a></div>
        <div><SectionLabel>数据说明</SectionLabel><p>公开页面仅展示脱敏摘要。</p></div>
        <div><SectionLabel>服务对象</SectionLabel><p>企业、园区、政府与平台运营方。</p></div>
      </div>
    </div>
  );
}

export function SiteHeader({ theme, onThemeChange }: { theme: Theme; onThemeChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [darkSurface, setDarkSurface] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => setScrolled(window.scrollY > 100));
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  useEffect(() => {
    let frame = 0;
    const updateContrast = () => {
      const elements = document.elementsFromPoint(window.innerWidth - 44, 44);
      const overDarkSection = elements.some((element) => element.closest('.indisea-problem-story,.indisea-proof,.indisea-footer'));
      setDarkSurface(overDarkSection);
    };
    const onViewportChange = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(updateContrast);
    };
    window.addEventListener('scroll', onViewportChange, { passive: true });
    window.addEventListener('resize', onViewportChange);
    updateContrast();
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onViewportChange);
      window.removeEventListener('resize', onViewportChange);
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle('indisea-menu-open', open);
    return () => document.body.classList.remove('indisea-menu-open');
  }, [open]);

  const close = useCallback(() => {
    setOpen(false);
    window.setTimeout(() => trigger.current?.focus(), 900);
  }, []);

  return <>
    <header className="indisea-header">
      <a className={`indisea-header__brand ${scrolled && !open ? 'is-hidden' : ''}`} tabIndex={scrolled && !open ? -1 : 0} href="#top" aria-label="Indisea home">
        <BrandLogo inverse={open ? theme === 'light' : theme === 'dark'} />
      </a>
      <button ref={trigger} type="button" className={`indisea-menu-trigger ${open ? 'is-open' : ''} ${(open ? theme === 'light' : darkSurface || theme === 'dark') ? 'is-inverse' : ''}`} onClick={() => setOpen((value) => !value)} aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} aria-controls="indisea-site-menu">
        <i /><i />
      </button>
    </header>
    <SiteMenu open={open} onClose={close} theme={theme} onThemeChange={onThemeChange} triggerRef={trigger} />
  </>;
}

export function SiteFooter() {
  return (
    <footer className="indisea-footer">
      <div className="indisea-footer__top" data-motion-reveal>
        <div className="indisea-footer__brand"><BrandLogo inverse /><p>让每一次采购<br />直达可核验的制造能力。</p></div>
        <div className="indisea-footer__columns">
          <nav aria-label="页脚导航"><SectionLabel>导航</SectionLabel>{homepageLinks.map((link) => <a key={link.label} href={link.href}>{link.label}</a>)}</nav>
          <nav aria-label="平台功能"><SectionLabel>平台功能</SectionLabel>{companyLinks.map((link) => <a key={link.label} href={link.href}>{link.label}</a>)}</nav>
          <div><SectionLabel>数据边界</SectionLabel><p>数据来源和更新时间随结果展示。</p><p>完整企业能力和联系方式需登录后查看。</p></div>
        </div>
      </div>
      <div data-motion-reveal><BrandLogo wordmark /></div>
      <div className="indisea-footer__bottom">
        <span>链易配 · 产业链供需协同平台</span>
        <span>公开页面展示脱敏摘要</span>
        <a href="#top">回到顶部 <ArrowIcon /></a>
      </div>
    </footer>
  );
}
