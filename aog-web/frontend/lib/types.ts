// 与 CONTRACT §1 数据模型 1:1 对齐
// 注意：mockup 阶段字段是英文（active/paused），CONTRACT 文档是中文（现行/暂停），
// 这里兼容两种 case，TS 联合类型用中文（CONTRACT 优先）

export type CityStatus = "现行" | "暂停" | "已废" | "active" | "paused" | "retired";
export type ExperienceStatus = "现行" | "历史" | "待审" | "已废" | "active" | "paused" | "retired";
export type ExperienceCategory = "流程" | "规范" | "案例" | "培训" | "技术" | "管理";
export type CityRegion =
  | "华北" | "华东" | "华南" | "华中" | "西南" | "西北" | "东北"
  | "国际-欧洲" | "国际-亚洲" | "国际-美洲" | "国际-中东" | "国际-非洲" | "国际-大洋洲";

export interface City {
  code: string;
  name: string;
  airport: string;
  iata: string;
  pinyin?: string;
  region: CityRegion | string;
  status: CityStatus;
  tags?: string[];
  fleet?: Array<{ model: string; short_stay: boolean; after: boolean }>;
  parts?: Array<{ pn: string; name: string; stock: number; unit: string }>;
  contacts?: Array<{ org: string; phone: string[]; email?: string; role: string }>;
  warehouse?: { location: string; main: string[] };
  logistics?: { rail: string; air: string; road: string };
  content_md?: string;
  source_path?: string;
  updated_at?: string;
  // 兼容 mockup 字段
  summary?: string;
  airport_obj?: { name: string; code: string; province: string };
  parts_mockup?: Array<{ name: string; pn: string; stock: boolean; note: string }>;
  contacts_mockup?: Array<{
    org: string; scope?: string; method?: string;
    contact?: string; phone?: string; email?: string;
  }>;
  warehouse_mockup?: {
    name: string; address?: string; phone?: string; owners?: string;
  };
  logistics_mockup?: Array<{ type: string; note: string }>;
}

export interface ExperienceContent {
  h: string;
  type: "p" | "list";
  text?: string;
  items?: string[];
}

export interface Experience {
  id: string;
  title: string;
  category: ExperienceCategory;
  status: ExperienceStatus;
  tags: string[];
  summary: string;
  content_md?: string;
  content?: ExperienceContent[];
  related_pn?: string[];
  source_path?: string;
  updated_at?: string;
  // 兼容 mockup 字段
  topic?: string; // mockup 用 topic，CONTRACT 用 category
  created?: string;
  updated?: string;
  author?: string;
  related?: string[];
}

export interface CorePlan {
  id: string;
  title: string;
  type: "master" | "checklist" | "manual" | "catalog";
  content_md: string;
  source_path?: string;
  updated_at?: string;
}

export interface ChatRequest {
  q: string;
  context_codes?: string[];
}

export interface ChatReference {
  id: string;
  title: string;
  href: string;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  references: ChatReference[];
  model: string;
  latency_ms: number;
}

export interface SyncStatus {
  status: "idle" | "running" | "error";
  last_sync: string | null;
  queue: number;
  indexed_total: number;
  last_error?: string;
}

/** normalize 函数已迁移到 lib/utils.ts（避免循环依赖） */
