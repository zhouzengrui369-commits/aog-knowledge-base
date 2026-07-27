// 与 CONTRACT §1 数据模型 1:1 对齐
// 注意：mockup 阶段字段是英文（active/paused），CONTRACT 文档是中文（现行/暂停），
// 这里兼容两种 case，TS 联合类型用中文（CONTRACT 优先）

export type CityStatus = "现行" | "暂停" | "已废" | "active" | "paused" | "retired";
export type ExperienceStatus = "现行" | "历史" | "待审" | "已废" | "active" | "paused" | "retired";
export type ExperienceCategory = "流程" | "规范" | "案例" | "培训" | "技术" | "管理";
export type CityRegion =
  | "华北" | "华东" | "华南" | "华中" | "西南" | "西北" | "东北"
  | "国际-欧洲" | "国际-亚洲" | "国际-美洲" | "国际-中东" | "国际-非洲" | "国际-大洋洲";

// D-030: 联系人权限级别 (FOCUSED_RETEST P0-3)
export type ContactPermission = "public" | "internal" | "restricted";

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
  contacts?: Array<{
    org: string;
    phone: string[];
    email?: string;
    role: string;
    permission?: ContactPermission;  // D-030
  }>;
  warehouse?: { location: string; main: string[] };
  logistics?: { rail: string; air: string; road: string };
  content_md?: string;
  source_path?: string;
  updated_at?: string;
  // 排序 & 地图字段（前端静态 fallback，SCF API 暂未返回）
  view_count?: number;
  lat?: number;
  lon?: number;
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

// ===== V30 (NJX 7/27 22:14 拍板 🅰️): 结构化输出 =====
// LLM 输出 JSON 描述 sections 数组, 前端用 React 组件渲染, 100% 视觉受控
// 失败 fallback: sections=undefined, 前端用 markdown 渲染 (answer 字段)

export type ChatSectionType =
  | "heading"          // heading.text + level (1-3)
  | "paragraph"        // paragraph.text
  | "table"            // table.header + table.rows
  | "list"             // list.items
  | "ordered_list"     // ordered_list.items
  | "code"             // code.text + code.language
  | "alert"            // alert.text + alert.variant (info/warning/danger/success)
  | "quote";           // quote.text

export type ChatAlertVariant = "info" | "warning" | "danger" | "success";

export interface ChatSection {
  type: ChatSectionType;
  /** heading 专用: 1=h1, 2=h2, 3=h3 */
  level?: number;
  /** paragraph / heading / code / quote / alert 专用 */
  text?: string;
  /** table 专用: 列名数组 */
  header?: string[];
  /** table 专用: rows = [[cell1, cell2, ...], ...] */
  rows?: string[][];
  /** list / ordered_list 专用 */
  items?: string[];
  /** code 专用: bash/text/sql 等 */
  language?: string;
  /** alert 专用 */
  variant?: ChatAlertVariant;
}

export interface ChatResponse {
  /** markdown 字符串 (V29d++ 兼容, V30 fallback 时用) */
  answer: string;
  /**
   * V30: 结构化 sections, 解析成功时填充.
   * undefined → 前端用 markdown 渲染 (answer 字段)
   * 有值 → 前端用 React 组件化渲染
   */
  sections?: ChatSection[];
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

// ===== Sprint C: 航司 (Airlines) =====

export type Alliance =
  | "星空联盟"
  | "天合联盟"
  | "寰宇一家"
  | "无"
  | string;

export interface AirlineHub {
  city_code: string | null;
  iata: string;
  type: "hub" | "focus";
  note?: string;
  /** 后端 enrich 字段 — city 在 codes.json 存在时填, 否则 null */
  city?: {
    code: string;
    name: string;
    iata: string;
    status: string;
  } | null;
}

export interface AirlineContact {
  phone?: string;
  email?: string;
}

export interface Airline {
  iata: string;
  icao: string;
  name_cn: string;
  name_short?: string;
  name_en: string;
  hubs: AirlineHub[];
  fleet_size: number;
  alliance: Alliance;
  headquarters?: string;
  website?: string;
  aog_contact?: AirlineContact;
  data_source?: string;
  verified?: boolean;
  verified_at?: string;
}

/** normalize 函数已迁移到 lib/utils.ts（避免循环依赖） */

// ===== V20: 全球机场（OpenFlights） =====

/** OpenFlights airports.dat 单条记录（前端只保留必要字段） */
export interface Airport {
  iata: string;
  name: string;
  city: string;
  country: string;
  lat: number;
  lon: number;
}

/** 全球机场 + by_country（V20 静态 JSON） */
export interface GlobalAirportsData {
  total: number;
  countries: number;
  by_country: Record<string, number>;
  airports: Airport[];
}
