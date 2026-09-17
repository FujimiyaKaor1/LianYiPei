import { FormEvent, PointerEvent, useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, FileUp, Minus, Send, Sparkles, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api, type ChainXiaoYiModelStatus } from '@/src/services/api';
import { useAuth } from '@/src/context/AuthContext';
import { SESSION_STORAGE_PREFIX } from '@/src/lib/authEvents';

type PanelMessage = { id: string; role: 'user' | 'assistant'; content: string; intent?: Record<string, unknown> };

const SESSION_KEY = `${SESSION_STORAGE_PREFIX}chain-xiaoyi-session`;
const POSITION_KEY = `${SESSION_STORAGE_PREFIX}chain-xiaoyi-position`;
const ENTRY_POSITION_KEY = `${SESSION_STORAGE_PREFIX}chain-xiaoyi-entry-position`;

type PanelPosition = { right: number; bottom: number };

function readSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) as { id: number } : null;
  } catch {
    return null;
  }
}

function readPosition(key: string): PanelPosition {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return { right: 20, bottom: 20 };
    const parsed = JSON.parse(raw) as Partial<PanelPosition>;
    return {
      right: typeof parsed.right === 'number' ? parsed.right : 20,
      bottom: typeof parsed.bottom === 'number' ? parsed.bottom : 20,
    };
  } catch {
    return { right: 20, bottom: 20 };
  }
}

export function ChainXiaoYiPanel() {
  const { user, requestLogin } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<PanelMessage[]>([
    { id: 'welcome', role: 'assistant', content: '你好，我是链小易。你可以直接告诉我想采购什么、找什么工厂，或者上传一张表，我会帮你整理成下一步任务。' },
  ]);
  const [session, setSession] = useState<{ id: number } | null>(readSession);
  const [modelStatus, setModelStatus] = useState<ChainXiaoYiModelStatus | null>(null);
  const [lastIntent, setLastIntent] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [position, setPosition] = useState(() => readPosition(POSITION_KEY));
  const [entryPosition, setEntryPosition] = useState(() => readPosition(ENTRY_POSITION_KEY));
  const dragRef = useRef<{ x: number; y: number; right: number; bottom: number } | null>(null);
  const entryDragRef = useRef<{ x: number; y: number; right: number; bottom: number; moved: boolean } | null>(null);
  const suppressEntryClick = useRef(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    void api.fetchChainXiaoYiModelStatus().then(setModelStatus).catch(() => undefined);
  }, []);

  const ensureSession = async () => {
    if (session) return session;
    const response = await api.createChainXiaoYiSession(user ? 'enterprise' : 'public');
    const next = { id: response.session.id };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
    setSession(next);
    setModelStatus(response.model_status);
    return next;
  };

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = input.trim();
    if (!content || busy) return;
    setInput('');
    setMessages(current => [...current, { id: `u-${Date.now()}`, role: 'user', content }]);
    setBusy(true); setNotice('');
    try {
      const currentSession = await ensureSession();
      const response = await api.sendChainXiaoYiMessage(currentSession.id, content);
      setModelStatus(response.model_status);
      setLastIntent(response.intent);
      setMessages(current => [...current, { id: `a-${Date.now()}`, role: 'assistant', content: response.reply, intent: response.intent }]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '链小易暂时无法响应，请稍后重试');
    } finally { setBusy(false); }
  };

  const createDraft = async () => {
    if (!lastIntent) return;
    if (!user) { requestLogin('/aia'); return; }
    setBusy(true); setNotice('');
    try {
      const currentSession = await ensureSession();
      const response = await api.createChainXiaoYiDemandDraft(currentSession.id, lastIntent);
      setNotice(`需求草稿已创建（#${response.inquiry.id}），正在进入匹配`);
      navigate(`/matching?query=${encodeURIComponent(String(lastIntent.product || ''))}&inquiry_id=${response.inquiry.id}&mode=agent`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '需求草稿创建失败');
    } finally { setBusy(false); }
  };

  const upload = async (file: File) => {
    setBusy(true); setNotice('正在读取文件并生成预览…');
    try {
      const currentSession = await ensureSession();
      const response = await api.previewChainXiaoYiFile(currentSession.id, file);
      const preview = response.file.preview;
      const sheetCount = Array.isArray(preview.sheets) ? preview.sheets.length : 0;
      setMessages(current => [...current, { id: `f-${Date.now()}`, role: 'assistant', content: `文件已安全接收：${response.file.filename}。识别为${response.file.detected_kind === 'table' ? '表格' : '文档'}，${sheetCount ? `发现 ${sheetCount} 个工作表` : '等待人工确认导入类型'}。当前只生成预览，不会自动写入业务数据。` }]);
      setNotice(response.file.errors.length ? response.file.errors.join('；') : '预览已生成，请确认字段后再导入');
    } catch (error) { setNotice(error instanceof Error ? error.message : '文件处理失败'); }
    finally { setBusy(false); }
  };

  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('button, input, textarea, select, a, [role="button"], [data-no-drag], [data-scrollable]')) return;
    dragRef.current = { x: event.clientX, y: event.clientY, right: position.right, bottom: position.bottom };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current) return;
    const nextRight = Math.max(8, Math.min(Math.max(8, window.innerWidth - 120), dragRef.current.right - (event.clientX - dragRef.current.x)));
    const nextBottom = Math.max(8, Math.min(Math.max(8, window.innerHeight - 120), dragRef.current.bottom - (event.clientY - dragRef.current.y)));
    const nextPosition = { right: nextRight, bottom: nextBottom };
    setPosition(nextPosition);
    localStorage.setItem(POSITION_KEY, JSON.stringify(nextPosition));
  };

  const stopDrag = () => { dragRef.current = null; };

  const startEntryDrag = (event: PointerEvent<HTMLButtonElement>) => {
    suppressEntryClick.current = false;
    entryDragRef.current = { x: event.clientX, y: event.clientY, right: entryPosition.right, bottom: entryPosition.bottom, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveEntryDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (!entryDragRef.current) return;
    const deltaX = event.clientX - entryDragRef.current.x;
    const deltaY = event.clientY - entryDragRef.current.y;
    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      entryDragRef.current.moved = true;
      suppressEntryClick.current = true;
    }
    const nextPosition = {
      right: Math.max(8, Math.min(Math.max(8, window.innerWidth - 120), entryDragRef.current.right - deltaX)),
      bottom: Math.max(8, Math.min(Math.max(8, window.innerHeight - 80), entryDragRef.current.bottom - deltaY)),
    };
    setEntryPosition(nextPosition);
    localStorage.setItem(ENTRY_POSITION_KEY, JSON.stringify(nextPosition));
  };

  const stopEntryDrag = (cancelled = false) => {
    entryDragRef.current = null;
    if (cancelled) suppressEntryClick.current = false;
  };

  const openFromEntry = () => {
    if (suppressEntryClick.current) {
      suppressEntryClick.current = false;
      return;
    }
    setOpen(true);
  };

  return <>
    {!open && <button type="button" aria-label="打开链小易" onClick={openFromEntry} onPointerDown={startEntryDrag} onPointerMove={moveEntryDrag} onPointerUp={() => stopEntryDrag()} onPointerCancel={() => stopEntryDrag(true)} style={{ right: entryPosition.right, bottom: entryPosition.bottom, touchAction: 'none' }} className="fixed z-[80] flex cursor-grab items-center gap-2 rounded-full bg-public-brand px-4 py-3 text-sm font-bold text-white shadow-[0_12px_35px_rgba(36,107,219,.3)] transition hover:-translate-y-0.5 active:cursor-grabbing"><Sparkles className="h-4 w-4" />链小易</button>}
    {open && <div ref={panelRef} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag} style={{ right: position.right, bottom: position.bottom }} className="fixed z-[80] flex h-[min(680px,calc(100vh-40px))] w-[min(390px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl border border-public-border bg-white shadow-[0_18px_60px_rgba(20,33,61,.22)]">
      <div className="flex cursor-move items-center gap-3 bg-public-brand px-4 py-3 text-white" title="拖动链小易窗口"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15"><Bot className="h-5 w-5" /></span><div className="min-w-0 flex-1"><p className="text-sm font-black">链小易</p><p className="text-[10px] text-white/75">统一处理找厂、询价和业务协同 · 可拖动窗口</p></div><button data-no-drag type="button" onClick={() => setOpen(false)} aria-label="收起链小易" className="cursor-pointer rounded-lg p-1.5 hover:bg-white/15"><Minus className="h-4 w-4" /></button><button data-no-drag type="button" onClick={() => setOpen(false)} aria-label="关闭链小易" className="cursor-pointer rounded-lg p-1.5 hover:bg-white/15"><X className="h-4 w-4" /></button></div>
      <div className="border-b border-public-border bg-public-bg px-4 py-2 text-[11px] text-public-muted">{modelStatus?.message || '正在检查智能模型状态…'}</div>
      <div data-scrollable className="min-h-0 flex-1 space-y-3 overflow-y-auto bg-public-bg/60 p-4">{messages.map(message => <div key={message.id} className={message.role === 'user' ? 'ml-8 rounded-xl bg-public-brand px-3 py-2.5 text-sm leading-6 text-white' : 'mr-5 rounded-xl border border-public-border bg-white px-3 py-2.5 text-sm leading-6 text-public-text'}>{message.content}</div>)}{notice && <div className="rounded-lg border border-public-border bg-white px-3 py-2 text-xs text-public-muted">{notice}</div>}{lastIntent && <div className="rounded-xl border border-public-brand/20 bg-white p-3"><p className="text-xs font-black text-public-text">我理解的需求</p><div className="mt-2 flex flex-wrap gap-1.5">{['product', 'region', 'quantity', 'delivery_days'].filter(key => lastIntent[key] !== undefined).map(key => <span key={key} className="rounded bg-public-brand-soft px-2 py-1 text-[11px] font-semibold text-public-brand">{key}：{String(lastIntent[key])}</span>)}</div><button data-no-drag type="button" disabled={busy} onClick={() => void createDraft()} className="mt-3 inline-flex items-center gap-1 rounded-lg bg-public-brand px-3 py-2 text-xs font-bold text-white disabled:opacity-50">创建需求草稿并找厂 <ChevronDown className="h-3.5 w-3.5" /></button></div>}</div>
      <form onSubmit={send} className="border-t border-public-border bg-white p-3"><div className="flex items-end gap-2"><button type="button" aria-label="上传文件" onClick={() => fileInputRef.current?.click()} className="rounded-lg border border-public-border p-2.5 text-public-muted hover:text-public-brand"><FileUp className="h-4 w-4" /></button><input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls,.pdf,.doc,.docx" className="hidden" onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.currentTarget.value = ''; }} /><textarea value={input} onChange={event => setInput(event.target.value)} rows={2} placeholder="告诉链小易你的需求…" className="min-h-[44px] flex-1 resize-none rounded-lg border border-public-border px-3 py-2 text-sm outline-none focus:border-public-brand" /><button type="submit" disabled={busy || !input.trim()} aria-label="发送" className="rounded-lg bg-public-brand p-2.5 text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></div></form>
    </div>}
  </>;
}
