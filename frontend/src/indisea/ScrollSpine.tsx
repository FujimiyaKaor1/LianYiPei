import { useLayoutEffect, useRef } from 'react';

type Point = [number, number];

type SpineAnchor = {
  element: HTMLElement;
  x: number;
  y: number;
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function roundedOrthogonalPath(points: Point[], radius: number) {
  if (points.length === 0) return '';
  let path = `M ${points[0][0]} ${points[0][1]}`;

  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const incoming: Point = [Math.sign(current[0] - previous[0]), Math.sign(current[1] - previous[1])];
    const outgoing: Point = [Math.sign(next[0] - current[0]), Math.sign(next[1] - current[1])];
    const incomingLength = Math.abs(current[0] - previous[0]) + Math.abs(current[1] - previous[1]);
    const outgoingLength = Math.abs(next[0] - current[0]) + Math.abs(next[1] - current[1]);
    const corner = Math.min(radius, incomingLength / 2, outgoingLength / 2);

    path += ` L ${current[0] - incoming[0] * corner} ${current[1] - incoming[1] * corner}`;
    path += ` Q ${current[0]} ${current[1]} ${current[0] + outgoing[0] * corner} ${current[1] + outgoing[1] * corner}`;
  }

  const last = points[points.length - 1];
  return `${path} L ${last[0]} ${last[1]}`;
}

export default function ScrollSpine() {
  const svgRef = useRef<SVGSVGElement>(null);
  const gradientRef = useRef<SVGLinearGradientElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const startRef = useRef<SVGCircleElement>(null);
  const endRef = useRef<SVGCircleElement>(null);

  useLayoutEffect(() => {
    const svg = svgRef.current;
    const gradient = gradientRef.current;
    const path = pathRef.current;
    const start = startRef.current;
    const end = endRef.current;
    const main = svg?.closest('main');
    if (!svg || !gradient || !path || !start || !end || !(main instanceof HTMLElement)) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let pathLength = 0;
    let startY = 0;
    let pathEndY = 1;
    let buildFrame = 0;
    let scrollFrame = 0;

    const relativeTop = (element: HTMLElement, mainTop: number) => (
      element.getBoundingClientRect().top + window.scrollY - mainTop
    );

    const getSection = (name: string) => main.querySelector<HTMLElement>(`[data-spine-section="${name}"]`);
    const getWaypoint = (name: string) => main.querySelector<HTMLElement>(`[data-spine-waypoint="${name}"]`);

    const updateProgress = () => {
      scrollFrame = 0;
      if (!pathLength) return;
      const mainTop = main.getBoundingClientRect().top + window.scrollY;
      const drawingLine = window.scrollY + window.innerHeight * 0.62 - mainTop;
      const progress = reducedMotion.matches ? 1 : clamp((drawingLine - startY) / Math.max(1, pathEndY - startY), 0, 1);
      path.style.strokeDashoffset = String(pathLength * (1 - progress));
      start.style.transform = progress > 0.001 ? 'scale(1)' : 'scale(.4)';
      end.setAttribute('opacity', progress >= 0.999 ? '1' : '0');
      svg.dataset.spineProgress = progress.toFixed(4);
    };

    const requestProgressUpdate = () => {
      if (!scrollFrame) scrollFrame = window.requestAnimationFrame(updateProgress);
    };

    const build = () => {
      buildFrame = 0;
      const hero = getSection('01');
      const cta = getSection('11');
      if (!hero || !cta) return;

      const width = main.clientWidth;
      const height = main.scrollHeight;
      if (!width || !height) return;

      const mainTop = main.getBoundingClientRect().top + window.scrollY;
      const mobile = width <= 640;
      const strokeWidth = width > 1024 ? 32 : width > 640 ? 16 : 8;
      const radius = strokeWidth * 2.5;
      const cornerRadius = strokeWidth * 2;
      const pagePadding = parseFloat(getComputedStyle(hero).paddingLeft) || (mobile ? 20 : 40);
      const contentWidth = Math.max(1, width - pagePadding * 2);
      const fraction = (value: number) => pagePadding + contentWidth * value;
      const edgeInset = Math.max(pagePadding / 2, mobile ? radius + strokeWidth / 2 + 2 : strokeWidth / 2 + 2);
      const rightEdge = width - edgeInset;
      const innerRight = fraction(mobile ? 0.89 : 0.76);
      const innerLeft = fraction(0.28);

      // 起点环放在标题上方右侧；路径永远在内容层下方，避免遮挡首屏文字。
      startY = relativeTop(hero, mainTop) + Math.min(hero.offsetHeight * 0.11, mobile ? 88 : 104);
      const startX = mobile ? rightEdge : fraction(0.84);
      const ctaTop = relativeTop(cta, mainTop);

      const sectionAnchor = (name: string, x: number): SpineAnchor | null => {
        const element = getSection(name);
        if (!element) return null;
        const top = relativeTop(element, mainTop);
        const paddingTop = parseFloat(getComputedStyle(element).paddingTop) || 0;
        return { element, x, y: top + (paddingTop > 90 ? Math.min(120, paddingTop * 0.42) : 36) };
      };

      const waypointAnchor = (name: string, x: number): SpineAnchor | null => {
        const element = getWaypoint(name);
        if (!element) return null;
        const marginTop = parseFloat(getComputedStyle(element).marginTop) || 0;
        return {
          element,
          x,
          y: relativeTop(element, mainTop) - Math.max(20, Math.min(90, marginTop * 0.5)),
        };
      };

      const anchors = (mobile ? [
        sectionAnchor('02', rightEdge),
        sectionAnchor('03', rightEdge),
        waypointAnchor('stats', innerRight),
        sectionAnchor('04', rightEdge),
        sectionAnchor('05', rightEdge),
        waypointAnchor('diagram', innerRight),
        sectionAnchor('07', innerLeft),
        sectionAnchor('08', innerRight),
        sectionAnchor('09', rightEdge),
        waypointAnchor('clients', innerRight),
        sectionAnchor('10', innerRight),
      ] : [
        sectionAnchor('02', fraction(0.25)),
        sectionAnchor('03', fraction(0.25)),
        waypointAnchor('stats', fraction(0.25)),
        sectionAnchor('04', rightEdge),
        sectionAnchor('05', fraction(0.80)),
        waypointAnchor('diagram', fraction(0.80)),
        sectionAnchor('07', fraction(0.50)),
        sectionAnchor('08', fraction(0.25)),
        sectionAnchor('09', fraction(0.25)),
        waypointAnchor('clients', fraction(0.25)),
        sectionAnchor('10', innerRight),
      ]).filter((anchor): anchor is SpineAnchor => anchor !== null).sort((a, b) => a.y - b.y);

      const points: Point[] = [[startX, startY]];
      let currentX = startX;
      let currentY = startY;
      for (const anchor of anchors) {
        const crossingY = Math.max(anchor.y, currentY + cornerRadius * 2.2);
        if (Math.abs(anchor.x - currentX) < 1) continue;
        points.push([currentX, crossingY], [anchor.x, crossingY]);
        currentX = anchor.x;
        currentY = crossingY;
      }

      const endX = mobile ? innerRight : fraction(0.76);
      const ctaCrossingY = Math.max(ctaTop + Math.min(110, Math.max(64, parseFloat(getComputedStyle(cta).paddingTop) * 0.4)), currentY + cornerRadius * 2.2);
      if (Math.abs(endX - currentX) >= 1) {
        points.push([currentX, ctaCrossingY], [endX, ctaCrossingY]);
        currentX = endX;
        currentY = ctaCrossingY;
      }

      const endY = clamp(ctaTop + cta.offsetHeight * 0.5, currentY + radius + cornerRadius, ctaTop + cta.offsetHeight - radius - 24);
      pathEndY = endY - radius;
      points.push([currentX, pathEndY]);

      svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.style.height = `${height}px`;
      gradient.setAttribute('x1', '0');
      gradient.setAttribute('x2', '0');
      gradient.setAttribute('y1', String(ctaTop - 1));
      gradient.setAttribute('y2', String(ctaTop + 1));
      path.setAttribute('d', roundedOrthogonalPath(points, cornerRadius));
      path.setAttribute('stroke-width', String(strokeWidth));
      start.setAttribute('cx', String(startX));
      start.setAttribute('cy', String(startY));
      start.setAttribute('r', String(radius));
      start.setAttribute('stroke-width', String(strokeWidth));
      end.setAttribute('cx', String(currentX));
      end.setAttribute('cy', String(endY));
      end.setAttribute('r', String(radius));
      end.setAttribute('stroke-width', String(strokeWidth));

      pathLength = path.getTotalLength();
      path.style.strokeDasharray = String(pathLength);
      path.style.strokeDashoffset = reducedMotion.matches ? '0' : String(pathLength);
      svg.dataset.spineLength = pathLength.toFixed(2);
      updateProgress();
    };

    const requestBuild = () => {
      if (buildFrame) window.cancelAnimationFrame(buildFrame);
      buildFrame = window.requestAnimationFrame(build);
    };

    const observer = new ResizeObserver(requestBuild);
    observer.observe(main);
    main.querySelectorAll<HTMLElement>('[data-spine-section], [data-spine-waypoint]').forEach((element) => observer.observe(element));
    const images = Array.from(main.querySelectorAll<HTMLImageElement>('img'));
    images.forEach((image) => image.addEventListener('load', requestBuild));
    window.addEventListener('resize', requestBuild);
    window.addEventListener('scroll', requestProgressUpdate, { passive: true });
    reducedMotion.addEventListener('change', requestBuild);
    document.fonts.ready.then(requestBuild).catch(() => undefined);
    requestBuild();

    return () => {
      observer.disconnect();
      images.forEach((image) => image.removeEventListener('load', requestBuild));
      window.removeEventListener('resize', requestBuild);
      window.removeEventListener('scroll', requestProgressUpdate);
      reducedMotion.removeEventListener('change', requestBuild);
      window.cancelAnimationFrame(buildFrame);
      window.cancelAnimationFrame(scrollFrame);
    };
  }, []);

  return (
    <svg ref={svgRef} className="indisea-spine" data-spine aria-hidden="true">
      <defs>
        <linearGradient ref={gradientRef} id="indisea-spine-hue" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--ind-blue)" />
          <stop offset="1" stopColor="var(--ind-stone)" />
        </linearGradient>
      </defs>
      <path ref={pathRef} data-spine-path fill="none" stroke="url(#indisea-spine-hue)" strokeLinecap="round" strokeLinejoin="round" />
      <circle ref={startRef} data-spine-start fill="var(--ind-bg)" stroke="var(--ind-blue)" />
      <circle ref={endRef} data-spine-end fill="var(--ind-blue)" stroke="var(--ind-stone)" opacity="0" />
    </svg>
  );
}
