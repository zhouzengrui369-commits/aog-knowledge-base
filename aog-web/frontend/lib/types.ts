export type CityStatus = "现行" | "暂停" | "已废" | "active" | "paused" | "retired" | "inactive";
export type ExperienceStatus = "现行" | "历史" | "待审" | "已废" | "active" | "paused" | "retired";
export type ExperienceCategory = "流程" | "规范" | "案例" | "培训" | "技术" | "管理";
export type CityRegion = string;

export type ReviewStatus = "VERIFIED" | "UNVERIFIED" | "STALE" | "MISSING" | "FIXTURE" | "REDACTED";
export type PiiClassification = "none" | "internal" | "confidential" | "restricted";
export type Environment = "dev" | "staging" | "production" | "all";

export interface DataTrust {
  source_document?: string | null;
  source_location?: string | null;
  source_version?: string | null;
  updated_at?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  review_status: ReviewStatus;
  confidence?: number | null;
  environment: Environment;
  pii_classification: PiiClassification;
}

export type ContactPermission = "public" | "internal" | "restricted";

export interface City {
  code: string;
  name: string;
  airport: string;
  iata: string;
  pinyin?: string;
  region: CityRegion;
  status: CityStatus;
  tags?: string[];
  fleet?: Array<{ model: string; short_stay: boolean; after: boolean }>;
  parts?: Array<{ pn: string; name: string; stock: number; unit: string }>;
  contacts?: Array<{
    org: string;
    phone: string[];
    email?: string;
    role: string;
    scope?: string;
    permission?: ContactPermission;
    redacted?: boolean;
  }>;
  warehouse?: { location: string; main: string[] };
  logistics?: { rail: string; air: string; road: string };
  content_md?: string;
  source_path?: string;
  updated_at?: string;
  trust?: DataTrust;
  view_count?: number;
  data_available?: boolean;
  operational_notice?: string | null;
  lat?: number;
  lon?: number;
  summary?: string;
  airport_obj?: { name: string; code: string; province: string };
  parts_mockup?: Array<{ name: string; pn: string; stock: boolean; note: string }>;
  contacts_mockup?: Array<{ org: string; scope?: string; method?: string; contact?: string; phone?: string; email?: string }>;
  warehouse_mockup?: { name: string; address?: string; phone?: string; owners?: string };
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
  topic?: string;
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

export interface ChatRequest { q: string; context_codes?: string[] }
export interface ChatReference {
  id: string;
  title: string;
  href?: string | null;
  snippet: string;
  score: number;
  available?: boolean;
  source_type?: string;
  verification_status?: ReviewStatus;
  reason?: string | null;
}
export type ChatSectionType = "heading" | "paragraph" | "table" | "list" | "ordered_list" | "code" | "alert" | "quote";
export type ChatAlertVariant = "info" | "warning" | "danger" | "success";
export interface ChatSection {
  type: ChatSectionType;
  level?: number;
  text?: string;
  header?: string[];
  rows?: string[][];
  items?: string[];
  language?: string;
  variant?: ChatAlertVariant;
}
export interface ChatResponse {
  answer: string;
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

export type Alliance = "星空联盟" | "天合联盟" | "寰宇一家" | "无" | string;
export interface AirlineHub {
  city_code: string | null;
  iata: string;
  type: "hub" | "focus";
  note?: string;
  city?: { code: string; name: string; iata: string; status: string } | null;
}
export interface AirlineContact { phone?: string; email?: string }
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
  verification_status?: "VERIFIED" | "UNVERIFIED" | "CONFLICT";
  verification_issue?: string;
}

export interface Airport { iata: string; name: string; city: string; country: string; lat: number; lon: number }
export interface GlobalAirportsData { total: number; countries: number; by_country: Record<string, number>; airports: Airport[] }