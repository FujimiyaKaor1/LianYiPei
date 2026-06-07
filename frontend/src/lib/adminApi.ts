/* adminApi.ts — 所有管理员专用 API 的统一封装 */

// 管理员 API 基础路径（Flask admin_panel_bp 前缀为 /admin）
const ADMIN_BASE = '/admin';

async function adminFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const res = await fetch(`${ADMIN_BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 403 || res.status === 401) {
    window.dispatchEvent(new Event('unauthorized'));
  }
  return res;
}

function handleJson<T>(json: T): T {
  return json;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export interface DashboardStats {
  enterprise_count: number;
  supply_count: number;
  demand_count: number;
  product_count: number;
  transaction_count: number;
  alert_count: number;
}

export interface Alert {
  id: number;
  product_name: string;
  message: string;
  level: string;
  dimension: string;
  created_at: string;
}

export interface SchedulerStatus {
  running: boolean;
  message: string;
  jobs: { id: string; name: string; next_run: string | null }[];
}

export interface DataQuality {
  total_enterprises: number;
  dormant_count: number;
  dormant_rate: number;
  complete_profile_count: number;
  complete_rate: number;
}

export const apiDashboard = {
  stats: () =>
    adminFetch('/dashboard/api/stats').then((r) => r.json() as Promise<DashboardStats>),

  alerts: () =>
    adminFetch('/dashboard/api/alerts').then((r) => r.json() as Promise<Alert[]>),

  schedulerStatus: () =>
    adminFetch('/api/scheduler/status').then((r) => r.json() as Promise<SchedulerStatus>),

  dataQuality: () =>
    adminFetch('/api/data-quality').then((r) => r.json() as Promise<DataQuality>),

  generateDemo: (count = 10) =>
    adminFetch('/api/demo/generate', {
      method: 'POST',
      body: JSON.stringify({ count }),
    }).then((r) => r.json()),

  clearDemo: () =>
    adminFetch('/api/demo/clear', {
      method: 'DELETE',
      body: JSON.stringify({ confirm: true }),
    }).then((r) => r.json()),

  runAlerts: () =>
    adminFetch('/dashboard/api/run-alerts', { method: 'POST' }).then((r) => r.json()),
};

// ── Verification ───────────────────────────────────────────────────────────────

export interface VerificationItem {
  id: number;
  name: string;
  address: string;
  contact: string;
  phone: string;
  verification_status: string;
  registered_at: string;
  verified_at: string;
  rejection_reason: string;
}

export interface VerificationPage {
  items: VerificationItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface VerificationStats {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface VerificationDetail {
  id: number;
  name: string;
  address: string;
  contact: string;
  phone: string;
  credit_score: number;
  capacity: number;
  registered_capital: number | null;
  business_scope: string;
  verification_status: string;
  registered_at: string;
  [key: string]: unknown;
}

export const apiVerification = {
  list: (params: { status?: string; page?: number; per_page?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set('status', params.status);
    if (params.page) qs.set('page', String(params.page));
    if (params.per_page) qs.set('per_page', String(params.per_page));
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return adminFetch(`/api/verifications${query}`).then((r) =>
      r.json() as Promise<VerificationPage>,
    );
  },

  detail: (id: number) =>
    adminFetch(`/api/verifications/${id}`).then((r) =>
      r.json() as Promise<VerificationDetail>,
    ),

  stats: () =>
    adminFetch('/api/verifications/stats').then((r) =>
      r.json() as Promise<VerificationStats>,
    ),

  approve: (id: number) =>
    adminFetch(`/api/verifications/${id}/approve`, { method: 'POST' }).then((r) =>
      r.json(),
    ),

  reject: (id: number, reason: string) =>
    adminFetch(`/api/verifications/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }).then((r) => r.json()),

  reset: (id: number) =>
    adminFetch(`/api/verifications/${id}/reset`, { method: 'POST' }).then((r) =>
      r.json(),
    ),
};

// ── Credit Rules ──────────────────────────────────────────────────────────────

export interface CreditRule {
  id: number;
  rule_type: string;
  score_change: number;
  description: string;
  max_per_month: number | null;
  is_active: boolean;
}

export interface AlertThreshold {
  id: number;
  dimension: string;
  threshold_value: number;
  description: string;
  updated_at: string | null;
}

export const apiRules = {
  getCreditRules: () =>
    adminFetch('/api/config/credit-rules').then((r) =>
      r.json() as Promise<{ rules: CreditRule[] }>,
    ),

  addCreditRule: (payload: {
    rule_type: string;
    score_change: number;
    change_reason: string;
  }) =>
    adminFetch('/api/config/credit-rules', {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then((r) => r.json()),

  updateCreditRule: (id: number, payload: { score_change: number; change_reason: string }) =>
    adminFetch(`/api/config/credit-rules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }).then((r) => r.json()),

  deleteCreditRule: (id: number, change_reason: string) =>
    adminFetch(`/api/config/credit-rules/${id}`, {
      method: 'DELETE',
      body: JSON.stringify({ change_reason }),
    }).then((r) => r.json()),

  getAlertThresholds: () =>
    adminFetch('/api/config/alert-thresholds').then((r) =>
      r.json() as Promise<{ thresholds: AlertThreshold[] }>,
    ),

  upsertAlertThreshold: (payload: { dimension: string; threshold_value: number }) =>
    adminFetch('/api/config/alert-thresholds', {
      method: 'POST',
      body: JSON.stringify(payload),
    }).then((r) => r.json()),
};

// ── Risk Center ───────────────────────────────────────────────────────────────

export interface CheckConfig {
  enabled: boolean;
  check_interval_hours: number;
  sample_size: number;
  auto_delist_enabled: boolean;
}

export interface CheckStats {
  total: number;
  active: number;
  abnormal: number;
  dormant: number;
}

export interface CheckHistoryItem {
  id: number;
  enterprise_id: number;
  enterprise_name: string;
  check_time: string;
  result: string;
  details: string;
}

export interface AbnormalEnterprise {
  id: number;
  name: string;
  business_status: string;
  checked_at: string;
}

export const apiRisk = {
  getConfig: () =>
    adminFetch('/api/enterprise-checks/config').then((r) =>
      r.json() as Promise<CheckConfig>,
    ),

  updateConfig: (payload: Partial<CheckConfig>) =>
    adminFetch('/api/enterprise-checks/config', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }).then((r) => r.json()),

  runCheck: () =>
    adminFetch('/api/enterprise-checks/run', { method: 'POST' }).then((r) =>
      r.json(),
    ),

  checkSingle: (id: number) =>
    adminFetch(`/api/enterprise-checks/${id}`, { method: 'POST' }).then((r) =>
      r.json(),
    ),

  restore: (id: number, reason: string) =>
    adminFetch(`/api/enterprise-checks/${id}/restore`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }).then((r) => r.json()),

  history: (limit = 50) =>
    adminFetch(`/api/enterprise-checks/history?limit=${limit}&format=flat`).then((r) =>
      r.json() as Promise<{ history: CheckHistoryItem[] }>,
    ),

  stats: () =>
    adminFetch('/api/enterprise-checks/stats').then((r) =>
      r.json() as Promise<CheckStats>,
    ),

  abnormalList: () =>
    adminFetch('/api/enterprise-checks/abnormal-list').then((r) =>
      r.json() as Promise<{ items: AbnormalEnterprise[] }>,
    ),
};

// ── API Gateway ──────────────────────────────────────────────────────────────

export interface ExternalInterfaceConfig {
  interface_type: string;
  name: string;
  enabled: boolean;
  status: string;
  config: Record<string, unknown>;
}

export interface ApiKey {
  id: number;
  key_name: string;
  /** 运行时创建的 Key 有完整值；环境变量中的 Key 仅有 key_preview */
  key_value?: string;
  key_preview?: string;
  created_at: string | null;
  is_active: boolean;
  rate_limit: number;
}

export const apiGateway = {
  // 注意：adminFetch 已带前缀 /admin，此处勿再写 /admin，否则会请求 /admin/admin/...
  listInterfaces: () =>
    adminFetch('/external-interfaces/api/configs').then((r) =>
      r.json() as Promise<{ success: boolean; data: ExternalInterfaceConfig[] }>,
    ),

  getInterface: (type: string) =>
    adminFetch(`/external-interfaces/api/configs/${encodeURIComponent(type)}`).then((r) =>
      r.json() as Promise<{ success: boolean; data: ExternalInterfaceConfig }>,
    ),

  updateInterface: (type: string, payload: Record<string, unknown>) =>
    adminFetch(`/external-interfaces/api/configs/${encodeURIComponent(type)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }).then((r) => r.json()),

  checkInterface: (type: string) =>
    adminFetch(`/external-interfaces/api/configs/${encodeURIComponent(type)}/check`, {
      method: 'POST',
    }).then((r) => r.json()),

  checkAllInterfaces: () =>
    adminFetch('/external-interfaces/api/configs/check-all', {
      method: 'POST',
    }).then((r) => r.json()),

  listApiKeys: () =>
    adminFetch('/api/api-keys').then((r) =>
      r.json() as Promise<{ api_keys: ApiKey[] }>,
    ),

  createApiKey: (key_name: string) =>
    adminFetch('/api/api-keys', {
      method: 'POST',
      body: JSON.stringify({ key_name }),
    }).then((r) => r.json()),

  disableApiKey: (id: number) =>
    adminFetch(`/api/api-keys/${id}/disable`, { method: 'PUT' }).then((r) =>
      r.json(),
    ),
};

// ── Audit Logs ───────────────────────────────────────────────────────────────

export interface OperationLog {
  id: number;
  user_id: number;
  user_name: string;
  operation: string;
  target_type: string;
  target_id: number | null;
  details: string;
  ip_address: string;
  created_at: string;
}

export const apiAudit = {
  list: () =>
    adminFetch('/api/operation-logs').then((r) =>
      r.json() as Promise<{ total: number; logs: OperationLog[] }>,
    ),
};
