import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export function ScrollToTop() {
  const { pathname, search } = useLocation();

  useEffect(() => {
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
      document
        .querySelectorAll<HTMLElement>('[data-scroll-root]')
        .forEach((element) => {
          element.scrollTop = 0;
          element.scrollLeft = 0;
        });
    });
  }, [pathname, search]);

  return null;
}
