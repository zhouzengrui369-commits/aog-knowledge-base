"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, Link2, Loader2, Send, Sparkles, X } from "lucide-react";
import { chatStream } from "@/lib/api";
import type { ChatReference, ChatSection } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sections?: ChatSection[];
  references?: ChatReference[];
  model?: string;
  loading?: boolean;
  error?: string;
  debugThoughts?: string;
  truncated?: boolean;
}

const DEBUG_THOUGHTS = process.env.NEXT_PUBLIC_DEBUG_THOUGHTS === "true";
const STARTERS = ["B787 风挡 AOG 怎么处理？", "北京大兴有哪些已核验保障资源？"];

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
  if (section.type === "alert") return <div className="my-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900"><Inline text={text} /></div>;
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

function AssistantMessage({ message, retry }: { message: Message; retry: () => void }) {
  return (
    <div className="rounded-lg bg-white p-3 text-sm shadow-sm">
      {message.loading && <div className="flex items-center gap-2 text-ink-500"><Loader2 className="h-4 w-4 animate-spin" />正在检索已核验资料…</div>}
      {message.error && <div className="rounded-md bg-red-50 p-2 text-red-800"><AlertTriangle className="mr-1 inline h-4 w-4" />{message.error}</div>}
      {DEBUG_THOUGHTS && message.debugThoughts && <details className="mb-2 rounded border border-ink-100 bg-ink-50 p-2 text-xs"><summary>开发调试信息</summary><pre className="mt-2 whitespace-pre-wrap">{message.debugThoughts}</pre></details>}
      {message.sections?.length ? <div className="space-y-1">{message.sections.map((section, index) => <Section key={index} section={section} />)}</div> : <MarkdownFallback text={message.text} />}
      {message.truncated && <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">回答可能不完整。<button type="button" onClick={retry} className="ml-1 font-semibold underline">重新生成</button></div>}
      {(message.references || []).length > 0 && <div className="mt-3 border-t border-ink-100 pt-2"><div className="mb-1 text-[11px] font-semibold text-ink-500">依据</div>{message.references!.map((reference) => <Link key={reference.id} href={reference.href} className="mb-1 flex items-start gap-1 text-xs text-primary hover:underline"><Link2 className="mt-0.5 h-3 w-3 shrink-0" /><span>{reference.title}</span></Link>)}</div>}
    </div>
  );
}

export function ChatWidget() {
  const [open, setOpen] = React.useState(false);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const lastQuestion = React.useRef("");
  const buffer = React.useRef(new Map<string, string>());

  const ask = React.useCallback(async (raw: string) => {
    const question = raw.trim();
    if (!question) return;
    lastQuestion.current = question;
    setOpen(true);
    setInput("");
    const id = `a-${Date.now()}`;
    setMessages((current) => [...current, { id: `u-${id}`, role: "user", text: question }, { id, role: "assistant", text: "", loading: true, references: [] }]);
    buffer.current.set(id, "");

    await chatStream({ q: question }, {
      onRefs: ({ references, model }) => setMessages((current) => current.map((message) => message.id === id ? { ...message, references, model, loading: false } : message)),
      onThink: DEBUG_THOUGHTS ? (delta) => setMessages((current) => current.map((message) => message.id === id ? { ...message, debugThoughts: `${message.debugThoughts || ""}${delta}` } : message)) : undefined,
      onToken: (delta) => buffer.current.set(id, `${buffer.current.get(id) || ""}${delta}`),
      onSections: (sections) => setMessages((current) => current.map((message) => message.id === id ? { ...message, sections, loading: false } : message)),
      onDone: () => {
        const text = stripPrivateProtocol(buffer.current.get(id) || "");
        buffer.current.delete(id);
        setMessages((current) => current.map((message) => message.id === id ? { ...message, text, loading: false, truncated: !message.sections?.length && looksTruncated(text) } : message));
      },
      onError: (error) => {
        buffer.current.delete(id);
        setMessages((current) => current.map((message) => message.id === id ? { ...message, loading: false, error: `AI 服务暂不可用：${error}` } : message));
      },
    });
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

  return (
    <>
      {!open && <button type="button" aria-label="打开 AI 助手" onClick={() => setOpen(true)} className="fixed bottom-6 left-6 z-[1000] grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-pop hover:bg-primary-700"><Sparkles className="h-6 w-6" /></button>}
      {open && <div role="dialog" aria-label="AOG AI 助手" className="fixed inset-0 z-[1100] flex flex-col bg-white shadow-pop sm:inset-auto sm:bottom-6 sm:left-6 sm:h-[640px] sm:max-h-[80vh] sm:w-[420px] sm:rounded-2xl sm:border sm:border-ink-100">
        <div className="flex items-center justify-between bg-primary px-4 py-3 text-white sm:rounded-t-2xl"><div><div className="text-sm font-semibold">AOG AI 助手</div><div className="text-[10px] text-white/75">只基于检索资料回答，生产环境不展示模型内部推理</div></div><button type="button" onClick={() => setOpen(false)} aria-label="关闭 AI 助手"><X className="h-5 w-5" /></button></div>
        <div className="flex-1 space-y-3 overflow-y-auto bg-ink-50 p-4">
          {messages.length === 0 && <div className="rounded-lg border border-ink-100 bg-white p-3 text-sm text-ink-600"><p>输入 AOG 问题，回答会附带来源。</p><div className="mt-3 flex flex-wrap gap-2">{STARTERS.map((starter) => <button key={starter} type="button" onClick={() => void ask(starter)} className="rounded-full border border-ink-200 px-3 py-1 text-xs hover:border-primary hover:text-primary">{starter}</button>)}</div></div>}
          {messages.map((message) => message.role === "user" ? <div key={message.id} className="ml-8 rounded-lg bg-primary p-3 text-sm text-white">{message.text}</div> : <AssistantMessage key={message.id} message={message} retry={() => void ask(lastQuestion.current)} />)}
        </div>
        <form onSubmit={(event) => { event.preventDefault(); void ask(input); }} className="flex gap-2 border-t border-ink-100 p-3"><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="输入城市、件号、机型或故障…" className="min-w-0 flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm focus:border-primary focus:outline-none" /><button type="submit" disabled={!input.trim()} className="grid h-10 w-10 place-items-center rounded-md bg-primary text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></form>
      </div>}
    </>
  );
}
