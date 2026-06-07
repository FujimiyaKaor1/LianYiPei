export interface ApiResponse<T> {
  code: number;
  message?: string;
  data: T;
  timestamp?: string;
}

/** 与 Flask `GET /api/credit/score/<id>` 的 jsonify 字段对齐（无外层 code/data 包装） */
export interface CreditScoreData {
  success?: boolean;
  enterprise_id?: number;
  credit_score: number;
  level: string;
  privileges?: Record<string, unknown>;
}

export interface CreditHistoryRecord {
  id: string;
  old_score: number;
  new_score: number;
  change_value: number;
  change_type: string;
  reason: string;
  created_at: string;
}

export interface CreditHistoryResponse {
  success?: boolean;
  total: number;
  limit: number;
  offset: number;
  records: CreditHistoryRecord[];
}

export interface AlertData {
  id: number;
  product_name: string;
  message: string;
  level: string;
  alert_type: string;
  suggestion?: string;
  created_at?: string;
  // 链小易 AI 风险深度分析字段（后端 analysis_data 展开）
  risk_reason?: string;
  impact_scope?: string;
  ai_suggestions?: string[];
  data_source_info?: {
    name?: string;
    node_id?: string;
    last_sync?: string;
  };
  historical_trend?: number[];
}

export interface AlertsPayload {
  total: number;
  alerts: AlertData[];
}

export interface RagIngestResult {
  file_path: string;
  pages: number;
  chunks: number;
  inserted_ids: number;
  persist_directory: string;
  collection_name: string;
  embedding_model: string;
}

export interface RagIngestResponse {
  ok: boolean;
  message?: string;
  data?: RagIngestResult;
  error?: string;
}

export interface InvoiceUploadResponse {
  success: boolean;
  message?: string;
  error?: string;
  manual_review_required?: boolean;
  fulfillment_id?: number;
  invoice_info?: {
    invoice_no?: string;
    amount?: number;
    date?: string;
    buyer?: string;
    seller?: string;
  };
}

export interface SupplierSearchParams {
  query?: string;
  tag?: string;
  sort?: 'score' | 'credit' | 'distance';
  delivery_days?: number;
  min_credit?: string | number;
  algorithm?: 'rule' | 'deep_learning';
  model_choice?: 'qwen' | 'deepseek';
}

export interface SupplierSearchItem {
  id: number;
  name: string;
  address: string;
  credit_score: number;
  score: number;
  match: string;
  desc: string;
  tags: string[];
  distance_km?: number | string;
  ai_match_reason?: string;
  deep_learning_score?: number;
  deep_learning_explain?: string;
  confidence_index?: number;
  match_basis?: 'semantic' | 'rule';
}

export interface SupplierSearchResponse {
  query: string;
  tag: string;
  sort: string;
  is_basic_match?: boolean;
  fallback_reason?: string | null;
  count: number;
  suppliers: SupplierSearchItem[];
}

export interface EnterpriseDirectoryItem {
  id: number;
  name: string;
  address: string;
  province: string;
  city: string;
  credit_score: number;
  business_scope: string;
  industry_code: string;
}

export interface EnterpriseDirectoryResponse {
  count: number;
  enterprises: EnterpriseDirectoryItem[];
}

export interface SalesMessageItem {
  id: number;
  type: string;
  title: string;
  content: string;
  link_url?: string;
  is_read: boolean;
  priority?: string;
  mode?: 'procurement' | 'sales';
  created_at?: string | null;
}

export interface SalesMessagesResponse {
  success: boolean;
  total: number;
  unread_count: number;
  page: number;
  per_page: number;
  messages: SalesMessageItem[];
}

/** POST /api/messages — 向指定企业发送站内信（意向报价回执等） */
export interface PostSalesMessagePayload {
  receiver_id: number;
  title?: string;
  content?: string;
  quote_price?: number | string;
  delivery_days?: number | string;
  inquiry_id?: number;
  product_name?: string;
  /** 消息视角模式：procurement（采购模式）/ sales（销售模式），默认 procurement */
  mode?: 'procurement' | 'sales';
}

export interface PostSalesMessageResponse {
  success: boolean;
  message_id: number;
  unread_count?: number;
}

export interface PriceIndexResponse {
  product_name: string;
  median_price?: number | null;
  mean_price?: number | null;
  std_dev?: number | null;
  min_price?: number | null;
  max_price?: number | null;
  sample_count: number;
  data_source?: string;
  last_updated?: string | null;
  is_cold_start?: boolean;
  history?: { name: string; price: number }[];
  note?: string;
  message?: string;
}

export interface InquiryPayload {
  supplier_id: number;
  product_name: string;
  content: string;
  dim_scores?: Record<string, number>;
  match_score?: number;
  session_id?: string;
}

export interface InquiryResponse {
  success: boolean;
  inquiry_id: number;
  match_feedback_id: number;
}

export interface OrderItem {
  id: number;
  order_no: string;
  product_name: string;
  quantity: number;
  unit: string;
  customer_name: string;
  order_date: string | null;
  delivery_date: string | null;
  actual_delivery_date: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  notes: string;
}

export interface OrdersResponse {
  success: boolean;
  orders: OrderItem[];
  total: number;
  page: number;
  pages: number;
}

export interface OrderStatistics {
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  cancelled: number;
}

export interface OrderCreatePayload {
  product_name: string;
  quantity: number;
  unit: string;
  customer_name: string;
  order_date: string;
  delivery_date?: string;
  notes?: string;
}

/** POST /orders/:id/update-status 请求体（与 Flask orders.update_status 对齐） */
export interface OrderStatusUpdatePayload {
  status: string;
  actual_delivery_date?: string;
}

export interface OrderStatusUpdateResponse {
  success: boolean;
  message?: string;
}

export interface GroupPurchaseItem {
  id: number;
  product_name: string;
  target_quantity: number | null;
  current_quantity: number | null;
  participant_count: number | null;
  deadline: string | null;
  min_credit_score: number | null;
}

export interface GroupPurchasesResponse {
  group_purchases: GroupPurchaseItem[];
}

export interface QuoteListItem {
  id: number;
  product_name: string;
  supplier_name: string;
  price: number;
  quantity: number | null;
  unit: string | null;
  delivery_days: number | null;
  status: string;
  created_at: string | null;
}

export interface QuoteListResponse {
  success: boolean;
  quotes: QuoteListItem[];
  total: number;
  page: number;
}

// ═══════════════════════════════════════════════════════════════════════════════════════
// 新增：收藏相关类型
// ═══════════════════════════════════════════════════════════════════════════════════════

export interface FavoriteSupplierItem {
  id: number;
  supplier_id: number;
  supplier_name: string;
  supplier_province: string;
  supplier_city: string;
  supplier_industry: string;
  capacity: number;
  credit_score: number;
  is_green_factory: boolean;
  patent_count: number;
  match_score: number | null;
  product_name: string;
  notes: string;
  created_at: string | null;
}

export interface FavoritesResponse {
  success: boolean;
  total: number;
  favorites: FavoriteSupplierItem[];
}

export interface FavoritesApiResponse {
  success: boolean;
  favorite_id?: number;
  message?: string;
  total?: number;
  favorites?: FavoriteSupplierItem[];
}

// ═══════════════════════════════════════════════════════════════════════════════════════
// 新增：意向报价相关类型
// ═══════════════════════════════════════════════════════════════════════════════════════

export interface IntentQuoteItem {
  id: number;
  chat_id: number | null;
  buyer_id: number;
  buyer_name: string;
  seller_id: number;
  seller_name: string;
  product_name: string;
  quantity: number | null;
  unit: string;
  target_price: number | null;
  budget_range: string | null;
  ai_suggested_price: number | null;
  ai_price_basis: string | null;
  ai_delivery_estimate: string | null;
  status: string;
  buyer_confirmed: boolean;
  seller_confirmed: boolean;
  seller_reply_price: number | null;
  seller_reply_notes: string | null;
  is_buyer: boolean;
  created_at: string | null;
  expires_at: string | null;
}

export interface IntentQuoteListResponse {
  success: boolean;
  total: number;
  quotes: IntentQuoteItem[];
}

export interface IntentQuoteResponse {
  success: boolean;
  quote_id: number;
  status: string;
  message?: string;
}

export interface AIQuoteSuggestion {
  suggested_price: number;
  price_range: { min: number; max: number };
  delivery_estimate: string;
  basis: string;
  capacity_available: boolean;
  median_price?: number;
  credit_score?: number;
  capacity_ratio?: number;
}

export interface AIQuoteSuggestionResponse {
  success: boolean;
  suggestion: AIQuoteSuggestion;
}

export interface EnterpriseProfile {
  enterprise_id: number;
  name: string;
  industry_code: string;
  province: string;
  city: string;
  main_products: string;
  capacity_status: string;
  capacity_usage: string;
  credit_score: number;
  credit_level: string;
  green_level: string;
  patent_count: number;
  cooperation_risk: string;
  registered_capital: string;
}

export interface EnterpriseProfileResponse {
  success: boolean;
  profile: EnterpriseProfile;
}

export interface BusinessInsightMessage {
  type: string;
  enterprise_id: number;
  enterprise_name: string;
  insight_summary: string;
  enterprise_profile: EnterpriseProfile;
  actions: {
    generate_quote: {
      enabled: boolean;
      label: string;
      description: string;
    };
  };
}

export interface BusinessInsightResponse {
  success: boolean;
  insight: BusinessInsightMessage;
}

// 覆盖旧类型
export interface FavoriteSupplier extends FavoriteSupplierItem {}

export interface FavoritesResponse {
  success: boolean;
  total: number;
  favorites: FavoriteSupplierItem[];
}

export interface EnterpriseAssetData {
  id: number;
  name: string;
  is_certified: boolean;
  location: string;
  industry_tag: string;
  tags: string[];
  credit_score: number;
  patent_count: number;
  qualifications: {
    title: string;
    date: string;
    status: string;
  }[];
  data_auth: {
    name: string;
    status: string;
    data: string;
  }[];
  team_members: {
    name: string;
    role: string;
    avatar: string;
  }[];
  credit_breakdown: {
    label: string;
    score: number;
  }[];
}

export interface AssetsResponse {
  success: boolean;
  assets: EnterpriseAssetData;
}

export interface UserSettingsData {
  name: string;
  role: string;
  email: string;
  phone: string;
  business_scope: string;
}

export interface UserSettingsResponse {
  success: boolean;
  settings: UserSettingsData;
}

export interface QuoteSubmitPayload {
  inquiry_id: number;
  /** 后端报价金额：可与单价×数量一致 */
  price: number;
  product_name?: string;
  quantity?: number;
  unit?: string;
  delivery_days?: number;
  remarks?: string;
}

export interface QuoteSubmitResponse {
  success: boolean;
  quote_id: number;
  remaining_quotes_today: number | string;
}

/** 销售控制台意向报价表单（前端本地状态，提交时组装为 QuoteSubmitPayload） */
export interface SalesQuoteFormValues {
  inquiryId: string;
  unitPrice: string;
  deliveryDays: string;
  remarks: string;
}

export interface OpportunityScoreResult {
  score: number;
  supplier?: SupplierSearchItem;
}

export interface CreditRiskResult {
  credit_score: number;
  level: string;
  risk_level: '低风险' | '中风险' | '高风险';
  risk_text: string;
}

import { emitUnauthorized } from '@/src/lib/authEvents';

/** 普通接口默认超时 */
const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;
/**
 * 匹配/深度思考：后端可能加载 sentence-transformers、调用本地 LLM，冷启动可远超 10s
 * 与 vite dev proxy 的 timeout/proxyTimeout 对齐（180s）
 */
const MATCHING_SEARCH_TIMEOUT_MS = 180_000;
const NETWORK_ERROR_MESSAGE = '网络请求失败，请检查后端服务';

class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/** 是否像「外层 code/message + data」的网关包装（避免把业务字段里恰好叫 data 的对象误判为包装） */
function looksLikeEnvelope(o: Record<string, unknown>): boolean {
  if (!('data' in o)) return false;
  return (
    'code' in o ||
    'success' in o ||
    'message' in o ||
    'msg' in o
  );
}

/**
 * 统一解析：Flask 直出对象、或 { code:200|0, data } / { success, data } 等包装。
 * 本项目使用原生 fetch，无 Axios；此前若网关返回 code=0 会误触发 code!==200 而抛错。
 */
function normalizeSuccessPayload<T>(payload: unknown): T {
  if (typeof payload !== 'object' || payload === null) {
    return payload as T;
  }
  const o = payload as Record<string, unknown>;

  if (!looksLikeEnvelope(o)) {
    return payload as T;
  }

  if (o.success === false) {
    const msg =
      (typeof o.message === 'string' && o.message) ||
      (typeof o.msg === 'string' && o.msg) ||
      NETWORK_ERROR_MESSAGE;
    throw new ApiError(msg);
  }

  const rawCode = o.code;
  const codeNum =
    typeof rawCode === 'number'
      ? rawCode
      : typeof rawCode === 'string' && /^-?\d+$/.test(String(rawCode).trim())
        ? Number(String(rawCode).trim())
        : null;

  const okByCode = codeNum === 200 || codeNum === 0;
  const errByCode = codeNum !== null && !okByCode;

  if (errByCode) {
    const msg =
      (typeof o.message === 'string' && o.message) ||
      (typeof o.msg === 'string' && o.msg) ||
      NETWORK_ERROR_MESSAGE;
    throw new ApiError(msg);
  }

  if (okByCode || o.success === true) {
    return o.data as T;
  }

  if (codeNum === null && o.success !== false) {
    return o.data as T;
  }

  return payload as T;
}

function messageFromErrorBody(payload: unknown): string | null {
  if (typeof payload !== 'object' || payload === null) return null;
  const o = payload as Record<string, unknown>;
  if (typeof o.message === 'string' && o.message.trim()) return o.message;
  if (typeof o.error === 'string' && o.error.trim()) return o.error;
  if (typeof o.error === 'object' && o.error !== null) {
    const errObj = o.error as Record<string, unknown>;
    if (typeof errObj.message === 'string' && errObj.message.trim()) return errObj.message;
  }
  return null;
}

export type RequestOptions = {
  /** 毫秒；<=0 表示不设客户端超时（不推荐用于一般接口） */
  timeoutMs?: number;
};

async function request<T>(
  path: string,
  init?: RequestInit,
  options?: RequestOptions,
): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs > 0) {
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }

  try {
    const response = await fetch(path, {
      ...init,
      credentials: init?.credentials ?? 'include',
      signal: timeoutMs > 0 ? controller.signal : init?.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {}),
      },
    });

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (response.status === 401 || response.status === 403) {
      emitUnauthorized();
    }

    if (!response.ok) {
      throw new ApiError(
        messageFromErrorBody(payload) || NETWORK_ERROR_MESSAGE,
      );
    }

    if (payload === null) {
      throw new ApiError(NETWORK_ERROR_MESSAGE);
    }

    return normalizeSuccessPayload<T>(payload);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('请求超时，请稍后重试');
    }

    throw new ApiError(NETWORK_ERROR_MESSAGE);
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
  }
}

export const api = {
  fetchCreditScore(enterpriseId: number | string) {
    return request<CreditScoreData>(`/api/credit/score/${enterpriseId}`);
  },

  fetchCreditHistory(enterpriseId: number | string, params?: { limit?: number; offset?: number }) {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    if (params?.offset !== undefined) query.set('offset', String(params.offset));
    const suffix = query.toString();
    const url = suffix
      ? `/api/credit/history/${enterpriseId}?${suffix}`
      : `/api/credit/history/${enterpriseId}`;
    return request<CreditHistoryResponse>(url);
  },

  getCreditScore(enterpriseId: number | string) {
    return request<CreditScoreData>(`/api/credit/score/${enterpriseId}`);
  },

  getAlerts(params?: { page?: number; per_page?: number }, options?: RequestOptions) {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.per_page) query.set('per_page', String(params.per_page));

    const suffix = query.toString();
    const url = suffix ? `/api/alerts?${suffix}` : '/api/alerts';
    return request<AlertsPayload>(url, undefined, options);
  },

  fetchSuppliers(params?: SupplierSearchParams) {
    const query = new URLSearchParams();
    if (params?.query) query.set('query', params.query);
    if (params?.tag) query.set('tag', params.tag);
    if (params?.sort) query.set('sort', params.sort);
    if (params?.delivery_days !== undefined) {
      query.set('delivery_days', String(params.delivery_days));
    }
    if (params?.min_credit !== undefined && params.min_credit !== '') {
      query.set('min_credit', String(params.min_credit));
    }
    if (params?.algorithm) {
      query.set('algorithm', params.algorithm);
    }
    if (params?.model_choice) {
      query.set('model_choice', params.model_choice);
    }

    const suffix = query.toString();
    const url = suffix ? `/api/matching/search?${suffix}` : '/api/matching/search';
    return request<SupplierSearchResponse>(url, undefined, {
      timeoutMs: MATCHING_SEARCH_TIMEOUT_MS,
    });
  },

  fetchEnterpriseDirectory(params?: {
    province?: string;
    industry?: string;
    q?: string;
    min_credit?: number;
    limit?: number;
  }) {
    const query = new URLSearchParams();
    if (params?.province) query.set('province', params.province);
    if (params?.industry) query.set('industry', params.industry);
    if (params?.q) query.set('q', params.q);
    if (params?.min_credit !== undefined && params.min_credit !== null) {
      query.set('min_credit', String(params.min_credit));
    }
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    const suffix = query.toString();
    const url = suffix ? `/api/enterprises/directory?${suffix}` : '/api/enterprises/directory';
    return request<EnterpriseDirectoryResponse>(url);
  },

  fetchSalesMessages(params?: {
    type?: string;
    is_read?: 'true' | 'false';
    mode?: 'procurement' | 'sales';
    page?: number;
    per_page?: number;
  }) {
    const query = new URLSearchParams();
    if (params?.type) query.set('type', params.type);
    if (params?.is_read !== undefined) query.set('is_read', params.is_read);
    if (params?.mode) query.set('mode', params.mode);
    if (params?.page !== undefined) query.set('page', String(params.page));
    if (params?.per_page !== undefined) query.set('per_page', String(params.per_page));
    const suffix = query.toString();
    const url = suffix ? `/api/messages?${suffix}` : '/api/messages';
    return request<SalesMessagesResponse>(url);
  },

  markSalesMessageRead(messageId: number) {
    return request<{ success: boolean; unread_count: number }>(`/api/messages/${messageId}/read`, {
      method: 'PUT',
    });
  },

  postSalesMessage(payload: PostSalesMessagePayload) {
    return request<PostSalesMessageResponse>('/api/messages', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  submitQuote(payload: QuoteSubmitPayload) {
    return request<QuoteSubmitResponse>('/api/quotes', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  fetchPriceIndex(productName: string) {
    return request<PriceIndexResponse>(`/api/price-index/${encodeURIComponent(productName)}`);
  },

  sendInquiry(payload: InquiryPayload) {
    return request<InquiryResponse>('/api/inquiry/send', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async fetchOpportunityScore(params: {
    query: string;
    sort?: 'score' | 'credit' | 'distance';
    min_credit?: string | number;
  }): Promise<OpportunityScoreResult> {
    const result = await this.fetchSuppliers({
      query: params.query,
      sort: params.sort ?? 'score',
      min_credit: params.min_credit,
    });
    const best = (result.suppliers || [])[0];
    return {
      score: Math.round(Number(best?.score || 0)),
      supplier: best,
    };
  },

  async fetchCreditRisk(enterpriseId: number | string): Promise<CreditRiskResult> {
    const scoreData = await this.fetchCreditScore(enterpriseId);
    const score = Number(scoreData.credit_score || 0);
    let riskLevel: CreditRiskResult['risk_level'] = '中风险';
    let riskText = '信用表现一般，建议谨慎合作并关注账期。';
    if (score >= 85) {
      riskLevel = '低风险';
      riskText = '信用表现优秀，违约风险较低。';
    } else if (score < 70) {
      riskLevel = '高风险';
      riskText = '信用表现偏弱，建议设置更严格的履约条件。';
    }
    return {
      credit_score: score,
      level: scoreData.level || '一般',
      risk_level: riskLevel,
      risk_text: riskText,
    };
  },

  async uploadPdfForRag(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/rag/ingest', {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });

    let payload: RagIngestResponse | null = null;
    try {
      payload = (await response.json()) as RagIngestResponse;
    } catch {
      payload = null;
    }

    if (response.status === 401 || response.status === 403) {
      emitUnauthorized();
    }

    if (!response.ok) {
      throw new ApiError(
        messageFromErrorBody(payload) || payload?.error || NETWORK_ERROR_MESSAGE,
      );
    }

    if (!payload) {
      throw new ApiError(NETWORK_ERROR_MESSAGE);
    }

    return payload;
  },

  async uploadInvoice(file: File, payload: {
    seller_id: number;
    invoice_no: string;
    invoice_date: string;
    invoice_amount: number;
    invoice_code?: string;
    collaboration_code?: string;
    delivery_date?: string;
    quality_rating?: number;
    buyer_tax_no?: string;
    seller_tax_no?: string;
  }) {
    const formData = new FormData();
    // 第三参保留原始文件名；multipart 不要手写 Content-Type（否则无 boundary）
    formData.append('file', file, file.name);
    formData.append('seller_id', String(payload.seller_id));
    formData.append('invoice_no', payload.invoice_no);
    formData.append('invoice_date', payload.invoice_date);
    formData.append('invoice_amount', String(payload.invoice_amount));
    if (payload.invoice_code) formData.append('invoice_code', payload.invoice_code);
    if (payload.collaboration_code) formData.append('collaboration_code', payload.collaboration_code);
    if (payload.delivery_date) formData.append('delivery_date', payload.delivery_date);
    if (payload.quality_rating !== undefined) formData.append('quality_rating', String(payload.quality_rating));
    if (payload.buyer_tax_no) formData.append('buyer_tax_no', payload.buyer_tax_no);
    if (payload.seller_tax_no) formData.append('seller_tax_no', payload.seller_tax_no);

    const response = await fetch('/api/invoice/upload', {
      method: 'POST',
      credentials: 'include',
      body: formData,
      // 禁止手动设置 multipart Content-Type，否则会丢失 boundary
    });

    let result: InvoiceUploadResponse | null = null;
    try {
      result = (await response.json()) as InvoiceUploadResponse;
    } catch {
      result = null;
    }

    if (response.status === 401 || response.status === 403) {
      emitUnauthorized();
    }

    if (!response.ok) {
      throw new ApiError(
        messageFromErrorBody(result) || result?.error || NETWORK_ERROR_MESSAGE,
      );
    }

    if (!result) {
      throw new ApiError(NETWORK_ERROR_MESSAGE);
    }

    if (result.success === false) {
      throw new ApiError(result.error || result.message || NETWORK_ERROR_MESSAGE);
    }

    return result;
  },

  getOrders(params?: { page?: number; status?: string }) {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.status) query.set('status', params.status);
    const suffix = query.toString();
    const url = suffix ? `/api/orders?${suffix}` : '/api/orders';
    return request<OrdersResponse>(url);
  },

  getOrderStatistics() {
    return request<{ success: boolean; statistics: OrderStatistics }>('/api/orders/statistics');
  },

  createOrder(payload: OrderCreatePayload) {
    return request<{ success: boolean; order: OrderItem }>('/api/orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  updateOrderStatus(orderId: number, status: string, actualDeliveryDate?: string) {
    const body: OrderStatusUpdatePayload = { status };
    if (actualDeliveryDate) body.actual_delivery_date = actualDeliveryDate;
    return request<OrderStatusUpdateResponse>(`/orders/${orderId}/update-status`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  exportOrders(params?: { status?: string; start_date?: string; end_date?: string }) {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const suffix = query.toString();
    const url = suffix ? `/orders/export?${suffix}` : '/orders/export';
    window.open(url, '_blank', 'noopener,noreferrer');
  },

  getGroupPurchases() {
    return request<GroupPurchasesResponse>('/api/group-purchases');
  },

  joinGroupPurchase(gpId: number, quantity: number) {
    return request<{ success: boolean; total_quantity: number; participants: number }>(
      `/api/group-purchases/${gpId}/join`,
      { method: 'POST', body: JSON.stringify({ quantity }) },
    );
  },

  getQuotesList(params?: { page?: number; per_page?: number }) {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.per_page) query.set('per_page', String(params.per_page));
    const suffix = query.toString();
    const url = suffix ? `/api/quotes?${suffix}` : '/api/quotes';
    return request<QuoteListResponse>(url);
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 企业端：收藏供应商（新API）
  // ═══════════════════════════════════════════════════════════════════════

  /** GET /api/favorites/list — 获取收藏列表 */
  getFavorites(params?: { limit?: number; offset?: number }) {
    const q = new URLSearchParams();
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    const suffix = q.toString();
    const url = suffix ? `/api/favorites/list?${suffix}` : '/api/favorites/list';
    return request<FavoritesResponse>(url);
  },

  /** POST /api/favorites/add — 添加收藏 */
  addFavorite(data: {
    supplier_id: number;
    product_name?: string;
    match_score?: number;
    notes?: string;
  }) {
    return request<{ success: boolean; favorite_id?: number; message?: string }>('/api/favorites/add', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** POST /api/favorites/remove — 取消收藏 */
  removeFavoriteById(supplierId: number) {
    return request<{ success: boolean; message: string }>('/api/favorites/remove', {
      method: 'POST',
      body: JSON.stringify({ supplier_id: supplierId }),
    });
  },

  /** GET /api/favorites/check/:id — 检查是否收藏 */
  checkFavorite(supplierId: number) {
    return request<{ success: boolean; is_favorited: boolean }>(`/api/favorites/check/${supplierId}`);
  },

  /** PUT /api/favorites/notes — 更新备注 */
  updateFavoriteNotes(supplierId: number, notes: string) {
    return request<{ success: boolean; message: string }>('/api/favorites/notes', {
      method: 'PUT',
      body: JSON.stringify({ supplier_id: supplierId, notes }),
    });
  },

  /** POST /api/favorites/batch-inquiry — 批量询价 */
  batchFavoriteInquiry(supplierIds: number[], productName: string) {
    return request<{
      success: boolean;
      results: { success: number; failed: number; errors: string[] };
    }>('/api/favorites/batch-inquiry', {
      method: 'POST',
      body: JSON.stringify({ supplier_ids: supplierIds, product_name: productName }),
    });
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 企业端：意向报价（新API）
  // ═══════════════════════════════════════════════════════════════════════

  /** POST /api/intent-quote/create — 创建意向报价 */
  createIntentQuote(data: {
    seller_id: number;
    product_name: string;
    chat_id?: number;
    match_record_id?: number;
    quantity?: number;
    unit?: string;
    target_price?: number;
    budget_range?: string;
  }) {
    return request<IntentQuoteResponse>('/api/intent-quote/create', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** GET /api/intent-quote/:id — 获取意向报价详情 */
  getIntentQuote(quoteId: number) {
    return request<{ success: boolean; quote: IntentQuoteItem }>(`/api/intent-quote/${quoteId}`);
  },

  /** POST /api/intent-quote/:id/send — 发送意向报价 */
  sendIntentQuote(quoteId: number) {
    return request<IntentQuoteResponse>(`/api/intent-quote/${quoteId}/send`, {
      method: 'POST',
    });
  },

  /** POST /api/intent-quote/:id/cancel — 取消意向报价 */
  cancelIntentQuote(quoteId: number) {
    return request<{ success: boolean; message: string }>(`/api/intent-quote/${quoteId}/cancel`, {
      method: 'POST',
    });
  },

  /** POST /api/intent-quote/:id/accept — 供应商接受意向报价 */
  acceptIntentQuote(quoteId: number, replyPrice?: number, replyNotes?: string) {
    return request<IntentQuoteResponse>(`/api/intent-quote/${quoteId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ reply_price: replyPrice, reply_notes: replyNotes }),
    });
  },

  /** POST /api/intent-quote/:id/reject — 供应商拒绝意向报价 */
  rejectIntentQuote(quoteId: number, reason?: string) {
    return request<IntentQuoteResponse>(`/api/intent-quote/${quoteId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },

  /** GET /api/intent-quote/buyer/list — 采购方意向报价列表 */
  getBuyerIntentQuotes(params?: { status?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    const suffix = q.toString();
    const url = suffix ? `/api/intent-quote/buyer/list?${suffix}` : '/api/intent-quote/buyer/list';
    return request<IntentQuoteListResponse>(url);
  },

  /** GET /api/intent-quote/seller/list — 供应方意向报价列表 */
  getSellerIntentQuotes(params?: { status?: string; limit?: number; offset?: number }) {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    const suffix = q.toString();
    const url = suffix ? `/api/intent-quote/seller/list?${suffix}` : '/api/intent-quote/seller/list';
    return request<IntentQuoteListResponse>(url);
  },

  /** POST /api/intent-quote/ai-suggestion — AI意向报价建议 */
  getAIQuoteSuggestion(data: { seller_id: number; product_name: string; quantity?: number }) {
    return request<AIQuoteSuggestionResponse>('/api/intent-quote/ai-suggestion', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** POST /api/intent-quote/:id/apply-ai-suggestion — 应用AI建议到意向报价 */
  applyAIQuoteSuggestion(quoteId: number, suggestion: AIQuoteSuggestion) {
    return request<{ success: boolean; message: string }>(`/api/intent-quote/${quoteId}/apply-ai-suggestion`, {
      method: 'POST',
      body: JSON.stringify({
        suggested_price: suggestion.suggested_price,
        price_basis: suggestion.basis,
        delivery_estimate: suggestion.delivery_estimate,
      }),
    });
  },

  /** GET /api/intent-quote/:id/card-eligible — 检查名片交换资格 */
  checkCardExchangeEligibility(quoteId: number) {
    return request<{ success: boolean; can_exchange: boolean; reason: string }>(
      `/api/intent-quote/${quoteId}/card-eligible`,
    );
  },

  /** GET /api/intent-quote/enterprise-profile/:id — 企业公开画像 */
  getEnterprisePublicProfile(enterpriseId: number) {
    return request<EnterpriseProfileResponse>(`/api/intent-quote/enterprise-profile/${enterpriseId}`);
  },

  /** POST /api/intent-quote/business-insight — AI商机洞察消息 */
  getBusinessInsight(data: { enterprise_id: number; product_name: string }) {
    return request<BusinessInsightResponse>('/api/intent-quote/business-insight', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** GET /api/intent-quote/recommendation/:id — AI匹配推荐理由 */
  getAIRecommendation(enterpriseId: number, productName?: string, matchScore?: number) {
    const q = new URLSearchParams();
    if (productName) q.set('product_name', productName);
    if (matchScore !== undefined) q.set('match_score', String(matchScore));
    const suffix = q.toString();
    const url = suffix
      ? `/api/intent-quote/recommendation/${enterpriseId}?${suffix}`
      : `/api/intent-quote/recommendation/${enterpriseId}`;
    return request<{ success: boolean; recommendation: string }>(url);
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 兼容旧API（保留但标记废弃）
  // ═══════════════════════════════════════════════════════════════════════

  getFavoritesLegacy() {
    return request<FavoritesResponse>('/api/favorites');
  },

  addFavoriteLegacy(supplierId: number) {
    return request<{ success: boolean; message: string }>(`/api/favorites/${supplierId}`, {
      method: 'POST',
    });
  },

  removeFavoriteLegacy(supplierId: number) {
    return request<{ success: boolean; message: string }>(`/api/favorites/${supplierId}`, {
      method: 'DELETE',
    });
  },

  getAssets() {
    return request<AssetsResponse>('/api/user/assets');
  },

  getUserSettings() {
    return request<UserSettingsResponse>('/api/user/settings');
  },

  updateUserSettings(data: Partial<UserSettingsData>) {
    return request<{ success: boolean; message: string }>('/api/user/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  logout() {
    return request<{ ok: boolean }>('/api/logout', { method: 'POST' });
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 企业端：履约看板 & 案例库
  // ═══════════════════════════════════════════════════════════════════════

  getFulfillmentDashboard() {
    return request<FulfillmentDashboardData>('/api/fulfillment');
  },

  getCaseLibrary() {
    return request<{ success: boolean; cases: CaseItem[] }>('/api/fulfillment/cases');
  },

  toggleCaseVisibility(caseId: number, isPublic: boolean) {
    return request<{ success: boolean; is_public: boolean }>(
      `/api/fulfillment/cases/${caseId}/toggle`,
      { method: 'POST', body: JSON.stringify({ is_public: isPublic }) },
    );
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 企业端：产能日历
  // ═══════════════════════════════════════════════════════════════════════

  getCapacityCalendar(year: number, month: number, options?: RequestOptions) {
    const q = new URLSearchParams({ year: String(year), month: String(month) });
    return request<CapacityCalendarData>(`/api/capacity?${q.toString()}`, undefined, {
      timeoutMs: 30_000,
      ...options,
    });
  },

  getOrdersByDate(dateStr: string) {
    return request<{ success: boolean; orders: OrderItem[]; date: string }>(
      `/api/orders-by-date/${encodeURIComponent(dateStr)}`,
    );
  },

  updateCalendarVisibility(visibility: string) {
    return request<{ success: boolean; message: string }>(
      '/api/calendar-visibility',
      { method: 'POST', body: JSON.stringify({ visibility }) },
    );
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 企业端：微信推送
  // ═══════════════════════════════════════════════════════════════════════

  bindWechat(data: { wechat_type: string; wechat_openid: string; wechat_userid?: string }) {
    return request<{ success: boolean; message: string }>('/api/wechat/bind', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  bindWechatOpenId(openid: string) {
    return request<{ success: boolean; message: string }>('/api/wechat/bind-openid', {
      method: 'POST',
      body: JSON.stringify({ openid }),
    });
  },

  unbindWechat() {
    return request<{ success: boolean; message: string }>('/api/wechat/unbind', {
      method: 'POST',
    });
  },

  setWechatPreference(preference: 'all' | 'urgent_only' | 'off') {
    return request<{ success: boolean; message: string }>('/api/wechat/preference', {
      method: 'POST',
      body: JSON.stringify({ preference }),
    });
  },

  testWechatPush() {
    return request<{
      success: boolean;
      message: string;
      channel?: string | null;
      wechat_ok?: boolean;
      wechat_errcode?: number;
      wechat_errmsg?: string;
      wechat_detail?: string;
      wechat_private_template_ids?: string[] | null;
      wechat_template_list_api_error?: { errcode?: number; errmsg?: string } | null;
      wechat_config_appid_prefix?: string;
      wechat_attempted_template_id?: string;
    }>('/api/wechat/test-push', {
      method: 'POST',
    });
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 政府端：监管首页
  // ═══════════════════════════════════════════════════════════════════════

  getGovStats() {
    return request<GovStatsData>('/dashboard/api/stats');
  },

  getGovGraphData(
    params?: { max_nodes?: number; max_links?: number; full?: boolean },
    options?: RequestOptions,
  ) {
    const q = new URLSearchParams();
    if (params?.full) q.set('full', '1');
    if (params?.max_nodes != null && params.max_nodes > 0) q.set('max_nodes', String(params.max_nodes));
    if (params?.max_links != null && params.max_links > 0) q.set('max_links', String(params.max_links));
    const suffix = q.toString();
    return request<{ nodes: unknown[]; links: unknown[]; error?: string }>(
      suffix ? `/dashboard/api/graph-data?${suffix}` : '/dashboard/api/graph-data',
      undefined,
      options,
    );
  },

  getGovAlertsList() {
    return request<GovAlertItem[]>('/dashboard/api/alerts');
  },

  getGovPageRank() {
    return request<{ success: boolean; data: unknown[] }>('/dashboard/api/graph-pagerank');
  },

  getGovForecast() {
    return request<Record<string, unknown>>('/dashboard/api/forecast');
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 政府端：预警 & 工作流
  // ═══════════════════════════════════════════════════════════════════════

  assignAlert(alertId: number, data: { assigned_to: number; deadline?: string }) {
    return request<{ success: boolean; workflow_id: number; message: string }>(
      `/api/alerts/${alertId}/assign`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  startWorkflow(workflowId: number) {
    return request<{ success: boolean; status: string }>(
      `/api/alert-workflows/${workflowId}/start`,
      { method: 'POST' },
    );
  },

  submitWorkflow(workflowId: number, data: { handling_notes: string; evidence_urls?: string[] }) {
    return request<{ success: boolean; status: string; workflow_id: number }>(
      `/api/alert-workflows/${workflowId}/submit`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  reviewWorkflow(workflowId: number, data: { approved: boolean; review_notes?: string }) {
    return request<{ success: boolean; status: string; review_result: string }>(
      `/api/alert-workflows/${workflowId}/review`,
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  getWorkflowStats() {
    return request<WorkflowStatsData>('/api/alert-workflows/stats');
  },

  getMyWorkflows(status?: string) {
    const query = status ? `?status=${status}` : '';
    return request<{ workflows: WorkflowItem[] }>(`/api/alert-workflows/mine${query}`);
  },

  runAlertChecks() {
    return request<{ success: boolean; alert_count: number; message: string }>(
      '/api/alerts/run-checks',
      { method: 'POST' },
    );
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 政府端：招商决策
  // ═══════════════════════════════════════════════════════════════════════

  getRecruitmentGaps(params?: { includeNeo4j?: boolean }, options?: RequestOptions) {
    const q = new URLSearchParams();
    if (params?.includeNeo4j === false) q.set('neo4j', '0');
    const suffix = q.toString();
    return request<{ success: boolean; total: number; gaps: RecruitmentGap[] }>(
      suffix ? `/api/recruitment/gaps?${suffix}` : '/api/recruitment/gaps',
      undefined,
      options,
    );
  },

  recommendEnterprises(data: { product_name: string; gap_type?: string }) {
    return request<{ success: boolean; enterprises: RecommendedEnterprise[] }>(
      '/api/recruitment/recommend',
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  getRecruitmentTasks(params?: { status?: string; page?: number }) {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.page) query.set('page', String(params.page));
    const suffix = query.toString();
    return request<RecruitmentTasksResponse>(
      suffix ? `/api/recruitment/tasks?${suffix}` : '/api/recruitment/tasks',
    );
  },

  createRecruitmentTask(data: CreateRecruitmentTaskPayload) {
    return request<{ success: boolean; task_id: number; message: string }>(
      '/api/recruitment/tasks',
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  updateRecruitmentTask(taskId: number, data: Record<string, unknown>) {
    return request<{ success: boolean; message: string }>(
      `/api/recruitment/tasks/${taskId}`,
      { method: 'PUT', body: JSON.stringify(data) },
    );
  },

  // ═══════════════════════════════════════════════════════════════════════
  // 政府端：质量标签
  // ═══════════════════════════════════════════════════════════════════════

  grantGreenLabel(data: { enterprise_id: number; label_name?: string; certificate_no?: string; valid_days?: number }) {
    return request<{ success: boolean; message: string; label_id?: number }>(
      '/quality-labels/api/grant-green',
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  grantInspection(data: { enterprise_id: number; label_name?: string; certificate_no?: string; valid_days?: number; inspection_notes?: string }) {
    return request<{ success: boolean; message: string; label_id?: number }>(
      '/quality-labels/api/grant-inspection',
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  revokeLabel(labelId: number, reason?: string) {
    return request<{ success: boolean; message: string }>(
      `/quality-labels/api/revoke/${labelId}`,
      { method: 'POST', body: JSON.stringify({ reason: reason || '' }) },
    );
  },

  getEnterpriseLabels(enterpriseId: number) {
    return request<{ success: boolean; labels: QualityLabelItem[] }>(
      `/quality-labels/api/enterprise/${enterpriseId}`,
    );
  },

  syncThirdPartyRating(data: { enterprise_id?: number; source?: string }) {
    return request<{ success: boolean; message: string; rating?: string }>(
      '/quality-labels/api/sync-third-party',
      { method: 'POST', body: JSON.stringify(data) },
    );
  },

  getAllEnterprises() {
    return request<{ success: boolean; enterprises: { id: number; name: string; credit_score: number }[] }>(
      '/api/matching/search',
    );
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // 企业端：意向询价/报价控制台（InquiryChat）
  // ═══════════════════════════════════════════════════════════════════════════

  /** POST /api/inquiry-chat/create — 创建或获取询价会话 */
  createInquiryChat(payload: {
    buyer_id: number;
    seller_id: number;
    match_record_id: number;
    is_anonymous?: boolean;
    product_name?: string;
    match_score?: number;
    dim_scores?: Record<string, number>;
    match_feedback_id?: number;
  }) {
    return request<{
      success: boolean;
      chat_id: number;
      is_new: boolean;
      chat: InquiryChatData;
    }>('/api/inquiry-chat/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /** GET /api/inquiry-chat/list — 获取会话列表 */
  getInquiryChats(params?: { role?: string; status?: string; limit?: number }) {
    const q = new URLSearchParams();
    if (params?.role) q.set('role', params.role);
    if (params?.status) q.set('status', params.status);
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    const suffix = q.toString();
    return request<{ success: boolean; total: number; chats: InquiryChatData[] }>(
      suffix ? `/api/inquiry-chat/list?${suffix}` : '/api/inquiry-chat/list',
    );
  },

  /** GET /api/inquiry-chat/<id> — 获取单个会话详情 */
  getInquiryChat(chatId: number) {
    return request<{ success: boolean; chat: InquiryChatData }>(
      `/api/inquiry-chat/${chatId}`,
    );
  },

  /** PUT /api/inquiry-chat/<id>/mode — 切换会话内视角（与列表「采购/销售」筛选独立） */
  switchInquiryChatMode(chatId: number, mode: 'procurement' | 'sales') {
    return request<{ success: boolean; mode: string; chat: InquiryChatData }>(
      `/api/inquiry-chat/${chatId}/mode`,
      { method: 'PUT', body: JSON.stringify({ mode }) },
    );
  },

  /** POST /api/inquiry-chat/<id>/seller-accept-quote — 卖方同意意向报价，解锁名片交换 */
  sellerAcceptQuote(chatId: number) {
    return request<{
      success: boolean;
      match_record_status: string;
      chat: InquiryChatData;
    }>(`/api/inquiry-chat/${chatId}/seller-accept-quote`, { method: 'POST' });
  },

  /** POST /api/inquiry-chat/<id>/message — 发送聊天消息 */
  sendChatMessage(chatId: number, payload: {
    content: string;
    message_type?: string;
    msg_metadata?: Record<string, unknown>;
  }) {
    return request<{
      success: boolean;
      message_id: number;
      message: ChatMessageData;
    }>(`/api/inquiry-chat/${chatId}/message`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /** GET /api/inquiry-chat/<id>/history — 获取聊天记录（含匿名脱敏） */
  getChatHistory(chatId: number, params?: { limit?: number; offset?: number }) {
    const q = new URLSearchParams();
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.offset !== undefined) q.set('offset', String(params.offset));
    const suffix = q.toString();
    return request<{
      success: boolean;
      chat_id: number;
      is_anonymous: boolean;
      messages: ChatMessageData[];
    }>(suffix ? `/api/inquiry-chat/${chatId}/history?${suffix}` : `/api/inquiry-chat/${chatId}/history`);
  },

  /** GET /api/inquiry-chat/<id>/insights — 获取 AI 商机评估数据 */
  getBusinessInsights(chatId: number) {
    return request<BusinessInsightsData>(`/api/inquiry-chat/${chatId}/insights`);
  },

  /** POST /api/inquiry-chat/<id>/quote — 提交正式结构化报价（触发价格指数+信用卡点） */
  submitFormalQuote(chatId: number, payload: {
    price: number;
    quantity: number;
    unit: string;
    delivery_days: number;
    remarks?: string;
  }) {
    return request<{
      success: boolean;
      quote_id: number;
      remaining_quotes_today: number | string;
      total_price?: number;
    }>(`/api/inquiry-chat/${chatId}/quote`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /** PUT /api/inquiry-chat/<id>/match-status — 更新匹配记录状态 */
  updateMatchStatus(chatId: number, status: string) {
    return request<{ success: boolean; match_record_id: number; status: string }>(
      `/api/inquiry-chat/${chatId}/match-status`,
      { method: 'PUT', body: JSON.stringify({ status }) },
    );
  },

  /** GET /api/enterprise/<id>/profile-mini — 获取企业名片信息（含经纬度） */
  getEnterpriseProfileMini(enterpriseId: number) {
    return request<{
      success: boolean;
      enterprise: {
        id: number;
        name: string;
        address: string;
        longitude: number | null;
        latitude: number | null;
        contact: string;
        phone: string;
        main_business: string;
        business_scope: string;
        credit_score: number;
        is_green_factory: boolean;
        tags: string[];
        collaboration_code: string | null;
      };
    }>(`/api/enterprise/${enterpriseId}/profile-mini`);
  },

  /** POST /api/inquiry-chat/<id>/exchange-card — 交换名片（仅 quoted 状态可用） */
  exchangeBusinessCard(chatId: number) {
    return request<{
      success: boolean;
      card: {
        id: number;
        name: string;
        address: string;
        longitude: number | null;
        latitude: number | null;
        contact: string;
        phone: string;
        main_business: string;
        credit_score: number;
        is_green_factory: boolean;
        tags: string[];
      };
    }>(`/api/inquiry-chat/${chatId}/exchange-card`, { method: 'POST' });
  },
};

// ═══════════════════════════════════════════════════════════════════════════
// 新增类型定义
// ═══════════════════════════════════════════════════════════════════════════

export interface ActiveFulfillmentItem {
  id: number;
  product_name: string;
  buyer_id: number;
  fulfillment_status: string;
  created_at: string | null;
  logistics_nodes: unknown[];
  logistics_current?: string | null;
  qc_status: string;
  payment_progress: number;
  invoice_info: {
    verified?: boolean;
    on_time?: boolean;
    delivery_date?: string | null;
  };
}

export interface FulfillmentDashboardData {
  success: boolean;
  current_score: number;
  trend: { month: string; score: number }[];
  delivery_stats: {
    own_rate: number;
    industry_rate: number;
    total_count: number;
    on_time_count: number;
  };
  dimensions: Record<string, number>;
  history: {
    id: number;
    change_value: number;
    change_type: string;
    reason: string;
    old_score: number;
    new_score: number;
    created_at: string;
  }[];
  active_fulfillments?: ActiveFulfillmentItem[];
}

export interface CaseItem {
  id: number;
  buyer_name_masked: string;
  product_category: string;
  cooperation_time: string;
  amount_range: string;
  is_public: boolean;
}

export interface CapacityCalendarDayCell {
  date?: string;
  utilization: number;
  order_count: number;
  orders_count?: number;
}

export interface CapacityCalendarData {
  success?: boolean;
  year: number;
  month: number;
  days: Record<string, CapacityCalendarDayCell>;
  max_capacity: number;
  current_orders?: number;
  overall_utilization?: number;
}

export interface GovStatsData {
  enterprise_count: number;
  supply_count: number;
  demand_count: number;
  alert_count: number;
}

export interface GovAlertItem {
  id: number;
  product_name: string;
  message: string;
  level: string;
  dimension: string;
  suggestion: string | null;
  created_at: string;
}

export interface WorkflowStatsData {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  rejected: number;
  avg_response_hours: number;
  completion_rate: number;
}

export interface WorkflowItem {
  id: number;
  alert_id: number;
  status: string;
  assigned_at: string | null;
  handling_notes: string | null;
  completed_at: string | null;
  review_result: string | null;
}

export interface RecruitmentGap {
  product_name: string;
  gap_type: string;
  gap_type_label?: string;
  supplier_count: number;
  local_ratio: number;
  /** 前端展示用：由 urgency_label 映射或后端直传 */
  urgency?: string;
  urgency_label?: string;
  urgency_score?: number;
  affected_enterprises?: number;
  affected_enterprise_count?: number;
  suggestion?: {
    enterprise_type?: string;
    estimated_investment?: string;
    investment_scale?: string;
    description?: string;
  };
}

export interface RecommendedEnterprise {
  name: string;
  location: string;
  main_products: string;
  scale: string;
  contact: string;
  credit_rating: string;
  match_score: number;
}

export interface RecruitmentTasksResponse {
  success: boolean;
  tasks: RecruitmentTask[];
  total: number;
  page: number;
}

export interface RecruitmentTask {
  id: number;
  task_name: string;
  target_product: string;
  target_enterprise_name: string | null;
  target_enterprise_location: string | null;
  status: string;
  priority: string;
  progress_notes: string | null;
  deadline: string | null;
  created_at: string;
}

export interface CreateRecruitmentTaskPayload {
  task_name?: string;
  target_product: string;
  target_enterprise_name?: string;
  target_enterprise_location?: string;
  assigned_to?: number;
  priority?: string;
  deadline?: string;
}

export interface QualityLabelItem {
  id: number;
  label_type: string;
  label_name: string;
  issuer_name: string;
  certificate_no: string;
  valid_from: string;
  valid_until: string;
  status: string;
}

/** InquiryChat API — 会话数据 */
export interface InquiryChatData {
  id: number;
  buyer_id: number;
  seller_id: number;
  match_record_id: number;
  mode: 'procurement' | 'sales';
  is_anonymous: boolean;
  status: 'active' | 'quoted' | 'closed' | 'contracted';
  /** MatchRecord.status：quoted → 卖方同意后 quote_acknowledged → 可交换名片 */
  match_record_status?: string | null;
  product_name?: string;
  counterparty_name: string;
  latest_message?: string;
  latest_message_at?: string | null;
  match_score?: number;
  created_at: string;
  updated_at: string;
}

/** InquiryChat API — 聊天消息数据 */
export interface ChatMessageData {
  id: number;
  chat_id: number;
  sender_id: number | null;
  sender_name: string;
  content: string;
  message_type: 'text' | 'quote_proposal' | 'system' | 'ai_suggestion';
  msg_metadata?: Record<string, unknown> | null;
  is_mine: boolean;
  created_at: string;
}

/** InquiryChat API — AI 商机评估数据 */
export interface BusinessInsightsData {
  success?: boolean;
  match_record_id: number;
  match_score: number;
  profit_rate: number;
  risk_level: string;
  risk_detail: string;
  credit_score: number;
  level: string;
}

export { ApiError, NETWORK_ERROR_MESSAGE };
