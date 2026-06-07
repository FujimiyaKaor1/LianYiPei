/** 与鉴权相关的 sessionStorage 前缀（logout 时清除） */
export const SESSION_STORAGE_PREFIX = 'lianyipei:';

export const UNAUTHORIZED_EVENT = 'lianyipei:unauthorized';

export function emitUnauthorized(): void {
  window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
}

export function clearAuthSessionStorage(): void {
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const k = sessionStorage.key(i);
    if (k?.startsWith(SESSION_STORAGE_PREFIX)) {
      sessionStorage.removeItem(k);
    }
  }
}

/** fetch 收到 401 / 403 时调用，触发全局登录弹窗 */
export function notifyIfUnauthorized(response: Response): boolean {
  if (response.status === 401 || response.status === 403) {
    emitUnauthorized();
    return true;
  }
  return false;
}
