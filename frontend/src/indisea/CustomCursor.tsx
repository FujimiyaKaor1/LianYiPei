import { useEffect, useRef } from 'react';

type Rgb = { red: number; green: number; blue: number; alpha: number };

const charcoal = '#262626';
const stone = '#f0edea';

function parseRgb(color: string): Rgb | null {
  const match = color.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+))?\s*\)/i);
  if (!match) return null;
  return {
    red: Number(match[1]),
    green: Number(match[2]),
    blue: Number(match[3]),
    alpha: match[4] === undefined ? 1 : Number(match[4]),
  };
}

function channelLuminance(value: number) {
  const channel = value / 255;
  return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

function isLight(color: Rgb) {
  return channelLuminance(color.red) * 0.2126
    + channelLuminance(color.green) * 0.7152
    + channelLuminance(color.blue) * 0.0722 > 0.4;
}

function reasonUsesDarkPanel(element: Element, x: number, y: number) {
  const reason = element.closest<HTMLElement>('.indisea-reason');
  if (!reason) return false;
  const bounds = reason.getBoundingClientRect();
  return bounds.width <= 640
    ? y < bounds.top + bounds.height * 0.58
    : x < bounds.left + bounds.width * 0.513;
}

export default function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cursor = cursorRef.current;
    if (!cursor) return;

    const finePointer = window.matchMedia('(pointer: fine)');
    let active = false;
    let moveFrame = 0;
    let toneFrame = 0;
    let pointerX = -100;
    let pointerY = -100;

    const paintPosition = () => {
      moveFrame = 0;
      cursor.style.transform = `translate3d(${pointerX - 9}px, ${pointerY - 9}px, 0)`;
    };

    const paintTone = () => {
      toneFrame = 0;
      if (pointerX < 0 || pointerY < 0) return;
      const elements = document.elementsFromPoint(pointerX, pointerY);
      const wordmark = elements.some((element) => element.closest('.indisea-wordmark'));
      cursor.style.mixBlendMode = wordmark ? 'difference' : 'normal';

      for (const element of elements) {
        if (element === cursor || cursor.contains(element)) continue;
        if (reasonUsesDarkPanel(element, pointerX, pointerY)) {
          cursor.style.color = stone;
          return;
        }
        const bounds = element.getBoundingClientRect();
        if (bounds.width < 18 && bounds.height < 18) continue;
        const background = parseRgb(getComputedStyle(element).backgroundColor);
        if (!background || background.alpha < 0.1) continue;
        cursor.style.color = isLight(background) ? charcoal : stone;
        return;
      }

      cursor.style.color = charcoal;
    };

    const requestTone = () => {
      if (!toneFrame) toneFrame = window.requestAnimationFrame(paintTone);
    };

    const onPointerMove = (event: PointerEvent) => {
      pointerX = event.clientX;
      pointerY = event.clientY;
      cursor.classList.add('is-visible');
      if (!moveFrame) moveFrame = window.requestAnimationFrame(paintPosition);
      requestTone();
    };
    const onPointerDown = () => cursor.classList.add('is-pressed');
    const onPointerUp = () => cursor.classList.remove('is-pressed');
    const onPointerLeave = () => cursor.classList.remove('is-visible', 'is-pressed');
    const onWindowBlur = () => cursor.classList.remove('is-visible', 'is-pressed');

    const enable = () => {
      if (active) return;
      active = true;
      document.documentElement.classList.add('indisea-custom-cursor-active');
      window.addEventListener('pointermove', onPointerMove, { passive: true });
      window.addEventListener('pointerdown', onPointerDown, { passive: true });
      window.addEventListener('pointerup', onPointerUp, { passive: true });
      document.addEventListener('pointerleave', onPointerLeave);
      window.addEventListener('blur', onWindowBlur);
      window.addEventListener('scroll', requestTone, { passive: true });
    };

    const disable = () => {
      if (!active) return;
      active = false;
      document.documentElement.classList.remove('indisea-custom-cursor-active');
      cursor.classList.remove('is-visible', 'is-pressed');
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointerup', onPointerUp);
      document.removeEventListener('pointerleave', onPointerLeave);
      window.removeEventListener('blur', onWindowBlur);
      window.removeEventListener('scroll', requestTone);
      window.cancelAnimationFrame(moveFrame);
      window.cancelAnimationFrame(toneFrame);
      moveFrame = 0;
      toneFrame = 0;
    };

    const syncPointerMode = () => finePointer.matches ? enable() : disable();
    finePointer.addEventListener('change', syncPointerMode);
    syncPointerMode();

    return () => {
      finePointer.removeEventListener('change', syncPointerMode);
      disable();
    };
  }, []);

  return <div ref={cursorRef} className="indisea-cursor" aria-hidden="true"><span /></div>;
}
