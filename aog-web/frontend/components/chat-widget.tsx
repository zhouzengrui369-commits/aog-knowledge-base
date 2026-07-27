"use client";

import * as React from "react";
import { Send, Sparkles, X, Link2, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { chat as chatApi, chatStream } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

interface Msg {
  id: string;
  role: "user" | "assistant";
  text: string;
  refs?: ChatResponse["references"];
  loading?: boolean;
  /** LLM model name (from stream refs) */
  model?: string;
  /** NSM-2 violation: AI answered without references */
  nsM2Fail?: boolean;
}

const SUGGESTIONS = [
  "B787 风挡 AOG 怎么处理？",
  "浦东 AOG 联系人？",
  "BMS9-3 玻璃纤维布哪里备？",
];

/** 鲁棒解析 <think>...</think> 段 (兼容大小写 + 多种结束符) */
function splitThink(s: string): { think: string | null; body: string } {
  if (!s) return { think: null, body: "" };
  // 兼容: <think>...</think> / <thinking>...</thinking> / <reasoning>...</reasoning> / <THINK>...</THINK>
  const re = /<(think|thinking|reasoning|THINK|Thinking)>([\s\S]*?)<\/\1>/;
  const m = s.match(re);
  if (m) {
    return { think: m[2].trim(), body: s.slice(m[0].length).trim() };
  }
  // 兜底: 找 </think> 位置, 之前都当 think
  const closeIdx = s.indexOf("</think>");
  if (closeIdx > 0) {
    // 找最近的开始标记
    const openIdx = s.lastIndexOf("<think>", closeIdx);
    if (openIdx >= 0) {
      return { think: s.slice(openIdx + 7, closeIdx).trim(), body: s.slice(closeIdx + 8).trim() };
    }
  }
  return { think: null, body: s };
}

/** 简单 markdown 渲染 (不引第三方库, 减少依赖体积 + 避免 pnpm 502 慢)
 *  P0 治本 (NJX 7/27 15:44 反馈: AI 答案显示原始 markdown 格式, ## 标题 / | 表格 | / 1. 列表 都没渲染)
 *  支持: #/##/### 标题 / | 表格 | / - 列表 / 1. 有序列表 / **bold** / `code` / > 引用 / --- 横线
 *  不支持: 链接 / 图片 / 嵌套列表 (RAG 输出极少用到)
 */
function formatInline(text: string): React.ReactNode[] {
  // 处理 **bold** / *italic* / `code` inline
  // 顺序: ** (bold) → * (italic, 但排除 **) → ` (code)
  const parts: React.ReactNode[] = [];
  // 用 3 个独立 regex 顺序处理 (避免一个 match 把另一个吃掉)
  // 先用 placeholder 替换 **bold** 和 `code`, 再用 *italic*
  let s = text;
  // 1) 替换 **bold** 为 \u0001B... \u0001E (sentinel)
  const boldSentinels: string[] = [];
  s = s.replace(/\*\*([^*]+?)\*\*/g, (_, content) => {
    boldSentinels.push(content);
    return `\u0001B${boldSentinels.length - 1}\u0001E`;
  });
  // 2) 替换 `code` 为 \u0001C... \u0001E
  const codeSentinels: string[] = [];
  s = s.replace(/`([^`]+?)`/g, (_, content) => {
    codeSentinels.push(content);
    return `\u0001C${codeSentinels.length - 1}\u0001E`;
  });
  // 3) 替换 *italic* (单星, 不在行首 — 行首 `* ` 是 list)
  const italicSentinels: string[] = [];
  s = s.replace(/(?<![*\s])\*([^*\n]+?)\*(?!\*)/g, (_, content) => {
    italicSentinels.push(content);
    return `\u0001I${italicSentinels.length - 1}\u0001E`;
  });
  // 4) 现在 s 含 sentinel + 普通文本, 按顺序 split
  const re = /(\u0001B\d+\u0001E|\u0001C\d+\u0001E|\u0001I\d+\u0001E)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let idx = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) parts.push(s.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("\u0001B")) {
      const i = parseInt(tok.slice(1, -1), 10);
      parts.push(
        <strong key={`b-${idx++}`} className="font-semibold text-ink-900">
          {boldSentinels[i]}
        </strong>
      );
    } else if (tok.startsWith("\u0001C")) {
      const i = parseInt(tok.slice(1, -1), 10);
      parts.push(
        <code key={`c-${idx++}`} className="rounded bg-ink-100 px-1 py-0.5 font-mono text-[12px]">
          {codeSentinels[i]}
        </code>
      );
    } else if (tok.startsWith("\u0001I")) {
      const i = parseInt(tok.slice(1, -1), 10);
      parts.push(
        <em key={`i-${idx++}`} className="italic text-ink-700">
          {italicSentinels[i]}
        </em>
      );
    }
    last = m.index + tok.length;
  }
  if (last < s.length) parts.push(s.slice(last));
  return parts;
}

function renderMarkdown(body: string): React.ReactNode {
  if (!body) return null;
  const lines = body.split("\n");
  const out: React.ReactNode[] = [];
  let i = 0;
  let k = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 表格块: |...| 连续行
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      // 分离 header + body (第二行是 |---|---|)
      const isSep = (l: string) => /^\|?[\s:|-]+\|?$/.test(l.trim());
      let header: string[] = [];
      let rows: string[][] = [];
      if (tableLines.length >= 2 && isSep(tableLines[1])) {
        header = tableLines[0].split("|").slice(1, -1).map((c) => c.trim());
        for (let r = 2; r < tableLines.length; r++) {
          rows.push(tableLines[r].split("|").slice(1, -1).map((c) => c.trim()));
        }
      } else {
        // 没 separator 全部当 rows
        for (const tl of tableLines) {
          rows.push(tl.split("|").slice(1, -1).map((c) => c.trim()));
        }
      }
      out.push(
        <div key={`tbl-${k++}`} className="my-2 overflow-x-auto">
          <table className="w-full border-collapse text-[12px]">
            {header.length > 0 && (
              <thead className="bg-ink-100">
                <tr>
                  {header.map((h, idx) => (
                    <th key={idx} className="border border-ink-200 px-2 py-1 text-left font-semibold">
                      {formatInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="even:bg-ink-50/50">
                  {row.map((cell, ci) => (
                    <td key={ci} className="border border-ink-200 px-2 py-1 align-top">
                      {formatInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // 标题: # / ## / ###
    const hMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (hMatch) {
      const level = hMatch[1].length;
      const text = hMatch[2].trim();
      const cls =
        level === 1
          ? "mt-2 mb-1.5 text-base font-semibold text-ink-900"
          : level === 2
          ? "mt-2 mb-1 text-[15px] font-semibold text-ink-900"
          : "mt-1.5 mb-1 text-sm font-semibold text-ink-800";
      const Tag = (`h${level}` as unknown) as keyof JSX.IntrinsicElements;
      out.push(
        <Tag key={`h-${k++}`} className={cls}>
          {formatInline(text)}
        </Tag>
      );
      i++;
      continue;
    }

    // 引用: > ...
    if (line.startsWith("> ")) {
      out.push(
        <blockquote key={`q-${k++}`} className="my-1 border-l-2 border-primary pl-2 text-ink-700">
          {formatInline(line.slice(2))}
        </blockquote>
      );
      i++;
      continue;
    }

    // 横线: ---
    if (/^---+$/.test(line.trim())) {
      out.push(<hr key={`hr-${k++}`} className="my-2 border-ink-200" />);
      i++;
      continue;
    }

    // 有序列表: 1. / 2. / 3. ...
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      out.push(
        <ol key={`ol-${k++}`} className="my-1 ml-4 list-decimal space-y-0.5">
          {items.map((it, idx) => (
            <li key={idx} className="leading-relaxed">
              {formatInline(it)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // 无序列表: - / * ...
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      out.push(
        <ul key={`ul-${k++}`} className="my-1 ml-4 list-disc space-y-0.5">
          {items.map((it, idx) => (
            <li key={idx} className="leading-relaxed">
              {formatInline(it)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // 空行
    if (line.trim() === "") {
      i++;
      continue;
    }

    // 普通段落
    out.push(
      <p key={`p-${k++}`} className="my-1 leading-relaxed">
        {formatInline(line)}
      </p>
    );
    i++;
  }

  return <div className="markdown-body text-sm leading-relaxed text-ink-900">{out}</div>;
}

/** 单行 markdown 表格识别 (P0 治本: NJX 7/27 15:44 反馈 minimax 输出把 markdown 拼成单行)
 *  检测: 同一行包含 |xxx|...|xxx| + 跟 |---|---| 紧跟着, 后面继续 |...|...| 数据行
 *  返回: { header: [cells], rows: [[cells], ...] } 或 null (不是表格)
 */
function parseInlineTable(s: string): { header: string[]; rows: string[][]; rest: string } | null {
  // 找第一个 | 起始
  const start = s.indexOf("|");
  if (start < 0) return null;
  // 从 start 开始, 必须有 header |...| 跟 separator |---|---|
  // 用 lookahead 找 header + separator 模式
  const re = /\|\s*([^|\n]+?)\s*(?:\|\s*([^|\n]+?)\s*)*\|/g;
  // 简化: 找 |X|Y|Z| 模式 (头) + |---|---|---| 模式 (分隔)
  // 模式: 从 start 开始提取: header 行 + |---| 分隔 + rows
  const headMatch = s.slice(start).match(/^\|([^\n]+)\|/);
  if (!headMatch) return null;
  // 之后必须紧跟 |---| 分隔
  const afterHead = s.slice(start + headMatch[0].length);
  const sepMatch = afterHead.match(/^\s*\|(\s*[-:]+)+\|/);
  if (!sepMatch) return null;
  // 解析 header
  const headerRaw = headMatch[1];  // 含尾随 "|", 去掉
  const header = s.slice(start + 1, start + headMatch[0].length - 1).split("|").map((c) => c.trim());
  // 跳到分隔行尾
  let pos = start + headMatch[0].length + sepMatch[0].length;
  // 解析 rows (连续 |...| 行, 遇非 | 行停)
  const rows: string[][] = [];
  while (pos < s.length) {
    // 跳过空白
    while (pos < s.length && s[pos] === " ") pos++;
    if (s[pos] !== "|") break;
    const rowEnd = s.indexOf("|", pos + 1);
    if (rowEnd < 0) break;
    // 看下一个字符: 如果是 | 后是换行或 |，这一行是数据
    const afterFirst = s.indexOf("|", pos + 1);
    if (afterFirst < 0) break;
    // 解析 cells
    const rowContent = s.slice(pos + 1, afterFirst);
    // 检查 rowContent 是不是 separator 模式 (---)
    if (/^\s*[-:]+\s*$/.test(rowContent.split("|")[0] || "")) {
      pos = afterFirst;
      continue;
    }
    // 取整行 cells
    const nextPipe = s.indexOf("\n", pos);
    const lineEnd = nextPipe > 0 && nextPipe < s.length ? nextPipe : s.length;
    const lineCells = s.slice(pos + 1, lineEnd).replace(/\|$/, "").split("|").map((c) => c.trim());
    if (lineCells.length >= 2) rows.push(lineCells);
    pos = lineEnd + 1;
  }
  if (rows.length === 0) return null;
  return { header, rows, rest: s.slice(pos) };
}

/** 鲁棒 markdown 渲染: 自动 normalize 单行 markdown → 多行
 *  P0 治本: minimax stream output 有时把表格行拼成单行 |...|...|...|...|...|...| (没 \n)
 *        或 把 # / * / - 标记 inline 不分行 (# 二、| *机场: | - 故障)
 *  修法: 检测 markdown 标记前自动插 \n, 让 renderMarkdown 正常解析
 */
function normalizeMarkdownLineBreaks(s: string): string {
  if (!s) return s;
  let out = s;
  // 1) 表格行: 连续 ≥ 3 个 | cells, 自动加 \n
  out = out.replace(
    /\|(\s*[^\n|]{2,40}\s*)(\|\s*[^\n|]{2,40}\s*){2,}\|(\s*[^\n|]{2,40}\s*)(\|\s*[^\n|]{2,40}\s*)*\|/g,
    (m) => m.replace(/\s*\|\s*/g, " | ").replace(/(?<!^)\s*\|\s*(?!$)/g, "\n| ")
  );
  // 2) Heading: 前面不是行首的 # (1-3 个), 自动插 \n
  // 匹配: 不是行首的 ## ## / ### ###, 前面是中文/英文/数字/符号 (非空白)
  out = out.replace(/([^\n\s])(\s*)(#{1,3}\s+)/g, "$1\n$3");
  // 3) List item: 前面不是行首的 `* ` 或 `- ` (1-3 个空格缩进 + 字符), 自动插 \n
  // ⚠️ 跳过 "**bold**" 内的 `*` (这里用 lookahead: `*` 后面跟空格 + 非 `*`)
  out = out.replace(/([^\n])\s+(\*+\s+[^*\n])/g, "$1\n$2");
  out = out.replace(/([^\n])\s+(-\s+[-*\w\u4e00-\u9fff])/g, "$1\n$2");
  // 4) Numbered list: 1. 2. 3. (前面不是行首, 后面是中文/英文)
  out = out.replace(/([^\n])\s+(\d+\.\s+[\u4e00-\u9fff\w])/g, "$1\n$2");
  return out;
}

/** Markdown 渲染 (自写, 不依赖第三方) + 思考过程折叠
 *  P0 治本 (NJX 7/27 15:44 反馈: AI 答案显示原始 markdown 格式, ## 标题 / | 表格 | / 1. 列表 都没渲染) */
function formatAnswer(s: string): React.ReactNode {
  if (!s) return null;
  const { think, body } = splitThink(s);
  const thinkBlock = think ? (
    <details key="think" className="mb-2 rounded-md border border-ink-100 bg-ink-50 px-2.5 py-1.5 text-[11px] text-ink-500">
      <summary className="cursor-pointer select-none font-medium text-ink-600 hover:text-primary">
        💭 AI 思考过程 (点击展开)
      </summary>
      <div className="mt-1 whitespace-pre-wrap leading-relaxed text-ink-500">
        {think}
      </div>
    </details>
  ) : null;
  return (
    <>
      {thinkBlock}
      {renderMarkdown(normalizeMarkdownLineBreaks(body))}
    </>
  );
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
      { id: loadingId, role: "assistant", text: "", loading: true, refs: [] },
    ]);

    // P0 治本 (NJX 7/27 15:44 反馈: AI 答案没流式输出)
    //   改用 chatStream: 后端 SSE emit refs (立刻) + token (打字机) + done (结束)
    //   - 收到 refs 立刻显示引用, 不等 LLM 30s
    //   - 收到 token 增量拼到 text, React state 触发 re-render
    await chatStream({ q: text }, {
      onRefs: ({ references, model }) => {
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? { ...m, loading: false, refs: references, model }
              : m
          )
        );
      },
      onToken: (delta) => {
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? { ...m, text: m.text + delta, loading: false }
              : m
          )
        );
      },
      onDone: () => {
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId ? { ...m, loading: false } : m
          )
        );
      },
      onError: (msg) => {
        setError(`流式 chat 异常: ${msg}`);
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? {
                  id: loadingId,
                  role: "assistant",
                  text: `抱歉，AI 服务异常：${msg}。请稍后重试，或直接浏览左侧城市 / 经验库。`,
                  nsM2Fail: true,
                }
              : m
          )
        );
      },
    });
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    doAsk(input);
  }

  return (
    <>
      {/* 浮动按钮 — 关闭时显示 (P0 治本 NJX 13:48 反馈: 弹右下挡地图, 改左下) */}
      {!open && (
        <button
          type="button"
          aria-label="打开 AI 助手"
          onClick={() => setOpen(true)}
          className="fixed bottom-5 left-5 z-[1000] grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-pop transition hover:scale-105 hover:bg-primary-700 sm:bottom-6 sm:left-6"
          style={{ zIndex: 1000 }}
        >
          <Sparkles className="h-6 w-6" />
          <span className="absolute -top-1 -right-1 grid h-5 w-5 place-items-center rounded-full bg-warning text-[10px] font-bold text-white ring-2 ring-white">
            AI
          </span>
        </button>
      )}

      {/* 面板 — 移动全屏 / 桌面左下抽屉 (P0 治本 NJX 13:48 + 14:43 反馈)
          z-[1100] 强制覆盖 leaflet attribution (z-1000) + messages 容器 bg-slate-50 不透明
          (NJX 15:04 反馈: panel 内部 50% 透明让 home 地图视觉穿透) */}
      {open && (
        <div
          role="dialog"
          aria-label="AOG AI 助手"
          className={cn(
            "fixed z-[1100] flex flex-col bg-white shadow-pop",
            "inset-0", // mobile fullscreen
            "sm:inset-auto sm:bottom-6 sm:left-6 sm:h-[640px] sm:max-h-[80vh] sm:w-[420px] sm:rounded-2xl sm:border sm:border-ink-100"
          )}
          style={{ zIndex: 1100, backgroundColor: "#ffffff" }}
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

          {/* messages — P0 治本 NJX 15:04 反馈: bg-ink-50/50 50% 透明让 home 地图视觉穿透 panel, 改不透明 bg-slate-50 + 显式 style */}
          <div
            ref={scrollRef}
            className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-4 sm:h-[440px]"
            style={{ backgroundColor: "#f8fafc" }}
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
