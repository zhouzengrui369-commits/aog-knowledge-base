"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Ban,
  Link2,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
  Square,
  Trash2,
  X,
} from "lucide-react";
import { AUTH_SESSION_EVENT, getAuthSessionId } from "@/components/auth-gate";
import { safeChatStream } from "@/lib/chat-stream";
import {
  applyIntermediateReferences,
  clearAllChatSessions,
  clearChatSession,
  isActivePhase,
  loadChatSession,
  saveChatSession,
  transitionChatPhase,
  type ChatMessageState,
  type ChatPhase,
} from "@/lib/chat-state";
import type { ChatReference, ChatSection } from "@/lib/types";

const STARTERS = ["B787 风挡 AOG 怎么处理？", "北京大兴有哪些已核验保障资源？"];
const SLOW_THRESHOLD_MS = 8_000;

function stripPrivateProtocol(text: string): string {
  return text
    .replace(/<(think|thinking|reasoning)>[\s\S]*?<\/\1>/gi, "")
    .replace(/===JSON_START===[\s\S]*?===JSON_END===/g, "")
    .replace(/\[(?:city|experience|wiki|core)[^\]]*:[^\]]*\]/gi, "")
    .trim();
}

function looksTruncated(text: string): boolean {
  const value = text.trim();
  if (!value) return false;
  const unmatchedBold = (value.match(/\*\*/g) || []).length % 2 !== 0;
  const unmatchedCode = (value.match(/`/g) || []).length % 2 !== 0;
  return unmatchedBold || unmatchedCode || (value.length > 80 && !/[。！？.!?）)\]】]$/.test(value));
}

function Inline({ text }: { text: string }) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return <>{tokens.map((token, index) => {
    if (token.startsWith("`") && token.endsWith("`")) return <code key={index} className="rounded bg-ink-100 px-1 py-0.5 font-mono text-[12px]">{token.slice(1, -1)}</code>;
    if (token.startsWith("**") && token.endsWith("**")) return <strong key={index}>{token.slice(2, -2)}</strong>;
    return <React.Fragment key={index}>{token}</React.Fragment>;
  })}</>;
}

function Section({ section }: { section: ChatSection }) {
  const text = stripPrivateProtocol(section.text || "");
  if (section.type === "heading") {
    const level = Math.min(3, Math.max(1, section.level || 2));
    if (level === 1) return <h2 className="mt-4 text-base font-bold text-ink-900"><Inline text={text} /></h2>;
    if (level === 2) return <h3 className="mt-3 border-l-2 border-primary pl-2 text-sm font-bold text-ink-900"><Inline text={text} /></h3>;
    return <h4 className="mt-2 text-sm font-semibold text-primary"><Inline text={text} /></h4>;
  }
  if (section.type === "table") return (
    <div className="my-2 overflow-x-auto rounded-md border border-ink-200">
      <table className="w-full border-collapse text-xs">
        {(section.header || []).length > 0 && <thead className="bg-primary-50"><tr>{section.header!.map((cell, index) => <th key={index} className="border-b border-ink-200 px-2 py-1.5 text-left font-semibold"><Inline text={cell} /></th>)}</tr></thead>}
        <tbody>{(section.rows || []).map((row, rowIndex) => <tr key={rowIndex} className="even:bg-ink-50">{row.map((cell, cellIndex) => <td key={cellIndex} className="border-b border-ink-100 px-2 py-1.5 align-top"><Inline text={cell} /></td>)}</tr>)}</tbody>
      </table>
    </div>
  );
  if (section.type === "list" || section.type === "ordered_list") {
    const items = section.items || [];
    const Tag = section.type === "ordered_list" ? "ol" : "ul";
    return <Tag className={`${section.type === "ordered_list" ? "list-decimal" : "list-disc"} ml-5 space-y-1`}>{items.map((item, index) => <li key={index}><Inline text={stripPrivateProtocol(item)} /></li>)}</Tag>;
  }
  if (section.type === "code") return <pre className="my-2 overflow-x-auto rounded-md bg-ink-900 p-3 text-xs text-white"><code>{text}</code></pre>;
  if (section.type === "alert") return <div className={`my-2 rounded-md border p-2 text-xs ${section.variant === "danger" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}><Inline text={text} /></div>;
  if (section.type === "quote") return <blockquote className="my-2 border-l-4 border-primary bg-primary-50 px-3 py-2 text-sm text-ink-700"><Inline text={text} /></blockquote>;
  return text ? <p className="my-1.5 whitespace-pre-wrap leading-relaxed"><Inline text={text} /></p> : null;
}

function MarkdownFallback({ text }: { text: string }) {
  const lines = stripPrivateProtocol(text).split("\n");
  const output: React.ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index += 1; continue; }
    const heading = line.match(/^(#{1,3})\s*(.+)$/);
    if (heading) {
      output.push(<h3 key={index} className="mt-3 border-l-2 border-primary pl-2 text-sm font-bold"><Inline text={heading[2]} /></h3>);
      index += 1;
      continue;
    }
    if (line.startsWith("|") && line.endsWith("|")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith("|") && lines[index].trim().endsWith("|")) {
        const cells = lines[index].trim().slice(1, -1).split("|").map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-+:?$/.test(cell))) rows.push(cells);
        index += 1;
      }
      const [header, ...body] = rows;
      output.push(<Section key={`table-${index}`} section={{ type: "table", header: header || [], rows: body }} />);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) { items.push(lines[index].replace(/^\s*[-*]\s+/, "")); index += 1; }
      output.push(<Section key={`list-${index}`} section={{ type: "list", items }} />);
      continue;
    }
    output.push(<p key={index} className="my-1.5 leading-relaxed"><Inline text={line} /></p>);
    index += 1;
  }
  return <>{output}</>;
}

const PHASE_LABEL: Record<ChatPhase, string> = {
  queued: "问题已排队…",
  retrieving: "正在检索已核验资料…",
  generating: "正在生成答案…",
  done: "回答完成",
  error: "生成失败",
  cancelled: "已取消",
};

function StatusLine({ message, cancel }: { message: ChatMessageState; cancel: () => void }) {
  if (!message.phase) return null;
  if (message.phase === "error" || message.phase === "cancelled") {
    return <div className="mb-2 flex items-center gap-2 text-xs text-ink-500"><Ban className="h-3.5 w-3.5" />{PHASE_LABEL[message.phase]}</div>;
  }
  if (message.phase === "done") {
    // R3 commit 8 (NJX 8/4 15:36 拍板): 思考过程摘要 done 后保留, 显示思考用时 + 引用条数 + model
    // 不再 return null — 用户能看到"思考完成 + 首字 Xms + 思考用时 Yms + 引用 Z 条 + model"
    const refs = message.references?.length || 0;
    const firstToken = message.firstTokenMs;
    const latency = message.latencyMs;
    const model = message.model;
    return (
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-ink-100 bg-ink-50 px-2 py-1.5 text-[11px] text-ink-500" role="status" aria-live="polite">
        <Sparkles className="h-3 w-3" />
        <span className="font-semibold text-ink-600">思考完成</span>
        {firstToken != null && <span>· 首字 {firstToken}ms</span>}
        {latency != null && <span>· 思考用时 {latency}ms</span>}
        {refs > 0 && <span>· 引用 {refs} 条</span>}
        {model && <span className="rounded bg-white px-1 py-0.5 text-[10px] font-mono text-ink-600">{model}</span>}
      </div>
    );
  }
  return (
    <div className="mb-2 rounded-md border border-primary-100 bg-primary-50 p-2 text-xs text-ink-700" role="status" aria-live="polite">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />{PHASE_LABEL[message.phase]}</span>
        <button type="button" onClick={cancel} aria-label="取消生成" className="inline-flex items-center gap-1 rounded px-2 py-1 font-medium text-primary hover:bg-white"><Square className="h-3 w-3" />取消</button>
      </div>
      {message.slow && <p className="mt-1 text-amber-800">仍在处理。你可以继续等待，或取消后重试。</p>}
    </div>
  );
}

function VerificationBadge({ reference }: { reference: ChatReference }) {
  const status = reference.verification_status || "UNVERIFIED";
  const safe = status === "VERIFIED";
  return <span className={`ml-1 rounded px-1.5 py-0.5 text-[9px] font-semibold ${safe ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`}>{status}</span>;
}

function AssistantMessage({
  message,
  retry,
  cancel,
  visit,
  lastVisitedReferenceId,
}: {
  message: ChatMessageState;
  retry: () => void;
  cancel: () => void;
  visit: (reference: ChatReference) => void;
  lastVisitedReferenceId: string | null;
}) {
  return (
    <div className="rounded-lg bg-white p-3 text-sm shadow-sm">
      {message.query && (
        <div className="mb-2 flex items-start gap-1.5 rounded-md border border-ink-200 bg-ink-50 px-2 py-1.5 text-xs text-ink-600" data-testid="query-card">
          <Link2 className="mt-0.5 h-3 w-3 shrink-0" />
          <span className="shrink-0 text-ink-500">问题</span>
          <span className="font-medium text-ink-700">{message.query}</span>
        </div>
      )}
      <StatusLine message={message} cancel={cancel} />
      {message.error && <div className="rounded-md bg-red-50 p-2 text-red-800" role="alert"><AlertTriangle className="mr-1 inline h-4 w-4" />{message.error}</div>}
      {message.sections?.length ? <div className="space-y-1">{message.sections.map((section, index) => <Section key={index} section={section} />)}</div> : <MarkdownFallback text={message.text} />}
      {message.truncated && <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">回答可能不完整。<button type="button" onClick={retry} className="ml-1 inline-flex items-center gap-1 font-semibold underline"><RotateCcw className="h-3 w-3" />重新生成</button></div>}
      {(message.references || []).length > 0 && (
        <div className="mt-3 border-t border-ink-100 pt-2">
          <div className="mb-1 text-[11px] font-semibold text-ink-500">依据</div>
          {message.references!.map((reference, index) => {
            const available = reference.available !== false && Boolean(reference.href);
            const visited = lastVisitedReferenceId === reference.id;
            const content = <><Link2 className="mt-0.5 h-3 w-3 shrink-0" /><span>{reference.title}<VerificationBadge reference={reference} />{visited && <span className="ml-1 text-[9px] text-ink-400">已访问</span>}</span></>;
            if (available) {
              return <Link key={`${reference.id}-${index}`} href={reference.href!} onClick={() => visit(reference)} className="mb-1 flex items-start gap-1 text-xs text-primary hover:underline">{content}</Link>;
            }
            return <div key={`${reference.id}-${index}`} aria-disabled="true" title={reference.reason || "来源暂不可打开"} className="mb-1 flex items-start gap-1 text-xs text-ink-500">{content}<span className="ml-1">（来源暂不可打开）</span></div>;
          })}
        </div>
      )}
    </div>
  );
}

function updatePhase(message: ChatMessageState, next: ChatPhase): ChatMessageState {
  const current = message.phase || "queued";
  try {
    return { ...message, phase: transitionChatPhase(current, next) };
  } catch {
    // Terminal states cannot be overwritten by late SSE events.
    return message;
  }
}

export function ChatWidget() {
  const [open, setOpen] = React.useState(false);
  const [messages, setMessages] = React.useState<ChatMessageState[]>([]);
  const [input, setInput] = React.useState("");
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [lastVisitedReferenceId, setLastVisitedReferenceId] = React.useState<string | null>(null);
  const lastQuestion = React.useRef("");
  const controllers = React.useRef(new Map<string, AbortController>());
  const hydrated = React.useRef(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const restore = React.useCallback((nextSessionId: string | null, clearExisting = false) => {
    if (typeof window === "undefined") return;
    if (clearExisting) clearAllChatSessions(window.sessionStorage);
    setSessionId(nextSessionId);
    if (!nextSessionId) {
      setMessages([]);
      setLastVisitedReferenceId(null);
      lastQuestion.current = "";
      hydrated.current = true;
      return;
    }
    const snapshot = loadChatSession(window.sessionStorage, nextSessionId);
    setMessages(snapshot?.messages || []);
    setLastVisitedReferenceId(snapshot?.lastVisitedReferenceId || null);
    lastQuestion.current = snapshot?.lastQuestion || "";
    hydrated.current = true;
  }, []);

  React.useEffect(() => {
    restore(getAuthSessionId());
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ sessionId: string | null; reason: string }>).detail;
      controllers.current.forEach((controller) => controller.abort());
      controllers.current.clear();
      restore(detail?.sessionId || null, detail?.reason === "login" || !detail?.sessionId);
    };
    window.addEventListener(AUTH_SESSION_EVENT, listener);
    return () => window.removeEventListener(AUTH_SESSION_EVENT, listener);
  }, [restore]);

  React.useEffect(() => {
    if (!hydrated.current || !sessionId || typeof window === "undefined") return;
    saveChatSession(window.sessionStorage, {
      sessionId,
      messages,
      lastQuestion: lastQuestion.current,
      lastVisitedReferenceId,
    });
  }, [messages, sessionId, lastVisitedReferenceId]);

  const cancel = React.useCallback((id: string) => {
    controllers.current.get(id)?.abort();
    controllers.current.delete(id);
    setMessages((current) => current.map((message) => message.id === id ? updatePhase(message, "cancelled") : message));
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, []);

  const ask = React.useCallback(async (raw: string) => {
    const question = raw.trim();
    if (!question) return;
    lastQuestion.current = question;
    setOpen(true);
    setInput("");
    const id = `a-${Date.now()}`;
    const controller = new AbortController();
    controllers.current.set(id, controller);
    setMessages((current) => [
      ...current,
      { id: `u-${id}`, role: "user", text: question },
      // R3 commit 8 (NJX 8/4 15:36 拍板): assistant message 存原 user query, 给 query 卡片用
      { id, role: "assistant", text: "", phase: "queued", query: question, references: [], slow: false },
    ]);

    const slowTimer = window.setTimeout(() => {
      setMessages((current) => current.map((message) => message.id === id && isActivePhase(message.phase) ? { ...message, slow: true } : message));
    }, SLOW_THRESHOLD_MS);

    try {
      await safeChatStream(
        { q: question },
        {
          onStatus: ({ phase, first_token_ms, latency_ms }) => setMessages((current) => current.map((message) => {
            if (message.id !== id) return message;
            const phased = updatePhase(message, phase);
            return {
              ...phased,
              firstTokenMs: first_token_ms ?? phased.firstTokenMs,
              latencyMs: latency_ms ?? phased.latencyMs,
              slow: phase === "done" || phase === "error" || phase === "cancelled" ? false : phased.slow,
            };
          })),
          onRefs: ({ references, model }) => setMessages((current) => current.map((message) => message.id === id ? applyIntermediateReferences(message, references, model) : message)),
          onToken: (delta) => setMessages((current) => current.map((message) => {
            if (message.id !== id || message.phase === "error" || message.phase === "cancelled" || message.phase === "done") return message;
            const phased = message.phase === "queued" || message.phase === "retrieving" ? updatePhase(message, "generating") : message;
            return { ...phased, text: stripPrivateProtocol(`${phased.text}${delta}`) };
          })),
          onSections: (sections) => setMessages((current) => current.map((message) => message.id === id && !["error", "cancelled", "done"].includes(message.phase || "") ? { ...message, sections } : message)),
          onDone: ({ latencyMs, firstTokenMs }) => {
            setMessages((current) => current.map((message) => {
              if (message.id !== id) return message;
              const phased = updatePhase(message, "done");
              const text = stripPrivateProtocol(phased.text);
              return { ...phased, text, latencyMs, firstTokenMs, slow: false, truncated: !phased.sections?.length && looksTruncated(text) };
            }));
            window.setTimeout(() => inputRef.current?.focus(), 0);
          },
          onError: (error) => {
            setMessages((current) => current.map((message) => message.id === id ? { ...updatePhase(message, "error"), slow: false, error: `AI 服务暂不可用：${error}` } : message));
            window.setTimeout(() => inputRef.current?.focus(), 0);
          },
          onCancelled: () => {
            setMessages((current) => current.map((message) => message.id === id ? { ...updatePhase(message, "cancelled"), slow: false } : message));
            window.setTimeout(() => inputRef.current?.focus(), 0);
          },
        },
        { signal: controller.signal }
      );
    } finally {
      window.clearTimeout(slowTimer);
      controllers.current.delete(id);
    }
  }, []);

  React.useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<{ q?: string }>).detail;
      setOpen(true);
      if (detail?.q) void ask(detail.q);
    };
    window.addEventListener("aog:ask", listener);
    return () => window.removeEventListener("aog:ask", listener);
  }, [ask]);

  const clearConversation = React.useCallback(() => {
    controllers.current.forEach((controller) => controller.abort());
    controllers.current.clear();
    if (sessionId && typeof window !== "undefined") clearChatSession(window.sessionStorage, sessionId);
    setMessages([]);
    setLastVisitedReferenceId(null);
    lastQuestion.current = "";
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [sessionId]);

  const busy = messages.some((message) => message.role === "assistant" && isActivePhase(message.phase));
  const activeAssistant = [...messages].reverse().find((message) => message.role === "assistant" && isActivePhase(message.phase));

  return (
    <>
      {!open && <button type="button" aria-label="打开 AI 助手" onClick={() => setOpen(true)} className="fixed bottom-6 left-6 z-[1000] grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-pop hover:bg-primary-700"><Sparkles className="h-6 w-6" /></button>}
      {open && <div role="dialog" aria-label="AOG AI 助手" className="fixed inset-0 z-[1100] flex flex-col bg-white shadow-pop sm:inset-auto sm:bottom-6 sm:left-6 sm:h-[640px] sm:max-h-[80vh] sm:w-[420px] sm:rounded-2xl sm:border sm:border-ink-100">
        <div className="flex items-center justify-between bg-primary px-4 py-3 text-white sm:rounded-t-2xl">
          <div><div className="text-sm font-semibold">AOG AI 助手</div><div className="text-[10px] text-white/75">只使用代码策略允许的已核验资料</div></div>
          <div className="flex items-center gap-1">
            <button type="button" onClick={clearConversation} aria-label="清空 AI 会话" title="清空 AI 会话" className="rounded p-1 hover:bg-white/10"><Trash2 className="h-4 w-4" /></button>
            <button type="button" onClick={() => setOpen(false)} aria-label="关闭 AI 助手" className="rounded p-1 hover:bg-white/10"><X className="h-5 w-5" /></button>
          </div>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto bg-ink-50 p-4">
          {messages.length === 0 && <div className="rounded-lg border border-ink-100 bg-white p-3 text-sm text-ink-600"><p>输入 AOG 问题，回答会显示来源的核验状态。</p><div className="mt-3 flex flex-wrap gap-2">{STARTERS.map((starter) => <button key={starter} type="button" onClick={() => void ask(starter)} className="rounded-full border border-ink-200 px-3 py-1 text-xs hover:border-primary hover:text-primary">{starter}</button>)}</div></div>}
          {messages.map((message) => message.role === "user" ? <div key={message.id} className="ml-8 rounded-lg bg-primary p-3 text-sm text-white">{message.text}</div> : <AssistantMessage key={message.id} message={message} retry={() => void ask(lastQuestion.current)} cancel={() => cancel(message.id)} visit={(reference) => setLastVisitedReferenceId(reference.id)} lastVisitedReferenceId={lastVisitedReferenceId} />)}
        </div>
        <form onSubmit={(event) => { event.preventDefault(); void ask(input); }} className="flex gap-2 border-t border-ink-100 p-3">
          <label htmlFor="aog-chat-question" className="sr-only">AOG 问题</label>
          <input ref={inputRef} id="aog-chat-question" value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入城市、件号、机型或故障…" className="min-w-0 flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" aria-describedby="aog-chat-send-help" />
          <button type="submit" aria-label="发送问题" aria-describedby="aog-chat-send-help" disabled={!input.trim() || busy} className="grid h-10 w-10 place-items-center rounded-md bg-primary text-white focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-40"><Send className="h-4 w-4" /></button>
          <span id="aog-chat-send-help" className="sr-only">{busy ? "当前问题仍在处理，可先取消再发送新问题" : "按 Enter 或聚焦发送按钮后按 Space 提交问题"}</span>
        </form>
        {activeAssistant && <div className="sr-only" aria-live="polite">{PHASE_LABEL[activeAssistant.phase || "queued"]}</div>}
      </div>}
    </>
  );
}
