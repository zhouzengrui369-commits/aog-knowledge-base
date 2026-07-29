"use client";

import * as React from "react";
import {
  Send, Sparkles, X, Link2, AlertTriangle, Loader2,
  Info, AlertCircle, CheckCircle2, ShieldAlert,
  Terminal, Code2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { chat as chatApi, chatStream } from "@/lib/api";
import type { ChatResponse, ChatSection, ChatSectionType } from "@/lib/types";

interface Msg {
  id: string;
  role: "user" | "assistant";
  text: string;
  /** V30 治本: LLM 解析成功时填充, 优先于 text 渲染 */
  sections?: ChatSection[];
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

// ====== V30 治本 (NJX 7/27 22:14 拍板 🅰️): 结构化 section 组件化渲染 ======
// LLM 输出 JSON 描述 sections 数组, 每个 section 独立 React 组件, 100% 视觉受控.
// 完全替代 V29d++ 的"正则吃 markdown" 模式, 不再依赖 LLM 严格遵循 markdown 标记.

/** V30 治本: strip text 字段里残留的 markdown 标记 (NJX 7/27 22:14 拍板)
 *  P0 容错: minimax M3 在 JSON 模板里也偶有 inline 残破 (前导 # / 紧贴 ** / 含 raw JSON 例子)
 *  避免: 用户看到 "### 注意事项" 在 paragraph 段里显示成 "### 注意事项"
 *  不动: formatInline 内的 `**bold**` / `*italic*` / `code` (LLM 偶有, 仍渲染)
 *  P1 容错: 整段是 raw JSON 例子 (LLM 错误地把 JSON 模板塞到 text/rows), 整段 strip */
function cleanText(s: string): string {
  if (!s) return s;
  let out = String(s)
    // 行首的 # 标记 (e.g. "### 注意事项" → "注意事项", "## 标题" → "标题")
    .replace(/^\s*#{1,6}\s+/gm, "")
    // 行首的 list 标记 (e.g. "- 步骤 1" → "步骤 1", "* 项目" → "项目", "1. 第一步" → "第一步")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    // 单独一行的 # 字符 (LLM 流拼接产物)
    .replace(/^\s*#\s*$/gm, "")
    // 末尾孤立 # 字符
    .replace(/\s*#\s*$/g, "")
    .trim();
  // P1 容错: 整段就是 raw JSON 例子 (LLM 错误地把 JSON 模板塞到 text/items/rows)
  if (/^\s*\{[\s\S]*"sections"[\s\S]*\}\s*$/.test(out)) {
    return "";  // 整段是 raw JSON 模板, 不显示
  }
  return out;
}

/** 单个 section 渲染 — 按 type 分发到对应组件 */
function SectionRenderer({ section }: { section: ChatSection }) {
  switch (section.type) {
    case "heading":
      return <HeadingSection level={section.level ?? 2} text={section.text ?? ""} />;
    case "paragraph":
      return <ParagraphSection text={cleanText(section.text ?? "")} />;
    case "table":
      return <TableSection header={section.header ?? []} rows={section.rows ?? []} />;
    case "list":
      return <ListSection items={section.items ?? []} />;
    case "ordered_list":
      return <OrderedListSection items={section.items ?? []} />;
    case "code":
      return <CodeSection text={section.text ?? ""} language={section.language} />;
    case "alert":
      return <AlertSection text={cleanText(section.text ?? "")} variant={section.variant ?? "info"} />;
    case "quote":
      return <QuoteSection text={cleanText(section.text ?? "")} />;
    default:
      return null;
  }
}

/** 多个 sections 渲染 (key 稳定, 避免 React warning) */
function renderSections(sections: ChatSection[]): React.ReactNode {
  return (
    <div className="space-y-1.5">
      {sections.map((s, i) => (
        <SectionRenderer key={i} section={s} />
      ))}
    </div>
  );
}

/** H1/H2/H3 视觉分级 (沿用 V29d 视觉 + V30 增强)
 *  P0 容错: strip text 里残留的 markdown 标记 (LLM 输出 "### xxx" 偶有) */
function HeadingSection({ level, text }: { level: number; text: string }) {
  // strip 前导的 # / ## / ### (兼容 LLM 偶有 inline 残破)
  const cleanText = String(text).replace(/^\s*#{1,6}\s*/, "").trim();
  if (level === 1) {
    return (
      <h1 className="mt-2.5 mb-1.5 flex items-center gap-2 border-l-4 border-primary bg-primary/5 px-2.5 py-1.5 text-base font-bold text-ink-900">
        <span className="text-primary/70">▎</span>
        {cleanText}
      </h1>
    );
  }
  if (level === 2) {
    return (
      <h2 className="mt-2.5 mb-1 flex items-center gap-2 border-l-2 border-primary/70 pl-2 text-[15px] font-bold text-ink-900">
        <span className="text-primary/70">▎</span>
        {cleanText}
      </h2>
    );
  }
  return (
    <h3 className="mt-2 mb-0.5 text-sm font-semibold text-primary">{cleanText}</h3>
  );
}

/** 段落 (允许 inline **bold** / *italic* / `code` — 走 formatInline) */
function ParagraphSection({ text }: { text: string }) {
  return (
    <p className="leading-relaxed text-ink-800">{formatInline(text)}</p>
  );
}

/** 表格 — V30 治本: header + rows 二维数组, 100% 视觉受控, 不依赖 |---| 解析 */
function TableSection({ header, rows }: { header: string[]; rows: string[][] }) {
  return (
    <div className="my-2 overflow-x-auto rounded-md border border-ink-200">
      <table className="w-full border-collapse text-[12px]">
        {header.length > 0 && (
          <thead className="bg-primary/5">
            <tr>
              {header.map((h, i) => (
                <th
                  key={i}
                  className="border-b border-ink-200 bg-primary/10 px-2.5 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-primary"
                >
                  {formatInline(cleanText(h))}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="even:bg-ink-50/50 hover:bg-primary/5 transition-colors">
              {row.map((cell, ci) => {
                const cleaned = cleanText(cell);
                if (!cleaned) return <td key={ci} className="border-b border-ink-100 px-2.5 py-1.5 align-top text-ink-400 italic">—</td>;
                return (
                  <td key={ci} className="border-b border-ink-100 px-2.5 py-1.5 align-top text-ink-800">
                    {formatInline(cleaned)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 无序列表 (蓝圆点, 沿用 V29d 视觉) */
function ListSection({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="ml-1 space-y-0.5">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2 leading-relaxed">
          <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
          <span className="flex-1 text-ink-800">{formatInline(cleanText(it))}</span>
        </li>
      ))}
    </ul>
  );
}

/** 有序列表 (蓝数字圆形, 沿用 V29d 视觉) */
function OrderedListSection({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ol className="ml-1 space-y-0.5">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2 leading-relaxed">
          <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
            {i + 1}
          </span>
          <span className="flex-1 text-ink-800">{formatInline(cleanText(it))}</span>
        </li>
      ))}
    </ol>
  );
}

/** 代码块 (block, 灰色背景 + 终端 icon + language 标签) */
function CodeSection({ text, language }: { text: string; language?: string }) {
  return (
    <div className="my-1.5 overflow-hidden rounded-md border border-ink-200 bg-ink-900 text-[12px]">
      <div className="flex items-center gap-1.5 border-b border-ink-700 bg-ink-800 px-2.5 py-1 text-[10px] text-ink-300">
        <Terminal className="h-3 w-3" />
        <span className="font-mono uppercase tracking-wide">{language || "text"}</span>
      </div>
      <pre className="overflow-x-auto px-2.5 py-2 font-mono leading-relaxed text-ink-100">
        {text}
      </pre>
    </div>
  );
}

/** 提示框 (4 变体: info / warning / danger / success)
 *  P0 容错: tailwind config 没 info color, info 改用 primary (蓝色, 跟 AOG 主题一致) */
function AlertSection({ text, variant }: { text: string; variant: "info" | "warning" | "danger" | "success" }) {
  const config = {
    info: {
      cls: "border-primary/30 bg-primary-50 text-primary-900",
      icon: <Info className="h-3.5 w-3.5 text-primary" />,
      label: "提示",
    },
    warning: {
      cls: "border-warning/30 bg-warning-50 text-warning-700",
      icon: <AlertCircle className="h-3.5 w-3.5 text-warning" />,
      label: "注意",
    },
    danger: {
      cls: "border-danger/30 bg-danger-50 text-danger-700",
      icon: <ShieldAlert className="h-3.5 w-3.5 text-danger" />,
      label: "危险",
    },
    success: {
      cls: "border-success/30 bg-success-50 text-success-700",
      icon: <CheckCircle2 className="h-3.5 w-3.5 text-success" />,
      label: "成功",
    },
  }[variant];
  return (
    <div className={cn("my-1.5 flex gap-2 rounded-md border px-2.5 py-1.5", config.cls)}>
      <div className="mt-0.5 shrink-0">{config.icon}</div>
      <div className="flex-1 leading-relaxed">
        <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide opacity-80">
          {config.label}
        </div>
        <div>{formatInline(text)}</div>
      </div>
    </div>
  );
}

/** 引用块 (左边色块 + 灰底) */
function QuoteSection({ text }: { text: string }) {
  return (
    <blockquote className="my-1.5 rounded-r-md border-l-4 border-primary bg-primary/5 px-3 py-1.5 text-ink-700">
      {formatInline(text)}
    </blockquote>
  );
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

    // 表格块: |...| 连续行 (V29d 升级: 更宽容处理 LLM 输出 `||` 空 cell)
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      // 分离 header + body (第二行是 |---|---|)
      // V29d: 兼容性增强 — separator 行允许 `|---|---|` / `|---|` / `||---|` (空 cell 前)
      const isSep = (l: string) => {
        const t = l.trim();
        if (!t.startsWith("|") || !t.endsWith("|")) return false;
        // 每个 cell 必须是 : / - / 空白
        return t.slice(1, -1).split("|").every((c) => /^[\s:\-]+$/.test(c));
      };
      let header: string[] = [];
      let rows: string[][] = [];
      if (tableLines.length >= 2 && isSep(tableLines[1])) {
        // V29d: 兼容空 cell  `| 机型| 备注 ||---|---|` split 会多出一个空 string
        const splitRow = (r: string) => {
          const cells = r.split("|");
          // 去头尾空 (开头 | 和 结尾 |)
          if (cells.length > 0 && cells[0] === "") cells.shift();
          if (cells.length > 0 && cells[cells.length - 1] === "") cells.pop();
          return cells.map((c) => c.trim());
        };
        header = splitRow(tableLines[0]);
        for (let r = 2; r < tableLines.length; r++) {
          rows.push(splitRow(tableLines[r]));
        }
        // V29d: 如果 header 全部为空, 第一行也当 row, 第二行是 sep
        if (header.every((c) => c === "")) {
          rows.unshift(splitRow(tableLines[0]));
          header = [];
        }
      } else {
        // 没 separator 全部当 rows
        const splitRow = (r: string) => {
          const cells = r.split("|");
          if (cells.length > 0 && cells[0] === "") cells.shift();
          if (cells.length > 0 && cells[cells.length - 1] === "") cells.pop();
          return cells.map((c) => c.trim());
        };
        for (const tl of tableLines) {
          rows.push(splitRow(tl));
        }
        // 第一行当 header (heuristic)
        if (rows.length >= 1) {
          header = rows.shift()!;
        }
      }
      out.push(
        <div key={`tbl-${k++}`} className="my-3 overflow-x-auto rounded-md border border-ink-200">
          <table className="w-full border-collapse text-[12px]">
            {header.length > 0 && (
              <thead className="bg-primary/5">
                <tr>
                  {header.map((h, idx) => (
                    <th
                      key={idx}
                      className="border-b border-ink-200 bg-primary/10 px-2.5 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-primary"
                    >
                      {formatInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="even:bg-ink-50/50 hover:bg-primary/5 transition-colors">
                  {row.map((cell, ci) => (
                    <td key={ci} className="border-b border-ink-100 px-2.5 py-1.5 align-top text-ink-800">
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
      // V29d 视觉升级: h1/h2 加左边色块 + 强调
      // ★ P0: 用 React.createElement 显式构造 heading, 不用 dynamic Tag + JSX.IntrinsicElements cast
      //   (React 19 + TS 5.9 下 dynamic string tag 已不合法)
      const cls =
        level === 1
          ? "mt-3 mb-2 flex items-center gap-2 border-l-4 border-primary bg-primary/5 px-2.5 py-1.5 text-base font-bold text-ink-900"
          : level === 2
          ? "mt-3 mb-1.5 flex items-center gap-2 border-l-2 border-primary/70 pl-2 text-[15px] font-bold text-ink-900"
          : "mt-2 mb-1 text-sm font-semibold text-primary";
      const showAccent = level === 1 || level === 2;
      const accent = showAccent ? <span className="text-primary/70">▎</span> : null;
      if (level === 1) {
        out.push(
          <h1 key={`h-${k++}`} className={cls}>
            {accent}
            {formatInline(text)}
          </h1>
        );
      } else if (level === 2) {
        out.push(
          <h2 key={`h-${k++}`} className={cls}>
            {accent}
            {formatInline(text)}
          </h2>
        );
      } else {
        out.push(
          <h3 key={`h-${k++}`} className={cls}>
            {formatInline(text)}
          </h3>
        );
      }
      i++;
      continue;
    }

    // 引用: > ...
    if (line.startsWith("> ")) {
      out.push(
        <blockquote
          key={`q-${k++}`}
          className="my-2 rounded-r-md border-l-4 border-primary bg-primary/5 px-3 py-1.5 text-ink-700"
        >
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
        <ol key={`ol-${k++}`} className="my-1.5 ml-1 space-y-1">
          {items.map((it, idx) => (
            <li key={idx} className="flex gap-2 leading-relaxed">
              <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
                {idx + 1}
              </span>
              <span className="flex-1">{formatInline(it)}</span>
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
        <ul key={`ul-${k++}`} className="my-1.5 ml-1 space-y-1">
          {items.map((it, idx) => (
            <li key={idx} className="flex gap-2 leading-relaxed">
              <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span className="flex-1">{formatInline(it)}</span>
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
      <p key={`p-${k++}`} className="my-1.5 leading-relaxed text-ink-800">
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
 *
 *  V29d 升级 (NJX 7/27 20:34 反馈"AI 文本输出依然不便于阅读"):
 *    1) heading 允许紧贴前字符 (无空白也拆): `([^\s\n])(#{1,3}\s+...)` 
 *       v2c 旧规则要求前有空白, LLM 输出 `--###` 紧贴, 完全不触发
 *    2) hr `---` 整行规整 (用 anchor 排除前 -, 但仍然处理行中的 \n---\n)
 *    3) list `-`/`*` 加 context guard: 排除 `数字-数字` (3-1531) / 排除 `**bold**` 中间 `*`
 *    4) 表格: `| ` (空格 + |) 在文本中(非行首) 拆行, 兼容 LLM 输出 `| 机型| 备注 ||---|---|` 空 cell
 */
function normalizeMarkdownLineBreaks(s: string): string {
  if (!s) return s;
  let out = s;

  // 0) HR --- 整行规整 (3 个或以上连续的 -, 前面是空白/行首/中文, 后面空白/行尾/中文)
  //    把 \n?---\n? 变成 \n\n---\n\n (用边界避免误伤: 后接字母是 hr 文字说明, 不拆)
  out = out.replace(/(^|[\n\u4e00-\u9fff，。；：、）])---($|[\n\u4e00-\u9fff，。；：、（])/g, "$1\n\n---\n\n$2");

  // 1) Heading: #{1,3} 后紧跟非空白字符 (LLM 流拼接丢空白), 前面有非空白字符就插 \n
  //   V29d+ 升级: 允许 ### 无空白紧跟 (e.g. `###注意事项` LLM 输出常见)
  //   兼容: `文本# 标题` / `文本##标题` / `## 文本## 标题` / `---###已知` / `###注意事项⚠️`
  //   排除: 行首的 # (前面是 \n 或行首)
  out = out.replace(/(\S)(#{1,3})(?=\S)/g, "$1\n$2");
  // 兼容: ### 后有空白 + 紧跟非空白 (原 rule 保留)
  out = out.replace(/(\S)(#{1,3}\s+\S)/g, "$1\n$2");

  // 2) List item "- " (1+ 空白 + - + 1+ 空白 + 中文/大写英文/数字.)
  //   排除: 数字-数字 (3-1531) — 用 lookbehind (?<!\d)
  //   排除: 减号-减号 (---) 已被 step 0 处理
  //   排除: ":" 后紧跟 - (e.g. "机场: - 处置" 仍要拆, 但 "件号:" 后跟 C20649000-兰州 不是 list)
  //   lookbehind 不支持变长, 但 (?<!\d) 可用
  out = out.replace(/(?<!\d)([^\s\n:])(-\s+[\u4e00-\u9fff])/g, "$1\n$2");
  out = out.replace(/(?<!\d)([^\s\n:])(-\s+[A-Z])/g, "$1\n$2");

  // 3) List item "* " (单星, 排除 **bold** 内的 *)
  //   排除: ** 在前 (lookbehind (?<!\*)) 或在后 (lookahead (?!\*))
  out = out.replace(/(?<!\*)([^\s\n*])(\*\s+[\u4e00-\u9fff])/g, "$1\n$2");

  // 4) Numbered list: 数字. 空格 + 中文/英文
  //   排除: 数字. 数字 (e.g. "1.5" 分数) — 用 lookbehind (?<!\d)
  out = out.replace(/(?<!\d)(\d+\.\s+[\u4e00-\u9fff])/g, "\n$1");

  // 5) 表格 inline 重整 (NJX 7/27 21:30 反馈 "排版混乱" V29d 升级):
  //   LLM 流式拼接把整段表格拼成单行: "| 项目| 内容 ||---|---|IATA/ ICAO| /| 机场|..."
  //   修法: 找第一个 "|---" (非贪心), 拆 [header, sep, data] 三段, 重组多行
  //   v5e 修: dataStart = sepEnd (separator 后立刻是 cell content, 不是 |), 不去头
  out = out.replace(
    /(?:^|\n)([^\n]*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*)/g,
    (fullLine) => {
      const pipeMatches = fullLine.match(/\|/g) || [];
      if (pipeMatches.length < 4) return fullLine;
      if (!fullLine.includes("---")) return fullLine;
      // 找第一个 "|---" 起始位置
      const sepStart = fullLine.indexOf("|---");
      if (sepStart < 0) return fullLine;
      // 状态机找 sepEnd: 接受 | - : 空白, 直到下一个 | 后跟 非 - (cell content 开始)
      let sepEnd = sepStart;
      while (sepEnd < fullLine.length) {
        const c = fullLine[sepEnd];
        if (c === "|" || c === "-" || c === ":" || /\s/.test(c)) {
          sepEnd++;
        } else {
          break;
        }
      }
      // sepPart: sepStart 到 sepEnd
      let sepPart = fullLine.slice(sepStart, sepEnd);
      // 修正 sepPart 边界: 头只 1 个 |, 尾只 1 个 |
      while (sepPart.startsWith("||")) sepPart = "|" + sepPart.slice(2);
      while (sepPart.endsWith("||")) sepPart = sepPart.slice(0, -2) + "|";
      // headerPart: fullLine 开头到 sepStart, 找第一个 |
      const firstPipe = fullLine.indexOf("|");
      const headerPart = fullLine.slice(firstPipe, sepStart);
      // dataPart: sepEnd 到 fullLine 末尾 (dataStart = sepEnd, 不要去头 |)
      let dataPart = fullLine.slice(sepEnd);
      // 去末尾的尾随 | (如果有)
      while (dataPart.endsWith("|")) dataPart = dataPart.slice(0, -1);
      // 切分 cells
      // headerPart = "|项目|内容|" split = ["", "项目", "内容", ""]
      //   我们要去首尾空 cell, 但保留中间空 cell (LLM "|x||y|" 偶有)
      // 修法: 只 filter 开头 (i==0) 和 末尾 (i==last && empty) 的空
      const headerArr = headerPart.split("|");
      const headerCells = headerArr.filter((c, i, arr) => {
        if (i === 0) return false;  // 开头空
        if (i === arr.length - 1 && c === "") return false;  // 末尾空
        return true;
      });
      const dataCells = dataPart.split("|");
      if (headerCells.length < 1) return fullLine;
      // 重组: prefix (fullLine 开头到第一个 |) + header 行 + sep + data 行 + suffix
      const headPrefix = fullLine.slice(0, firstPipe);
      const headerLine = "|" + headerCells.map((c) => c.trim()).join("|") + "|";
      const sepLine = sepPart;
      const dataLines: string[] = [];
      const colCount = headerCells.length;
      for (let i = 0; i < dataCells.length; i += colCount) {
        const row = dataCells.slice(i, i + colCount);
        dataLines.push("|" + row.map((c) => c.trim()).join("|") + "|");
      }
      return headPrefix + "\n" + headerLine + "\n" + sepLine + "\n" + dataLines.join("\n");
    }
  );

  return out;
}

/** Markdown 渲染 (自写, 不依赖第三方) + 思考过程折叠
 *  P0 治本 (NJX 7/27 15:44 反馈: AI 答案显示原始 markdown 格式, ## 标题 / | 表格 | / 1. 列表 都没渲染)
 *  V30 治本 (NJX 7/27 22:14 拍板 🅰️): 有 sections 走组件化渲染, 否则 fallback markdown */
function formatAnswer(msg: Msg): React.ReactNode {
  const { text, sections } = msg;
  // V30 治本: 优先 sections 渲染 (NJX 22:14 拍板, 100% 视觉受控)
  if (sections && sections.length > 0) {
    // sections 模式不解析 think (LLM 在 JSON 模板里不输出 <think>)
    return <>{renderSections(sections)}</>;
  }
  // Fallback: markdown 渲染 (V29d++ 兼容, 解析失败 / 老 LLM 走这里)
  if (!text) return null;
  const { think, body } = splitThink(text);
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
    //   改用 chatStream: 后端 SSE emit refs (立刻) + token (打字机) + sections (V30 组件化) + done (结束)
    //   - 收到 refs 立刻显示引用, 不等 LLM 30s
    //   - 收到 token 增量拼到 text, React state 触发 re-render (markdown 打字机)
    //   - 收到 sections 用 React 组件化渲染, 覆盖之前的 markdown (V30 治本)
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
      onSections: (sections) => {
        // V30 治本: LLM 解析成功, 用 sections 覆盖流式 markdown 渲染
        // 100% 视觉受控 — 不再依赖 markdown 解析, 8 种 type 各对应独立 React 组件
        setMsgs((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? { ...m, sections, loading: false }
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
          <div className="space-y-1">{formatAnswer(msg)}</div>
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
