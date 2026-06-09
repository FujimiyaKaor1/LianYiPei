import React, { useEffect, useRef, useState } from 'react';
import { Download, MessageCircle, Minus, Send, Sparkles, Trash2, Upload } from 'lucide-react';
import { notifyIfUnauthorized } from '@/src/lib/authEvents';
import { api, ApiError } from '@/src/services/api';
import { getStoredModelChoice, setStoredModelChoice, type ModelChoice } from '@/src/lib/modelChoice';

type MessageRole = 'user' | 'assistant';
interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
}

function createMessageId(role: MessageRole) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatTimestamp(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function extractStreamText(payload: unknown): string {
  if (typeof payload === 'string') {
    return payload;
  }

  if (Array.isArray(payload)) {
    return payload.map(extractStreamText).join('');
  }

  if (typeof payload !== 'object' || payload === null) {
    return '';
  }

  const record = payload as Record<string, unknown>;
  const directKeys = ['content', 'text', 'response', 'answer', 'output_text'];

  for (const key of directKeys) {
    const text = extractStreamText(record[key]);
    if (text) {
      return text;
    }
  }

  const nestedKeys = ['delta', 'message'];

  for (const key of nestedKeys) {
    const text = extractStreamText(record[key]);
    if (text) {
      return text;
    }
  }

  const collectionKeys = ['choices', 'output', 'data'];

  for (const key of collectionKeys) {
    const text = extractStreamText(record[key]);
    if (text) {
      return text;
    }
  }

  return '';
}

function parseStreamPayload(payload: string) {
  const trimmedPayload = payload.trim();

  if (!trimmedPayload || trimmedPayload === '[DONE]') {
    return '';
  }

  try {
    const parsed = JSON.parse(trimmedPayload);
    return extractStreamText(parsed);
  } catch {
    return trimmedPayload;
  }
}

export function AISidebar() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [modelChoice, setModelChoice] = useState<ModelChoice>(getStoredModelChoice());
  const [useRag, setUseRag] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isUploadingPdf, setIsUploadingPdf] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const messagesListRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!messages.length) {
      return;
    }

    window.requestAnimationFrame(() => {
      const messageList = messagesListRef.current;
      if (!messageList) {
        return;
      }

      messageList.scrollTo({
        top: messageList.scrollHeight,
        behavior: 'smooth',
      });
    });
  }, [messages]);

  const updateAssistantMessage = (messageId: string, content: string) => {
    setMessages((previousMessages) =>
      previousMessages.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content,
            }
          : message,
      ),
    );
  };

  const sendMessage = async () => {
    const message = inputValue.trim();

    if (!message || isStreaming) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId('user'),
      role: 'user',
      content: message,
      timestamp: formatTimestamp(),
    };

    const assistantMessageId = createMessageId('assistant');
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: formatTimestamp(),
    };

    setMessages((previousMessages) => [
      ...previousMessages,
      userMessage,
      assistantMessage,
    ]);
    setInputValue('');
    setIsStreaming(true);

    let streamedContent = '';
    let hasReceivedContent = false;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          model_choice: modelChoice,
          use_rag: useRag,
        }),
      });

      if (notifyIfUnauthorized(response)) {
        setMessages((prev) =>
          prev.filter((m) => m.id !== userMessage.id && m.id !== assistantMessageId),
        );
        setIsStreaming(false);
        return;
      }

      if (!response.ok || !response.body) {
        throw new Error('chat_request_failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const flushBuffer = (force = false) => {
        const normalizedBuffer = buffer.replace(/\r\n/g, '\n');
        const lines = normalizedBuffer.split('\n');

        if (!force) {
          buffer = lines.pop() ?? '';
        } else {
          buffer = '';
        }

        for (const line of lines) {
          const trimmedLine = line.trim();

          if (!trimmedLine || trimmedLine.startsWith(':')) {
            continue;
          }

          if (!trimmedLine.startsWith('data:')) {
            continue;
          }

          const nextChunk = parseStreamPayload(
            trimmedLine.slice(5).trimStart(),
          );

          if (!nextChunk) {
            continue;
          }

          streamedContent += nextChunk;
          hasReceivedContent = true;
          updateAssistantMessage(assistantMessageId, streamedContent);
        }
      };

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        flushBuffer();
      }

      buffer += decoder.decode();
      flushBuffer(true);

      if (!hasReceivedContent) {
        updateAssistantMessage(assistantMessageId, '模型连接异常，请重试');
      }
    } catch {
      updateAssistantMessage(assistantMessageId, '模型连接异常，请重试');
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const handleClearMessages = () => {
    if (isStreaming) {
      return;
    }

    setMessages([]);
  };

  const handleExportReport = () => {
    if (!messages.length) {
      return;
    }

    const report = messages
      .map(
        (message) =>
          `[${message.timestamp}] ${message.role === 'user' ? '用户' : '链小易 AI'}：${message.content}`,
      )
      .join('\n\n');

    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = `ai-chat-${Date.now()}.txt`;
    link.click();

    URL.revokeObjectURL(url);
  };

  const handlePickPdf = () => {
    if (isUploadingPdf || isStreaming) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleUploadPdf = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';

    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus('仅支持上传 PDF 文件');
      return;
    }

    setIsUploadingPdf(true);
    setUploadStatus('正在上传并入库，请稍候...');
    try {
      const result = await api.uploadPdfForRag(file);
      const chunks = result.data?.chunks ?? 0;
      setUploadStatus(`上传成功，已入库 ${chunks} 个文本块`);
    } catch (error) {
      if (error instanceof ApiError) {
        setUploadStatus(`上传失败：${error.message}`);
      } else {
        setUploadStatus('上传失败，请稍后重试');
      }
    } finally {
      setIsUploadingPdf(false);
    }
  };

  const canSend = inputValue.trim().length > 0 && !isStreaming;

  return (
    <div data-ai-floating-root className="pointer-events-none fixed bottom-5 right-5 z-[120] flex flex-col items-end gap-3">
      {isOpen ? (
        <section
          data-ai-floating-window
          className="pointer-events-auto flex h-[min(78dvh,680px)] w-[min(calc(100vw-2rem),380px)] flex-col overflow-hidden rounded-md border border-border bg-white/94 shadow-elevation-3 backdrop-blur-xl"
          aria-label="链小易 AI 悬浮窗口"
        >
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <h3 className="text-base font-bold text-ink">链小易 AI</h3>
          <p className="text-[10px] font-semibold text-ink-muted">
            实时产业协作大脑
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-solid text-white">
            <Sparkles className="w-4 h-4" />
          </div>
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-surface text-ink-muted transition-colors hover:border-brand/30 hover:text-brand"
            onClick={() => setIsOpen(false)}
            title="收起链小易 AI"
            aria-label="收起链小易 AI"
          >
            <Minus className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div ref={messagesListRef} className="scrollbar-thin flex-1 space-y-5 overflow-y-auto p-5">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="rounded-md border border-border bg-surface-subtle px-4 py-3 text-center text-xs leading-relaxed text-ink-muted">
              输入你的问题后，链小易 AI 会基于模型实时生成回复。
            </div>
          </div>
        ) : (
          messages.map((messageItem) => {
            const isAssistant = messageItem.role === 'assistant';
            const displayContent =
              isAssistant && !messageItem.content && isStreaming
                ? '正在思考...'
                : messageItem.content;

            return (
              <div
                key={messageItem.id}
                className={`flex flex-col ${isAssistant ? 'items-start' : 'items-end'}`}
              >
                <div
                  className={`max-w-[90%] whitespace-pre-wrap rounded-md px-4 py-3 text-xs leading-relaxed ${
                    isAssistant
                      ? 'border border-border bg-surface-subtle text-ink-soft'
                      : 'bg-brand text-white'
                  }`}
                >
                  {displayContent}
                </div>
                <span
                  className={`mt-1 text-[9px] text-ink-faint ${
                    isAssistant ? 'ml-1' : 'mr-1'
                  }`}
                >
                  {messageItem.timestamp}
                </span>
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-border p-5">
        <div className="mb-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1 text-[10px] font-semibold text-ink-muted">
              模型
              <select
                className="rounded-md border border-border bg-surface px-2 py-2 text-xs text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                value={modelChoice}
                onChange={(event) => {
                  const nextChoice = event.target.value as ModelChoice;
                  setModelChoice(nextChoice);
                  setStoredModelChoice(nextChoice);
                }}
                disabled={isStreaming || isUploadingPdf}
              >
                <option value="qwen">qwen（本地隐私专家）</option>
                <option value="deepseek">deepseek（云端深度思考引擎）</option>
              </select>
            </label>
            <div className="flex flex-col gap-1 text-[10px] font-semibold text-ink-muted">
              知识库模式
              <label className="flex items-center justify-between rounded-md border border-border bg-surface px-2 py-2 text-xs text-ink">
                <span>启用 RAG</span>
                <input
                  type="checkbox"
                  checked={useRag}
                  onChange={(event) => setUseRag(event.target.checked)}
                  disabled={isStreaming}
                  className="accent-primary"
                />
              </label>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              className={`flex items-center gap-1 rounded-md border px-3 py-2 text-[10px] font-semibold transition-colors ${
                isUploadingPdf || isStreaming
                  ? 'cursor-not-allowed border-border bg-surface-subtle text-ink-faint'
                  : 'border-border bg-surface text-ink-muted hover:border-brand/30 hover:text-brand'
              }`}
              onClick={handlePickPdf}
              disabled={isUploadingPdf || isStreaming}
            >
              <Upload className="w-3 h-3" />
              {isUploadingPdf ? '上传中...' : '上传 PDF 到知识库'}
            </button>
            {uploadStatus ? (
              <span className="text-right text-[10px] text-ink-muted">
                {uploadStatus}
              </span>
            ) : null}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={handleUploadPdf}
          />
        </div>

        <div className="relative group">
          <textarea
            className="w-full resize-none rounded-md border border-border bg-surface p-4 pr-12 text-xs text-ink transition-all placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand-soft"
            placeholder="向链小易提问..."
            rows={2}
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            className={`absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-md transition-transform ${
              canSend
                ? 'bg-brand text-white hover:scale-105'
                : 'cursor-not-allowed bg-surface-container text-ink-faint'
            }`}
            onClick={() => void sendMessage()}
            disabled={!canSend}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-4 flex justify-between">
          <button
            type="button"
              className={`flex items-center gap-1 text-[10px] font-semibold transition-colors ${
                isStreaming
                  ? 'cursor-not-allowed text-ink-faint'
                  : 'text-ink-muted hover:text-brand'
            }`}
            onClick={handleClearMessages}
            disabled={isStreaming}
          >
            <Trash2 className="w-3 h-3" /> 清除对话
          </button>
          <button
            type="button"
              className={`flex items-center gap-1 text-[10px] font-semibold transition-colors ${
              messages.length
                ? 'text-ink-muted hover:text-brand'
                : 'cursor-not-allowed text-ink-faint'
            }`}
            onClick={handleExportReport}
            disabled={!messages.length}
          >
            <Download className="w-3 h-3" /> 导出报告
          </button>
        </div>
      </div>
        </section>
      ) : null}

      <button
        type="button"
        className="pointer-events-auto flex items-center gap-2 rounded-md border border-brand/25 bg-brand-solid px-4 py-3 text-sm font-bold text-white shadow-elevation-3 transition-transform hover:-translate-y-0.5 hover:bg-brand-solid-hover"
        onClick={() => setIsOpen((current) => !current)}
        title={isOpen ? '收起链小易 AI' : '打开链小易 AI'}
        aria-label={isOpen ? '收起链小易 AI' : '打开链小易 AI'}
        aria-expanded={isOpen}
      >
        <MessageCircle className="h-4 w-4" />
        链小易 AI
      </button>
    </div>
  );
}
