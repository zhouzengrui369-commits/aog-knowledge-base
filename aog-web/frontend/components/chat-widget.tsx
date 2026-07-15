"use client";

import * as React from "react";
import { Send, Sparkles, X, Link2, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { chat as chatApi } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

interface Msg {
  id: string;
  role: "user" | "assistant";
  text: string;
  refs?: ChatResponse["references"];
  loading?: boolean;
  /** NSM-2 violation: AI answered without references */
  nsM2Fail?: boolean;
}

const SUGGESTIONS = [
  "B787 风挡 AOG 怎么处理？",
  "浦东 AOG 联系人？",
  "BMS9-3 玻璃纤维布哪里备？",
];

/** 简单 markdown → HTML 转换（粗体 + 换行） */
function formatAnswer(s: string): React.ReactNode {
  if (!s) return null;
  const lines = s.split("\n");
  return lines.map((line, i) => {
    const parts: React.ReactNode[] = [];
    const re = /\*\*(.+?)\*\*/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push(line.slice(last, m.index));
      parts.push(
        <strong key={`b-${i}-${m.index}`} className="font-semibold text-ink-900">
          {m[1]}
        </strong>
      );
      last = m.index + m[0].length;
    }
    if (last < line.length) parts.push(line.slice(last));
    return (
      <span key={i} className="block">
        {parts}
      </span>
    );
  });
}

interface ChatWidgetHandle {
  open: () => void;
  close: () => void;
  ask: (q: string) => void;
}

/** ChatWidget — 右下角浮窗 + 桌面抽屉 / 移动全屏 */
export const ChatWidget = React.forwardRef<ChatWidgetHandle>((_, ref) => {
  const [open, setOpen] = React.useState(false);
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [suggHidden, setSuggHidden] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // Auto-scroll
  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, open]);

  // 首次打开显示欢迎语
  React.useEffect(() => {
    if (open && msgs.length === 0) {
      setMsgs([
        {
          id: "welcome",
          role: "assistant",
          text: "你好，我是 AOG AI 助手。可以问我城市预案、备件库存、保障经验等问题，每个回答都会附带真实文档引用。",
        },
      ]);
    }
  }, [open, msgs.length]);

  // expose handle
  React.useImperativeHandle(
    ref,
    () => ({
      open: () => setOpen(true),
      close: () => setOpen(false),
      ask: (q: string) => {
        setOpen(true);
        setTimeout(() => doAsk(q), 50);
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  async function doAsk(q: string) {
    const text = q.trim();
    if (!text) return;
    setError(null);
    setInput("");
    setSuggHidden(true);

    const userMsg: Msg = { id: `u-${Date.now()}`, role: "user", text };
    const loadingId = `l-${Date.now()}`;
    setMsgs((prev) => [
      ...prev,
      userMsg,
      { id: loadingId, role: "assistant", text: "", loading: true },
    ]);

    try {
      const res = await chatApi({ q: text });
      if (!res) {
        // 网络错误 / 后端没启动
        setError("后端未响应，请检查 API 地址或稍后重试");
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? {
                  id: loadingId,
                  role: "assistant",
                  text: "抱歉，暂时无法连接到 AI 服务。请稍后重试，或直接浏览左侧城市 / 经验库。",
                  nsM2Fail: true,
                }
              : m
          )
        );
        return;
      }
      // NSM-2 验证：references.length >= 1 (CONTRACT §1.4 + rules R10)
      const hasRefs = res.references && res.references.length >= 1;
      setMsgs((prev) =>
        prev.map((m) =>
          m.id === loadingId
            ? {
                id: loadingId,
                role: "assistant",
                text: res.answer,
                refs: res.references,
                nsM2Fail: !hasRefs,
              }
            : m
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
      setMsgs((prev) =>
        prev.map((m) =>
          m.id === loadingId
            ? {
                id: loadingId,
                role: "assistant",
                text: "调用 AI 服务时发生异常。",
                nsM2Fail: true,
              }
            : m
        )
      );
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    doAsk(input);
  }

  return (
    <>
      {/* 浮动按钮 — 关闭时显示 */}
      {!open && (
        <button
          type="button"
          aria-label="打开 AI 助手"
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-40 grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-pop transition hover:scale-105 hover:bg-primary-700 sm:bottom-6 sm:right-6"
        >
          <Sparkles className="h-6 w-6" />
          <span className="absolute -top-1 -right-1 grid h-5 w-5 place-items-center rounded-full bg-warning text-[10px] font-bold text-white ring-2 ring-white">
            AI
          </span>
        </button>
      )}

      {/* 面板 — 移动全屏 / 桌面右下抽屉 */}
      {open && (
        <div
          role="dialog"
          aria-label="AOG AI 助手"
          className={cn(
            "fixed z-50 flex flex-col bg-white shadow-pop",
            "inset-0", // mobile fullscreen
            "sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[640px] sm:max-h-[80vh] sm:w-[420px] sm:rounded-2xl sm:border sm:border-ink-100"
          )}
        >
          {/* header */}
          <div className="flex items-center justify-between border-b border-ink-100 bg-gradient-to-r from-primary to-primary-700 px-4 py-3 sm:rounded-t-2xl">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-white/15 text-white">
                <Sparkles className="h-4 w-4" />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold text-white">AI 助手</div>
                <div className="text-[10px] text-white/70">MiniMax M3 · RAG</div>
              </div>
            </div>
            <button
              type="button"
              aria-label="关闭"
              onClick={() => setOpen(false)}
              className="grid h-8 w-8 place-items-center rounded-md text-white/80 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* messages */}
          <div
            ref={scrollRef}
            className="flex-1 space-y-3 overflow-y-auto bg-ink-50/50 px-4 py-4 sm:h-[440px]"
          >
            {msgs.map((m) => (
              <MessageBubble key={m.id} msg={m} />
            ))}
            {error && (
              <div className="rounded-md border border-danger-100 bg-danger-50 px-3 py-2 text-xs text-danger-700">
                {error}
              </div>
            )}
          </div>

          {/* suggestions */}
          {!suggHidden && (
            <div className="border-t border-ink-100 bg-white px-3 py-2">
              <div className="mb-1 text-[10px] text-ink-500">试试这些问题：</div>
              <div className="flex flex-wrap gap-1.5">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => doAsk(s)}
                    className="rounded-full border border-ink-100 bg-ink-50 px-2.5 py-1 text-[11px] text-ink-700 hover:border-primary hover:bg-primary-50 hover:text-primary"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* input */}
          <form
            onSubmit={onSubmit}
            className="flex items-center gap-2 border-t border-ink-100 bg-white px-3 py-3 sm:rounded-b-2xl"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入你的 AOG 问题…"
              autoComplete="off"
              className="flex-1 rounded-md border border-ink-100 bg-ink-50 px-3 py-2 text-sm placeholder:text-ink-500 focus:border-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            <button
              type="submit"
              aria-label="发送"
              className="grid h-9 w-9 place-items-center rounded-md bg-primary text-white hover:bg-primary-700"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
});

ChatWidget.displayName = "ChatWidget";

/** 单条消息气泡（用户 / AI + 参考资料） */
function MessageBubble({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3.5 py-2.5 text-sm leading-relaxed text-white">
          {msg.text}
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex flex-col items-start gap-1.5">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-ink-100 bg-white px-3.5 py-2.5 text-sm leading-relaxed text-ink-900">
        {msg.loading ? (
          <span className="dot-bounce inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-ink-500" />
            <span className="h-1.5 w-1.5 rounded-full bg-ink-500" />
            <span className="h-1.5 w-1.5 rounded-full bg-ink-500" />
          </span>
        ) : (
          <div className="space-y-1">{formatAnswer(msg.text)}</div>
        )}
      </div>

      {/* NSM-2 提示：回答无 references */}
      {msg.nsM2Fail && !msg.loading && (
        <div className="max-w-[85%] rounded-md border border-warning/30 bg-warning-50 px-3 py-1.5 text-[11px] text-warning-700">
          <span className="inline-flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> AI 回答可能不准确（未提供真实文档引用）
          </span>
        </div>
      )}

      {/* 参考资料 */}
      {msg.refs && msg.refs.length > 0 && (
        <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-ink-100 bg-white px-3.5 py-2 text-[11px]">
          <div className="mb-1 flex items-center gap-1 text-ink-500">
            <Link2 className="h-3 w-3" />
            参考资料（{msg.refs.length}）
          </div>
          <ul className="space-y-0.5">
            {msg.refs.map((r) => (
              <li key={r.id || r.href}>
                <a
                  href={r.href}
                  className="text-primary hover:underline"
                  target={r.href.startsWith("http") ? "_blank" : undefined}
                  rel={r.href.startsWith("http") ? "noreferrer" : undefined}
                >
                  {r.title}
                </a>
                {r.snippet && (
                  <span className="ml-1 text-ink-500">— {r.snippet.slice(0, 60)}…</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
