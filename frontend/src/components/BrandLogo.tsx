import React, { useId } from 'react';
import { cn } from '@/src/lib/utils';

interface BrandLogoProps {
  subtitle?: string;
  showText?: boolean;
  sidebar?: boolean;
  className?: string;
  markClassName?: string;
  copyClassName?: string;
  titleClassName?: string;
  subtitleClassName?: string;
}

export function BrandLogo({
  subtitle = '供应链经营工作台',
  showText = true,
  sidebar = false,
  className,
  markClassName,
  copyClassName,
  titleClassName,
  subtitleClassName,
}: BrandLogoProps) {
  const id = useId().replace(/:/g, '');
  const gradientId = `brand-logo-gradient-${id}`;
  const glowId = `brand-logo-glow-${id}`;

  return (
    <div className={cn('flex min-w-0 items-center gap-3', className)}>
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md border border-sidebar-divider bg-brand text-white shadow-elevation-1',
          sidebar && 'sidebar-logo-mark',
          markClassName,
        )}
        aria-hidden="true"
      >
        <svg className="h-full w-full" viewBox="0 0 48 48" role="img">
          <defs>
            <linearGradient id={gradientId} x1="8" x2="40" y1="6" y2="42" gradientUnits="userSpaceOnUse">
              <stop stopColor="#7DD3FC" />
              <stop offset="0.46" stopColor="#2F7CF6" />
              <stop offset="1" stopColor="#155EEF" />
            </linearGradient>
            <radialGradient id={glowId} cx="0" cy="0" r="1" gradientTransform="matrix(19 23 -23 19 17 13)" gradientUnits="userSpaceOnUse">
              <stop stopColor="#FFFFFF" stopOpacity="0.85" />
              <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="48" height="48" rx="12" fill={`url(#${gradientId})`} />
          <rect width="48" height="48" rx="12" fill={`url(#${glowId})`} />
          <path
            d="M18.2 17.7h8.5a6.8 6.8 0 0 1 0 13.6h-3.9"
            fill="none"
            stroke="#FFFFFF"
            strokeLinecap="round"
            strokeWidth="4.2"
          />
          <path
            d="M29.8 30.3h-8.5a6.8 6.8 0 0 1 0-13.6h3.9"
            fill="none"
            stroke="#BFDBFE"
            strokeLinecap="round"
            strokeWidth="4.2"
          />
          <path
            d="M16.4 34.2 31.6 13.8"
            fill="none"
            stroke="#FFFFFF"
            strokeLinecap="round"
            strokeOpacity="0.92"
            strokeWidth="3"
          />
          <circle cx="15.8" cy="34.4" r="3.2" fill="#E0F2FE" />
          <circle cx="32.2" cy="13.6" r="3.2" fill="#FFFFFF" />
        </svg>
      </div>
      {showText && (
        <div className={cn('min-w-0', sidebar && 'sidebar-logo-copy', copyClassName)}>
          <h1 className={cn('truncate text-base font-bold leading-tight text-sidebar-text-active', titleClassName)}>
            链易配
          </h1>
          <span className={cn('block truncate text-[10px] font-semibold text-sidebar-text', subtitleClassName)}>
            {subtitle}
          </span>
        </div>
      )}
    </div>
  );
}
