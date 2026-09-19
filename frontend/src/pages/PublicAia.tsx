import { FormEvent, useEffect, useRef, useState } from 'react';
import { Archive, Check, ChevronRight, Download, FileUp, History, Loader2, Menu, MessageSquare, PanelRight, Plus, Send, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type ChainXiaoYiBatchQuoteSummary, type ChainXiaoYiBatchRfqPreview, type ChainXiaoYiItemMatch, type ChainXiaoYiMatchItem, type ChainXiaoYiMatchResult, type ChainXiaoYiProcurementDraft, type ChainXiaoYiQuoteSummary, type ChainXiaoYiRfqPreview, type ChainXiaoYiSession, type ChainXiaoYiTask, type ChainXiaoYiTaskAudit, type ChainXiaoYiTaskInboxItem, type ChainXiaoYiTaskProgress } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { PublicSiteHeader } from '@/src/components/PublicSiteHeader';

type ChatMessage = { role: 'user' | 'assistant'; content: string };
const QUICK_PROMPTS = ['找华东能做精密注塑、30天交付的工厂', '找支持出口的汽车零部件工厂', '找有产能的工业电机供应商'];
const DIMENSION_NAMES: Record<string, string> = { product: '产品', distance: '距离', capacity: '产能', green: '绿色', semantic: '语义', credit: '信用', tech: '技术', history: '合作', gnn: '图谱' };
const RFQ_PROGRESS_STATUSES = ['queued', 'running', 'sent', 'partial_failure', 'timed_out', 'completed', 'fulfillment_in_progress', 'fulfillment_exception', 'fulfillment_completed'];
const RFQ_QUOTE_STATUSES = ['sent', 'partial_failure', 'timed_out', 'completed', 'fulfillment_in_progress', 'fulfillment_exception', 'fulfillment_completed'];

function freshnessLabel(item: ChainXiaoYiMatchItem) {
  const freshness = item.data_freshness;
  if (freshness?.status === 'stale') return `数据已过期${freshness.age_days != null ? `（${freshness.age_days}天前）` : ''}，建议重新核验`;
  if (freshness?.status === 'fresh') return `数据新鲜${freshness.age_days != null ? `（${freshness.age_days}天前）` : ''}`;
  return '更新时间未知，不能视为最新事实';
}

function IntentChips({ intent }: { intent: Record<string, unknown> }) {
  const values = [
    typeof intent.product === 'string' && `产品：${intent.product}`,
    typeof intent.region === 'string' && `地区：${intent.region}`,
    typeof intent.quantity === 'number' && `数量：${intent.quantity}${typeof intent.unit === 'string' ? intent.unit : ''}`,
    typeof intent.delivery_days === 'number' && `交期：${intent.delivery_days}天`,
    Array.isArray(intent.processes) && intent.processes.length > 0 && `工艺：${intent.processes.join('、')}`,
    Array.isArray(intent.certifications) && intent.certifications.length > 0 && `资质：${intent.certifications.join('、')}`,
    intent.is_export === true && '支持出口', intent.is_green_factory === true && '绿色工厂',
  ].filter((value): value is string => Boolean(value));
  return <div className="flex flex-wrap gap-1.5">{values.map(value => <span key={value} className="rounded-full bg-public-brand-soft px-2.5 py-1 text-[11px] font-semibold text-public-brand">{value}</span>)}</div>;
}

function RfqApprovalPreview({ preview }: { preview?: ChainXiaoYiRfqPreview }) {
  if (!preview) return null;
  const disclosed = Object.entries(preview.disclosed_fields || {}).filter(([, value]) => value !== null && value !== '' && !(Array.isArray(value) && value.length === 0));
  return <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-900">
    <p className="font-black">发送前预览</p>
    <p className="mt-1">将触达 {preview.supplier_count} 家供应商 · 渠道：{preview.channels.join('、') || '站内消息'}</p>
    <p className="mt-1">披露字段：{disclosed.map(([key, value]) => `${key}=${Array.isArray(value) ? value.join('、') : String(value)}`).join('；') || '采购需求'}。</p>
    <p className="mt-1">询价内容：{preview.content || '请按采购需求报价。'}</p>
    <div className="mt-2 flex flex-wrap gap-1">{preview.suppliers.map(supplier => <span key={supplier.id} className="rounded bg-white px-1.5 py-1">{supplier.name} · {supplier.city || supplier.province || '地区未公开'} · {supplier.contact_authorized ? '已授权触达' : '未授权'}</span>)}</div>
  </div>;
}

export default function PublicAia() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { user, requestLogin } = useAuth();
  const initialQuery = params.get('q') || params.get('query') || '';
  const [query, setQuery] = useState(initialQuery);
  const [session, setSession] = useState<ChainXiaoYiSession | null>(null);
  const [history, setHistory] = useState<ChainXiaoYiSession[]>([]);
  const [taskInbox, setTaskInbox] = useState<ChainXiaoYiTaskInboxItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [intent, setIntent] = useState<Record<string, unknown>>({});
  const [matches, setMatches] = useState<ChainXiaoYiMatchResult | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState('');
  const [error, setError] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [selectedSuppliers, setSelectedSuppliers] = useState<number[]>([]);
  const [rfqChannels, setRfqChannels] = useState<string[]>(['site']);
  const [rfqTask, setRfqTask] = useState<{ id: number; status: string; preview?: ChainXiaoYiRfqPreview } | null>(null);
  const [quoteSummary, setQuoteSummary] = useState<ChainXiaoYiQuoteSummary | null>(null);
  const [quoteQuery, setQuoteQuery] = useState('只看含税价最低且30天内能交付的三家');
  const [quoteQueryExplanation, setQuoteQueryExplanation] = useState('');
  const [taskProgress, setTaskProgress] = useState<ChainXiaoYiTaskProgress | null>(null);
  const [taskAudit, setTaskAudit] = useState<ChainXiaoYiTaskAudit | null>(null);
  const [enterpriseEvidence, setEnterpriseEvidence] = useState<Record<number, { is_demo: boolean; updated_at?: string | null; sources: Array<Record<string, unknown>>; uncertain_fields: string[] }>>({});
  const [orderDraft, setOrderDraft] = useState<Record<string, unknown> | null>(null);
  const [formalOrder, setFormalOrder] = useState<Record<string, unknown> | null>(null);
  const [procurementTask, setProcurementTask] = useState<ChainXiaoYiTask | null>(null);
  const [procurementDraft, setProcurementDraft] = useState<ChainXiaoYiProcurementDraft | null>(null);
  const [itemMatches, setItemMatches] = useState<ChainXiaoYiItemMatch[]>([]);
  const [activeItemIndex, setActiveItemIndex] = useState<number | null>(null);
  const [materialSelections, setMaterialSelections] = useState<Record<number, number[]>>({});
  const [batchRfqPreview, setBatchRfqPreview] = useState<ChainXiaoYiBatchRfqPreview | null>(null);
  const [batchQuoteSummary, setBatchQuoteSummary] = useState<ChainXiaoYiBatchQuoteSummary | null>(null);
  const [batchOrderDrafts, setBatchOrderDrafts] = useState<Array<Record<string, unknown>>>([]);
  const [batchFormalOrders, setBatchFormalOrders] = useState<Array<Record<string, unknown>>>([]);
  const [batchQuoteQuery, setBatchQuoteQuery] = useState('每个采购项只看含税价最低且30天内能交付的一家');
  const autoSent = useRef(false);
  const fileInput = useRef<HTMLInputElement | null>(null);

  const refreshHistory = async () => {
    if (!user) return;
    try {
      const [sessions, tasks] = await Promise.all([api.listChainXiaoYiSessions(), api.listChainXiaoYiTasks()]);
      setHistory(sessions.sessions); setTaskInbox(tasks.tasks);
    } catch { setHistory([]); setTaskInbox([]); }
  };

  const ensureSession = async () => {
    if (session) return session;
    setStage('正在创建安全会话');
    const created = await api.createChainXiaoYiSession('public');
    setSession(created.session);
    return created.session;
  };

  const send = async (content: string, allowWhileLoading = false) => {
    const clean = content.trim();
    if (!clean || (loading && !allowWhileLoading)) return;
    setLoading(true); setError(''); setStage('正在理解需求');
    setMessages(previous => [...previous, { role: 'user', content: clean }]);
    setQuery('');
    try {
      const active = await ensureSession();
      setStage('数据库正在召回并计算九维分数');
      const response = await api.sendChainXiaoYiMessage(active.id, clean);
      setIntent(response.intent); setMatches(response.match_result); setSuggestions(response.suggestions || []);
      setSelectedSuppliers(response.match_result.results.filter(item => item.contact_eligible).slice(0, 10).map(item => item.id));
      setItemMatches([]); setActiveItemIndex(null); setMaterialSelections({}); setBatchRfqPreview(null); setBatchQuoteSummary(null); setBatchOrderDrafts([]); setBatchFormalOrders([]);
      setRfqTask(null);
      setTaskAudit(null);
      setQuoteSummary(null); setTaskProgress(null); setOrderDraft(null); setFormalOrder(null);
      // Chat commands operate on the persisted source task. Restore that
      // task into the same review surface as button actions so a buyer can
      // say “暂停/恢复/重试” without losing the recoverable state card.
      const workflow = response.workflow;
      const sourceTaskId = workflow?.source_task_id ? Number(workflow.source_task_id) : 0;
      if (sourceTaskId > 0) {
        try {
          const source = await api.getChainXiaoYiProcurementTask(sourceTaskId);
          const sourceTask = source.task;
          if (sourceTask.type === 'procurement_intake') {
            setProcurementTask(sourceTask);
            const output = sourceTask.output || {};
            const restoredItems = Array.isArray(output.item_matches) ? output.item_matches as ChainXiaoYiItemMatch[] : [];
            const restoredBatch = output.batch_rfq && typeof output.batch_rfq === 'object' ? output.batch_rfq as ChainXiaoYiBatchRfqPreview : null;
            if (restoredItems.length) setItemMatches(restoredItems);
            if (restoredBatch) setBatchRfqPreview(restoredBatch);
            if (workflow?.action === 'order_draft') {
              setBatchOrderDrafts(workflow.orders || []);
              try { setBatchQuoteSummary(await api.getChainXiaoYiBatchQuoteSummary(sourceTaskId)); } catch { /* card remains reviewable from the workflow payload */ }
            }
          } else {
            const status = String(workflow?.status || sourceTask.status);
            setRfqTask({ id: sourceTaskId, status });
            try {
              const preview = await api.getChainXiaoYiRfqPreview(sourceTaskId);
              setRfqTask({ id: sourceTaskId, status, preview: preview.preview });
            } catch { /* preview may be unavailable for legacy tasks */ }
            if (workflow?.action === 'order_draft' && workflow.orders?.[0]) setOrderDraft(workflow.orders[0]);
            if (workflow?.action === 'task_retry') {
              try {
                setTaskProgress((await api.getChainXiaoYiTaskProgress(sourceTaskId)));
                setQuoteSummary(await api.getChainXiaoYiQuoteSummary(sourceTaskId));
              } catch { /* the assistant reply remains truthful even if refresh races the worker */ }
            }
          }
        } catch {
          // The chat reply remains useful if a source task was archived between
          // the command and the UI refresh; do not turn a successful command
          // into a blank screen.
        }
      }
      setMessages(previous => [...previous, { role: 'assistant', content: response.reply }]);
      setResultsOpen(true);
      if (user) await refreshHistory();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Agent 暂时不可用，请稍后重试';
      setError(message);
      if (message.includes('登录')) requestLogin(`/aia?q=${encodeURIComponent(clean)}`);
    } finally { setLoading(false); setStage(''); }
  };

  useEffect(() => {
    if (!autoSent.current && initialQuery.trim()) { autoSent.current = true; void send(initialQuery); }
  // Initial URL input is intentionally submitted once.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void refreshHistory(); }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!user || !session || session.status !== 'active') return;
    void api.claimChainXiaoYiSession(session.id).then(({ session: claimed }) => { setSession(claimed); void refreshHistory(); }).catch(() => undefined);
  // Claim is attempted when auth/session identity changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, session?.id]);

  const openHistory = async (item: ChainXiaoYiSession) => {
    try {
      const detail = await api.getChainXiaoYiSession(item.id);
      setSession(detail.session); setIntent(detail.intent || {}); setMatches(detail.match_result || null);
      setItemMatches([]); setActiveItemIndex(null); setMaterialSelections({}); setBatchRfqPreview(null); setBatchQuoteSummary(null); setBatchOrderDrafts([]); setBatchFormalOrders([]);
      setMessages(detail.messages.map(message => ({ role: message.role === 'user' ? 'user' : 'assistant', content: message.content })));
      setHistoryOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : '会话加载失败'); }
  };

  const openTask = async (item: ChainXiaoYiTaskInboxItem) => {
    try {
      const detail = await api.getChainXiaoYiSession(item.session_id);
      setSession(detail.session); setIntent(detail.intent || {}); setMatches(detail.match_result || null);
      setItemMatches([]); setActiveItemIndex(null); setMaterialSelections({}); setBatchRfqPreview(null); setBatchQuoteSummary(null); setBatchOrderDrafts([]); setBatchFormalOrders([]);
      setMessages(detail.messages.map(message => ({ role: message.role === 'user' ? 'user' : 'assistant', content: message.content })));
      setRfqTask(item.type === 'rfq' ? { id: item.id, status: item.status } : null);
      if (item.type === 'rfq') {
        try {
          const preview = await api.getChainXiaoYiRfqPreview(item.id);
          setRfqTask({ id: item.id, status: item.status, preview: preview.preview });
        } catch { /* historical tasks may not have a preview snapshot */ }
      }
      const audit = await api.getChainXiaoYiTaskAudit(item.id);
      setTaskAudit(audit);
      if (item.type === 'procurement_intake') {
        const output = audit.task.output || {};
        const restoredDraft = output.draft as ChainXiaoYiProcurementDraft | undefined;
        const restoredItems = Array.isArray(output.item_matches) ? output.item_matches as ChainXiaoYiItemMatch[] : [];
        const restoredBatch = output.batch_rfq && typeof output.batch_rfq === 'object' ? output.batch_rfq as ChainXiaoYiBatchRfqPreview : null;
        setProcurementTask({ id: item.id, type: item.type, status: item.status, requires_approval: item.requires_approval });
        setProcurementDraft(restoredDraft || null); setItemMatches(restoredItems); setBatchRfqPreview(restoredBatch);
        const disclosureSelections = Object.fromEntries((restoredBatch?.disclosures || []).map(row => [row.item_index, row.supplier_ids]));
        const defaults = Object.fromEntries(restoredItems.map(row => [row.item_index, disclosureSelections[row.item_index] || row.match_result.results.filter(candidate => candidate.contact_eligible).slice(0, 10).map(candidate => candidate.id)]));
        setMaterialSelections(defaults);
        const first = restoredItems[0];
        if (first) { setActiveItemIndex(first.item_index); setIntent(first.intent); setMatches(first.match_result); setSelectedSuppliers(defaults[first.item_index] || []); setResultsOpen(true); }
        if (restoredBatch?.task_ids?.length && ['completed', 'partial_failure'].includes(item.status)) {
          const batchSummary = await api.getChainXiaoYiBatchQuoteSummary(item.id);
          setBatchQuoteSummary(batchSummary);
          setBatchOrderDrafts(batchSummary.order_drafts || []);
          setBatchFormalOrders(batchSummary.formal_orders || []);
        }
      }
      if (item.type === 'rfq' && RFQ_PROGRESS_STATUSES.includes(item.status)) {
        const progress = await api.getChainXiaoYiTaskProgress(item.id); setTaskProgress(progress);
        if (RFQ_QUOTE_STATUSES.includes(item.status)) setQuoteSummary(await api.getChainXiaoYiQuoteSummary(item.id));
      }
      setHistoryOpen(false);
    } catch (err) { setTaskAudit(null); setError(err instanceof Error ? err.message : '任务恢复失败'); }
  };

  const archive = async (item: ChainXiaoYiSession) => {
    await api.archiveChainXiaoYiSession(item.id);
    if (session?.id === item.id) { setSession(null); setMessages([]); setMatches(null); setIntent({}); setItemMatches([]); setActiveItemIndex(null); setMaterialSelections({}); setBatchRfqPreview(null); setBatchQuoteSummary(null); setBatchOrderDrafts([]); setBatchFormalOrders([]); }
    await refreshHistory();
  };

  const submit = (event: FormEvent) => { event.preventDefault(); void send(query); };

  const selectMaterialItem = (item: ChainXiaoYiItemMatch) => {
    setActiveItemIndex(item.item_index);
    setIntent(item.intent);
    setMatches(item.match_result);
    const defaults = item.match_result.results.filter(candidate => candidate.contact_eligible).slice(0, 10).map(candidate => candidate.id);
    setSelectedSuppliers(materialSelections[item.item_index] || defaults);
    setRfqTask(null); setTaskAudit(null); setQuoteSummary(null); setTaskProgress(null); setOrderDraft(null); setFormalOrder(null);
    setResultsOpen(true);
  };

  const recomputeMaterialTask = async (task: ChainXiaoYiTask) => {
    setStage('正在为每个采购项自动找厂');
    const response = await api.recomputeChainXiaoYiTask(task.id);
    setProcurementTask(response.task);
    setItemMatches(response.item_matches);
    const defaults = Object.fromEntries(response.item_matches.map(item => [item.item_index, item.match_result.results.filter(candidate => candidate.contact_eligible).slice(0, 10).map(candidate => candidate.id)]));
    setMaterialSelections(defaults);
    setBatchRfqPreview(null);
    const first = response.item_matches[0];
    if (first) {
      setActiveItemIndex(first.item_index); setIntent(first.intent); setMatches(first.match_result);
      setSelectedSuppliers(defaults[first.item_index] || []); setResultsOpen(true);
    }
    setMessages(previous => [...previous, { role: 'assistant', content: `已为 ${response.item_matches.length} 个采购项分别完成候选工厂召回。可切换采购项审阅结果，对外询价仍需你确认。` }]);
    return response.item_matches;
  };

  const autoPlanMaterialTask = async (task: ChainXiaoYiTask) => {
    setStage('正在自动选择已授权供应商并生成询价审批卡');
    try {
      const response = await api.autoPlanChainXiaoYiProcurement(task.id, '请分别按采购项提供含税报价、最早交期和有效期。', rfqChannels);
      setProcurementTask(response.task);
      setItemMatches(response.item_matches);
      setBatchRfqPreview(response.preview);
      setMessages(previous => [...previous, { role: 'assistant', content: `已自动为 ${response.item_matches.length} 个采购项选取已认领且授权触达的供应商，询价内容和披露范围已生成审批卡。确认后才会对外发送。` }]);
      return response;
    } catch (err) {
      // No authorized supplier is a reviewable state, not a silent fallback:
      // keep the candidate comparison visible so the buyer can inspect and
      // resolve authorization instead of accidentally contacting anyone.
      setError(err instanceof Error ? err.message : '自动询价规划失败，请先确认供应商授权');
      return null;
    }
  };

  const uploadMaterial = async (file: File, autoSearch = true) => {
    if (!user) { requestLogin('/aia'); return; }
    setLoading(true); setError(''); setStage('正在解析材料并标注字段证据');
    try {
      const active = await ensureSession();
      const response = await api.previewChainXiaoYiFile(active.id, file);
      if (!response.draft) throw new Error('材料未生成采购草稿');
      setProcurementTask(response.task || null); setProcurementDraft(response.draft);
      const nextIntent: Record<string, unknown> = { raw_text: file.name };
      Object.entries(response.draft.fields).forEach(([key, field]) => { nextIntent[key] = field.value; });
      setIntent(nextIntent);
      const itemCount = response.draft.items?.length || 1;
      setMessages(previous => [...previous, { role: 'user', content: `上传采购材料：${file.name}` }, { role: 'assistant', content: response.draft!.clarifying_questions.length ? `材料已解析，还需确认：${response.draft!.clarifying_questions.join('、')}` : `材料已解析为 ${itemCount} 个采购项，并保留字段来源证据。确认后即可找厂。` }]);
      if (autoSearch && !response.draft.clarifying_questions.length && response.task) await recomputeMaterialTask(response.task);
      return { intent: nextIntent, ready: response.draft.clarifying_questions.length === 0, task: response.task };
    } catch (err) { setError(err instanceof Error ? err.message : '材料解析失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const uploadMaterials = async (files: File[]) => {
    try {
      let result: { intent: Record<string, unknown>; ready: boolean; task?: ChainXiaoYiTask } | undefined;
      for (const file of files.slice(0, 10)) result = await uploadMaterial(file, false) || result;
      if (result?.ready && result.task) {
        setLoading(true);
        await recomputeMaterialTask(result.task);
        await autoPlanMaterialTask(result.task);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '材料候选重算失败');
    } finally {
      setLoading(false); setStage('');
    }
  };

  const confirmMaterialField = async (field: string, value: unknown) => {
    if (!procurementTask) return;
    setLoading(true); setError('');
    try {
      const response = await api.updateChainXiaoYiTaskFields(procurementTask.id, { [field]: value });
      setProcurementDraft(response.draft); setProcurementTask(response.task);
      const nextIntent = { ...intent, [field]: value }; setIntent(nextIntent);
      if (!response.draft.clarifying_questions.length) await recomputeMaterialTask(response.task);
    } catch (err) { setError(err instanceof Error ? err.message : '字段确认失败'); }
    finally { setLoading(false); }
  };

  const createRfqPreview = async () => {
    if (!user) { requestLogin('/aia'); return; }
    if (!session || !selectedSuppliers.length) return;
    setLoading(true); setError(''); setStage('正在生成询价发送预览');
    try {
      const response = await api.createChainXiaoYiRfqDraft(session.id, intent, selectedSuppliers, '请按采购需求提供含税报价、最早交期和有效期。', rfqChannels);
      setRfqTask({ ...response.task, preview: response.preview });
    } catch (err) { setError(err instanceof Error ? err.message : '询价预览生成失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const createBatchRfqPreview = async () => {
    if (!procurementTask || itemMatches.length < 2) return;
    const selections = itemMatches.map(item => ({ item_index: item.item_index, supplier_ids: materialSelections[item.item_index] || [] }));
    if (selections.some(row => row.supplier_ids.length === 0)) { setError('每个采购项至少需要选择一家已授权供应商'); return; }
    setLoading(true); setError(''); setStage('正在生成全部采购项的统一发送预览');
    try {
      const response = await api.createChainXiaoYiBatchRfqPreview(procurementTask.id, selections, '请分别按采购项提供含税报价、最早交期和有效期。', rfqChannels);
      setProcurementTask(response.task); setBatchRfqPreview(response.preview);
    } catch (err) { setError(err instanceof Error ? err.message : '批量询价预览生成失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const approveBatchRfq = async () => {
    if (!procurementTask || !batchRfqPreview) return;
    if (!window.confirm(`确认一次性向 ${batchRfqPreview.supplier_count} 个供应商触达记录发送 ${batchRfqPreview.item_count} 个采购项？`)) return;
    setLoading(true); setError(''); setStage('正在将批量询价加入后台队列');
    try {
      const response = await api.approveChainXiaoYiBatchRfq(procurementTask.id, '采购方在统一预览中确认批量发送');
      setProcurementTask(response.task); setBatchRfqPreview(current => current ? { ...current, status: 'queued' } : current);
      setMessages(previous => [...previous, { role: 'assistant', content: `${response.queued} 个采购项已通过一次确认进入后台询价队列。可从待办中心查看逐项发送和报价进度。` }]);
      await refreshHistory();
    } catch (err) { setError(err instanceof Error ? err.message : '批量询价发送失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const refreshBatchQuotes = async () => {
    if (!procurementTask) return;
    setLoading(true); setError(''); setStage('正在汇总全部采购项报价');
    try {
      const response = await api.getChainXiaoYiBatchQuoteSummary(procurementTask.id);
      setBatchQuoteSummary(response);
      setBatchOrderDrafts(response.order_drafts || []);
      setBatchFormalOrders(response.formal_orders || []);
    } catch (err) { setError(err instanceof Error ? err.message : '批量报价汇总失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const applyBatchQuoteQuery = async () => {
    if (!procurementTask || !batchQuoteQuery.trim()) return;
    setLoading(true); setError(''); setStage('正在按一句话逐项筛选报价');
    try {
      const response = await api.queryChainXiaoYiBatchQuotes(procurementTask.id, batchQuoteQuery.trim());
      setBatchQuoteSummary({
        task_id: response.task_id,
        item_count: response.item_count,
        quoted_item_count: response.items.filter(item => item.quotes.length > 0).length,
        quote_count: response.items.reduce((total, item) => total + item.quotes.length, 0),
        complete: response.complete,
        items: response.items,
      });
      setMessages(previous => [...previous, { role: 'assistant', content: response.complete ? `已按你的条件为 ${response.item_count} 个采购项分别选出供应商，结果只使用供应商实际回复。` : `有 ${response.missing_items.length} 个采购项没有符合条件的报价，请放宽条件或继续等待报价。` }]);
    } catch (err) { setError(err instanceof Error ? err.message : '批量报价筛选失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const createBatchOrderDrafts = async () => {
    if (!procurementTask || !batchQuoteQuery.trim()) return;
    if (!window.confirm('按这句话为每个采购项各生成一份订单草稿？本操作不会创建正式订单、合同或付款。')) return;
    setLoading(true); setError(''); setStage('正在生成全部订单草稿');
    try {
      const response = await api.createChainXiaoYiBatchOrderDrafts(procurementTask.id, batchQuoteQuery.trim());
      setBatchOrderDrafts(response.orders);
      setMessages(previous => [...previous, { role: 'assistant', content: `已生成 ${response.orders.length} 份订单草稿。正式下单、合同和付款仍需人工分别确认。` }]);
    } catch (err) { setError(err instanceof Error ? err.message : '批量订单草稿生成失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const confirmBatchOrderDrafts = async () => {
    if (!procurementTask || !batchOrderDrafts.length || !batchQuoteQuery.trim()) return;
    if (!window.confirm(`确认一次创建 ${batchOrderDrafts.length} 份正式订单？合同和付款仍会逐单独立确认。`)) return;
    setLoading(true); setError(''); setStage('正在创建正式订单');
    try {
      const response = await api.confirmChainXiaoYiBatchOrderDrafts(procurementTask.id, batchQuoteQuery.trim());
      setBatchFormalOrders(response.orders);
      setMessages(previous => [...previous, { role: 'assistant', content: `已创建 ${response.orders.length} 份正式订单。每份订单的合同和付款仍需你分别确认。` }]);
    } catch (err) { setError(err instanceof Error ? err.message : '批量正式订单创建失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const confirmBatchOrderRequirement = async (orderId: number, requirement: 'contract' | 'payment') => {
    setLoading(true); setError('');
    try {
      const response = requirement === 'contract'
        ? await api.confirmOrderContract(orderId)
        : await api.confirmOrderPayment(orderId);
      setBatchFormalOrders(current => current.map(order => Number(order.id) === orderId ? response.order : order));
    } catch (err) { setError(err instanceof Error ? err.message : '订单确认失败'); }
    finally { setLoading(false); }
  };

  const approveAndSend = async () => {
    if (!rfqTask) return;
    setLoading(true); setError(''); setStage('正在加入后台发送队列');
    try {
      await api.approveChainXiaoYiTask(rfqTask.id);
      await api.sendChainXiaoYiTaskAsync(rfqTask.id);
      setRfqTask({ ...rfqTask, status: 'queued' }); setStage('后台正在发送询价');
      for (let attempt = 0; attempt < 20; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 750));
        const progress = await api.getChainXiaoYiTaskProgress(rfqTask.id); setTaskProgress(progress);
        if (['sent', 'partial_failure', 'timed_out', 'completed'].includes(progress.task.status)) {
          setRfqTask({ ...rfqTask, status: progress.task.status });
          setQuoteSummary(await api.getChainXiaoYiQuoteSummary(rfqTask.id));
          const terminal = progress.task.status === 'timed_out' ? `，${progress.counts.timed_out || 0} 家已超时未回复` : progress.counts.failed ? `，${progress.counts.failed} 家发送失败，可在待办中重试` : '';
          setMessages(previous => [...previous, { role: 'assistant', content: `询价已发送给 ${progress.counts.sent || 0} 家供应商${terminal}。` }]);
          await refreshHistory();
          return;
        }
      }
      setMessages(previous => [...previous, { role: 'assistant', content: '询价已进入后台队列，你可以关闭页面，稍后从待办任务继续查看。' }]);
    } catch (err) { setError(err instanceof Error ? err.message : '询价发送失败'); }
    finally { setLoading(false); setStage(''); }
  };

  const createOrderDraft = async (supplierId: number) => {
    if (!rfqTask) return;
    setLoading(true); setError('');
    try { setOrderDraft((await api.createChainXiaoYiOrderDraft(rfqTask.id, supplierId)).order); }
    catch (err) { setError(err instanceof Error ? err.message : '订单草稿生成失败'); }
    finally { setLoading(false); }
  };

  const confirmOrderDraft = async () => {
    if (!rfqTask || !orderDraft || typeof orderDraft.supplier_id !== 'number') return;
    if (!window.confirm('确认创建正式订单？合同签署和付款仍会分别再次确认。')) return;
    setLoading(true); setError('');
    try { setFormalOrder((await api.confirmChainXiaoYiOrderDraft(rfqTask.id, orderDraft.supplier_id)).order); }
    catch (err) { setError(err instanceof Error ? err.message : '正式订单创建失败'); }
    finally { setLoading(false); }
  };

  const confirmFormalOrderRequirement = async (requirement: 'contract' | 'payment') => {
    const orderId = formalOrder && Number(formalOrder.id);
    if (!orderId) return;
    setLoading(true); setError('');
    try {
      const response = requirement === 'contract'
        ? await api.confirmOrderContract(orderId)
        : await api.confirmOrderPayment(orderId);
      setFormalOrder(response.order);
    } catch (err) { setError(err instanceof Error ? err.message : '订单确认失败'); }
    finally { setLoading(false); }
  };

  const refreshRfq = async () => {
    if (!rfqTask) return;
    setLoading(true); setError('');
    try {
      const [summary, progress, audit] = await Promise.all([api.getChainXiaoYiQuoteSummary(rfqTask.id), api.getChainXiaoYiTaskProgress(rfqTask.id), api.getChainXiaoYiTaskAudit(rfqTask.id)]);
      setQuoteSummary(summary); setTaskProgress(progress); setTaskAudit(audit);
    } catch (err) { setError(err instanceof Error ? err.message : '询价状态刷新失败'); }
    finally { setLoading(false); }
  };

  const retryRfq = async () => {
    if (!rfqTask) return;
    setLoading(true); setError('');
    try { setTaskProgress((await api.retryChainXiaoYiTask(rfqTask.id)).progress); await refreshRfq(); }
    catch (err) { setError(err instanceof Error ? err.message : '询价重试失败'); setLoading(false); }
  };

  const loadEnterpriseEvidence = async (enterpriseId: number) => {
    if (enterpriseEvidence[enterpriseId]) { setEnterpriseEvidence(current => { const next = { ...current }; delete next[enterpriseId]; return next; }); return; }
    setLoading(true); setError('');
    try { const evidence = await api.getEnterpriseDataEvidence(enterpriseId); setEnterpriseEvidence(current => ({ ...current, [enterpriseId]: evidence })); }
    catch (err) { setError(err instanceof Error ? err.message : '数据证据加载失败'); }
    finally { setLoading(false); }
  };

  const applyQuoteQuery = async () => {
    if (!rfqTask || !quoteQuery.trim()) return;
    setLoading(true); setError('');
    try {
      const response = await api.queryChainXiaoYiQuotes(rfqTask.id, quoteQuery.trim());
      setQuoteSummary(current => current ? { ...current, quotes: response.quotes, recommendation: response.quotes[0] ? { ...response.quotes[0], reason: response.explanation } : null } : null);
      setQuoteQueryExplanation(response.explanation);
    } catch (err) { setError(err instanceof Error ? err.message : '报价筛选失败'); }
    finally { setLoading(false); }
  };

  const cancelRfq = async () => {
    if (!rfqTask || !window.confirm('确认暂停这条询价任务？暂停后不会继续向供应商发送。')) return;
    setLoading(true); setError('');
    try { const response = await api.cancelChainXiaoYiTask(rfqTask.id, '采购方手动暂停'); setRfqTask({ ...rfqTask, status: response.status }); await refreshHistory(); }
    catch (err) { setError(err instanceof Error ? err.message : '任务暂停失败'); }
    finally { setLoading(false); }
  };

  const resumeRfq = async () => {
    if (!rfqTask) return;
    setLoading(true); setError('');
    try { const response = await api.resumeChainXiaoYiTask(rfqTask.id); setRfqTask({ ...rfqTask, status: response.status }); await refreshHistory(); }
    catch (err) { setError(err instanceof Error ? err.message : '任务恢复失败'); }
    finally { setLoading(false); }
  };

  const HistoryPanel = <aside className="flex h-full flex-col border-r border-public-border bg-white p-4">
    <button type="button" onClick={() => { setSession(null); setMessages([]); setMatches(null); setIntent({}); setSuggestions([]); setItemMatches([]); setActiveItemIndex(null); setMaterialSelections({}); setBatchRfqPreview(null); setHistoryOpen(false); }} className="btn-public-primary w-full"><Plus className="h-4 w-4" />新建会话</button>
    {user && taskInbox.length > 0 && <div className="mt-5"><h2 className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-public-muted"><Check className="h-4 w-4" />待办任务</h2><div className="mt-2 space-y-2">{taskInbox.slice(0, 6).map(item => <button key={item.id} type="button" onClick={() => void openTask(item)} className="w-full rounded-lg border border-amber-200 bg-amber-50 p-3 text-left"><p className="truncate text-xs font-bold text-amber-900">{item.product || (item.type === 'rfq' ? '询价任务' : '材料采购任务')}</p><p className="mt-1 text-[10px] text-amber-700">{{ review_and_approve: '待审批发送', resolve_fields: '待确认字段', send_rfq: '待发送', processing: '后台处理中', retry_failed: '发送失败待重试', await_supplier_quotes: '等待/查看报价', resume_task: '已暂停，可恢复' }[item.next_action || ''] || item.status}</p></button>)}</div></div>}
    <h2 className="mt-6 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-public-muted"><History className="h-4 w-4" />历史会话</h2>
    {!user ? <button type="button" onClick={() => requestLogin('/aia')} className="mt-4 rounded-lg bg-public-bg p-4 text-left text-xs leading-5 text-public-muted">登录后查看历史会话并继续追问</button> : <div className="mt-3 space-y-2 overflow-y-auto">{history.map(item => <div key={item.id} className="group rounded-lg border border-public-border p-3"><button type="button" onClick={() => void openHistory(item)} className="w-full text-left"><p className="truncate text-sm font-bold">{item.title || '找厂会话'}</p><p className="mt-1 text-[11px] text-public-muted">{item.match_count ?? 0} 家候选 · {item.updated_at?.slice(0, 10)}</p></button><button type="button" aria-label="归档会话" onClick={() => void archive(item)} className="mt-2 text-public-muted opacity-0 transition group-hover:opacity-100"><Archive className="h-3.5 w-3.5" /></button></div>)}</div>}
  </aside>;

  const orderConfirmationPanel = formalOrder ? (() => {
    const metadata = (formalOrder.metadata || {}) as Record<string, unknown>;
    const orderId = Number(formalOrder.id || 0);
    const contractConfirmed = Boolean(metadata.contract_confirmed_at);
    const paymentConfirmed = Boolean(metadata.payment_confirmed_at);
    return <div className="mt-2 rounded bg-emerald-50 p-2 text-[11px] text-emerald-700">
      <p>正式订单 {String(formalOrder.order_no || '')} 已创建。</p>
      <p className="mt-1">合同和付款仍需分别确认，确认后订单才能进入执行。</p>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={loading || !orderId || contractConfirmed} onClick={() => void confirmFormalOrderRequirement('contract')} className="btn-public-secondary btn-sm">{contractConfirmed ? '合同已确认' : '确认合同'}</button>
        <button type="button" disabled={loading || !orderId || paymentConfirmed} onClick={() => void confirmFormalOrderRequirement('payment')} className="btn-public-secondary btn-sm">{paymentConfirmed ? '付款已确认' : '确认付款'}</button>
      </div>
    </div>;
  })() : null;

  const taskAuditPanel = taskAudit ? <details className="mb-3 rounded-xl border border-public-border bg-white p-3 text-[10px] text-public-muted">
    <summary className="cursor-pointer text-xs font-black text-public-text">任务审计 · {taskAudit.task.status}</summary>
    <div className="mt-2 grid grid-cols-3 gap-2"><span>候选快照 {taskAudit.candidates.length}</span><span>审批 {taskAudit.approvals.length}</span><span>外发 {taskAudit.outbound.length}</span></div>
    {taskAudit.approvals.map((approval, index) => <p key={`approval-${index}`} className="mt-2 rounded bg-public-bg p-2">审批：{approval.decision} · 操作人 #{approval.decided_by || '—'} · {approval.decided_at ? new Date(approval.decided_at).toLocaleString('zh-CN') : '待记录'}{approval.comment ? ` · ${approval.comment}` : ''}</p>)}
    {taskAudit.candidates.map(candidate => <p key={candidate.supplier_id} className="mt-1">候选：{candidate.name || `#${candidate.supplier_id}`} · {candidate.trust_profile.claim_status || '未认领'} · {candidate.trust_profile.contact_authorized ? '已授权触达' : '未授权'} · 数据更新 {candidate.data_updated_at || '待补充'}</p>)}
    <div className="mt-2 border-t border-public-border pt-2">{taskAudit.events.slice(-8).map((event, index) => <p key={`${event.type}-${index}`} className="mt-1">{new Date(event.created_at).toLocaleString('zh-CN')} · {event.type}</p>)}</div>
  </details> : null;

  const timeoutRetryPanel = taskProgress && (taskProgress.counts.timed_out || 0) > 0
    ? <button type="button" disabled={loading} onClick={() => void retryRfq()} className="mb-3 w-full rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-left text-[11px] font-bold text-amber-800">{taskProgress.counts.timed_out} 家供应商已超时，点击重新触达</button>
    : null;

  const ResultsPanel = <aside className="h-full overflow-y-auto border-l border-public-border bg-public-bg p-4">
    {orderConfirmationPanel}
    {taskAuditPanel}
    {timeoutRetryPanel}
    {itemMatches.length > 0 && <div className="mb-3 rounded-xl border border-public-border bg-white p-3"><p className="text-xs font-black">材料采购项 · 已自动分别找厂</p><div className="mt-2 flex flex-wrap gap-2">{itemMatches.map(item => <button key={item.item_index} type="button" onClick={() => selectMaterialItem(item)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${activeItemIndex === item.item_index ? 'border-public-brand bg-public-brand-soft text-public-brand' : 'border-public-border text-public-muted'}`}>#{item.item_index} {String(item.intent.product || '待确认产品')} · {item.match_result.total}家</button>)}</div><button type="button" disabled={loading || Boolean(batchRfqPreview)} onClick={() => void createBatchRfqPreview()} className="btn-public-primary btn-sm mt-3 w-full">{batchRfqPreview ? '已生成统一询价审批卡' : '生成全部采购项统一询价预览'}</button>{batchRfqPreview && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800"><p>将发送 {batchRfqPreview.item_count} 个采购项，共 {batchRfqPreview.supplier_count} 个供应商触达记录。</p><p className="mt-1">渠道：{batchRfqPreview.channels.join('、')}。每个采购项的产品、数量、规格和询价正文已纳入预览。</p>{batchRfqPreview.quote_deadline_at && <p className="mt-1">供应商回复截止：{new Date(batchRfqPreview.quote_deadline_at).toLocaleString('zh-CN')}，逾期未回复会自动标记为超时。</p>}{batchRfqPreview.status === 'awaiting_approval' ? <button type="button" disabled={loading} onClick={() => void approveBatchRfq()} className="btn-public-primary btn-sm mt-2 w-full">一次确认并全部加入发送队列</button> : <p className="mt-2 font-bold text-emerald-700">已确认，后台发送中</p>}</div>}</div>}
    {procurementTask && batchRfqPreview && batchRfqPreview.status !== 'awaiting_approval' && <div className="mb-3 rounded-xl border border-public-brand/20 bg-white p-3">
      <div className="flex items-center justify-between"><p className="text-xs font-black">全部采购项报价与选厂</p><button type="button" disabled={loading} onClick={() => void refreshBatchQuotes()} className="text-[11px] text-public-brand">刷新全部报价</button></div>
      <p className="mt-1 text-[10px] text-public-muted">一句话会分别应用到每个采购项；价格、税率和交期只读取供应商实际回复。</p>
      <div className="mt-2 flex gap-1"><input value={batchQuoteQuery} onChange={event => setBatchQuoteQuery(event.target.value)} aria-label="批量报价筛选条件" className="min-w-0 flex-1 rounded border border-public-border px-2 py-1.5 text-[10px]"/><button type="button" disabled={loading || !batchQuoteQuery.trim()} onClick={() => void applyBatchQuoteQuery()} className="btn-public-secondary btn-sm">逐项筛选</button></div>
      {batchQuoteSummary && <div className="mt-2 space-y-2">
        <p className="text-[10px] text-public-muted">{batchQuoteSummary.quoted_item_count}/{batchQuoteSummary.item_count} 个采购项已有符合条件的报价，共 {batchQuoteSummary.quote_count} 份。</p>
        {batchQuoteSummary.items.map(item => <div key={item.rfq_task_id} className="rounded bg-public-bg p-2 text-[10px]"><p className="font-bold">#{item.item_index} {item.product}</p>{item.quotes.length ? item.quotes.map(quote => <p key={quote.quote_id} className="mt-1 text-public-muted">{quote.supplier_name} · ¥{quote.price}/{quote.unit}{quote.tax_included ? ' · 含税' : ''}{quote.delivery_days ? ` · ${quote.delivery_days}天` : ''}</p>) : <p className="mt-1 text-amber-700">暂无符合条件的报价</p>}</div>)}
        <button type="button" disabled={loading || !batchQuoteSummary.complete} onClick={() => void createBatchOrderDrafts()} className="btn-public-primary btn-sm w-full">按这句话生成全部订单草稿</button>
      </div>}
      {batchOrderDrafts.length > 0 && batchFormalOrders.length === 0 && <div className="mt-2 rounded bg-emerald-50 p-2 text-[11px] text-emerald-700"><p>已生成 {batchOrderDrafts.length} 份订单草稿；正式订单、合同和付款尚未执行。</p><button type="button" disabled={loading} onClick={() => void confirmBatchOrderDrafts()} className="btn-public-primary btn-sm mt-2 w-full">人工确认并创建全部正式订单</button></div>}
      {batchFormalOrders.length > 0 && <div className="mt-2 space-y-2">{batchFormalOrders.map(order => {
        const metadata = (order.metadata || {}) as Record<string, unknown>;
        const orderId = Number(order.id || 0);
        return <div key={orderId} className="rounded bg-emerald-50 p-2 text-[10px] text-emerald-800"><p className="font-bold">正式订单 {String(order.order_no || '')}</p><p className="mt-1">合同：{metadata.contract_confirmed_at ? '已确认' : '待确认'} · 付款：{metadata.payment_confirmed_at ? '已确认' : '待确认'}</p><div className="mt-2 flex gap-2"><button type="button" disabled={loading || Boolean(metadata.contract_confirmed_at)} onClick={() => void confirmBatchOrderRequirement(orderId, 'contract')} className="btn-public-secondary btn-sm">确认合同</button><button type="button" disabled={loading || Boolean(metadata.payment_confirmed_at)} onClick={() => void confirmBatchOrderRequirement(orderId, 'payment')} className="btn-public-secondary btn-sm">确认付款</button></div></div>;
      })}</div>}
    </div>}
    <div className="flex items-center justify-between"><div><p className="text-xs font-bold text-public-brand">实时匹配</p><h2 className="mt-1 font-black">{matches ? `${matches.total} 家候选工厂` : '等待需求'}</h2></div>{session && user && matches && <a href={`/api/chain-xiaoyi/sessions/${session.id}/export.xlsx`} className="btn-public-secondary btn-sm"><Download className="h-3.5 w-3.5" />导出</a>}</div>
    {matches?.degraded && <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-[11px] text-amber-700">解释模型不可用，本轮使用确定性数据库理由；匹配与排序不受影响。</p>}
    {user && (matches || rfqTask) && <div className="mt-3 rounded-xl border border-public-brand/20 bg-white p-3"><div className="flex items-center justify-between"><p className="text-xs font-black">批量询价工作台</p><span className="text-[11px] text-public-muted">已选 {selectedSuppliers.length} 家</span></div><p className="mt-1 text-[11px] text-public-muted">仅可触达已认领且授权的供应商；发送前将显示完整内容并由你确认。</p>{!rfqTask && <div className="mt-2 flex gap-2 text-[10px]"><span className="rounded bg-public-brand-soft px-2 py-1 text-public-brand">站内消息（默认）</span>{['email', 'wechat', 'work_wechat'].map(channel => <button key={channel} type="button" aria-pressed={rfqChannels.includes(channel)} onClick={() => setRfqChannels(current => current.includes(channel) ? current.filter(value => value !== channel) : [...current, channel])} className={`rounded border px-2 py-1 ${rfqChannels.includes(channel) ? 'border-public-brand bg-public-brand-soft text-public-brand' : 'border-public-border text-public-muted'}`}>{channel === 'email' ? '邮件' : channel === 'wechat' ? '微信' : '企业微信'}（仅授权时）</button>)}</div>}<button type="button" disabled={!selectedSuppliers.length || loading || rfqTask?.status === 'cancelled'} onClick={() => void createRfqPreview()} className="btn-public-primary btn-sm mt-3 w-full"><FileUp className="h-3.5 w-3.5" />生成询价发送预览</button>{rfqTask?.status === 'awaiting_approval' && <RfqApprovalPreview preview={rfqTask.preview} />}{rfqTask?.status === 'awaiting_approval' && <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800">预览已生成。点击确认后将向选中的供应商发送询价；外部渠道只在企业单独授权且配置可用时尝试。{rfqTask.quote_deadline_at && <span className="mt-1 block">供应商回复截止：{new Date(rfqTask.quote_deadline_at).toLocaleString('zh-CN')}。</span>}</div>}{rfqTask?.status === 'awaiting_approval' && <button type="button" disabled={loading} onClick={() => void approveAndSend()} className="btn-public-primary btn-sm mt-2 w-full"><Check className="h-3.5 w-3.5" />确认并发送</button>}{rfqTask?.status === 'awaiting_approval' && <button type="button" disabled={loading} onClick={() => void cancelRfq()} className="btn-public-secondary btn-sm mt-2 w-full">暂停询价任务</button>}{rfqTask?.status === 'cancelled' && <button type="button" disabled={loading} onClick={() => void resumeRfq()} className="btn-public-primary btn-sm mt-2 w-full">恢复询价任务</button>}{quoteSummary && <div className="mt-3 border-t pt-3"><div className="flex items-center justify-between"><p className="text-xs font-black">报价汇总</p><button type="button" disabled={loading} onClick={() => void refreshRfq()} className="text-[11px] text-public-brand">刷新状态</button></div><div className="mt-2 flex gap-1"><input value={quoteQuery} onChange={event => setQuoteQuery(event.target.value)} placeholder="例如：只看含税价最低且30天内交付的三家" className="min-w-0 flex-1 rounded border border-public-border px-2 py-1.5 text-[10px]"/><button type="button" disabled={loading || !quoteQuery.trim()} onClick={() => void applyQuoteQuery()} className="btn-public-secondary btn-sm">筛选</button></div>{quoteQueryExplanation && <p className="mt-1 text-[10px] text-public-muted">{quoteQueryExplanation}</p>}{taskProgress && <p className="mt-1 text-[10px] text-public-muted">已发送 {taskProgress.counts.sent || 0} · 已送达 {taskProgress.counts.delivered || 0} · 已回复 {taskProgress.counts.replied || 0} · 已拒绝 {taskProgress.counts.rejected || 0} · 超时 {taskProgress.counts.timed_out || 0} · 失败 {taskProgress.counts.failed || 0}{taskProgress.deadline?.at ? ` · 截止 ${new Date(taskProgress.deadline.at).toLocaleString('zh-CN')}` : ''}</p>}{quoteSummary.quotes.length ? quoteSummary.quotes.map(quote => <div key={quote.quote_id} className="mt-2 flex items-center justify-between rounded bg-public-bg p-2 text-[11px]"><span>{quote.supplier_name} · ¥{quote.price}/{quote.unit}{quote.tax_included ? ' · 含税' : ''}{quote.delivery_days ? ` · ${quote.delivery_days}天` : ''}</span><button type="button" onClick={() => void createOrderDraft(quote.supplier_id)} className="btn-public-secondary btn-sm">生成订单草稿</button></div>) : <p className="mt-2 text-[11px] text-public-muted">等待供应商在站内回复报价，或当前筛选条件下没有结果。</p>}{quoteSummary.recommendation && <p className="mt-2 text-[11px] text-emerald-700">推荐：{quoteSummary.recommendation.supplier_name}。{quoteSummary.recommendation.reason}</p>}{taskProgress && taskProgress.counts.failed > 0 && <button type="button" disabled={loading} onClick={() => void retryRfq()} className="btn-public-secondary btn-sm mt-2 w-full">重试失败发送</button>}{orderDraft && !formalOrder && <div className="mt-2 rounded bg-emerald-50 p-2 text-[11px] text-emerald-700"><p>订单草稿已生成，尚未创建正式订单。</p><button type="button" disabled={loading} onClick={() => void confirmOrderDraft()} className="btn-public-primary btn-sm mt-2 w-full">人工确认并创建正式订单</button></div>}{formalOrder && <p className="mt-2 rounded bg-emerald-50 p-2 text-[11px] text-public-brand">正式订单 {String(formalOrder.order_no || '')} 已创建；合同和付款仍需分别确认。</p>}</div>}</div>}
    <div className="mt-4 space-y-3">{matches?.results.map((item, index) => <article key={item.id} className="rounded-xl border border-public-border bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-[10px] font-bold text-public-muted">#{index + 1} · {item.province}{item.city}</p><h3 className="mt-1 truncate font-black">{item.name}</h3></div><div className="flex items-center gap-2"><span className="shrink-0 text-xl font-black text-emerald-600">{Math.round(item.score)}<small className="text-[10px]">分</small></span>{user && item.contact_eligible && <input aria-label={`选择${item.name}`} type="checkbox" checked={selectedSuppliers.includes(item.id)} onChange={event => { const next = event.target.checked ? [...selectedSuppliers, item.id] : selectedSuppliers.filter(id => id !== item.id); setSelectedSuppliers(next); if (activeItemIndex !== null) setMaterialSelections(current => ({ ...current, [activeItemIndex]: next })); }} />}</div></div><p className="mt-3 text-xs leading-5 text-public-muted">{item.reason}</p><p className="mt-2 text-[10px] text-public-muted">{item.contact_eligible ? '已认领 · 已授权触达' : '未认领或未授权触达，不可自动询价'} · 数据更新：{item.data_updated_at || '待补充'} · {freshnessLabel(item)}</p><div className="mt-3 grid grid-cols-3 gap-1">{(Object.entries(item.dimensions) as Array<[string, { score?: number; desc?: string }]>).map(([key, value]) => <div key={key} title={value.desc || ''} className="rounded bg-public-bg px-1.5 py-1 text-center"><p className="text-[9px] text-public-muted">{DIMENSION_NAMES[key] || key}</p><p className="text-[11px] font-bold">{typeof value.score === 'number' ? Math.round(value.score <= 1 ? value.score * 100 : value.score) : '—'}</p></div>)}</div>{enterpriseEvidence[item.id] && <div className="mt-3 rounded bg-public-bg p-2 text-[10px] text-public-muted"><p>{enterpriseEvidence[item.id].is_demo ? '演示数据' : '可核验档案'} · 来源 {enterpriseEvidence[item.id].sources.length} 个 · 更新 {enterpriseEvidence[item.id].updated_at || '待补充'}</p>{enterpriseEvidence[item.id].sources.map((source, sourceIndex) => <p key={sourceIndex} className="mt-1">来源：{String(source.name || source.source_type || '未命名来源')}</p>)}{enterpriseEvidence[item.id].uncertain_fields.length > 0 && <p className="mt-1 text-amber-700">不确定字段：{enterpriseEvidence[item.id].uncertain_fields.join('、')}</p>}</div>}<div className="mt-4 flex gap-2"><button type="button" onClick={() => navigate(`/factory/${item.id}`)} className="btn-public-secondary btn-sm flex-1">详情</button><button type="button" onClick={() => user ? void loadEnterpriseEvidence(item.id) : requestLogin('/aia')} className="btn-public-secondary btn-sm flex-1">{enterpriseEvidence[item.id] ? '收起证据' : '数据证据'}</button><button type="button" onClick={() => user ? navigate(`/matching?query=${encodeURIComponent(String(intent.product || ''))}&supplier_id=${item.id}`) : requestLogin('/aia')} className="btn-public-primary btn-sm flex-1"><ShieldCheck className="h-3.5 w-3.5" />询价</button></div></article>)}</div>
    {matches && matches.total === 0 && <div className="mt-8 rounded-xl border border-dashed border-public-border bg-white p-6 text-center text-sm text-public-muted">没有符合全部硬条件的企业。可在对话中说“取消地区限制”或放宽资质要求。</div>}
  </aside>;

  return <div className="public-site flex h-screen flex-col overflow-hidden bg-public-bg text-public-text"><PublicSiteHeader onLogin={() => requestLogin('/aia')} />
    <div className="flex min-h-0 flex-1 lg:grid lg:grid-cols-[240px_minmax(420px,1fr)_380px]">
      <div className="hidden min-h-0 lg:block">{HistoryPanel}</div>
      <main className="flex min-w-0 flex-1 flex-col bg-white">
        <header className="flex items-center justify-between border-b border-public-border px-4 py-3"><button type="button" aria-label="打开历史" onClick={() => setHistoryOpen(true)} className="lg:hidden"><Menu className="h-5 w-5" /></button><div className="text-center"><h1 className="font-black">链小易 · AI 找工厂</h1><p className="text-[10px] text-public-muted">数据库九维算法决定召回、排序与分数</p></div><button type="button" aria-label="打开结果" onClick={() => setResultsOpen(true)} className="lg:hidden"><PanelRight className="h-5 w-5" /></button></header>
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8"><div className="mx-auto max-w-3xl space-y-5">{messages.length === 0 && <section className="py-12 text-center"><span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-public-brand text-white"><Sparkles className="h-7 w-7" /></span><h2 className="mt-5 text-2xl font-black">用一句话描述你要找的工厂</h2><p className="mt-2 text-sm text-public-muted">产品、工艺、地区、数量、交期和资质都可以直接说</p><div className="mt-6 flex flex-wrap justify-center gap-2">{QUICK_PROMPTS.map(prompt => <button key={prompt} type="button" onClick={() => void send(prompt)} className="rounded-full border border-public-border px-3 py-2 text-xs hover:border-public-brand hover:text-public-brand">{prompt}</button>)}</div></section>}{messages.map((message, index) => <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'bg-public-brand text-white' : 'bg-public-bg text-public-text'}`}>{message.role === 'assistant' && <MessageSquare className="mr-2 inline h-4 w-4 text-public-brand" />}{message.content}</div></div>)}{Object.keys(intent).length > 0 && <IntentChips intent={intent} />}{procurementDraft?.conflicts?.map(conflict => <div key={conflict.field} className="rounded-xl border border-amber-200 bg-amber-50 p-3"><p className="text-xs font-black text-amber-900">材料中的“{conflict.field}”存在冲突，请确认：</p><div className="mt-2 flex flex-wrap gap-2">{conflict.values.map((value, index) => <button key={`${conflict.field}-${index}`} type="button" disabled={loading} onClick={() => void confirmMaterialField(conflict.field, value)} className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs text-amber-900">{String(value)}</button>)}</div></div>)}{suggestions.length > 0 && <div className="flex flex-wrap gap-2">{suggestions.map(item => <button key={item} type="button" onClick={() => setQuery(item)} className="rounded-full bg-public-bg px-3 py-1.5 text-[11px] text-public-muted">{item}<ChevronRight className="ml-1 inline h-3 w-3" /></button>)}</div>}{loading && <div className="flex items-center gap-2 text-sm text-public-muted"><Loader2 className="h-4 w-4 animate-spin text-public-brand" />{stage}</div>}{error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}</div></div>
        <form onSubmit={submit} className="border-t border-public-border bg-white p-4"><div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-public-border bg-public-bg p-2 focus-within:border-public-brand"><button type="button" aria-label="上传采购材料" onClick={() => user ? fileInput.current?.click() : requestLogin('/aia')} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-public-border bg-white text-public-muted hover:text-public-brand"><FileUp className="h-4 w-4" /></button><input ref={fileInput} type="file" multiple accept=".csv,.xlsx,.pdf,.docx" className="hidden" onChange={event => { const files = Array.from(event.currentTarget.files || []) as File[]; if (files.length) void uploadMaterials(files); event.currentTarget.value = ''; }} /><textarea value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(query); } }} rows={2} maxLength={2000} placeholder="说出需求，或直接上传 Excel、PDF、Word 采购材料" className="min-h-12 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none" /><button type="submit" disabled={loading || !query.trim()} className="flex h-10 w-10 items-center justify-center rounded-lg bg-public-brand text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></div><p className="mx-auto mt-2 max-w-3xl text-center text-[10px] text-public-muted">可一次上传多个材料；系统合并字段并标记冲突，对外发送询价前必须由你确认。</p></form>
      </main>
      <div className="hidden min-h-0 lg:block">{ResultsPanel}</div>
    </div>
    {historyOpen && <div className="fixed inset-0 z-50 flex bg-black/30 lg:hidden"><div className="h-full w-[82%] max-w-xs">{HistoryPanel}</div><button type="button" aria-label="关闭" onClick={() => setHistoryOpen(false)} className="m-4 h-9 w-9 rounded-full bg-white"><X className="mx-auto h-4 w-4" /></button></div>}
    {resultsOpen && <div className="fixed inset-0 z-50 flex justify-end bg-black/30 lg:hidden"><button type="button" aria-label="关闭" onClick={() => setResultsOpen(false)} className="m-4 h-9 w-9 rounded-full bg-white"><X className="mx-auto h-4 w-4" /></button><div className="h-full w-[88%] max-w-md">{ResultsPanel}</div></div>}
  </div>;
}
