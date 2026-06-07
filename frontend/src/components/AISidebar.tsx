import React, { useEffect, useRef, useState } from 'react';
import { Download, Send, Sparkles, Trash2, Upload } from 'lucide-react';
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
  const [isUploadingPdf, setIsUploadingPdf] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    <aside className="w-80 h-screen flex flex-col glass-panel border-l border-black/5 sticky top-0 shrink-0">
      <div className="p-6 flex items-center justify-between border-b border-black/5">
        <div>
          <h3 className="font-bold text-lg">链小易 AI</h3>
          <p className="text-[10px] text-neutral-500 font-medium tracking-tight">
            实时产业协作大脑
          </p>
        </div>
        <div className="w-8 h-8 rounded-full bg-black flex items-center justify-center text-white">
          <Sparkles className="w-4 h-4" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="bg-surface-container-high px-4 py-3 rounded-2xl text-xs text-neutral-500 leading-relaxed text-center">
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
                  className={`px-4 py-3 rounded-2xl text-xs leading-relaxed max-w-[90%] whitespace-pre-wrap ${
                    isAssistant
                      ? 'bg-surface-container-high text-primary rounded-tl-none'
                      : 'bg-primary text-white rounded-tr-none'
                  }`}
                >
                  {displayContent}
                </div>
                <span
                  className={`text-[9px] text-neutral-400 mt-1 ${
                    isAssistant ? 'ml-1' : 'mr-1'
                  }`}
                >
                  {messageItem.timestamp}
                </span>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-6">
        <div className="mb-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[10px] text-neutral-500 flex flex-col gap-1">
              模型
              <select
                className="bg-surface-container-low rounded-xl px-2 py-2 text-xs border border-black/5 focus:outline-none focus:ring-1 focus:ring-primary"
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
            <div className="text-[10px] text-neutral-500 flex flex-col gap-1">
              知识库模式
              <label className="bg-surface-container-low rounded-xl px-2 py-2 text-xs border border-black/5 flex items-center justify-between">
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
              className={`text-[10px] px-3 py-2 rounded-xl border border-black/5 flex items-center gap-1 transition-colors ${
                isUploadingPdf || isStreaming
                  ? 'text-neutral-300 cursor-not-allowed bg-neutral-50'
                  : 'text-neutral-500 hover:text-primary bg-surface-container-low'
              }`}
              onClick={handlePickPdf}
              disabled={isUploadingPdf || isStreaming}
            >
              <Upload className="w-3 h-3" />
              {isUploadingPdf ? '上传中...' : '上传 PDF 到知识库'}
            </button>
            {uploadStatus ? (
              <span className="text-[10px] text-neutral-500 text-right">
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
            className="w-full bg-surface-container-low border-none rounded-2xl p-4 pr-12 text-xs focus:ring-1 focus:ring-primary transition-all resize-none placeholder:text-neutral-400"
            placeholder="向链小易提问..."
            rows={2}
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            type="button"
            className={`absolute bottom-3 right-3 w-8 h-8 rounded-xl flex items-center justify-center transition-transform ${
              canSend
                ? 'bg-primary text-white hover:scale-105'
                : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
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
            className={`text-[10px] flex items-center gap-1 transition-colors ${
              isStreaming
                ? 'text-neutral-300 cursor-not-allowed'
                : 'text-neutral-500 hover:text-primary'
            }`}
            onClick={handleClearMessages}
            disabled={isStreaming}
          >
            <Trash2 className="w-3 h-3" /> 清除对话
          </button>
          <button
            type="button"
            className={`text-[10px] flex items-center gap-1 transition-colors ${
              messages.length
                ? 'text-neutral-500 hover:text-primary'
                : 'text-neutral-300 cursor-not-allowed'
            }`}
            onClick={handleExportReport}
            disabled={!messages.length}
          >
            <Download className="w-3 h-3" /> 导出报告
          </button>
        </div>
      </div>
    </aside>
  );
}
