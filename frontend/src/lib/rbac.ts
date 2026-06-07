export type SessionRole = 'admin' | 'government' | 'enterprise';

export function isPlatformAdmin(role: string | undefined | null): boolean {
  return role === 'admin';
}

export function canAccessGovPortal(role: string | undefined | null): boolean {
  return role === 'admin' || role === 'government';
}

export function loginHomePathForRole(role: string | undefined | null): string {
  if (role === 'government') return '/gov';
  if (role === 'admin') return '/admin/dashboard';
  return '/';
}

export function redirectPathForUnauthorizedRole(role: string | undefined | null): string {
  return loginHomePathForRole(role);
}
