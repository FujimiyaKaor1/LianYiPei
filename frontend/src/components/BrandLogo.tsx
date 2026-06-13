import React from 'react';
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
  return (
    <div className={cn('flex min-w-0 items-center gap-3', className)}>
      <div
        className={cn(
          'flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md border border-sidebar-divider bg-white shadow-elevation-1',
          sidebar && 'sidebar-logo-mark',
          markClassName,
        )}
        aria-hidden="true"
      >
        <img
          src="/logo.png"
          alt=""
          className="h-full w-full scale-[2.08] object-contain"
          draggable={false}
        />
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
