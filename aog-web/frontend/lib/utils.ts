import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn 标准 cn 函数（合并 className） */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 从中文字符串提取首字母（拼音首字母简化版：取第一个字符） */
export function firstLetter(s: string): string {
  if (!s) return "#";
  return s.charAt(0).toUpperCase();
}

/** 格式化 ISO 日期为 YYYY-MM-DD */
export function fmtDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10);
}

/** 城市 status -> 中文 + 颜色 */
export const STATUS_LABEL: Record<
  string,
  { text: string; cls: string; dot: string }
> = {
  active: { text: "现行", cls: "bg-success-50 text-success-700", dot: "bg-success" },
  paused: { text: "暂停", cls: "bg-warning-50 text-warning-700", dot: "bg-warning" },
  retired: { text: "已废止", cls: "bg-danger-50 text-danger-700", dot: "bg-danger" },
  // CONTRACT §1.1 中文 status
  现行: { text: "现行", cls: "bg-success-50 text-success-700", dot: "bg-success" },
  暂停: { text: "暂停", cls: "bg-warning-50 text-warning-700", dot: "bg-warning" },
  已废: { text: "已废止", cls: "bg-danger-50 text-danger-700", dot: "bg-danger" },
};

/** 经验 topic -> Tailwind class */
export const TOPIC_COLOR: Record<string, string> = {
  流程: "bg-primary-50 text-primary-700",
  规范: "bg-secondary/10 text-secondary",
  案例: "bg-warning-50 text-warning-700",
  培训: "bg-success-50 text-success-700",
  技术: "bg-ink-100 text-ink-700",
  管理: "bg-ink-100 text-ink-700",
};

/** 物流 icon 映射 */
export const LOGISTICS_ICON: Record<string, string> = {
  公路: "🚚",
  航空: "✈",
  铁路: "🚆",
  海运: "🚢",
  陆运: "🚚",
};

/** 联系人 method 颜色 */
export const METHOD_COLOR: Record<string, string> = {
  互援: "bg-success-50 text-success-700",
  中介: "bg-warning-50 text-warning-700",
  协议: "bg-primary-50 text-primary-700",
  内部: "bg-secondary/10 text-secondary",
  点对点: "bg-ink-100 text-ink-700",
};

/** 城市 status 归一化（接受 mockup 英文 + CONTRACT 中文） */
export function normalizeCityStatus(s: string | undefined | null): "现行" | "暂停" | "已废" {
  if (!s) return "现行";
  if (s === "active" || s === "现行") return "现行";
  if (s === "paused" || s === "暂停") return "暂停";
  return "已废";
}

/** 经验 status 归一化 */
export function normalizeExpStatus(s: string | undefined | null): "现行" | "暂停" | "已废" {
  if (!s) return "现行";
  if (s === "active" || s === "现行") return "现行";
  if (s === "paused" || s === "暂停" || s === "历史") return "暂停";
  return "已废";
}

/** 经验 topic -> ExperienceCategory 归一化 */
export function normalizeCategory(topic?: string): "流程" | "规范" | "案例" | "培训" | "技术" | "管理" {
  if (!topic) return "管理";
  if (["流程", "规范", "案例", "培训", "技术", "管理"].includes(topic)) {
    return topic as "流程" | "规范" | "案例" | "培训" | "技术" | "管理";
  }
  return "管理";
}
