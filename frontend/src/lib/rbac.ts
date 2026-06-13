export type SessionRole = 'admin' | 'government' | 'enterprise';

export const GUEST_HOME_PATH = '/enterprise-directory';

export const PUBLIC_GUEST_ROUTES = ['/enterprise-directory', '/matching'] as const;

export const ENTERPRISE_PRIVATE_ROUTES = [
  '/dashboard',
  '/sales-console',
  '/risk',
  '/group-purchase',
  '/quote-pool',
  '/fulfillment',
  '/capacity-calendar',
  '/orders',
  '/favorites',
  '/assets',
  '/settings',
] as const;

export function isPlatformAdmin(role: string | undefined | null): boolean {
  return role === 'admin';
}

export function canAccessGovPortal(role: string | undefined | null): boolean {
  return role === 'admin' || role === 'government';
}

export function loginHomePathForRole(role: string | undefined | null): string {
  if (role === 'government') return '/gov';
  if (role === 'admin') return '/admin/dashboard';
  return '/dashboard';
}

export function redirectPathForUnauthorizedRole(role: string | undefined | null): string {
  return loginHomePathForRole(role);
}

export function isPublicGuestPath(path: string): boolean {
  return PUBLIC_GUEST_ROUTES.some((route) => path === route || path.startsWith(`${route}/`));
}

export function canRoleAccessPath(role: string | undefined | null, path: string | undefined | null): boolean {
  if (!role || !path || !path.startsWith('/')) return false;
  if (path.startsWith('/admin')) return role === 'admin';
  if (path.startsWith('/gov') || path.startsWith('/supervision')) {
    return role === 'admin' || role === 'government';
  }
  if (isPublicGuestPath(path)) return role === 'enterprise';
  if (ENTERPRISE_PRIVATE_ROUTES.some((route) => path === route || path.startsWith(`${route}/`))) {
    return role === 'enterprise';
  }
  return role === 'enterprise';
}
