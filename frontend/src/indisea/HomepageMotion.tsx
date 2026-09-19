import { useEffect } from 'react';

type MotionProps = {
  loading: boolean;
  onLoadingComplete: () => void;
};

const easeOut = (value: number) => 1 - (1 - value) ** 3;
const clamp = (value: number, minimum: number, maximum: number) => Math.min(maximum, Math.max(minimum, value));

function formatCounter(value: number, pad: number, suffix: string) {
  return `${String(value).padStart(pad, '0')}${suffix}`;
}

export default function HomepageMotion({ loading, onLoadingComplete }: MotionProps) {
  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const frameIds = new Set<number>();
    const observers: IntersectionObserver[] = [];
    let disposed = false;

    const raf = (callback: FrameRequestCallback) => {
      const id = window.requestAnimationFrame((time) => {
        frameIds.delete(id);
        callback(time);
      });
      frameIds.add(id);
      return id;
    };

    const showEverything = () => {
      document.querySelectorAll<HTMLElement>('[data-motion-reveal],[data-cta-line]').forEach((element) => {
        element.classList.add('is-visible');
      });
      document.querySelectorAll<SVGPathElement>('[data-draw-path]').forEach((path) => {
        path.style.strokeDasharray = '';
        path.style.strokeDashoffset = '';
      });
      document.querySelectorAll<HTMLElement>('[data-count-target]').forEach((element) => {
        const target = Number(element.dataset.countTarget ?? '0');
        const pad = Number(element.dataset.countPad ?? '0');
        const suffix = element.dataset.countSuffix ?? '';
        element.textContent = formatCounter(target, pad, suffix);
      });
      const loaderCount = document.querySelector<HTMLElement>('[data-loader-count]');
      if (loaderCount) loaderCount.textContent = '100';
      onLoadingComplete();
    };

    if (reducedMotion.matches) {
      showEverything();
      return undefined;
    }

    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const element = entry.target as HTMLElement;
        element.classList.add('is-visible');
        revealObserver.unobserve(element);
      });
    }, { threshold: 0.16, rootMargin: '0px 0px -8% 0px' });
    observers.push(revealObserver);

    document.querySelectorAll<HTMLElement>('[data-motion-reveal]').forEach((element, index) => {
      element.style.setProperty('--motion-delay', `${Math.min(index % 6, 5) * 70}ms`);
      revealObserver.observe(element);
    });

    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const element = entry.target as HTMLElement;
        counterObserver.unobserve(element);
        const target = Number(element.dataset.countTarget ?? '0');
        const pad = Number(element.dataset.countPad ?? '0');
        const suffix = element.dataset.countSuffix ?? '';
        const start = performance.now();
        const duration = 1200;
        const tick = (time: number) => {
          if (disposed) return;
          const progress = clamp((time - start) / duration, 0, 1);
          element.textContent = formatCounter(Math.round(target * easeOut(progress)), pad, suffix);
          if (progress < 1) raf(tick);
        };
        raf(tick);
      });
    }, { threshold: 0.35 });
    observers.push(counterObserver);

    document.querySelectorAll<HTMLElement>('[data-count-target]').forEach((element) => {
      const pad = Number(element.dataset.countPad ?? '0');
      const suffix = element.dataset.countSuffix ?? '';
      element.textContent = formatCounter(0, pad, suffix);
      counterObserver.observe(element);
    });

    const drawObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const group = entry.target as HTMLElement;
        drawObserver.unobserve(group);
        group.querySelectorAll<SVGPathElement>('[data-draw-path]').forEach((path, index) => {
          const length = path.getTotalLength();
          path.style.strokeDasharray = String(length);
          path.style.strokeDashoffset = String(length);
          raf(() => {
            path.style.transition = `stroke-dashoffset 900ms cubic-bezier(.16,1,.3,1) ${index * 120}ms`;
            path.style.strokeDashoffset = '0';
          });
        });
      });
    }, { threshold: 0.32 });
    observers.push(drawObserver);

    document.querySelectorAll<HTMLElement>('[data-draw-group]').forEach((group) => drawObserver.observe(group));

    const ctaObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const section = entry.target as HTMLElement;
        ctaObserver.unobserve(section);
        section.querySelectorAll<HTMLElement>('[data-cta-line]').forEach((line, index) => {
          line.style.setProperty('--motion-delay', `${index * 120}ms`);
          line.classList.add('is-visible');
        });
      });
    }, { threshold: 0.42 });
    observers.push(ctaObserver);

    document.querySelectorAll<HTMLElement>('.indisea-final-cta').forEach((section) => ctaObserver.observe(section));

    const tracks = Array.from(document.querySelectorAll<HTMLElement>('.indisea-logo-track'));
    let lastY = window.scrollY;
    let lastTime = performance.now();
    let velocity = 0;
    let logoFrame = 0;
    const updateLogoSpeed = (time: number) => {
      logoFrame = 0;
      const deltaY = Math.abs(window.scrollY - lastY);
      const deltaTime = Math.max(16, time - lastTime);
      lastY = window.scrollY;
      lastTime = time;
      velocity = velocity * 0.78 + (deltaY / deltaTime) * 0.22;
      const speed = clamp(1 + velocity * 2.8, 1, 3.6);
      tracks.forEach((track) => {
        const base = Number(track.dataset.logoDuration ?? '62');
        track.style.animationDuration = `${base / speed}s`;
      });
      if (velocity > 0.02) logoFrame = raf(updateLogoSpeed);
    };
    const requestLogoSpeed = () => {
      if (!logoFrame) logoFrame = raf(updateLogoSpeed);
    };
    window.addEventListener('scroll', requestLogoSpeed, { passive: true });

    const runLoader = () => {
      const loader = document.querySelector<HTMLElement>('[data-loader]');
      const count = document.querySelector<HTMLElement>('[data-loader-count]');
      const progress = document.querySelector<HTMLElement>('[data-loader-progress]');
      const started = performance.now();
      const finish = () => {
        if (disposed) return;
        if (count) count.textContent = '100';
        if (progress) progress.style.transform = 'scaleX(1)';
        window.setTimeout(onLoadingComplete, 180);
      };
      const animate = (time: number) => {
        if (disposed) return;
        const percent = clamp((time - started) / 1450, 0, 1);
        const eased = easeOut(percent);
        if (count) count.textContent = formatCounter(Math.round(eased * 100), 3, '');
        if (progress) progress.style.transform = `scaleX(${eased})`;
        if (percent < 1 || (document.fonts.status !== 'loaded' && time - started < 2400)) {
          raf(animate);
        } else {
          finish();
        }
      };
      if (!loader) {
        onLoadingComplete();
        return;
      }
      raf(animate);
    };

    if (loading) runLoader();

    return () => {
      disposed = true;
      observers.forEach((observer) => observer.disconnect());
      window.removeEventListener('scroll', requestLogoSpeed);
      frameIds.forEach((id) => window.cancelAnimationFrame(id));
      frameIds.clear();
    };
  }, [onLoadingComplete]);

  return null;
}
